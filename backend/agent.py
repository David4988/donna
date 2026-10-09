"""The agent decides what happens with each user message.

    user message -> ask the LLM -> reply

(Tools arrive in Step 5: then the LLM may ask for a tool before replying.)
"""

import llm

SYSTEM_PROMPT = (
    "You are DONNA, a helpful desktop assistant running on the user's own computer. "
    "Keep replies short: one to three sentences."
)


def handle(text, history, send):
    """Handle one user message. `send` delivers a message dict to the UI."""
    history.append({"role": "user", "content": text})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]

    try:
        reply = llm.ask(messages, tools=[])
    except llm.LLMError as error:
        send({"type": "error", "text": str(error)})
        return

    history.append(reply)
    send({"type": "assistant_message", "text": reply.get("content") or "(no reply)"})
