import json

import pytest

from donna_core.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    decode_client,
    decode_server,
    encode,
)
from donna_core.protocol.codec import json_schema
from donna_core.protocol.messages import (
    CLIENT_MESSAGE_TYPES,
    SERVER_MESSAGE_TYPES,
    AssistantState,
    AssistantStateChanged,
    AssistantStatePayload,
    SessionHello,
    UserCancel,
    UserText,
)


def msg(type_: str, payload: object = None, **extra: object) -> str:
    return json.dumps({"v": 1, "type": type_, "payload": payload or {}, **extra})


def test_valid_user_text() -> None:
    m = decode_client(msg("user.text", {"text": "hello"}, turn=None, ts="2026-01-01T00:00:00Z"))
    assert isinstance(m, UserText)
    assert m.payload.text == "hello"


def test_valid_hello_and_cancel() -> None:
    hello = decode_client(msg("session.hello", {"token": "t", "client": {"name": "cli"}}))
    assert isinstance(hello, SessionHello)
    assert isinstance(decode_client(msg("user.cancel")), UserCancel)


def test_ts_and_turn_are_optional_and_defaulted() -> None:
    m = decode_client(msg("user.text", {"text": "hi"}))
    assert m.turn is None
    assert m.ts.endswith("Z")


def test_round_trip_server_message() -> None:
    out = AssistantStateChanged(
        turn="t_1",
        payload=AssistantStatePayload(state=AssistantState.THINKING, previous=AssistantState.IDLE),
    )
    back = decode_server(encode(out))
    assert back == out


@pytest.mark.parametrize("raw", ["not json", "[1, 2]", '"string"', "{}", '{"v": 1}'])
def test_malformed(raw: str) -> None:
    with pytest.raises(ProtocolError) as exc:
        decode_client(raw)
    assert exc.value.code == "malformed"


@pytest.mark.parametrize("version", [0, 2, "1", None])
def test_unsupported_version(version: object) -> None:
    raw = json.dumps({"v": version, "type": "user.text", "payload": {"text": "hi"}})
    with pytest.raises(ProtocolError) as exc:
        decode_client(raw)
    assert exc.value.code == "unsupported_version"


def test_unknown_type() -> None:
    with pytest.raises(ProtocolError) as exc:
        decode_client(msg("gesture.detected", {}))
    assert exc.value.code == "unknown_type"


def test_client_cannot_send_server_only_types() -> None:
    with pytest.raises(ProtocolError) as exc:
        decode_client(msg("assistant.text", {"text": "I am the server now"}))
    assert exc.value.code == "unknown_type"


@pytest.mark.parametrize(
    "raw",
    [
        msg("user.text", {}),  # missing text
        msg("user.text", {"text": ""}),  # too short
        msg("user.text", {"text": "x" * 2001}),  # too long
        msg("user.text", {"text": "hi", "extra": 1}),  # unknown field
        msg("session.hello", {"token": "t"}),  # missing client
        json.dumps({"v": 1, "type": "user.text", "payload": {"text": "hi"}, "bogus": True}),
    ],
)
def test_invalid_payload(raw: str) -> None:
    with pytest.raises(ProtocolError) as exc:
        decode_client(raw)
    assert exc.value.code == "invalid_payload"


def test_type_sets_are_disjoint_and_complete() -> None:
    assert not CLIENT_MESSAGE_TYPES & SERVER_MESSAGE_TYPES
    required = {
        "session.hello", "session.ready", "user.text", "assistant.text", "turn.started",
        "turn.cancelled", "turn.completed", "assistant.state", "tool.request",
        "tool.result", "tool.error", "error",
    }  # fmt: skip
    assert required <= CLIENT_MESSAGE_TYPES | SERVER_MESSAGE_TYPES


def test_json_schema_exports_both_directions() -> None:
    schema = json_schema()
    assert {"ClientMessage", "ServerMessage"} <= set(schema["$defs"])
    assert PROTOCOL_VERSION == 1
