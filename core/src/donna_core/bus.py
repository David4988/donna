"""A deliberately tiny in-process event bus.

The core publishes ``Event`` objects; the WebSocket gateway is just one
subscriber. Nothing in the agent knows about sockets or JSON.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class Event:
    """An internal event. ``type`` uses the same names as outbound protocol messages."""

    type: str
    payload: BaseModel
    turn: str | None = None


Handler = Callable[[Event], Awaitable[None]]


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[Handler] = []

    def subscribe(self, handler: Handler) -> Callable[[], None]:
        """Register a handler. Returns a function that unsubscribes it."""
        self._handlers.append(handler)

        def unsubscribe() -> None:
            if handler in self._handlers:
                self._handlers.remove(handler)

        return unsubscribe

    async def publish(self, event: Event) -> None:
        # Handlers run in subscription order. One failing handler must not stop
        # the others (or the agent that published the event).
        for handler in list(self._handlers):
            try:
                await handler(event)
            except Exception:
                log.exception("event handler failed for %s", event.type)
