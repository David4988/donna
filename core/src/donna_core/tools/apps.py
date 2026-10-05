"""App catalog: the fixed set of apps DONNA is allowed to launch.

The model asks for an app by name ("vscode"); the catalog resolves that to a
known entry, and the launcher launches the *entry*. A model-supplied string is
never executed. Later the catalog is built from the Windows Start Menu index.
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AppEntry:
    id: str
    name: str
    aliases: tuple[str, ...]


DEFAULT_APPS: tuple[AppEntry, ...] = (
    AppEntry("vscode", "Visual Studio Code", ("vscode", "vs code", "code", "visual studio code")),
    AppEntry("chrome", "Google Chrome", ("chrome", "google chrome", "browser")),
    AppEntry("terminal", "Windows Terminal", ("terminal", "windows terminal", "the terminal")),
    AppEntry("notepad", "Notepad", ("notepad",)),
    AppEntry("explorer", "File Explorer", ("explorer", "file explorer", "files")),
)


def _clean(name: str) -> str:
    name = re.sub(r"[^\w\s]", " ", name.casefold())
    name = re.sub(r"^(the|my)\s+", "", name.strip())
    name = re.sub(r"\s+(app|application)$", "", name)
    return " ".join(name.split())


class AppCatalog:
    def __init__(self, apps: Iterable[AppEntry] = DEFAULT_APPS, cutoff: float = 0.85) -> None:
        self._apps = tuple(apps)
        self._cutoff = cutoff
        self._by_alias: dict[str, AppEntry] = {}
        for app in self._apps:
            for alias in (app.id, app.name, *app.aliases):
                self._by_alias[_clean(alias)] = app

    @property
    def apps(self) -> tuple[AppEntry, ...]:
        return self._apps

    def resolve(self, name: str) -> AppEntry | None:
        """Exact alias match, else a single close fuzzy match, else None."""
        key = _clean(name)
        if not key:
            return None
        if key in self._by_alias:
            return self._by_alias[key]
        close = difflib.get_close_matches(key, list(self._by_alias), n=2, cutoff=self._cutoff)
        candidates = {self._by_alias[c].id for c in close}
        if len(candidates) == 1:
            return self._by_alias[close[0]]
        return None
