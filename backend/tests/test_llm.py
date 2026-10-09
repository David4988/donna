import contextlib
import json

import httpx
import pytest

import llm


def sse(chunks):
    """The wire format: one `data:` line per chunk, blank lines between, then [DONE]."""
    return "".join(f"data: {json.dumps(chunk)}\n\n" for chunk in chunks) + "data: [DONE]\n\n"


def text_chunk(piece):
    return {"choices": [{"index": 0, "delta": {"content": piece}}]}


def fake_stream(monkeypatch, chunks=None, error=None, status=200, body=None):
    """Replace httpx.stream with a canned event stream. Returns what was sent."""
    sent = {}

    @contextlib.contextmanager
    def stream(method, url, json, timeout):
        sent.update(method=method, url=url, body=json)
        if error:
            raise error
        text = body if body is not None else sse(chunks or [])
        yield httpx.Response(status, text=text, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "stream", stream)
    return sent


def sink():
    """A list of the pieces streamed, and the callback that fills it."""
    pieces = []
    return pieces, pieces.append


def test_sends_model_messages_and_tools(monkeypatch):
    sent = fake_stream(monkeypatch, [text_chunk("Hi")])
    tools = [{"type": "function", "function": {"name": "open_app"}}]
    reply = llm.ollama_ask([{"role": "user", "content": "hello"}], tools)
    assert reply == {"role": "assistant", "content": "Hi"}
    assert sent["url"] == llm.URL
    assert sent["body"]["model"] == llm.MODEL
    assert sent["body"]["stream"] is True
    assert sent["body"]["tools"] == tools


def test_content_arrives_piece_by_piece(monkeypatch):
    pieces, on_delta = sink()
    fake_stream(monkeypatch, [text_chunk("Hel"), text_chunk("lo"), text_chunk(".")])
    reply = llm.ollama_ask([{"role": "user", "content": "hi"}], [], on_delta=on_delta)
    assert pieces == ["Hel", "lo", "."]
    assert reply == {"role": "assistant", "content": "Hello."}


def test_a_caller_that_wants_no_pieces_still_gets_the_whole_reply(monkeypatch):
    fake_stream(monkeypatch, [text_chunk("Hel"), text_chunk("lo.")])
    assert llm.ollama_ask([{"role": "user", "content": "hi"}], []) == {
        "role": "assistant",
        "content": "Hello.",
    }


def test_thinking_is_never_shown_as_the_answer():
    """DONNA_THINK=1 makes the model send its reasoning too. It is not the answer."""
    pieces, on_delta = sink()
    lines = [
        'data: {"choices": [{"delta": {"reasoning": "The user said hi, so"}}]}',
        "",
        'data: {"choices": [{"delta": {"reasoning_content": "I will greet them."}}]}',
        "",
        'data: {"choices": [{"delta": {"content": "Hello."}}]}',
        "",
        "data: [DONE]",
    ]
    reply = llm.read_stream(iter(lines), on_delta)
    assert pieces == ["Hello."]
    assert reply == {"role": "assistant", "content": "Hello."}


def test_done_blank_lines_and_junk_are_skipped():
    lines = [
        "",
        "data: {broken",
        "",
        'data: {"choices": [{"delta": {"content": "Hi"}}]}',
        "",
        "data: [DONE]",
        'data: {"choices": [{"delta": {"content": "ignored"}}]}',
    ]
    assert llm.read_stream(iter(lines), None)["content"] == "Hi"


def test_a_stream_with_nothing_readable_is_an_error():
    with pytest.raises(llm.LLMError, match="couldn't read"):
        llm.read_stream(iter(["", "data: [DONE]"]), None)


def test_tool_call_reply_is_passed_through(monkeypatch):
    """Ollama sends a whole call in one fragment."""
    fragment = {
        "id": "c1",
        "index": 0,
        "type": "function",
        "function": {"name": "open_app", "arguments": '{"app": "vscode"}'},
    }
    fake_stream(monkeypatch, [{"choices": [{"delta": {"tool_calls": [fragment]}}]}])
    reply = llm.ollama_ask([{"role": "user", "content": "open vs code"}], [])
    assert reply == {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "open_app", "arguments": '{"app": "vscode"}'},
            }
        ],
    }


def test_tool_call_arguments_are_joined_across_chunks():
    """llama.cpp and LM Studio split one call over several fragments."""
    pieces, on_delta = sink()
    lines = [
        'data: {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "c1",'
        ' "function": {"name": "open_app", "arguments": ""}}]}}]}',
        'data: {"choices": [{"delta": {"tool_calls": [{"index": 0,'
        ' "function": {"arguments": "{\\"app\\":"}}]}}]}',
        'data: {"choices": [{"delta": {"tool_calls": [{"index": 0,'
        ' "function": {"arguments": " \\"vscode\\"}"}}]}}]}',
        "data: [DONE]",
    ]
    reply = llm.read_stream(iter(lines), on_delta)
    assert pieces == []  # a tool call is not visible text
    assert reply["content"] is None
    assert len(reply["tool_calls"]) == 1
    call = reply["tool_calls"][0]
    assert call["id"] == "c1"
    assert call["function"]["name"] == "open_app"
    assert json.loads(call["function"]["arguments"]) == {"app": "vscode"}


def test_two_tool_calls_with_indexes_stay_separate():
    reply = llm.read_stream(
        iter(
            [
                'data: {"choices": [{"delta": {"tool_calls": ['
                '{"index": 0, "function": {"name": "open_app", "arguments": "{}"}},'
                '{"index": 1, "function": {"name": "find_files", "arguments": "{}"}}]}}]}',
                "data: [DONE]",
            ]
        ),
        None,
    )
    assert [c["function"]["name"] for c in reply["tool_calls"]] == ["open_app", "find_files"]


def test_two_whole_tool_calls_without_an_index_stay_separate():
    """A server that leaves `index` off the wire must not have its calls merged."""
    reply = llm.read_stream(
        iter(
            [
                'data: {"choices": [{"delta": {"tool_calls": [{"function":'
                ' {"name": "open_app", "arguments": "{\\"app\\": \\"notepad\\"}"}}]}}]}',
                'data: {"choices": [{"delta": {"tool_calls": [{"function":'
                ' {"name": "find_files", "arguments": "{\\"query\\": \\"x\\"}"}}]}}]}',
                "data: [DONE]",
            ]
        ),
        None,
    )
    assert [c["function"]["name"] for c in reply["tool_calls"]] == ["open_app", "find_files"]
    assert [json.loads(c["function"]["arguments"]) for c in reply["tool_calls"]] == [
        {"app": "notepad"},
        {"query": "x"},
    ]


def test_a_stream_that_dies_mid_reply_is_an_error():
    pieces, on_delta = sink()

    def lines():
        yield 'data: {"choices": [{"delta": {"content": "Half a sen"}}]}'
        raise httpx.RemoteProtocolError("peer closed connection")

    with pytest.raises(llm.LLMError, match="stopped partway"):
        llm.read_stream(lines(), on_delta)
    assert pieces == ["Half a sen"]  # what the user already saw is not taken back


def test_ollama_not_running(monkeypatch):
    fake_stream(monkeypatch, error=httpx.ConnectError("refused"))
    with pytest.raises(llm.LLMError, match="Is Ollama running"):
        llm.ollama_ask([{"role": "user", "content": "hello"}], [])


def test_a_failing_model_server_still_reports_its_message(monkeypatch):
    """Reading .text on an unread stream raises RuntimeError, which no except would catch."""
    fake_stream(monkeypatch, status=503, body="model is loading")
    with pytest.raises(llm.LLMError, match="503"):
        llm.ollama_ask([{"role": "user", "content": "hi"}], [])


def test_unexpected_response(monkeypatch):
    fake_stream(monkeypatch, body="something else entirely")
    with pytest.raises(llm.LLMError):
        llm.ollama_ask([{"role": "user", "content": "hello"}], [])


def test_thinking_is_off_by_default(monkeypatch):
    monkeypatch.delenv("DONNA_THINK", raising=False)
    sent = fake_stream(monkeypatch, [text_chunk("Hi")])
    llm.ollama_ask([{"role": "user", "content": "hello"}], [])
    assert sent["body"]["reasoning_effort"] == "none"


def test_thinking_can_be_turned_on(monkeypatch):
    monkeypatch.setenv("DONNA_THINK", "1")
    sent = fake_stream(monkeypatch, [text_chunk("Hi")])
    llm.ollama_ask([{"role": "user", "content": "hello"}], [])
    assert "reasoning_effort" not in sent["body"]


def test_ask_uses_fake_brain_when_asked(monkeypatch):
    monkeypatch.setenv("DONNA_LLM", "fake")
    assert llm.ask([{"role": "user", "content": "hi"}], [])["content"] == "Hello."


def test_the_fake_brain_streams_its_answer():
    pieces, on_delta = sink()
    reply = llm.fake_ask([{"role": "user", "content": "Hello Donna!"}], tools=[], on_delta=on_delta)
    assert pieces == ["Hello."]
    assert reply["content"] == "Hello."


def test_the_fake_brain_streams_nothing_for_a_tool_call():
    pieces, on_delta = sink()
    llm.fake_ask([{"role": "user", "content": "Open VS Code"}], tools=[], on_delta=on_delta)
    assert pieces == []
