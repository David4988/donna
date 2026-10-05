"""Wire protocol between the core and its clients (CLI, Tauri UI).

Pydantic models here are the single source of truth. JSON Schema and TypeScript
types are generated from them (see scripts/gen_protocol.py).
"""

from donna_core.protocol.codec import (
    PROTOCOL_VERSION,
    ProtocolError,
    decode_client,
    decode_server,
    encode,
)
from donna_core.protocol.messages import (
    CLIENT_MESSAGE_TYPES,
    SERVER_MESSAGE_TYPES,
    AssistantState,
    ClientMessage,
    ResultItem,
    ServerMessage,
)

__all__ = [
    "CLIENT_MESSAGE_TYPES",
    "PROTOCOL_VERSION",
    "SERVER_MESSAGE_TYPES",
    "AssistantState",
    "ClientMessage",
    "ProtocolError",
    "ResultItem",
    "ServerMessage",
    "decode_client",
    "decode_server",
    "encode",
]
