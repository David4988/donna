from __future__ import annotations

import pytest

from donna_core.bus import Event, EventBus


class Recorder:
    """Collects every event published on a bus."""

    def __init__(self, bus: EventBus) -> None:
        self.events: list[Event] = []
        bus.subscribe(self._on)

    async def _on(self, event: Event) -> None:
        self.events.append(event)

    @property
    def types(self) -> list[str]:
        return [e.type for e in self.events]

    def of(self, type_: str) -> list[Event]:
        return [e for e in self.events if e.type == type_]

    def states(self) -> list[str]:
        return [str(e.payload.state) for e in self.of("assistant.state")]  # type: ignore[attr-defined]


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
def recorder(bus: EventBus) -> Recorder:
    return Recorder(bus)
