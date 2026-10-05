import asyncio
import json
from collections.abc import Sequence

from donna_core.agent.agent import GIVE_UP, Agent
from donna_core.app import build_core
from donna_core.llm.base import LLMResponse, Message, ToolCall, ToolSpec
from tests.conftest import Recorder


def run_core(llm=None):  # type: ignore[no-untyped-def]
    core = build_core(llm=llm)
    return core, Recorder(core.bus)


async def say(core, text: str) -> None:  # type: ignore[no-untyped-def]
    await core.submit(text)
    await core.turns.wait()


async def test_input_to_text_response() -> None:
    core, rec = run_core()
    await say(core, "hello")
    assert [e.payload.text for e in rec.of("assistant.text")] == ["Hello."]
    assert rec.states() == ["THINKING", "SPEAKING", "IDLE"]
    assert rec.of("turn.completed")[0].payload.route == "llm"


async def test_input_to_tool_request_to_response() -> None:
    core, rec = run_core()
    await say(core, "find my TrialGuard files")
    [request] = rec.of("tool.request")
    assert request.payload.tool == "find_files"
    assert request.payload.args == {"query": "TrialGuard"}
    assert request.payload.label == "Searching files..."
    [result] = rec.of("tool.result")
    assert result.payload.call_id == request.payload.call_id
    assert [r.id for r in result.payload.results] == ["r_1", "r_2", "r_3", "r_4"]
    [reply] = rec.of("assistant.text")
    assert reply.payload.text.startswith("I found 4 files")
    assert rec.states() == ["THINKING", "EXECUTING", "THINKING", "SPEAKING", "IDLE"]
    # every event of the turn carries its id
    turn_id = rec.of("turn.started")[0].turn
    assert {e.turn for e in rec.events} == {turn_id}


async def test_tool_messages_given_to_the_llm_contain_no_paths() -> None:
    seen: list[Message] = []

    class Capture:
        async def complete(
            self, messages: Sequence[Message], tools: Sequence[ToolSpec]
        ) -> LLMResponse:
            seen.extend(messages)
            if messages[-1].role == "tool":
                return LLMResponse(text="ok")
            return LLMResponse(tool_calls=(ToolCall("c1", "find_files", {"query": "TrialGuard"}),))

    core, _ = run_core(Capture())
    await say(core, "find stuff")
    tool_msgs = [m for m in seen if m.role == "tool"]
    assert tool_msgs
    data = json.loads(tool_msgs[0].content)
    assert data["results"][0] == {"id": "r_1", "kind": "file", "title": "TrialGuard_Proposal.pdf"}
    assert "C:\\" not in tool_msgs[0].content


async def test_multi_step_uses_result_ids() -> None:
    core, rec = run_core()
    await say(core, "find my TrialGuard files and open the first one")
    assert [e.payload.tool for e in rec.of("tool.request")] == ["find_files", "open_result"]
    assert rec.of("tool.request")[1].payload.args == {"result_id": "r_1"}
    assert core.backends.opener.opened[0][1] == "open"  # type: ignore[attr-defined]
    assert rec.of("assistant.text")[0].payload.text == "Opened TrialGuard_Proposal.pdf."


async def test_tool_error_is_reported_to_user() -> None:
    core, rec = run_core()
    await say(core, "open photoshop")
    [err] = rec.of("tool.error")
    assert err.payload.code == "app_not_found"
    assert "photoshop" in rec.of("assistant.text")[0].payload.text


async def test_step_limit() -> None:
    class Looping:
        async def complete(
            self, messages: Sequence[Message], tools: Sequence[ToolSpec]
        ) -> LLMResponse:
            return LLMResponse(tool_calls=(ToolCall("c", "find_files", {"query": "x"}),))

    core, rec = run_core(Looping())
    await say(core, "loop forever")
    assert len(rec.of("tool.request")) == Agent.MAX_STEPS
    assert rec.of("assistant.text")[0].payload.text == GIVE_UP


async def test_history_carries_over_between_turns() -> None:
    core, _ = run_core()
    await say(core, "hello")
    await say(core, "find my TrialGuard files")
    roles = [m.role for m in core.agent.history]
    assert roles[0] == "user"
    assert roles.count("user") == 2


async def test_cancelled_turn_leaves_no_history() -> None:
    gate = asyncio.Event()

    class Slow:
        async def complete(
            self, messages: Sequence[Message], tools: Sequence[ToolSpec]
        ) -> LLMResponse:
            gate.set()
            await asyncio.sleep(60)
            return LLMResponse(text="never")

    core, rec = run_core(Slow())
    await core.submit("think hard")
    await gate.wait()
    await core.cancel()
    assert core.agent.history == []
    assert rec.of("turn.cancelled")
    assert core.assistant_state == "IDLE"


async def test_call_ids_are_unique_within_a_turn_even_if_the_model_repeats_them() -> None:
    class Repeats:
        async def complete(
            self, messages: Sequence[Message], tools: Sequence[ToolSpec]
        ) -> LLMResponse:
            if sum(m.role == "tool" for m in messages) >= 2:
                return LLMResponse(text="done")
            return LLMResponse(tool_calls=(ToolCall("call_0", "find_files", {"query": "x"}),))

    core, rec = run_core(Repeats())
    await say(core, "go")
    ids = [e.payload.call_id for e in rec.of("tool.request")]
    assert ids == ["call_1", "call_2"]


async def test_multi_step_works_again_later_in_the_same_session() -> None:
    core, rec = run_core()
    await say(core, "find my TrialGuard files and open the first one")
    await say(core, "find my TrialGuard files and open the first one")
    tools = [e.payload.tool for e in rec.of("tool.request")]
    assert tools == ["find_files", "open_result"] * 2
    assert rec.of("tool.request")[3].payload.args == {"result_id": "r_5"}
