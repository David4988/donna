"""OS / network backends behind small interfaces.

Tools depend on these protocols, never on the OS directly. The mocks below are
what the skeleton runs with; real Windows backends (Start Menu index,
Everything/es.exe, os.startfile, a search provider) replace them later in
app.py without touching the tools, router or agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

from donna_core.tools.apps import AppEntry

OpenAction = Literal["open", "reveal"]


@dataclass(frozen=True, slots=True)
class FileHit:
    name: str
    folder: str
    path: str


@dataclass(frozen=True, slots=True)
class WebHit:
    title: str
    url: str
    snippet: str = ""


class AppLauncher(Protocol):
    async def launch(self, app: AppEntry) -> None: ...


class FileSearcher(Protocol):
    async def search(self, query: str, limit: int) -> list[FileHit]: ...


class WebSearcher(Protocol):
    async def search(self, query: str, limit: int) -> list[WebHit]: ...


class Opener(Protocol):
    async def open(self, target: str, action: OpenAction) -> None: ...


# ------------------------------------------------------------------ mocks

_DOCS = r"C:\Users\donna\Documents"
_DOWNLOADS = r"C:\Users\donna\Downloads"


def _file(folder: str, name: str) -> FileHit:
    return FileHit(name=name, folder=folder, path=f"{folder}\\{name}")


MOCK_FILES: tuple[FileHit, ...] = (
    _file(rf"{_DOCS}\TrialGuard", "TrialGuard_Proposal.pdf"),
    _file(rf"{_DOCS}\TrialGuard", "TrialGuard_Architecture.docx"),
    _file(rf"{_DOCS}\notes", "trialguard-notes.md"),
    _file(_DOWNLOADS, "TrialGuard_Setup.exe"),
    _file(rf"{_DOCS}\Career", "Resume_2026.pdf"),
    _file(rf"{_DOCS}\Career", "placement-prep.xlsx"),
)


@dataclass
class MockAppLauncher:
    launched: list[str] = field(default_factory=list)

    async def launch(self, app: AppEntry) -> None:
        self.launched.append(app.id)


@dataclass
class MockFileSearcher:
    files: tuple[FileHit, ...] = MOCK_FILES

    async def search(self, query: str, limit: int) -> list[FileHit]:
        terms = query.casefold().split()
        hits = [f for f in self.files if all(t in f.name.casefold() for t in terms)]
        return hits[:limit]


@dataclass
class MockWebSearcher:
    async def search(self, query: str, limit: int) -> list[WebHit]:
        slug = "-".join(query.casefold().split())
        hits = [
            WebHit(f"{query} - Wikipedia", f"https://en.wikipedia.org/wiki/{slug}"),
            WebHit(f"What is {query}? A beginner's guide", f"https://example.com/guides/{slug}"),
            WebHit(f"{query} news and updates", f"https://news.example.com/{slug}"),
        ]
        return hits[:limit]


@dataclass
class MockOpener:
    opened: list[tuple[str, OpenAction]] = field(default_factory=list)

    async def open(self, target: str, action: OpenAction) -> None:
        self.opened.append((target, action))
