"""Result registry: the only bridge between "something a tool found" and
"something DONNA may open".

Tools register what they found and get back an opaque id (``r_1``). The model
and the UI only ever see ids, titles and subtitles; the real path or URL
(``target``) stays here. ``open_result`` takes an id, never a path.
"""

from __future__ import annotations

import itertools
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from donna_core.protocol.messages import ResultItem

ResultKind = Literal["file", "app", "web"]


@dataclass(frozen=True, slots=True)
class ResultEntry:
    id: str
    kind: ResultKind
    title: str
    subtitle: str
    target: str  # path or URL. Private: never sent to clients or the LLM.
    created_at: float

    def public(self) -> ResultItem:
        return ResultItem(id=self.id, kind=self.kind, title=self.title, subtitle=self.subtitle)


class UnknownResult(LookupError):
    pass


class ExpiredResult(LookupError):
    pass


class ResultRegistry:
    def __init__(
        self,
        ttl_s: float = 30 * 60,
        max_entries: int = 500,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl_s = ttl_s
        self._max = max_entries
        self._clock = clock
        self._ids = itertools.count(1)
        self._entries: OrderedDict[str, ResultEntry] = OrderedDict()

    def register(
        self, kind: ResultKind, title: str, target: str, subtitle: str = ""
    ) -> ResultEntry:
        entry = ResultEntry(
            id=f"r_{next(self._ids)}",
            kind=kind,
            title=title,
            subtitle=subtitle,
            target=target,
            created_at=self._clock(),
        )
        self._entries[entry.id] = entry
        while len(self._entries) > self._max:
            self._entries.popitem(last=False)  # evict the oldest
        return entry

    def resolve(self, result_id: str) -> ResultEntry:
        entry = self._entries.get(result_id)
        if entry is None:
            raise UnknownResult(result_id)
        if self._clock() - entry.created_at > self._ttl_s:
            del self._entries[result_id]
            raise ExpiredResult(result_id)
        return entry

    def __len__(self) -> int:
        return len(self._entries)
