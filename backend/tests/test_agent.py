import agent
import llm
import tools


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


def tool_call(name, arguments, call_id="c1"):
    return {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": call_id, "function": {"name": name, "arguments": arguments}}],
    }


def test_tool_call_then_reply(monkeypatch):
    calls = fake_model(
        monkeypatch,
        [
            tool_call("open_app", '{"app": "vscode"}'),
            {"role": "assistant", "content": "VS Code is open."},
        ],
    )
    monkeypatch.setitem(tools.FUNCTIONS, "open_app", lambda app: f"Opened {app}.")

    history = []
    assert run("Open VS Code", history) == [
        {"type": "tool_call", "name": "open_app", "args": {"app": "vscode"}},
        {"type": "tool_result", "name": "open_app", "result": "Opened vscode."},
        {"type": "assistant_message", "text": "VS Code is open."},
    ]
    # The second LLM call saw the tool result, linked to the request by id.
    assert calls[1][-1] == {"role": "tool", "tool_call_id": "c1", "content": "Opened vscode."}
    assert [m["role"] for m in history] == ["user", "assistant", "tool", "assistant"]


def test_unknown_tool_error_goes_back_to_the_llm(monkeypatch):
    calls = fake_model(
        monkeypatch,
        [tool_call("delete_everything", "{}"), {"role": "assistant", "content": "I can't do that."}],
    )
    sent = run("delete my files")
    assert sent[1]["result"] == "Error: there is no tool called 'delete_everything'."
    assert sent[-1] == {"type": "assistant_message", "text": "I can't do that."}
    assert calls[1][-1]["content"].startswith("Error:")


def test_invalid_json_arguments(monkeypatch):
    fake_model(
        monkeypatch,
        [tool_call("open_app", "{not json"), {"role": "assistant", "content": "Oops."}],
    )
    sent = run("open something")
    assert sent[0] == {"type": "tool_call", "name": "open_app", "args": {}}
    assert sent[1]["result"].startswith("Error:")


def test_stops_after_max_tool_rounds(monkeypatch):
    fake_model(monkeypatch, [tool_call("no_such_tool", "{}")] * agent.MAX_TOOL_ROUNDS)
    sent = run("loop forever")
    assert sum(m["type"] == "tool_call" for m in sent) == agent.MAX_TOOL_ROUNDS
    assert sent[-1] == {"type": "assistant_message", "text": "Sorry, I got stuck trying to do that."}


def test_fake_brain_opens_apps():
    reply = llm.fake_ask([{"role": "user", "content": "Open VS Code"}], tools=[])
    assert reply["tool_calls"][0]["function"] == {"name": "open_app", "arguments": '{"app": "VS Code"}'}


def test_fake_brain_sums_up_tool_results():
    result = {"role": "tool", "tool_call_id": "c1", "content": "Found 2 file(s):\na.pdf\nb.pdf"}
    assert llm.fake_ask([result], tools=[])["content"] == "Found 2 file(s)"
