"""Composition root. Every concrete class is chosen here and nowhere else.

To plug in real hardware or OS integrations later, swap the implementation
passed in here (e.g. MockFileSearcher -> EverythingFileSearcher, FakeLLM ->
OpenAICompatLLM, InstantSpeaker -> PiperSpeaker).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from donna_core.agent.agent import Agent
from donna_core.agent.fastpath import FastPath
from donna_core.agent.speaker import InstantSpeaker, SimulatedSpeaker, Speaker
from donna_core.agent.state import StateMachine
from donna_core.agent.turns import Turn, TurnManager
from donna_core.bus import EventBus
from donna_core.config import Config
from donna_core.llm.base import LLM
from donna_core.llm.fake import FakeLLM
from donna_core.llm.openai_compat import OpenAICompatLLM
from donna_core.protocol.messages import AssistantState
from donna_core.tools.apps import AppCatalog
from donna_core.tools.backends import (
    AppLauncher,
    FileSearcher,
    MockAppLauncher,
    MockFileSearcher,
    MockOpener,
    MockWebSearcher,
    Opener,
    WebSearcher,
)
from donna_core.tools.base import ToolContext
from donna_core.tools.find_files import FindFilesTool
from donna_core.tools.open_app import OpenAppTool
from donna_core.tools.open_result import OpenResultTool
from donna_core.tools.results import ResultRegistry
from donna_core.tools.router import ToolRouter
from donna_core.tools.web_search import WebSearchTool


@dataclass
class Backends:
    launcher: AppLauncher = field(default_factory=MockAppLauncher)
    files: FileSearcher = field(default_factory=MockFileSearcher)
    web: WebSearcher = field(default_factory=MockWebSearcher)
    opener: Opener = field(default_factory=MockOpener)


@dataclass
class Core:
    """The assembled brain. The gateway only uses submit/cancel/state/tool_names."""

    bus: EventBus
    state: StateMachine
    results: ResultRegistry
    router: ToolRouter
    agent: Agent
    turns: TurnManager
    backends: Backends

    async def submit(self, text: str) -> Turn:
        return await self.turns.start(text)

    async def cancel(self, reason: str = "cancelled by user") -> bool:
        return await self.turns.cancel(reason)

    @property
    def assistant_state(self) -> AssistantState:
        return self.state.state

    @property
    def tool_names(self) -> list[str]:
        return self.router.names


def make_llm(name: str) -> LLM:
    if name == "fake":
        return FakeLLM()
    if name == "openai_compat":
        return OpenAICompatLLM()
    raise ValueError(f"unknown llm {name!r}")


def build_core(
    config: Config | None = None,
    *,
    llm: LLM | None = None,
    speaker: Speaker | None = None,
    backends: Backends | None = None,
    catalog: AppCatalog | None = None,
) -> Core:
    config = config or Config()
    backends = backends or Backends()
    catalog = catalog or AppCatalog()
    if speaker is None:
        speaker = SimulatedSpeaker() if config.simulate_speech else InstantSpeaker()

    bus = EventBus()
    state = StateMachine(bus)
    results = ResultRegistry()
    router = ToolRouter(
        [
            OpenAppTool(catalog, backends.launcher),
            FindFilesTool(backends.files),
            OpenResultTool(backends.opener),
            WebSearchTool(backends.web),
        ],
        ToolContext(results),
        timeout_s=config.tool_timeout_s,
    )
    agent = Agent(llm or make_llm(config.llm), router, FastPath(catalog), speaker, state)
    turns = TurnManager(agent.run, bus, state)
    return Core(bus, state, results, router, agent, turns, backends)
