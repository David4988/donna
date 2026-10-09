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

import os
import re


class LLMError(Exception):
    """The model couldn't be reached, or sent back something we can't use."""


def ask(messages, tools):
    if os.environ.get("DONNA_LLM", "ollama") == "fake":
        return fake_ask(messages, tools)
    return ollama_ask(messages, tools)


def ollama_ask(messages, tools):
    raise LLMError("The real model is connected in Step 4. For now, set DONNA_LLM=fake.")


# ---------------------------------------------------------------- fake brain


def fake_ask(messages, tools):
    """Pretend to be a model using keyword rules. Same reply shape as the real one."""
    words = re.findall(r"[a-z0-9]+", messages[-1]["content"].lower())

    if words and words[0] in ("hello", "hi", "hey"):
        return {"role": "assistant", "content": "Hello."}

    return {
        "role": "assistant",
        "content": "I'm DONNA's offline brain, so I only understand a few things, like 'hello'.",
    }
