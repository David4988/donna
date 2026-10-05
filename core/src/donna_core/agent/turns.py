"""Turn lifecycle.

A turn is one user request and everything DONNA does about it. Each turn runs
in its own asyncio.Task, so cancelling the task cancels whatever it is awaiting
(LLM call, tool, speech) at that moment.

Only one turn runs at a time: starting a new turn cancels the current one and
waits for it to finish cleaning up first, so events never interleave.
"""

from __future__ import annotations

import asyncio
import itertools
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel

from donna_core.agent.state import StateMachine
from donna_core.bus import Event, EventBus
from donna_core.protocol.messages import (
    AssistantState,
    Route,
    TurnCancelledPayload,
    TurnCompletedPayload,
    TurnFailedPayload,
    TurnStartedPayload,
)

log = logging.getLogger(__name__)


class TurnStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(slots=True)
class TurnContext:
    """What the turn's runner gets: its id, its input and a way to emit events."""

    turn_id: str
    input: str
    bus: EventBus

    async def emit(self, type_: str, payload: BaseModel) -> None:
        await self.bus.publish(Event(type_, payload, self.turn_id))


@dataclass(slots=True)
class Turn:
    id: str
    input: str
    status: TurnStatus = TurnStatus.RUNNING
    task: asyncio.Task[None] | None = field(default=None, repr=False)
    cancel_reason: str = "cancelled"

    @property
    def done(self) -> bool:
        return self.task is None or self.task.done()


# The runner (normally Agent.run) returns the route the turn took.
Runner = Callable[[TurnContext], Awaitable[Route]]


class TurnManager:
    def __init__(self, runner: Runner, bus: EventBus, state: StateMachine) -> None:
        self._runner = runner
        self._bus = bus
        self._state = state
        self._ids = itertools.count(1)
        self._lock = asyncio.Lock()
        self.current: Turn | None = None

    async def start(self, text: str) -> Turn:
        """Cancel the running turn (if any), then start a new one for ``text``."""
        async with self._lock:
            await self._cancel_current("superseded")
            turn = Turn(id=f"t_{next(self._ids)}", input=text)
            ctx = TurnContext(turn.id, text, self._bus)
            await ctx.emit("turn.started", TurnStartedPayload(input=text))
            turn.task = asyncio.create_task(self._run(turn, ctx), name=f"turn-{turn.id}")
            self.current = turn
            return turn

    async def cancel(self, reason: str = "cancelled") -> bool:
        """Cancel the running turn. Returns False if nothing was running."""
        async with self._lock:
            return await self._cancel_current(reason)

    async def wait(self) -> None:
        """Wait until the current turn has finished (in any way)."""
        turn = self.current
        if turn is not None and turn.task is not None:
            await asyncio.wait({turn.task})

    async def _cancel_current(self, reason: str) -> bool:
        turn = self.current
        if turn is None or turn.done or turn.task is None:
            return False
        turn.cancel_reason = reason
        turn.task.cancel()
        # asyncio.wait doesn't re-raise the task's CancelledError, but it does
        # let *our* caller be cancelled normally.
        await asyncio.wait({turn.task})
        return True

    async def _run(self, turn: Turn, ctx: TurnContext) -> None:
        try:
            route = await self._runner(ctx)
        except asyncio.CancelledError:
            turn.status = TurnStatus.CANCELLED
            await ctx.emit("turn.cancelled", TurnCancelledPayload(reason=turn.cancel_reason))
            await self._state.transition(AssistantState.IDLE, turn.id)
            raise
        except Exception as exc:
            log.exception("turn %s failed", turn.id)
            turn.status = TurnStatus.FAILED
            await ctx.emit("turn.failed", TurnFailedPayload(message=str(exc) or type(exc).__name__))
            await self._state.transition(AssistantState.ERROR, turn.id)
            await self._state.transition(AssistantState.IDLE, turn.id)
        else:
            turn.status = TurnStatus.COMPLETED
            await self._state.transition(AssistantState.IDLE, turn.id)
            await ctx.emit("turn.completed", TurnCompletedPayload(route=route))
