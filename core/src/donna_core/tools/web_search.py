from __future__ import annotations

from urllib.parse import urlparse

from pydantic import Field

from donna_core.tools.backends import WebSearcher
from donna_core.tools.base import Permission, Tool, ToolArgs, ToolContext, ToolOutput


class WebSearchArgs(ToolArgs):
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=3, ge=1, le=10)


class WebSearchTool(Tool):
    name = "web_search"
    description = "Search the web. Returns result ids with titles."
    label = "Searching the web..."
    permission = Permission.NETWORK
    Args = WebSearchArgs

    def __init__(self, searcher: WebSearcher) -> None:
        self._searcher = searcher

    async def run(self, args: WebSearchArgs, ctx: ToolContext) -> ToolOutput:
        hits = await self._searcher.search(args.query, args.limit)
        items = [
            ctx.results.register(
                "web", hit.title, target=hit.url, subtitle=urlparse(hit.url).netloc
            ).public()
            for hit in hits
        ]
        if not items:
            return ToolOutput(summary=f"I couldn't find anything for '{args.query}'.")
        return ToolOutput(summary=f"Here's what I found for '{args.query}'.", results=items)
