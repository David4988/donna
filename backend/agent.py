"""The agent decides what happens with each user message.

    user message -> ask the LLM
                      |-- LLM answers with text      -> send it to the UI, done
                      '-- LLM asks for a tool        -> run it, add the result,
                                                        ask the LLM again

That loop is the whole agent.
"""

import json

import llm
import tools

SYSTEM_PROMPT = (
    "You are DONNA, a helpful desktop assistant running on the user's own computer. "
    "Keep replies short: one to three sentences.\n"
    "Only use a tool when the user actually asks you to do something. Greetings, "
    "small talk, thanks and questions you can answer yourself get a plain reply and "
    "NO tool call. If you cannot tell what the user wants -- the microphone may have "
    "misheard them -- say so and ask. Never guess at a tool.\n"
    "Your reply is read out loud, so write it to be heard rather than read. Talk the "
    "way a person talks: contractions, the answer first, active voice. No lists, no "
    "bullet points and no markdown. Don't read out file paths or web addresses, and "
    "don't quote file names -- just say what the thing is called. Say units as words, "
    "like 'fourteen degrees' rather than '14C'."
)
# Neither added paragraph is decoration, and both were measured.
#
# The second: on qwen3.5:4b the old one-line prompt scored 30/40 on "should
# this be a tool call?" and this one scores 39/40, without losing a single real
# tool call. Adding a worked example made it WORSE (46/60) -- naming a tool in
# the prompt primes the model to reach for one. Don't add examples here.
#
# The third buys less than it looks like it should, because the model already
# wrote fairly spoken prose: 11/12 of its tool-result summaries were clean
# before it existed. It exists for the rest -- passive "Notepad has been
# opened", "both located in different OneDrive folders" -- and because telling
# it to say "degrees" costs nothing on top of speech_text.say_numbers(), which
# is what actually guarantees it. See PLAN.md 6a.

MAX_TOOL_ROUNDS = 5  # so a confused model can't loop forever


def handle(text, history, send):
    """Handle one user message. `send` delivers a message dict to the UI."""
    history.append({"role": "user", "content": text})

    def on_delta(piece):
        # The answer as it is typed. The assistant_message at the end still
        # carries the whole thing, so this is extra, never a replacement.
        send({"type": "assistant_delta", "text": piece})

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            reply = llm.ask(
                [{"role": "system", "content": SYSTEM_PROMPT}, *history],
                tools.TOOLS,
                on_delta=on_delta,
            )
        except llm.LLMError as error:
            send({"type": "error", "text": str(error)})
            return

        history.append(reply)
        tool_calls = reply.get("tool_calls") or []
        if not tool_calls:
            send({"type": "assistant_message", "text": reply.get("content") or "(no reply)"})
            return

        for call in tool_calls:
            run_tool_call(call, history, send)

    send({"type": "assistant_message", "text": "Sorry, I got stuck trying to do that."})


def run_tool_call(call, history, send):
    function = call.get("function", {})
    name = function.get("name", "?")
    args = parse_arguments(function.get("arguments"))

    send({"type": "tool_call", "name": name, "args": args if isinstance(args, dict) else {}})
    result = tools.run_tool(name, args)
    send({"type": "tool_result", "name": name, "result": result})

    # The LLM sees the result on its next turn, matched to its request by id.
    history.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": result})


def parse_arguments(raw):
    """Models send tool arguments as a JSON string (some send a dict). None if invalid."""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw or "{}")
    except (TypeError, ValueError):
        return None
