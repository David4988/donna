from __future__ import annotations

from pathlib import PureWindowsPath

from pydantic import Field

from donna_core.tools.backends import Opener
from donna_core.tools.base import Permission, Tool, ToolArgs, ToolContext, ToolFailed, ToolOutput
from donna_core.tools.results import ExpiredResult, UnknownResult

# Opening one of these would *run* it. They are revealed in their folder instead.
EXECUTABLE_EXTENSIONS = frozenset(
    {".exe", ".msi", ".bat", ".cmd", ".com", ".ps1", ".vbs", ".vbe", ".js", ".jse",
     ".wsf", ".wsh", ".scr", ".hta", ".lnk", ".pif", ".cpl", ".reg", ".jar"}
)  # fmt: skip


class OpenResultArgs(ToolArgs):
    result_id: str = Field(
        pattern=r"^r_\d+$", description="Id of a result from an earlier tool, e.g. 'r_1'."
    )


class OpenResultTool(Tool):
    name = "open_result"
    description = "Open a file or web page returned by an earlier tool, by its result id."
    label = "Opening..."
    permission = Permission.LAUNCH
    Args = OpenResultArgs

    def __init__(self, opener: Opener) -> None:
        self._opener = opener

    async def run(self, args: OpenResultArgs, ctx: ToolContext) -> ToolOutput:
        try:
            entry = ctx.results.resolve(args.result_id)
        except UnknownResult:
            raise ToolFailed("unknown_result", f"I don't have a result {args.result_id}.") from None
        except ExpiredResult:
            raise ToolFailed(
                "expired_result", f"Result {args.result_id} has expired. Search again."
            ) from None

        is_program = (
            entry.kind == "file"
            and PureWindowsPath(entry.target).suffix.casefold() in EXECUTABLE_EXTENSIONS
        )
        if is_program:
            await self._opener.open(entry.target, "reveal")
            return ToolOutput(
                summary=f"{entry.title} is a program, so I showed it in its folder "
                "instead of running it.",
                results=[entry.public()],
            )
        await self._opener.open(entry.target, "open")
        return ToolOutput(summary=f"Opened {entry.title}.", results=[entry.public()])
