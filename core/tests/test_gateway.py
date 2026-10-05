"""Auth + end-to-end tests against a real WebSocket server on 127.0.0.1."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, InvalidStatus
from websockets.typing import Origin

from donna_core.agent.speaker import SimulatedSpeaker
from donna_core.app import Core, build_core
from donna_core.config import DEFAULT_ALLOWED_ORIGINS
from donna_core.server.auth import CLOSE_AUTH_TIMEOUT, CLOSE_BAD_REQUEST, CLOSE_UNAUTHORIZED
from donna_core.server.gateway import Gateway

TOKEN = "test-token-123"


class Harness:
    def __init__(self, core: Core, gateway: Gateway) -> None:
        self.core = core
        self.gateway = gateway

    @property
    def url(self) -> str:
        return f"ws://127.0.0.1:{self.gateway.port}"


async def _start(speaker: Any = None, hello_timeout_s: float = 5.0) -> Harness:
    core = build_core(speaker=speaker)
    gateway = Gateway(core, core.bus, TOKEN, DEFAULT_ALLOWED_ORIGINS, hello_timeout_s)
    await gateway.start(0)
    return Harness(core, gateway)


@pytest.fixture
async def harness() -> AsyncIterator[Harness]:
    h = await _start()
    yield h
    await h.gateway.stop()


def hello(token: str = TOKEN) -> str:
    return json.dumps(
        {"v": 1, "type": "session.hello", "payload": {"token": token, "client": {"name": "test"}}}
    )


def user_text(text: str) -> str:
    return json.dumps({"v": 1, "type": "user.text", "payload": {"text": text}})


async def recv(ws: ClientConnection) -> dict[str, Any]:
    return json.loads(await asyncio.wait_for(ws.recv(), 2))  # type: ignore[no-any-return]


async def recv_until(ws: ClientConnection, type_: str) -> list[dict[str, Any]]:
    msgs = []
    while True:
        msg = await recv(ws)
        msgs.append(msg)
        if msg["type"] == type_:
            return msgs


async def authed(url: str) -> ClientConnection:
    ws = await connect(url)
    await ws.send(hello())
    ready = await recv(ws)
    assert ready["type"] == "session.ready"
    return ws


async def closed_code(ws: ClientConnection) -> int | None:
    with pytest.raises(ConnectionClosed) as exc:
        await asyncio.wait_for(ws.recv(), 2)
    return exc.value.rcvd.code if exc.value.rcvd else None


# ------------------------------------------------------------------ auth


async def test_valid_token(harness: Harness) -> None:
    async with connect(harness.url) as ws:
        await ws.send(hello())
        ready = await recv(ws)
    assert ready["type"] == "session.ready"
    assert ready["v"] == 1
    assert ready["payload"]["state"] == "IDLE"
    assert set(ready["payload"]["tools"]) == {"open_app", "find_files", "open_result", "web_search"}


async def test_invalid_token(harness: Harness) -> None:
    async with connect(harness.url) as ws:
        await ws.send(hello("wrong"))
        assert await closed_code(ws) == CLOSE_UNAUTHORIZED
    assert harness.gateway.client_count == 0


async def test_missing_token_first_message_not_hello(harness: Harness) -> None:
    async with connect(harness.url) as ws:
        await ws.send(user_text("open chrome"))
        assert await closed_code(ws) == CLOSE_UNAUTHORIZED
    assert harness.core.backends.launcher.launched == []  # type: ignore[attr-defined]


async def test_missing_token_field(harness: Harness) -> None:
    async with connect(harness.url) as ws:
        await ws.send(json.dumps({"v": 1, "type": "session.hello", "payload": {"client": {}}}))
        assert await closed_code(ws) == CLOSE_BAD_REQUEST


async def test_hello_timeout() -> None:
    h = await _start(hello_timeout_s=0.1)
    try:
        async with connect(h.url) as ws:
            assert await closed_code(ws) == CLOSE_AUTH_TIMEOUT
    finally:
        await h.gateway.stop()


async def test_invalid_origin_is_rejected_at_handshake(harness: Harness) -> None:
    with pytest.raises(InvalidStatus) as exc:
        await connect(harness.url, origin=Origin("https://evil.example.com"))
    assert exc.value.response.status_code == 403


async def test_allowed_origin(harness: Harness) -> None:
    async with connect(harness.url, origin=Origin("http://localhost:1420")) as ws:
        await ws.send(hello())
        assert (await recv(ws))["type"] == "session.ready"


async def test_unauthenticated_clients_get_no_events(harness: Harness) -> None:
    async with connect(harness.url) as lurker:
        ws = await authed(harness.url)
        await ws.send(user_text("hello"))
        await recv_until(ws, "turn.completed")
        await ws.close()
        # The lurker never sent a hello, so none of that turn's events reached it.
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(lurker.recv(), 0.3)


# ------------------------------------------------------------------ protocol errors


@pytest.mark.parametrize(
    ("raw", "code"),
    [
        ("{not json", "malformed"),
        (
            json.dumps({"v": 2, "type": "user.text", "payload": {"text": "x"}}),
            "unsupported_version",
        ),
        (json.dumps({"v": 1, "type": "gesture.detected", "payload": {}}), "unknown_type"),
        (json.dumps({"v": 1, "type": "user.text", "payload": {}}), "invalid_payload"),
    ],
)
async def test_malformed_messages_get_an_error_and_keep_the_connection(
    harness: Harness, raw: str, code: str
) -> None:
    ws = await authed(harness.url)
    await ws.send(raw)
    err = await recv(ws)
    assert err["type"] == "error"
    assert err["payload"]["code"] == code
    await ws.send(user_text("hello"))  # still usable
    msgs = await recv_until(ws, "turn.completed")
    assert any(m["type"] == "assistant.text" for m in msgs)
    await ws.close()


# ------------------------------------------------------------------ end to end


async def test_find_files_flow_over_the_wire(harness: Harness) -> None:
    ws = await authed(harness.url)
    await ws.send(user_text("find my TrialGuard files"))
    msgs = await recv_until(ws, "turn.completed")
    types = [m["type"] for m in msgs]
    assert types == [
        "turn.started",
        "assistant.state",  # THINKING
        "assistant.state",  # EXECUTING
        "tool.request",
        "tool.result",
        "assistant.state",  # THINKING
        "assistant.state",  # SPEAKING
        "assistant.text",
        "assistant.state",  # IDLE
        "turn.completed",
    ]
    turn = msgs[0]["turn"]
    assert all(m["turn"] == turn for m in msgs)
    result = msgs[4]["payload"]
    assert result["results"][0] == {
        "id": "r_1",
        "kind": "file",
        "title": "TrialGuard_Proposal.pdf",
        "subtitle": r"C:\Users\donna\Documents\TrialGuard",
    }
    assert all("target" not in r for r in result["results"])
    await ws.close()


async def test_events_are_broadcast_to_every_client(harness: Harness) -> None:
    cli = await authed(harness.url)
    ui = await authed(harness.url)
    await cli.send(user_text("open chrome"))
    ui_msgs = await recv_until(ui, "turn.completed")
    assert ui_msgs[-1]["payload"]["route"] == "fast_path"
    await recv_until(cli, "turn.completed")
    await cli.close()
    await ui.close()


async def test_barge_in_cancels_the_speaking_turn() -> None:
    h = await _start(speaker=SimulatedSpeaker(ms_per_char=1000))  # speech "never" ends
    try:
        ws = await authed(h.url)
        await ws.send(user_text("hello"))
        first = await recv_until(ws, "assistant.text")
        assert h.core.assistant_state == "SPEAKING"  # still "talking"
        await ws.send(user_text("open notepad"))
        msgs = await recv_until(ws, "assistant.text")
        types = [m["type"] for m in msgs]
        # old turn is wound down (cancelled -> IDLE) before the new one starts
        assert types[:3] == ["turn.cancelled", "assistant.state", "turn.started"]
        assert msgs[0]["turn"] == first[0]["turn"]
        assert msgs[1]["payload"]["state"] == "IDLE"
        assert msgs[-1]["turn"] == msgs[2]["turn"] != first[0]["turn"]
        assert msgs[-1]["payload"]["text"] == "Opened Notepad."
        await ws.close()
    finally:
        await h.gateway.stop()


async def test_user_cancel_message() -> None:
    h = await _start(speaker=SimulatedSpeaker(ms_per_char=1000))
    try:
        ws = await authed(h.url)
        await ws.send(user_text("hello"))
        await recv_until(ws, "assistant.text")
        await ws.send(json.dumps({"v": 1, "type": "user.cancel", "payload": {}}))
        msgs = await recv_until(ws, "assistant.state")
        assert msgs[0]["type"] == "turn.cancelled"
        assert msgs[-1]["payload"]["state"] == "IDLE"
        await ws.close()
    finally:
        await h.gateway.stop()
