from __future__ import annotations

from pydantic import Field

from donna_core.tools.backends import FileSearcher
from donna_core.tools.base import Permission, Tool, ToolArgs, ToolContext, ToolOutput


class FindFilesArgs(ToolArgs):
    query: str = Field(min_length=1, max_length=200, description="Words in the file name.")
    limit: int = Field(default=5, ge=1, le=20)


class FindFilesTool(Tool):
    name = "find_files"
    description = "Search the user's files by name. Read-only. Returns result ids."
    label = "Searching files..."
    permission = Permission.READ_ONLY
    Args = FindFilesArgs

    def __init__(self, searcher: FileSearcher) -> None:
        self._searcher = searcher

    async def run(self, args: FindFilesArgs, ctx: ToolContext) -> ToolOutput:
        hits = await self._searcher.search(args.query, args.limit)
        items = [
            ctx.results.register("file", hit.name, target=hit.path, subtitle=hit.folder).public()
            for hit in hits
        ]
        if not items:
            return ToolOutput(summary=f"I couldn't find any files matching '{args.query}'.")
        noun = "file" if len(items) == 1 else "files"
        return ToolOutput(summary=f"I found {len(items)} {noun} for '{args.query}'.", results=items)
