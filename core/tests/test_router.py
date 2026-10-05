import asyncio
from typing import Any

import pytest
from pydantic import Field

from donna_core.tools.apps import AppCatalog
from donna_core.tools.backends import MockAppLauncher, MockFileSearcher, MockOpener
from donna_core.tools.base import Permission, Tool, ToolArgs, ToolContext, ToolOutput
from donna_core.tools.find_files import FindFilesTool
from donna_core.tools.open_app import OpenAppTool
from donna_core.tools.open_result import OpenResultTool
from donna_core.tools.results import ResultRegistry
from donna_core.tools.router import ToolFailure, ToolRouter, ToolSuccess


class _NoArgs(ToolArgs):
    pass


class SlowTool(Tool):
    name = "slow"
    description = "never finishes"
    label = "..."
    permission = Permission.READ_ONLY
    Args = _NoArgs

    async def run(self, args: Any, ctx: ToolContext) -> ToolOutput:
        await asyncio.sleep(60)
        return ToolOutput("done")


class CrashTool(SlowTool):
    name = "crash"

    async def run(self, args: Any, ctx: ToolContext) -> ToolOutput:
        raise RuntimeError("bug")


class DeleteTool(SlowTool):
    name = "delete_file"
    permission = Permission.DESTRUCTIVE

    class Args(ToolArgs):
        result_id: str = Field(pattern=r"^r_\d+$")


@pytest.fixture
def launcher() -> MockAppLauncher:
    return MockAppLauncher()


@pytest.fixture
def opener() -> MockOpener:
    return MockOpener()


@pytest.fixture
def router(launcher: MockAppLauncher, opener: MockOpener) -> ToolRouter:
    return ToolRouter(
        [
            OpenAppTool(AppCatalog(), launcher),
            FindFilesTool(MockFileSearcher()),
            OpenResultTool(opener),
            SlowTool(),
            CrashTool(),
            DeleteTool(),
        ],
        ToolContext(ResultRegistry()),
        timeout_s=0.05,
    )


async def test_known_tool(router: ToolRouter, launcher: MockAppLauncher) -> None:
    outcome = await router.execute("open_app", {"app": "vs code"})
    assert isinstance(outcome, ToolSuccess)
    assert outcome.output.summary == "Opened Visual Studio Code."
    assert launcher.launched == ["vscode"]


async def test_unknown_tool(router: ToolRouter) -> None:
    outcome = await router.execute("run_shell", {"cmd": "rm -rf /"})
    assert outcome == ToolFailure("unknown_tool", "There is no tool called 'run_shell'.")


@pytest.mark.parametrize(
    ("tool", "args"),
    [
        ("open_app", {}),
        ("open_app", {"app": ""}),
        ("open_app", {"app": "chrome", "path": r"C:\evil.exe"}),  # extra args rejected
        ("find_files", {"query": "x", "limit": 1000}),
        ("open_result", {"result_id": r"C:\Windows\System32\cmd.exe"}),  # paths rejected
    ],
)
async def test_invalid_arguments(router: ToolRouter, tool: str, args: dict[str, Any]) -> None:
    outcome = await router.execute(tool, args)
    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "invalid_arguments"


async def test_permission_denied(router: ToolRouter) -> None:
    outcome = await router.execute("delete_file", {"result_id": "r_1"})
    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "permission_denied"


async def test_timeout(router: ToolRouter) -> None:
    outcome = await router.execute("slow", {})
    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "timeout"


async def test_tool_crash_is_contained(router: ToolRouter) -> None:
    outcome = await router.execute("crash", {})
    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "tool_failed"


async def test_expected_tool_failure(router: ToolRouter, launcher: MockAppLauncher) -> None:
    outcome = await router.execute("open_app", {"app": "photoshop"})
    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "app_not_found"
    assert launcher.launched == []


async def test_find_then_open_by_result_id(router: ToolRouter, opener: MockOpener) -> None:
    found = await router.execute("find_files", {"query": "TrialGuard"})
    assert isinstance(found, ToolSuccess)
    first = found.output.results[0]
    assert first.id.startswith("r_")
    opened = await router.execute("open_result", {"result_id": first.id})
    assert isinstance(opened, ToolSuccess)
    assert opener.opened == [
        (r"C:\Users\donna\Documents\TrialGuard\TrialGuard_Proposal.pdf", "open")
    ]


async def test_executables_are_revealed_not_run(router: ToolRouter, opener: MockOpener) -> None:
    found = await router.execute("find_files", {"query": "setup"})
    assert isinstance(found, ToolSuccess)
    [exe] = found.output.results
    outcome = await router.execute("open_result", {"result_id": exe.id})
    assert isinstance(outcome, ToolSuccess)
    assert opener.opened == [(r"C:\Users\donna\Downloads\TrialGuard_Setup.exe", "reveal")]


async def test_open_unknown_result(router: ToolRouter, opener: MockOpener) -> None:
    outcome = await router.execute("open_result", {"result_id": "r_404"})
    assert isinstance(outcome, ToolFailure)
    assert outcome.code == "unknown_result"
    assert opener.opened == []


def test_specs_expose_name_description_and_schema(router: ToolRouter) -> None:
    spec = next(s for s in router.specs() if s.name == "open_app")
    assert spec.description
    assert spec.parameters["properties"]["app"]["type"] == "string"
    assert spec.parameters["additionalProperties"] is False
