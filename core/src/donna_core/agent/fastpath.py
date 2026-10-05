"""Fast paths: obvious commands that skip the LLM entirely.

Deliberately small and explicit. A rule only fires when it is *confident*
(e.g. the app name resolves in the catalog); otherwise the input falls through
to the LLM. Add rules one at a time, each with a test.
"""

from __future__ import annotations

import itertools
import re

from donna_core.llm.base import ToolCall
from donna_core.tools.apps import AppCatalog

_OPEN_APP = re.compile(r"^(?:please\s+)?(?:open|launch|start)\s+(?P<app>.+?)[.!]*$", re.I)


class FastPath:
    def __init__(self, catalog: AppCatalog) -> None:
        self._catalog = catalog
        self._ids = itertools.count(1)

    def match(self, text: str) -> ToolCall | None:
        m = _OPEN_APP.match(" ".join(text.split()))
        if m:
            app = self._catalog.resolve(m["app"])
            if app is not None:
                return ToolCall(f"fp_{next(self._ids)}", "open_app", {"app": app.id})
        return None
