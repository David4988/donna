"""Decoding/encoding of wire messages.

Decoding is staged so every failure maps to one precise error code:

    malformed            not JSON, not an object, or missing ``type``
    unsupported_version  ``v`` is not a version this core speaks
    unknown_type         ``type`` isn't a message this side accepts
    invalid_payload      envelope/payload fail validation
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic.json_schema import GenerateJsonSchema
from pydantic_core import CoreSchema

from donna_core.protocol.messages import (
    CLIENT_MESSAGE_TYPES,
    SERVER_MESSAGE_TYPES,
    ClientMessage,
    ServerMessage,
)

PROTOCOL_VERSION = 1

_client_adapter: TypeAdapter[Any] = TypeAdapter(ClientMessage)
_server_adapter: TypeAdapter[Any] = TypeAdapter(ServerMessage)


class ProtocolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def _decode(raw: str | bytes, allowed: frozenset[str], adapter: TypeAdapter[Any]) -> Any:
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError("malformed", "message is not valid JSON") from exc
    if not isinstance(data, dict):
        raise ProtocolError("malformed", "message must be a JSON object")
    if "v" not in data:
        raise ProtocolError("malformed", "missing protocol version 'v'")
    if data["v"] != PROTOCOL_VERSION:
        raise ProtocolError(
            "unsupported_version",
            f"protocol version {data['v']!r} is not supported (expected {PROTOCOL_VERSION})",
        )
    msg_type = data.get("type")
    if not isinstance(msg_type, str):
        raise ProtocolError("malformed", "missing message 'type'")
    if msg_type not in allowed:
        raise ProtocolError("unknown_type", f"unknown message type {msg_type!r}")
    try:
        return adapter.validate_python(data)
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"][1:]) or "message"
        raise ProtocolError("invalid_payload", f"{where}: {first['msg']}") from exc


def decode_client(raw: str | bytes) -> Any:
    """Parse a message sent by a client. Returns one of the ClientMessage models."""
    return _decode(raw, CLIENT_MESSAGE_TYPES, _client_adapter)


def decode_server(raw: str | bytes) -> Any:
    """Parse a message sent by the core (used by the Python CLI client and tests)."""
    return _decode(raw, SERVER_MESSAGE_TYPES, _server_adapter)


def encode(message: BaseModel) -> str:
    return message.model_dump_json()


class _NoFieldTitles(GenerateJsonSchema):
    """Skip per-field titles so generated TypeScript stays readable."""

    def field_title_should_be_set(self, schema: CoreSchema) -> bool:
        return False


def json_schema() -> dict[str, Any]:
    """Combined JSON Schema for both directions, used to generate TypeScript types.

    Serialization mode: every envelope field is required, i.e. the schema describes
    complete messages. (The Python decoder is lenient and fills in ``turn``/``ts``.)
    """
    opts: dict[str, Any] = {
        "ref_template": "#/$defs/{model}",
        "mode": "serialization",
        "schema_generator": _NoFieldTitles,
    }
    client = _client_adapter.json_schema(**opts)
    server = _server_adapter.json_schema(**opts)
    defs: dict[str, Any] = {**client.pop("$defs", {}), **server.pop("$defs", {})}
    defs["ClientMessage"] = client
    defs["ServerMessage"] = server
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "DonnaProtocol",
        "description": f"DONNA wire protocol v{PROTOCOL_VERSION}. Generated from Pydantic.",
        "$defs": dict(sorted(defs.items())),
    }
