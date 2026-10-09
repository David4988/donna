"""The only file that talks to the language model.

ask(messages, tools) returns the model's reply in the OpenAI chat format:

    {"role": "assistant", "content": "Hello."}             a normal answer
    {"role": "assistant", "content": None,
     "tool_calls": [{"id": ..., "function": {"name": ..., "arguments": "{...}"}}]}
                                                            the model wants a tool

If on_delta is given it is called with each piece of the answer as the model
produces it: on_delta("Hel"), on_delta("lo"), on_delta("."). The returned reply
still holds the whole text, so a caller that ignores the pieces behaves exactly
as it did before streaming existed.

Which brain answers is chosen with the DONNA_LLM environment variable:
    DONNA_LLM=ollama  (default) the real model, running locally in Ollama
    DONNA_LLM=fake    a few keyword rules, so DONNA works without any model
"""

import json
import os
import re

import httpx

# The model and where it runs. Ollama, llama.cpp's llama-server and LM Studio all
# speak this same OpenAI-style API, so switching is just a different URL/model.
# Check the exact model tag on your PC with `ollama list`.
MODEL = os.environ.get("DONNA_MODEL", "qwen3.5:9b")
URL = os.environ.get("DONNA_LLM_URL", "http://127.0.0.1:11434/v1/chat/completions")
# The longest DONNA waits for the NEXT token, not for the whole reply: a big model
# on a modest GPU can be slow on the first call while it loads.
TIMEOUT_SECONDS = 180


class LLMError(Exception):
    """The model couldn't be reached, or sent back something we can't use."""


def ask(messages, tools, *, on_delta=None):
    if os.environ.get("DONNA_LLM", "ollama") == "fake":
        return fake_ask(messages, tools, on_delta=on_delta)
    return ollama_ask(messages, tools, on_delta=on_delta)


def thinking_enabled():
    """Qwen reasons before answering, which roughly triples the tokens a short
    reply costs (measured on an RX 580: 15.2s vs 4.9s for the same answer).
    DONNA's replies are meant to be short, so thinking is off unless you ask:
    set DONNA_THINK=1 for harder, multi-step requests.
    """
    return os.environ.get("DONNA_THINK", "").strip().lower() in ("1", "true", "yes", "on")


def ollama_ask(messages, tools, *, on_delta=None):
    body = {"model": MODEL, "messages": messages, "stream": True}
    if tools:
        body["tools"] = tools
    if not thinking_enabled():
        # This endpoint spells it "reasoning_effort". Ollama's native
        # {"think": false} is silently ignored here, so don't use it.
        body["reasoning_effort"] = "none"

    try:
        with httpx.stream("POST", URL, json=body, timeout=TIMEOUT_SECONDS) as response:
            # A streamed response has no body loaded yet, and reading .text before
            # it does raises a RuntimeError that no `except` below would catch. An
            # error reply is small, so pull it in before raise_for_status needs it.
            if response.status_code != 200:
                response.read()
            response.raise_for_status()
            return read_stream(response.iter_lines(), on_delta)
    except httpx.ConnectError:
        raise LLMError(
            f"Can't reach the model at {URL}. Is Ollama running? "
            "(To try DONNA without a model, start the server with DONNA_LLM=fake.)"
        ) from None
    except httpx.TimeoutException:
        raise LLMError("The model took too long to answer.") from None
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        raise LLMError(f"The model server said {status}: {error.response.text[:200]}") from None
    except (KeyError, IndexError, ValueError):
        raise LLMError("The model sent back something DONNA couldn't read.") from None


def read_stream(lines, on_delta):
    """Turn the model's stream of chunks into one reply.

    Each event is a line `data: {...}`, events are separated by blank lines, and
    the stream ends with `data: [DONE]`. A chunk is the normal reply with
    "message" replaced by "delta":

        {"choices": [{"delta": {"content": "Hel"}}]}
        {"choices": [{"delta": {"tool_calls": [{...}]}}]}
        {"choices": [{"delta": {}, "finish_reason": "stop"}]}

    Only "content" and "tool_calls" are read. With DONNA_THINK=1 the model also
    sends its private reasoning in these chunks; ignoring every other key is
    what keeps that thinking out of DONNA's answer.
    """
    content = []
    fragments = []
    read_a_chunk = False

    try:
        for line in lines:
            if not line.startswith("data:"):
                continue  # the blank line between events
            payload = line[len("data:") :].strip()
            if payload == "[DONE]":
                break
            try:
                delta = json.loads(payload)["choices"][0].get("delta") or {}
            except (KeyError, IndexError, ValueError):
                continue  # one chunk we can't read shouldn't cost us the reply
            read_a_chunk = True

            piece = delta.get("content") or ""
            if piece:
                content.append(piece)
                if on_delta:
                    on_delta(piece)
            fragments.extend(delta.get("tool_calls") or [])
    except httpx.RequestError:
        # The pieces already sent stay sent: we can't un-say them.
        raise LLMError("The model stopped partway through its reply.") from None

    if not read_a_chunk:
        raise LLMError("The model sent back something DONNA couldn't read.")

    reply = {"role": "assistant", "content": "".join(content) or None}
    calls = join_tool_calls(fragments)
    if calls:
        reply["tool_calls"] = calls
    return reply


def join_tool_calls(fragments):
    """Rebuild whole tool calls from the pieces a stream sends.

    Ollama sends each call complete in one fragment. Other OpenAI-compatible
    servers (llama.cpp, LM Studio) split ONE call across fragments sharing an
    `index`, with the arguments arriving a few characters at a time:

        {"index": 0, "id": "c1", "function": {"name": "open_app", "arguments": ""}}
        {"index": 0, "function": {"arguments": "{\"app\":"}}
        {"index": 0, "function": {"arguments": " \"vscode\"}"}}

    Both shapes work here: a fragment bringing a name the slot already has
    starts a new call, anything else extends the call it belongs to. That also
    keeps two calls apart when a server leaves `index` off the wire entirely.
    """
    calls = []
    slots = {}  # index -> the call that index is currently filling

    for fragment in fragments:
        index = fragment.get("index", 0)
        function = fragment.get("function") or {}
        name = function.get("name") or ""
        call = slots.get(index)

        if call is None or (name and call["function"]["name"]):
            call = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
            calls.append(call)
            slots[index] = call

        call["id"] = call["id"] or fragment.get("id") or ""
        call["function"]["name"] = call["function"]["name"] or name
        call["function"]["arguments"] += function.get("arguments") or ""

    return calls


# ---------------------------------------------------------------- fake brain


def fake_ask(messages, tools, *, on_delta=None):
    """Pretend to be a model using keyword rules. Same reply shape as the real one."""
    reply = fake_reply(messages)
    # No real tokens to drip-feed, but still stream: that way DONNA_LLM=fake
    # exercises the same path the real model uses.
    if on_delta and reply.get("content"):
        on_delta(reply["content"])
    return reply


def fake_reply(messages):
    last = messages[-1]

    # A tool just ran: sum up its result in one line (the UI already shows the details).
    if last["role"] == "tool":
        summary = last["content"].splitlines()[0].rstrip(":")
        if summary.startswith("Error: "):
            summary = "Sorry, " + summary.removeprefix("Error: ")
        return {"role": "assistant", "content": summary}

    text = last["content"].strip().rstrip(".!?")
    words = re.findall(r"[a-z0-9]+", text.lower())

    if words and words[0] in ("hello", "hi", "hey"):
        return {"role": "assistant", "content": "Hello."}
    for start in ("search the web for ", "search for ", "look up ", "google "):
        if text.lower().startswith(start):
            return _tool_call("web_search", query=text[len(start) :])
    if words and words[0] in ("open", "launch", "start"):
        return _tool_call("open_app", app=text.split(maxsplit=1)[1] if len(words) > 1 else "")
    if words and words[0] in ("find", "locate"):
        return _tool_call("find_files", query=" ".join(text.split()[1:]))

    return {
        "role": "assistant",
        "content": "I'm DONNA's offline brain, so I only understand a few things, "
        "like 'hello', 'open <app>', 'find <files>' and 'search the web for <topic>'.",
    }


def _tool_call(name, **args):
    """A reply asking for a tool, in the same format a real model uses."""
    call = {
        "id": f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }
    return {"role": "assistant", "content": None, "tool_calls": [call]}
