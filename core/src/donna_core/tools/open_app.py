from __future__ import annotations

from pydantic import Field

from donna_core.tools.apps import AppCatalog
from donna_core.tools.backends import AppLauncher
from donna_core.tools.base import Permission, Tool, ToolArgs, ToolContext, ToolFailed, ToolOutput


class OpenAppArgs(ToolArgs):
    app: str = Field(min_length=1, max_length=100, description="App name, e.g. 'vscode'.")


class OpenAppTool(Tool):
    name = "open_app"
    description = "Launch an installed application by name."
    label = "Opening app..."
    permission = Permission.LAUNCH
    Args = OpenAppArgs

    def __init__(self, catalog: AppCatalog, launcher: AppLauncher) -> None:
        self._catalog = catalog
        self._launcher = launcher

    async def run(self, args: OpenAppArgs, ctx: ToolContext) -> ToolOutput:
        app = self._catalog.resolve(args.app)
        if app is None:
            raise ToolFailed("app_not_found", f"I couldn't find an app called '{args.app}'.")
        await self._launcher.launch(app)
        return ToolOutput(summary=f"Opened {app.name}.")
