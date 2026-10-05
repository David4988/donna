"""The Tool interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

from donna_core.llm.base import ToolSpec
from donna_core.protocol.messages import ResultItem
from donna_core.tools.results import ResultRegistry


class Permission(StrEnum):
    READ_ONLY = "read_only"  # looks things up, changes nothing
    LAUNCH = "launch"  # opens an app or a known result
    NETWORK = "network"  # talks to the internet
    DESTRUCTIVE = "destructive"  # moves/deletes. Not allowed in v1.


class ToolArgs(BaseModel):
    """Base for tool argument models. Unknown arguments are rejected."""

    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class ToolContext:
    results: ResultRegistry


@dataclass(slots=True)
class ToolOutput:
    summary: str  # one human-readable sentence
    results: list[ResultItem] = field(default_factory=list)


class ToolFailed(Exception):
    """An expected failure a tool reports (app not found, unknown result, ...)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class Tool(ABC):
    name: ClassVar[str]
    description: ClassVar[str]
    label: ClassVar[str]  # shown to the user while the tool runs
    permission: ClassVar[Permission]
    Args: ClassVar[type[ToolArgs]]

    @abstractmethod
    async def run(self, args: Any, ctx: ToolContext) -> ToolOutput:
        """``args`` is an already-validated instance of ``self.Args``."""

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, self.Args.model_json_schema())
