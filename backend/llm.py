"""The only file that talks to the language model.

ask(messages, tools) returns the model's reply in the OpenAI chat format:

    {"role": "assistant", "content": "Hello."}             a normal answer
    {"role": "assistant", "content": None,
     "tool_calls": [{"id": ..., "function": {"name": ..., "arguments": "{...}"}}]}
                                                            the model wants a tool

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
MODEL = os.environ.get("DONNA_MODEL", "qwen3.6:35b-a3b")
URL = os.environ.get("DONNA_LLM_URL", "http://127.0.0.1:11434/v1/chat/completions")
TIMEOUT_SECONDS = 180  # a big model on a modest GPU can be slow on the first call


class LLMError(Exception):
    """The model couldn't be reached, or sent back something we can't use."""


def ask(messages, tools):
    if os.environ.get("DONNA_LLM", "ollama") == "fake":
        return fake_ask(messages, tools)
    return ollama_ask(messages, tools)


def ollama_ask(messages, tools):
    body = {"model": MODEL, "messages": messages, "stream": False}
    if tools:
        body["tools"] = tools

    try:
        response = httpx.post(URL, json=body, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]
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


# ---------------------------------------------------------------- fake brain


def fake_ask(messages, tools):
    """Pretend to be a model using keyword rules. Same reply shape as the real one."""
    last = messages[-1]

    # A tool just ran: report its result.
    if last["role"] == "tool":
        result = last["content"]
        if result.startswith("Error: "):
            result = "Sorry, " + result.removeprefix("Error: ")
        return {"role": "assistant", "content": result}

    text = last["content"].strip().rstrip(".!?")
    words = re.findall(r"[a-z0-9]+", text.lower())

    if words and words[0] in ("hello", "hi", "hey"):
        return {"role": "assistant", "content": "Hello."}
    if words and words[0] in ("open", "launch", "start"):
        return _tool_call("open_app", app=text.split(maxsplit=1)[1] if len(words) > 1 else "")

    return {
        "role": "assistant",
        "content": "I'm DONNA's offline brain, so I only understand a few things, "
        "like 'hello' and 'open <app>'.",
    }


def _tool_call(name, **args):
    """A reply asking for a tool, in the same format a real model uses."""
    call = {
        "id": f"call_{name}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }
    return {"role": "assistant", "content": None, "tool_calls": [call]}
