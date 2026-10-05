"""The agent: one turn = route the input, run tools, reply.

    input -> fast path? --yes--> tool -> reply
                 |no
                 v
            LLM <-> tools (at most MAX_STEPS rounds) -> reply

The agent talks to the outside world only through injected parts (LLM, tool
router, speaker, state machine) and TurnContext.emit. It has no idea whether
a CLI, the Tauri UI, or a test is listening.
"""

from __future__ import annotations

import json

from donna_core.agent.fastpath import FastPath
from donna_core.agent.speaker import Speaker
from donna_core.agent.state import StateMachine
from donna_core.agent.turns import TurnContext
from donna_core.llm.base import LLM, Message, ToolCall
from donna_core.protocol.messages import (
    AssistantState,
    AssistantTextPayload,
    Route,
    ToolErrorPayload,
    ToolRequestPayload,
    ToolResultPayload,
)
from donna_core.tools.router import ToolFailure, ToolOutcome, ToolRouter, ToolSuccess

S = AssistantState

SYSTEM_PROMPT = (
    "You are DONNA, a concise desktop assistant. Reply in one or two short spoken "
    "sentences, no markdown. Use tools to act. Refer to files and pages only by "
    "their result id (like r_1); never invent paths."
)

GIVE_UP = "Sorry, I couldn't finish that."


def tool_message_content(outcome: ToolOutcome) -> str:
    """What the model sees about a tool run: summary + result ids/titles. No paths."""
    if isinstance(outcome, ToolFailure):
        return json.dumps({"ok": False, "error": outcome.code, "message": outcome.message})
    return json.dumps(
        {
            "ok": True,
            "summary": outcome.output.summary,
            "results": [
                {"id": r.id, "kind": r.kind, "title": r.title} for r in outcome.output.results
            ],
        }
    )


class Agent:
    MAX_STEPS = 4

    def __init__(
        self,
        llm: LLM,
        router: ToolRouter,
        fast_path: FastPath,
        speaker: Speaker,
        state: StateMachine,
        history_limit: int = 12,
    ) -> None:
        self._llm = llm
        self._router = router
        self._fast_path = fast_path
        self._speaker = speaker
        self._state = state
        self._history_limit = history_limit
        self.history: list[Message] = []

    async def run(self, ctx: TurnContext) -> Route:
        await self._state.transition(S.THINKING, ctx.turn_id)

        call = self._fast_path.match(ctx.input)
        if call is not None:
            outcome = await self._execute(ctx, call)
            reply = outcome.output.summary if isinstance(outcome, ToolSuccess) else outcome.message
            await self._speak(ctx, reply)
            self._remember([Message("user", ctx.input), Message("assistant", reply)])
            return "fast_path"

        turn_messages = [Message("user", ctx.input)]
        for _ in range(self.MAX_STEPS):
            response = await self._llm.complete(
                [Message("system", SYSTEM_PROMPT), *self.history, *turn_messages],
                self._router.specs(),
            )
            if not response.tool_calls:
                reply = response.text or GIVE_UP
                break
            turn_messages.append(Message("assistant", tool_calls=response.tool_calls))
            for tool_call in response.tool_calls:
                outcome = await self._execute(ctx, tool_call)
                turn_messages.append(
                    Message(
                        "tool",
                        tool_message_content(outcome),
                        tool_call_id=tool_call.id,
                        name=tool_call.name,
                    )
                )
            await self._state.transition(S.THINKING, ctx.turn_id)
        else:
            reply = GIVE_UP

        await self._speak(ctx, reply)
        # History is only committed when a turn finishes, so a cancelled turn
        # leaves no half-finished tool exchange behind.
        self._remember([*turn_messages, Message("assistant", reply)])
        return "llm"

    async def _execute(self, ctx: TurnContext, call: ToolCall) -> ToolOutcome:
        await self._state.transition(S.EXECUTING, ctx.turn_id)
        await ctx.emit(
            "tool.request",
            ToolRequestPayload(
                call_id=call.id,
                tool=call.name,
                args=call.arguments,
                label=self._router.label_for(call.name),
            ),
        )
        outcome = await self._router.execute(call.name, call.arguments)
        if isinstance(outcome, ToolSuccess):
            await ctx.emit(
                "tool.result",
                ToolResultPayload(
                    call_id=call.id,
                    tool=call.name,
                    summary=outcome.output.summary,
                    results=outcome.output.results,
                ),
            )
        else:
            await ctx.emit(
                "tool.error",
                ToolErrorPayload(
                    call_id=call.id, tool=call.name, code=outcome.code, message=outcome.message
                ),
            )
        return outcome

    async def _speak(self, ctx: TurnContext, text: str) -> None:
        await self._state.transition(S.SPEAKING, ctx.turn_id)
        await ctx.emit("assistant.text", AssistantTextPayload(text=text))
        await self._speaker.say(text)

    def _remember(self, messages: list[Message]) -> None:
        history = [*self.history, *messages][-self._history_limit :]
        # Never start history mid-exchange (with a tool or tool-call message).
        while history and history[0].role != "user":
            history.pop(0)
        self.history = history
