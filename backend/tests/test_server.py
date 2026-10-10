import json
import threading

import pytest
from websockets.exceptions import InvalidStatus
from websockets.sync.client import connect

import server
import voice


@pytest.fixture
def url(monkeypatch):
    """Start the real server on a free port in a background thread (fake brain)."""
    monkeypatch.setenv("DONNA_LLM", "fake")
    monkeypatch.setenv("DONNA_STT", "fake")  # the audio bytes ARE the text
    monkeypatch.setenv("DONNA_WAKE", "fake")  # ...and they decide the wake word too
    monkeypatch.setenv("DONNA_TTS", "fake")  # silence of a plausible length
    # She really does wait for her own audio to finish before listening again
    # -- that is the half-duplex rule -- but a test shouldn't spend ten real
    # seconds pretending to speak a long sentence.
    monkeypatch.setattr(voice, "_sleep", lambda seconds: None)
    srv = server.make_server(port=0)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    port = srv.socket.getsockname()[1]
    yield f"ws://127.0.0.1:{port}"
    srv.shutdown()
    thread.join(timeout=5)


def start(websocket):
    """Swallow the settings frame she sends on connect, and return it."""
    return json.loads(websocket.recv(timeout=5))


def collect(websocket):
    """Everything until the turn ends. Returns (json messages, audio frames).

    A turn ends with `state` going back to "awake" AFTER the final reply, not
    with the final reply itself: the last sentence is synthesised after its
    text has gone to the screen, so her audio arrives behind it.
    """
    messages, audio, said_the_last_word = [], [], False
    while True:
        frame = websocket.recv(timeout=5)
        if isinstance(frame, bytes):
            audio.append(frame)
            continue
        message = json.loads(frame)
        messages.append(message)
        if message["type"] in ("assistant_message", "error"):
            said_the_last_word = True
        elif said_the_last_word and message["type"] == "state":
            return messages, audio


def ask(websocket, text):
    """Send a typed user_message and collect up to and including the final reply.

    The turn's trailing `state` is still read off the socket, so the next call
    starts clean, but it isn't returned: these tests were written when the
    last message was the final reply, and that is still the useful contract.
    """
    websocket.send(json.dumps({"type": "user_message", "text": text}))
    messages = collect(websocket)[0]
    for i, message in enumerate(messages):
        if message["type"] in ("assistant_message", "error"):
            return messages[: i + 1]
    return messages


def say(websocket, text):
    """Speak an utterance. With DONNA_STT=fake the bytes are the transcript."""
    websocket.send(text.encode())
    return collect(websocket)


def test_round_trip(url):
    with connect(url) as ws:
        assert ask(ws, "hi")[-1] == {
            "type": "assistant_message",
            "text": "Hello. What can I do for you?",
        }


def test_a_real_question_reaches_the_brain(url):
    """"hi" is answered without the model, so this is the one that proves the pipe."""
    with connect(url) as ws:
        reply = ask(ws, "what time is it")[-1]
    assert reply["type"] == "assistant_message"
    assert reply["text"].startswith("I'm DONNA's offline brain")


def test_a_spoken_utterance_wakes_her_and_gets_a_spoken_reply(url):
    with connect(url) as ws:
        messages, audio = say(ws, "Hey Jarvis, what time is it")
    assert {"type": "state", "name": "awake"} in messages
    assert {"type": "transcript", "text": "Hey Jarvis, what time is it"} in messages
    assert [m["type"] for m in messages].count("assistant_message") == 1
    assert audio, "she replied, but said nothing out loud"
    assert all(len(frame) % 2 == 0 for frame in audio), "PCM16 frames are even-length"


def test_an_overheard_remark_produces_no_traffic_at_all(url):
    """The behaviour an open mic lives or dies on."""
    with connect(url) as ws:
        start(ws)
        ws.send(b"what time is the train")
        with pytest.raises(TimeoutError):
            ws.recv(timeout=0.5)  # she says nothing whatsoever
        assert say(ws, "Hey Jarvis, hi")[0], "and she still works afterwards"


def test_typed_and_spoken_turns_share_one_connection(url):
    with connect(url) as ws:
        say(ws, "Hey Jarvis, hi")
        assert ask(ws, "hi")[-1]["type"] == "assistant_message"


def test_a_junk_binary_frame_does_not_kill_the_connection(url):
    with connect(url) as ws:
        ws.send(b"\x00\x01\x02")
        assert ask(ws, "hi")[-1]["type"] == "assistant_message"


def test_the_reply_arrives_in_pieces_that_add_up_to_the_final_message(url):
    with connect(url) as websocket:
        messages = ask(websocket, "what time is it")

    pieces = [m["text"] for m in messages if m["type"] == "assistant_delta"]
    assert pieces, "no assistant_delta arrived"
    assert "".join(pieces) == messages[-1]["text"]
    assert sum(m["type"] in ("assistant_message", "error") for m in messages) == 1


def test_bad_message_gets_error_and_connection_stays_open(url):
    with connect(url) as ws:
        start(ws)
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


def test_she_says_what_she_is_set_to_when_you_connect(url):
    with connect(url) as ws:
        first = start(ws)
    assert first["type"] == "settings"
    assert set(first["settings"]) == {"voice", "speed"}
    assert isinstance(first["voices"], list)


def test_a_settings_change_is_not_a_turn(url):
    """Moving a control says nothing, remembers nothing, and ends no turn."""
    with connect(url) as ws:
        start(ws)
        ws.send(json.dumps({"type": "settings_change", "settings": {"speed": 1.4}}))
        reply = json.loads(ws.recv(timeout=5))
        assert reply["type"] == "settings"
        assert reply["settings"]["speed"] == 1.4
        with pytest.raises(TimeoutError):
            ws.recv(timeout=0.5)  # no state, nothing spoken


def test_a_refused_setting_comes_back_as_it_really_is(url):
    with connect(url) as ws:
        start(ws)
        ws.send(json.dumps({"type": "settings_change",
                            "settings": {"speed": 99, "voice": "no-such-voice"}}))
        reply = json.loads(ws.recv(timeout=5))
    assert reply["settings"]["speed"] == 2.0  # clamped, not accepted
    assert reply["settings"]["voice"] != "no-such-voice"
