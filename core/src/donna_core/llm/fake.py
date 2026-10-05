"""A deterministic, rule-based stand-in for the real model.

It exists so the agent loop, tool routing and every test run without Ollama
or a GPU. Same input -> same output, always. It is not meant to be clever.
"""

from __future__ import annotations

import itertools
import json
import re
from collections.abc import Sequence
from typing import Any

from donna_core.llm.base import LLMResponse, Message, ToolCall, ToolSpec

_AMBIGUOUS_TARGETS = {"it", "that", "this", "them", "the file", "the thing"}

_GREETING = re.compile(r"^(hi|hello|hey|good (morning|afternoon|evening))( donna)?$", re.I)
_OPEN_RESULT = re.compile(r"^(?:please )?open (?:result )?(?P<id>r_\d+)$", re.I)
_WEB = re.compile(
    r"^(?:please )?(?:search the web|search online|look up|google)(?: for)? (?P<q>.+)$", re.I
)
_FIND = re.compile(
    r"^(?:please )?(?:find|look for|locate|search for) (?:my |the |all )?(?P<q>.+?)"
    r"(?: (?:files?|docs?|documents?))?"
    r"(?P<open> and open (?:the first one|the top one|it))?$",
    re.I,
)
_OPEN = re.compile(r"^(?:please )?(?:open|launch|start) (?P<target>.+)$", re.I)


def _normalise(text: str) -> str:
    """Trim whitespace and trailing punctuation. Case is kept (queries care)."""
    return re.sub(r"[.!?]+$", "", " ".join(text.split())).strip()


class FakeLLM:
    def __init__(self) -> None:
        self._ids = itertools.count(1)

    def _call(self, name: str, **arguments: Any) -> LLMResponse:
        return LLMResponse(tool_calls=(ToolCall(f"call_{next(self._ids)}", name, arguments),))

    async def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMResponse:
        if not messages:
            return LLMResponse(text="Hello.")
        last = messages[-1]
        if last.role == "tool":
            return self._after_tool(messages, last)
        user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        return self._from_user(_normalise(user), {t.name for t in tools})

    def _from_user(self, text: str, tools: set[str]) -> LLMResponse:
        if _GREETING.match(text):
            return LLMResponse(text="Hello.")
        if (m := _OPEN_RESULT.match(text)) and "open_result" in tools:
            return self._call("open_result", result_id=m["id"])
        if (m := _WEB.match(text)) and "web_search" in tools:
            return self._call("web_search", query=m["q"])
        if (m := _FIND.match(text)) and "find_files" in tools:
            return self._call("find_files", query=m["q"])
        if m := _OPEN.match(text):
            if m["target"].casefold() in _AMBIGUOUS_TARGETS:
                return LLMResponse(text="What would you like me to open?")
            if "open_app" in tools:
                return self._call("open_app", app=m["target"])
        return LLMResponse(text="Sorry, I can't help with that yet.")

    def _after_tool(self, messages: Sequence[Message], last: Message) -> LLMResponse:
        data = json.loads(last.content)
        if not data.get("ok"):
            return LLMResponse(text=f"Sorry, that didn't work. {data.get('message', '')}".strip())

        results: list[dict[str, Any]] = data.get("results", [])
        last_user = max(i for i, m in enumerate(messages) if m.role == "user")
        this_turn = messages[last_user:]  # ignore earlier turns in the history
        find = _FIND.match(_normalise(this_turn[0].content))
        already_opened = any(m.role == "tool" and m.name == "open_result" for m in this_turn)

        # Multi-step: "find X and open the first one" -> open_result(first id).
        if last.name == "find_files" and find and find["open"] and results and not already_opened:
            return self._call("open_result", result_id=results[0]["id"])

        summary: str = data.get("summary", "Done.")
        if results and last.name in ("find_files", "web_search"):
            return LLMResponse(text=f"{summary} The top one is {results[0]['title']}.")
        return LLMResponse(text=summary)
