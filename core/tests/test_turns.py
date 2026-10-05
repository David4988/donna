import asyncio

from donna_core.agent.state import StateMachine
from donna_core.agent.turns import TurnContext, TurnManager, TurnStatus
from donna_core.bus import EventBus
from donna_core.protocol.messages import AssistantState as S
from donna_core.protocol.messages import Route
from tests.conftest import Recorder


def manager(bus: EventBus, runner):  # type: ignore[no-untyped-def]
    state = StateMachine(bus)
    return TurnManager(runner, bus, state), state


async def test_start_and_complete(bus: EventBus, recorder: Recorder) -> None:
    async def runner(ctx: TurnContext) -> Route:
        return "llm"

    turns, state = manager(bus, runner)
    turn = await turns.start("hello")
    await turns.wait()
    assert turn.status is TurnStatus.COMPLETED
    assert recorder.types == ["turn.started", "turn.completed"]
    assert all(e.turn == turn.id for e in recorder.events)
    assert state.state is S.IDLE


async def test_cancel_propagates_into_the_runner(bus: EventBus, recorder: Recorder) -> None:
    started = asyncio.Event()
    saw_cancel = asyncio.Event()

    async def runner(ctx: TurnContext) -> Route:
        started.set()
        try:
            await asyncio.sleep(60)  # stands in for an LLM call / speech
        except asyncio.CancelledError:
            saw_cancel.set()
            raise
        return "llm"

    turns, state = manager(bus, runner)
    turn = await turns.start("long task")
    await started.wait()
    assert await turns.cancel("user pressed stop")
    assert saw_cancel.is_set()
    assert turn.status is TurnStatus.CANCELLED
    [cancelled] = recorder.of("turn.cancelled")
    assert cancelled.payload.reason == "user pressed stop"  # type: ignore[attr-defined]
    assert state.state is S.IDLE


async def test_cancel_with_nothing_running(bus: EventBus) -> None:
    async def runner(ctx: TurnContext) -> Route:
        return "llm"

    turns, _ = manager(bus, runner)
    assert not await turns.cancel()


async def test_new_turn_cancels_the_current_one(bus: EventBus, recorder: Recorder) -> None:
    started = asyncio.Event()

    async def runner(ctx: TurnContext) -> Route:
        if ctx.input == "first":
            started.set()
            await asyncio.sleep(60)
        return "llm"

    turns, _ = manager(bus, runner)
    first = await turns.start("first")
    await started.wait()
    second = await turns.start("second")
    await turns.wait()
    assert first.status is TurnStatus.CANCELLED
    assert second.status is TurnStatus.COMPLETED
    # The old turn is fully wound down before the new one starts.
    assert recorder.types == ["turn.started", "turn.cancelled", "turn.started", "turn.completed"]
    assert [e.turn for e in recorder.events] == [first.id, first.id, second.id, second.id]


async def test_failure(bus: EventBus, recorder: Recorder) -> None:
    async def runner(ctx: TurnContext) -> Route:
        await asyncio.sleep(0)
        raise RuntimeError("boom")

    turns, state = manager(bus, runner)
    turn = await turns.start("explode")
    await turns.wait()
    assert turn.status is TurnStatus.FAILED
    [failed] = recorder.of("turn.failed")
    assert failed.payload.message == "boom"  # type: ignore[attr-defined]
    assert recorder.states() == ["ERROR", "IDLE"]
    assert state.state is S.IDLE


async def test_turn_ids_are_unique(bus: EventBus) -> None:
    async def runner(ctx: TurnContext) -> Route:
        return "llm"

    turns, _ = manager(bus, runner)
    ids = []
    for text in ("a", "b", "c"):
        ids.append((await turns.start(text)).id)
        await turns.wait()
    assert len(set(ids)) == 3
