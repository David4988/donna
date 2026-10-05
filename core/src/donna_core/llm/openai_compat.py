"""Placeholder for the production model client.

The planned model is Qwen3.6-35B-A3B served locally behind an OpenAI-compatible
API (Ollama or llama.cpp's llama-server). This class only pins down the
configuration shape; it is deliberately not implemented in the skeleton.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from donna_core.llm.base import LLMResponse, Message, ToolSpec


@dataclass(frozen=True, slots=True)
class OpenAICompatConfig:
    base_url: str = "http://127.0.0.1:11434/v1"
    model: str = "qwen3.6:35b-a3b"
    timeout_s: float = 30.0


class OpenAICompatLLM:
    def __init__(self, config: OpenAICompatConfig | None = None) -> None:
        self.config = config or OpenAICompatConfig()

    async def complete(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> LLMResponse:
        raise NotImplementedError(
            "The real LLM client isn't implemented yet. Run the core with --llm fake."
        )
