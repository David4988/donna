"""Assistant state machine.

The state machine knows nothing about microphones or speakers: LISTENING and
SPEAKING are just states that adapters (or the agent) move into and out of.
"""

from __future__ import annotations

from donna_core.bus import Event, EventBus
from donna_core.protocol.messages import AssistantState, AssistantStatePayload

S = AssistantState

# Allowed transitions. Every state may go to ERROR, and to IDLE (cancellation).
TRANSITIONS: dict[AssistantState, frozenset[AssistantState]] = {
    S.IDLE: frozenset({S.LISTENING, S.THINKING}),
    S.LISTENING: frozenset({S.THINKING}),
    S.THINKING: frozenset({S.EXECUTING, S.SPEAKING}),
    S.EXECUTING: frozenset({S.THINKING, S.SPEAKING}),
    S.SPEAKING: frozenset({S.LISTENING}),
    S.ERROR: frozenset(),
}


def can_transition(current: AssistantState, target: AssistantState) -> bool:
    if target in (S.IDLE, S.ERROR):
        return current != target
    return target in TRANSITIONS[current]


class InvalidTransition(Exception):
    def __init__(self, current: AssistantState, target: AssistantState) -> None:
        super().__init__(f"invalid state transition {current} -> {target}")
        self.current = current
        self.target = target


class StateMachine:
    def __init__(self, bus: EventBus, initial: AssistantState = S.IDLE) -> None:
        self._bus = bus
        self._state = initial

    @property
    def state(self) -> AssistantState:
        return self._state

    async def transition(self, target: AssistantState, turn: str | None = None) -> None:
        """Move to ``target`` and publish ``assistant.state``.

        Re-entering the current state is a no-op. Anything not allowed by
        TRANSITIONS raises InvalidTransition and leaves the state unchanged.
        """
        if target == self._state:
            return
        if not can_transition(self._state, target):
            raise InvalidTransition(self._state, target)
        previous, self._state = self._state, target
        await self._bus.publish(
            Event(
                "assistant.state",
                AssistantStatePayload(state=target, previous=previous),
                turn,
            )
        )
