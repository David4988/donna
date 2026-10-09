import agent
import llm


def fake_model(monkeypatch, replies):
    """Replace llm.ask with a scripted fake. Returns the list of calls it received."""
    calls = []
    replies = list(replies)

    def ask(messages, tools):
        calls.append(messages)
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply

    monkeypatch.setattr(llm, "ask", ask)
    return calls


def run(text, history=None):
    sent = []
    agent.handle(text, history if history is not None else [], sent.append)
    return sent


def test_plain_reply(monkeypatch):
    calls = fake_model(monkeypatch, [{"role": "assistant", "content": "Hello."}])
    history = []
    assert run("Hello Donna", history) == [{"type": "assistant_message", "text": "Hello."}]
    assert calls[0][0]["role"] == "system"
    assert [m["role"] for m in history] == ["user", "assistant"]


def test_model_unreachable_gives_error(monkeypatch):
    fake_model(monkeypatch, [llm.LLMError("Can't reach the model.")])
    assert run("Hello") == [{"type": "error", "text": "Can't reach the model."}]


def test_fake_brain_says_hello():
    reply = llm.fake_ask([{"role": "user", "content": "Hello Donna!"}], tools=[])
    assert reply["content"] == "Hello."
