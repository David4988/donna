"""Message models for protocol v1.

Every message shares the envelope ``{v, type, turn, ts, payload}``. Each message
type is its own model with ``type`` as a Literal, so the two unions below are
discriminated on ``type``.

Adding a message type (e.g. a future ``gesture.detected``): define a payload
model, define the message model, add it to the right union. Nothing else.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class AssistantState(StrEnum):
    IDLE = "IDLE"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    EXECUTING = "EXECUTING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"


Route = Literal["fast_path", "llm"]


class _Model(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        # In the generated schema, fields the core always sends are required.
        json_schema_serialization_defaults_required=True,
    )


# ---------------------------------------------------------------- payloads


class ClientInfo(_Model):
    name: str = Field(min_length=1, max_length=64)
    version: str = Field(default="0", max_length=32)


class SessionHelloPayload(_Model):
    token: str = Field(min_length=1, max_length=256)
    client: ClientInfo


class UserTextPayload(_Model):
    text: str = Field(min_length=1, max_length=2000)


class UserCancelPayload(_Model):
    pass


class SessionReadyPayload(_Model):
    session_id: str
    protocol_version: int
    server_version: str
    state: AssistantState
    tools: list[str]


class TurnStartedPayload(_Model):
    input: str


class TurnCompletedPayload(_Model):
    route: Route


class TurnCancelledPayload(_Model):
    reason: str


class TurnFailedPayload(_Model):
    message: str


class AssistantStatePayload(_Model):
    state: AssistantState
    previous: AssistantState


class AssistantTextPayload(_Model):
    text: str
    final: bool = True


class ToolRequestPayload(_Model):
    call_id: str
    tool: str
    args: dict[str, Any]
    label: str


class ResultItem(_Model):
    """What clients and the LLM may see about a result. Never the raw path/URL."""

    id: str
    kind: Literal["file", "app", "web"]
    title: str
    subtitle: str = ""


class ToolResultPayload(_Model):
    call_id: str
    tool: str
    summary: str
    results: list[ResultItem] = Field(default_factory=list)


class ToolErrorPayload(_Model):
    call_id: str
    tool: str
    code: str
    message: str


class ErrorPayload(_Model):
    code: str
    message: str


# ---------------------------------------------------------------- envelope


class _Envelope(_Model):
    v: Literal[1] = 1
    turn: str | None = None
    ts: str = Field(default_factory=utc_now_iso)


# Client -> core


class SessionHello(_Envelope):
    type: Literal["session.hello"] = "session.hello"
    payload: SessionHelloPayload


class UserText(_Envelope):
    type: Literal["user.text"] = "user.text"
    payload: UserTextPayload


class UserCancel(_Envelope):
    type: Literal["user.cancel"] = "user.cancel"
    payload: UserCancelPayload = Field(default_factory=UserCancelPayload)


# Core -> client


class SessionReady(_Envelope):
    type: Literal["session.ready"] = "session.ready"
    payload: SessionReadyPayload


class TurnStarted(_Envelope):
    type: Literal["turn.started"] = "turn.started"
    payload: TurnStartedPayload


class TurnCompleted(_Envelope):
    type: Literal["turn.completed"] = "turn.completed"
    payload: TurnCompletedPayload


class TurnCancelled(_Envelope):
    type: Literal["turn.cancelled"] = "turn.cancelled"
    payload: TurnCancelledPayload


class TurnFailed(_Envelope):
    type: Literal["turn.failed"] = "turn.failed"
    payload: TurnFailedPayload


class AssistantStateChanged(_Envelope):
    type: Literal["assistant.state"] = "assistant.state"
    payload: AssistantStatePayload


class AssistantText(_Envelope):
    type: Literal["assistant.text"] = "assistant.text"
    payload: AssistantTextPayload


class ToolRequest(_Envelope):
    type: Literal["tool.request"] = "tool.request"
    payload: ToolRequestPayload


class ToolResult(_Envelope):
    type: Literal["tool.result"] = "tool.result"
    payload: ToolResultPayload


class ToolError(_Envelope):
    type: Literal["tool.error"] = "tool.error"
    payload: ToolErrorPayload


class Error(_Envelope):
    type: Literal["error"] = "error"
    payload: ErrorPayload


ClientMessage = Annotated[
    SessionHello | UserText | UserCancel,
    Field(discriminator="type"),
]

ServerMessage = Annotated[
    SessionReady
    | TurnStarted
    | TurnCompleted
    | TurnCancelled
    | TurnFailed
    | AssistantStateChanged
    | AssistantText
    | ToolRequest
    | ToolResult
    | ToolError
    | Error,
    Field(discriminator="type"),
]

CLIENT_MODELS: tuple[type[_Envelope], ...] = (SessionHello, UserText, UserCancel)
SERVER_MODELS: tuple[type[_Envelope], ...] = (
    SessionReady,
    TurnStarted,
    TurnCompleted,
    TurnCancelled,
    TurnFailed,
    AssistantStateChanged,
    AssistantText,
    ToolRequest,
    ToolResult,
    ToolError,
    Error,
)


def _type_of(model: type[_Envelope]) -> str:
    default = model.model_fields["type"].default
    assert isinstance(default, str)
    return default


CLIENT_MESSAGE_TYPES: frozenset[str] = frozenset(_type_of(m) for m in CLIENT_MODELS)
SERVER_MESSAGE_TYPES: frozenset[str] = frozenset(_type_of(m) for m in SERVER_MODELS)

# Maps a server message type to its model, so internal events can be wrapped.
SERVER_MODEL_BY_TYPE: dict[str, type[_Envelope]] = {_type_of(m): m for m in SERVER_MODELS}
