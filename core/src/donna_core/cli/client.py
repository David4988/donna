"""``donna-cli``: a terminal client that speaks exactly the same protocol as the UI.

    $ donna-cli
    You > hello
    DONNA > Hello.

You can type while DONNA is busy: a new message cancels the current turn
(barge-in), and /cancel just stops it. /quit or Ctrl+C exits.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import os
import sys
from pathlib import Path
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from donna_core import __version__
from donna_core.config import default_session_file
from donna_core.protocol import ProtocolError, decode_server, encode
from donna_core.protocol.messages import (
    ClientInfo,
    SessionHello,
    SessionHelloPayload,
    UserCancel,
    UserText,
    UserTextPayload,
)
from donna_core.server.session_file import read_session_file

TURN_END = {"turn.completed", "turn.cancelled", "turn.failed"}


PROMPT = "You > "


class Renderer:
    def __init__(self, verbose: bool = False, interactive: bool = False) -> None:
        self.verbose = verbose
        self.interactive = interactive
        self.ansi = True

    def _print(self, line: str) -> None:
        # In interactive mode the prompt may be on screen: clear it, print, redraw.
        if self.interactive and self.ansi:
            print(f"\r\033[K{line}", flush=True)
        else:
            print(line, flush=True)

    def prompt(self) -> None:
        if self.interactive:
            print(PROMPT, end="", flush=True)

    def render(self, msg: Any) -> None:
        p = msg.payload
        match msg.type:
            case "assistant.text":
                self._print(f"DONNA > {p.text}")
            case "tool.request":
                self._print(f"DONNA > {p.label}")
            case "tool.result":
                for r in p.results:
                    extra = f" - {r.subtitle}" if r.subtitle else ""
                    self._print(f"        [{r.id}] {r.title}{extra}")
            case "tool.error":
                self._print(f"        ! {p.tool}: {p.message}")
            case "turn.cancelled":
                self._print(f"        (cancelled: {p.reason})")
            case "turn.failed":
                self._print(f"        ! turn failed: {p.message}")
            case "error":
                self._print(f"        ! error [{p.code}]: {p.message}")
            case "turn.started" if self.verbose:
                self._print(f"        (turn {msg.turn}: {p.input!r})")
            case "assistant.state" if self.verbose:
                self._print(f"        [{p.state}]")
            case "turn.completed" if self.verbose:
                self._print(f"        (route: {p.route})")
            case "session.ready":
                self._print(f"Connected to DONNA {p.server_version} (state {p.state}).")


async def handshake(ws: ClientConnection, token: str) -> Any:
    hello = SessionHello(
        payload=SessionHelloPayload(token=token, client=ClientInfo(name="cli", version=__version__))
    )
    await ws.send(encode(hello))
    return decode_server(await ws.recv())


class Client:
    def __init__(self, ws: ClientConnection, renderer: Renderer) -> None:
        self.ws = ws
        self.renderer = renderer
        self.idle = asyncio.Event()
        self.idle.set()

    async def receive_loop(self) -> None:
        async for raw in self.ws:
            try:
                msg = decode_server(raw)
            except ProtocolError as exc:
                print(f"        ! bad message from core: {exc}", file=sys.stderr)
                continue
            self.renderer.render(msg)
            if msg.type == "turn.started":
                self.idle.clear()
            elif msg.type in TURN_END or msg.type == "error":
                self.idle.set()
                if msg.type != "turn.cancelled":  # a cancel is followed by a new turn
                    self.renderer.prompt()

    async def say(self, text: str) -> None:
        self.idle.clear()
        await self.ws.send(encode(UserText(payload=UserTextPayload(text=text))))

    async def cancel(self) -> None:
        await self.ws.send(encode(UserCancel()))

    async def wait_for_turn(self) -> None:
        await self.idle.wait()


async def interactive(client: Client) -> None:
    # Piped input (scripts, tests) runs one turn at a time; a human at a terminal
    # can type while DONNA is busy, which barges in on the current turn.
    sequential = not sys.stdin.isatty()
    client.renderer.prompt()
    while True:
        raw = await asyncio.to_thread(sys.stdin.readline)
        if raw == "":  # EOF (Ctrl+D / closed stdin)
            await client.wait_for_turn()
            return
        line = raw.strip()
        if line in ("/quit", "/exit"):
            return
        if not line:
            client.renderer.prompt()
        elif line == "/cancel":
            await client.cancel()
        else:
            if sequential:
                print(line, flush=True)
            await client.say(line)
            if sequential:
                await client.wait_for_turn()


async def run(url: str, token: str, once: str | None, verbose: bool) -> int:
    try:
        async with connect(url, max_size=64 * 1024) as ws:
            ready = await handshake(ws, token)
            renderer = Renderer(verbose, interactive=once is None)
            renderer.ansi = sys.stdout.isatty()
            renderer.render(ready)
            client = Client(ws, renderer)
            receiver = asyncio.create_task(client.receive_loop())
            try:
                if once is not None:
                    print(f"{PROMPT}{once}", flush=True)
                    await client.say(once)
                    await client.wait_for_turn()
                else:
                    await interactive(client)
            finally:
                receiver.cancel()
                with contextlib.suppress(asyncio.CancelledError, ConnectionClosed):
                    await receiver
    except ConnectionClosed as exc:
        reason = exc.rcvd.reason if exc.rcvd else "connection closed"
        code = exc.rcvd.code if exc.rcvd else "?"
        print(f"Disconnected by core ({code}: {reason}).", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Can't reach the core at {url}: {exc}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="donna-cli", description="Talk to a running DONNA core.")
    p.add_argument("--session-file", type=Path, default=None)
    p.add_argument("--url", help="override ws://127.0.0.1:<port> from the session file")
    p.add_argument("--once", metavar="TEXT", help="send one message, print the turn, exit")
    p.add_argument("-v", "--verbose", action="store_true", help="also show states and routes")
    args = p.parse_args(argv)

    session_path = args.session_file or default_session_file()
    token = os.environ.get("DONNA_TOKEN")
    url = args.url
    if token is None or url is None:
        try:
            info = read_session_file(session_path)
        except (OSError, ValueError, KeyError):
            sys.exit(f"No running core found ({session_path}). Start it with: donna-core")
        token = token or info.token
        url = url or info.url

    with contextlib.suppress(KeyboardInterrupt):
        sys.exit(asyncio.run(run(url, token, args.once, args.verbose)))


if __name__ == "__main__":
    main()
