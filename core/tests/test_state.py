import pytest

from donna_core.agent.state import TRANSITIONS, InvalidTransition, StateMachine, can_transition
from donna_core.bus import EventBus
from donna_core.protocol.messages import AssistantState as S
from tests.conftest import Recorder


@pytest.mark.parametrize(
    ("current", "target"),
    [(c, t) for c, targets in TRANSITIONS.items() for t in targets]
    + [(c, S.IDLE) for c in S if c != S.IDLE]
    + [(c, S.ERROR) for c in S if c != S.ERROR],
)
async def test_valid_transitions(current: S, target: S) -> None:
    machine = StateMachine(EventBus(), initial=current)
    await machine.transition(target)
    assert machine.state == target


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (S.IDLE, S.SPEAKING),
        (S.IDLE, S.EXECUTING),
        (S.LISTENING, S.EXECUTING),
        (S.SPEAKING, S.THINKING),
        (S.ERROR, S.THINKING),
        (S.ERROR, S.SPEAKING),
    ],
)
async def test_invalid_transitions(current: S, target: S) -> None:
    machine = StateMachine(EventBus(), initial=current)
    assert not can_transition(current, target)
    with pytest.raises(InvalidTransition):
        await machine.transition(target)
    assert machine.state == current


async def test_transition_publishes_event(bus: EventBus, recorder: Recorder) -> None:
    machine = StateMachine(bus)
    await machine.transition(S.THINKING, turn="t_1")
    [event] = recorder.events
    assert event.type == "assistant.state"
    assert event.turn == "t_1"
    assert event.payload.model_dump() == {"state": S.THINKING, "previous": S.IDLE}


async def test_same_state_is_a_silent_noop(bus: EventBus, recorder: Recorder) -> None:
    machine = StateMachine(bus)
    await machine.transition(S.IDLE)
    assert recorder.events == []
