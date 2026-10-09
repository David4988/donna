import json
import threading

import pytest
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

import server


@pytest.fixture
def url(monkeypatch):
    """Start the real server on a free port in a background thread (fake brain)."""
    monkeypatch.setenv("DONNA_LLM", "fake")
    srv = server.make_server(port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    port = srv.socket.getsockname()[1]
    yield f"ws://127.0.0.1:{port}"
    srv.shutdown()
    thread.join(timeout=5)


def ask(websocket, text):
    """Send a user_message and collect everything until the final reply."""
    websocket.send(json.dumps({"type": "user_message", "text": text}))
    messages = []
    while True:
        message = json.loads(websocket.recv(timeout=5))
        messages.append(message)
        if message["type"] in ("assistant_message", "error"):
            return messages


def test_round_trip(url):
    with connect(url) as ws:
        assert ask(ws, "hi")[-1] == {"type": "assistant_message", "text": "Hello."}


def test_the_reply_arrives_in_pieces_that_add_up_to_the_final_message(url):
    with connect(url) as websocket:
        messages = ask(websocket, "hi")

    pieces = [m["text"] for m in messages if m["type"] == "assistant_delta"]
    assert pieces, "no assistant_delta arrived"
    assert "".join(pieces) == messages[-1]["text"]
    assert sum(m["type"] in ("assistant_message", "error") for m in messages) == 1


def test_bad_message_gets_error_and_connection_stays_open(url):
    with connect(url) as ws:
        ws.send("this is not json")
        assert json.loads(ws.recv(timeout=5))["type"] == "error"
        for bad in ([1, 2], {"type": "something_else"}, {"type": "user_message", "text": "  "}):
            ws.send(json.dumps(bad))
            assert json.loads(ws.recv(timeout=5))["type"] == "error"
        assert ask(ws, "still there?")[-1]["type"] == "assistant_message"


def test_random_website_cannot_connect(url):
    with pytest.raises(InvalidStatus) as excinfo:
        connect(url, origin="https://evil.example.com")
    assert excinfo.value.response.status_code == 403


def test_donna_ui_origin_can_connect(url):
    with connect(url, origin="http://localhost:5173") as ws:
        assert ask(ws, "hi")[-1]["type"] == "assistant_message"
