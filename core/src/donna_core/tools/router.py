"""Tool router: the single choke point between a tool *request* and a tool *run*.

Every request goes through the same checks, in order:
unknown tool -> argument validation -> permission policy -> run with timeout.
Failures come back as values (ToolFailure), never as exceptions, so the agent
can report them to the model and the user.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from donna_core.llm.base import ToolSpec
from donna_core.tools.base import Permission, Tool, ToolContext, ToolFailed, ToolOutput

log = logging.getLogger(__name__)

DEFAULT_ALLOWED = frozenset({Permission.READ_ONLY, Permission.LAUNCH, Permission.NETWORK})


@dataclass(frozen=True, slots=True)
class ToolSuccess:
    output: ToolOutput


@dataclass(frozen=True, slots=True)
class ToolFailure:
    code: str
    message: str


ToolOutcome = ToolSuccess | ToolFailure


@dataclass(frozen=True, slots=True)
class PermissionPolicy:
    allowed: frozenset[Permission] = DEFAULT_ALLOWED

    def allows(self, tool: Tool) -> bool:
        return tool.permission in self.allowed


def _describe(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors()[:3]:
        where = ".".join(str(p) for p in err["loc"]) or "arguments"
        parts.append(f"{where}: {err['msg']}")
    return "; ".join(parts)


class ToolRouter:
    def __init__(
        self,
        tools: Iterable[Tool],
        ctx: ToolContext,
        policy: PermissionPolicy | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self._tools = {t.name: t for t in tools}
        self._ctx = ctx
        self._policy = policy or PermissionPolicy()
        self._timeout_s = timeout_s

    @property
    def names(self) -> list[str]:
        return list(self._tools)

    def specs(self) -> list[ToolSpec]:
        return [t.spec() for t in self._tools.values()]

    def label_for(self, name: str) -> str:
        tool = self._tools.get(name)
        return tool.label if tool else f"Running {name}..."

    async def execute(self, name: str, arguments: dict[str, Any]) -> ToolOutcome:
        tool = self._tools.get(name)
        if tool is None:
            return ToolFailure("unknown_tool", f"There is no tool called '{name}'.")
        try:
            args = tool.Args.model_validate(arguments)
        except ValidationError as exc:
            return ToolFailure("invalid_arguments", _describe(exc))
        if not self._policy.allows(tool):
            return ToolFailure("permission_denied", f"'{name}' isn't allowed.")
        try:
            output = await asyncio.wait_for(tool.run(args, self._ctx), self._timeout_s)
        except ToolFailed as exc:
            return ToolFailure(exc.code, exc.message)
        except TimeoutError:
            return ToolFailure("timeout", f"'{name}' took too long.")
        except Exception:
            log.exception("tool %s crashed", name)
            return ToolFailure("tool_failed", f"'{name}' failed unexpectedly.")
        return ToolSuccess(output)
