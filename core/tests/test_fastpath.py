from collections.abc import Sequence

import pytest

from donna_core.agent.fastpath import FastPath
from donna_core.app import build_core
from donna_core.llm.base import LLMResponse, Message, ToolSpec
from donna_core.llm.fake import FakeLLM
from donna_core.tools.apps import AppCatalog


class SpyLLM:
    def __init__(self) -> None:
        self.calls = 0
        self._inner = FakeLLM()

    async def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMResponse:
        self.calls += 1
        return await self._inner.complete(messages, tools)


@pytest.mark.parametrize(
    ("text", "app_id"),
    [
        ("open VS Code", "vscode"),
        ("Open vscode.", "vscode"),
        ("launch chrome", "chrome"),
        ("please open the terminal", "terminal"),
        ("start  Notepad!", "notepad"),
    ],
)
def test_matcher_recognises_known_apps(text: str, app_id: str) -> None:
    call = FastPath(AppCatalog()).match(text)
    assert call is not None
    assert (call.name, call.arguments) == ("open_app", {"app": app_id})


@pytest.mark.parametrize(
    "text",
    ["open photoshop", "open it", "hello", "find my TrialGuard files", "open the pod bay doors"],
)
def test_matcher_ignores_anything_unsure(text: str) -> None:
    assert FastPath(AppCatalog()).match(text) is None


async def test_known_command_bypasses_the_llm() -> None:
    spy = SpyLLM()
    core = build_core(llm=spy)
    await core.submit("open VS Code")
    await core.turns.wait()
    assert spy.calls == 0
    assert core.backends.launcher.launched == ["vscode"]  # type: ignore[attr-defined]


async def test_unknown_command_reaches_the_llm() -> None:
    spy = SpyLLM()
    core = build_core(llm=spy)
    await core.submit("open photoshop")
    await core.turns.wait()
    assert spy.calls >= 1
