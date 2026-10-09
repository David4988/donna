import httpx
import pytest

import llm


def fake_post(monkeypatch, response=None, error=None):
    """Replace httpx.post. Returns a dict that records what was sent."""
    sent = {}

    def post(url, json, timeout):
        sent.update(url=url, body=json)
        if error:
            raise error
        return httpx.Response(200, json=response, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    return sent


def test_sends_model_messages_and_tools(monkeypatch):
    sent = fake_post(monkeypatch, {"choices": [{"message": {"role": "assistant", "content": "Hi"}}]})
    tools = [{"type": "function", "function": {"name": "open_app"}}]
    reply = llm.ollama_ask([{"role": "user", "content": "hello"}], tools)
    assert reply == {"role": "assistant", "content": "Hi"}
    assert sent["url"] == llm.URL
    assert sent["body"]["model"] == llm.MODEL
    assert sent["body"]["stream"] is False
    assert sent["body"]["tools"] == tools


def test_tool_call_reply_is_passed_through(monkeypatch):
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "function": {"name": "open_app", "arguments": '{"app": "vscode"}'}}
        ],
    }
    fake_post(monkeypatch, {"choices": [{"message": message}]})
    assert llm.ollama_ask([{"role": "user", "content": "open vs code"}], []) == message


def test_ollama_not_running(monkeypatch):
    fake_post(monkeypatch, error=httpx.ConnectError("refused"))
    with pytest.raises(llm.LLMError, match="Is Ollama running"):
        llm.ollama_ask([{"role": "user", "content": "hello"}], [])


def test_unexpected_response(monkeypatch):
    fake_post(monkeypatch, {"something": "else"})
    with pytest.raises(llm.LLMError):
        llm.ollama_ask([{"role": "user", "content": "hello"}], [])


def test_thinking_is_off_by_default(monkeypatch):
    monkeypatch.delenv("DONNA_THINK", raising=False)
    sent = fake_post(monkeypatch, {"choices": [{"message": {"role": "assistant", "content": "Hi"}}]})
    llm.ollama_ask([{"role": "user", "content": "hello"}], [])
    assert sent["body"]["reasoning_effort"] == "none"


def test_thinking_can_be_turned_on(monkeypatch):
    monkeypatch.setenv("DONNA_THINK", "1")
    sent = fake_post(monkeypatch, {"choices": [{"message": {"role": "assistant", "content": "Hi"}}]})
    llm.ollama_ask([{"role": "user", "content": "hello"}], [])
    assert "reasoning_effort" not in sent["body"]


def test_ask_uses_fake_brain_when_asked(monkeypatch):
    monkeypatch.setenv("DONNA_LLM", "fake")
    assert llm.ask([{"role": "user", "content": "hi"}], [])["content"] == "Hello."
