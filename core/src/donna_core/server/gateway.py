"""WebSocket gateway: translates between the wire protocol and the core.

    client --JSON--> decode_client --> core.submit()/core.cancel()
    core --Event--> bus --> this gateway --> envelope --JSON--> every client

The gateway is the only place that knows about sockets, JSON and envelopes.
It never calls tools directly.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import secrets
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.typing import Origin

from donna_core import __version__
from donna_core.bus import Event, EventBus
from donna_core.protocol import PROTOCOL_VERSION, ProtocolError, decode_client, encode
from donna_core.protocol.messages import (
    SERVER_MODEL_BY_TYPE,
    AssistantState,
    Error,
    ErrorPayload,
    SessionHello,
    SessionReady,
    SessionReadyPayload,
    UserCancel,
    UserText,
)
from donna_core.server.auth import (
    CLOSE_AUTH_TIMEOUT,
    CLOSE_BAD_REQUEST,
    CLOSE_UNAUTHORIZED,
    token_matches,
)

log = logging.getLogger(__name__)

HOST = "127.0.0.1"  # never configurable: the core is not a network service
MAX_MESSAGE_BYTES = 64 * 1024


class AssistantPort(Protocol):
    """The slice of the core the gateway needs. Keeps the two decoupled."""

    async def submit(self, text: str) -> object: ...
    async def cancel(self, reason: str = ...) -> bool: ...
    @property
    def assistant_state(self) -> AssistantState: ...
    @property
    def tool_names(self) -> list[str]: ...


@dataclass(eq=False)
class _Client:
    ws: ServerConnection
    session_id: str
    name: str
    queue: asyncio.Queue[str] = field(default_factory=lambda: asyncio.Queue(maxsize=256))


def event_to_wire(event: Event) -> str:
    model = SERVER_MODEL_BY_TYPE[event.type]
    return encode(model(turn=event.turn, payload=event.payload))  # type: ignore[call-arg]


class Gateway:
    def __init__(
        self,
        core: AssistantPort,
        bus: EventBus,
        token: str,
        allowed_origins: Sequence[str],
        hello_timeout_s: float = 5.0,
    ) -> None:
        self._core = core
        self._token = token
        self._origins: list[Origin | None] = [Origin(o) for o in allowed_origins]
        self._origins.append(None)  # non-browser clients (CLI) send no Origin
        self._hello_timeout_s = hello_timeout_s
        self._clients: set[_Client] = set()
        self._server: Server | None = None
        self._unsubscribe = bus.subscribe(self._broadcast)

    @property
    def port(self) -> int:
        assert self._server is not None, "gateway not started"
        port: int = next(iter(self._server.sockets)).getsockname()[1]
        return port

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def start(self, port: int = 0) -> int:
        self._server = await serve(
            self._handle,
            HOST,
            port,
            origins=self._origins,
            max_size=MAX_MESSAGE_BYTES,
        )
        return self.port

    async def stop(self) -> None:
        self._unsubscribe()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    # ------------------------------------------------------------ connection

    async def _handle(self, ws: ServerConnection) -> None:
        client = await self._authenticate(ws)
        if client is None:
            return
        self._clients.add(client)
        sender = asyncio.create_task(self._send_loop(client))
        log.info("client %s (%s) connected", client.session_id, client.name)
        try:
            self._enqueue(
                client,
                encode(
                    SessionReady(
                        payload=SessionReadyPayload(
                            session_id=client.session_id,
                            protocol_version=PROTOCOL_VERSION,
                            server_version=__version__,
                            state=self._core.assistant_state,
                            tools=self._core.tool_names,
                        )
                    )
                ),
            )
            async for raw in ws:
                await self._dispatch(client, raw)
        except ConnectionClosed:
            pass
        finally:
            self._clients.discard(client)
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sender
            log.info("client %s disconnected", client.session_id)

    async def _authenticate(self, ws: ServerConnection) -> _Client | None:
        try:
            raw = await asyncio.wait_for(ws.recv(), self._hello_timeout_s)
        except TimeoutError:
            await ws.close(CLOSE_AUTH_TIMEOUT, "authentication timeout")
            return None
        except ConnectionClosed:
            return None
        try:
            hello = decode_client(raw)
        except ProtocolError as exc:
            await ws.close(CLOSE_BAD_REQUEST, exc.code)
            return None
        if not isinstance(hello, SessionHello) or not token_matches(
            self._token, hello.payload.token
        ):
            log.warning("rejected unauthenticated client")
            await ws.close(CLOSE_UNAUTHORIZED, "unauthorized")
            return None
        return _Client(ws, f"s_{secrets.token_hex(4)}", hello.payload.client.name)

    async def _dispatch(self, client: _Client, raw: str | bytes) -> None:
        try:
            msg = decode_client(raw)
        except ProtocolError as exc:
            self._send_error(client, exc.code, exc.message)
            return
        if isinstance(msg, UserText):
            await self._core.submit(msg.payload.text)
        elif isinstance(msg, UserCancel):
            await self._core.cancel("cancelled by user")
        elif isinstance(msg, SessionHello):
            self._send_error(client, "already_authenticated", "session.hello was already sent")

    # ------------------------------------------------------------ outbound

    async def _broadcast(self, event: Event) -> None:
        if not self._clients:
            return
        wire = event_to_wire(event)
        for client in list(self._clients):
            self._enqueue(client, wire)

    def _send_error(self, client: _Client, code: str, message: str) -> None:
        self._enqueue(client, encode(Error(payload=ErrorPayload(code=code, message=message))))

    def _enqueue(self, client: _Client, wire: str) -> None:
        try:
            client.queue.put_nowait(wire)
        except asyncio.QueueFull:
            # A client that can't keep up is dropped rather than slowing DONNA down.
            log.warning("client %s too slow; disconnecting", client.session_id)
            self._clients.discard(client)
            asyncio.get_running_loop().create_task(client.ws.close(1013, "too slow"))

    async def _send_loop(self, client: _Client) -> None:
        with contextlib.suppress(ConnectionClosed):
            while True:
                await client.ws.send(await client.queue.get())
