"""The LLM interface.

Shapes mirror the OpenAI chat-completions format (messages, tools, tool_calls)
because the production model (Qwen3.6-35B-A3B) will be served behind an
OpenAI-compatible endpoint. Swapping FakeLLM for the real thing is a change in
the composition root, not in the agent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str = ""
    tool_calls: tuple[ToolCall, ...] = ()
    tool_call_id: str | None = None  # set on role="tool" messages
    name: str | None = None  # tool name on role="tool" messages


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema of the tool's arguments


@dataclass(frozen=True, slots=True)
class LLMResponse:
    """Either a text reply or one or more tool calls."""

    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = field(default_factory=tuple)


class LLM(Protocol):
    async def complete(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec]
    ) -> LLMResponse: ...
