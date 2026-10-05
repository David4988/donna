"""Speech output seam.

The agent "speaks" by awaiting ``Speaker.say``. Real TTS (Piper, Kokoro) plugs
in here later. For now speech is either instant or simulated with a delay, so
the SPEAKING state lasts long enough to test barge-in cancellation.
"""

from __future__ import annotations

import asyncio
from typing import Protocol


class Speaker(Protocol):
    async def say(self, text: str) -> None: ...


class InstantSpeaker:
    async def say(self, text: str) -> None:
        return None


class SimulatedSpeaker:
    """Pretends to speak: sleeps roughly as long as reading ``text`` aloud takes."""

    def __init__(self, ms_per_char: float = 45.0, min_ms: float = 400.0) -> None:
        self._ms_per_char = ms_per_char
        self._min_ms = min_ms

    async def say(self, text: str) -> None:
        await asyncio.sleep(max(self._min_ms, len(text) * self._ms_per_char) / 1000)
