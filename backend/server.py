"""DONNA's backend: a WebSocket server that the UI (or chat.py) talks to.

Run it with:  python server.py

Binary means audio, JSON means everything else. A binary frame going up is one
whole utterance you just spoke (PCM16 mono 16 kHz); a binary frame coming down
is one sentence of her reply (PCM16 mono 22050 Hz).

A binary frame going up that starts with b"DONNAPRT" is the utterance SO FAR,
sent while you are still speaking, so the words can appear on screen. It
starts no turn and never reaches the agent.

Every other message is JSON with a "type":

    UI -> backend   user_message       {"text": "..."}
                    settings_change    {"settings": {"voice": "...", "speed": 1.0}}
    backend -> UI   transcript         {"text": "..."}
                    state              {"name": "..."}
                    settings           {"settings": {...}, "voices": [...]}
                    partial_transcript {"text": "..."}
                    tool_call          {"name": "...", "args": {...}}
                    tool_result        {"name": "...", "result": "..."}
                    assistant_delta    {"text": "..."}
                    assistant_message  {"text": "..."}
                    error              {"text": "..."}

Rule: every turn -- a typed user_message, or a spoken utterance that reaches
the agent -- gets exactly ONE final reply (assistant_message or error),
followed by one state returning to "awake". An utterance that is dropped
(asleep and unaddressed, arriving while she speaks, garbage, too long) starts
no turn and sends NOTHING AT ALL.

assistant_delta carries the next piece of the answer as the model produces it.
Deltas are additive and advisory: the assistant_message that follows always
holds the complete text, so a client may ignore them and lose nothing. Any
non-delta message ends the run of deltas before it.

state is "asleep", "awake" or "speaking" for the session, plus "deaf" or
"mute" sent once if she loses the ability to hear or speak. Those ride this
channel rather than `error` because an error would be a second final reply.

partial_transcript is what she thinks you are saying so far. Each one
REPLACES the previous one -- unlike assistant_delta, they do not add up -- and
the transcript that follows is the authority and may well contradict them.

settings_change is an event (the user moved a control, and may send only the
part that changed); settings is the state, sent once when you connect and
again after every change. The window draws what the reply says rather than
what it asked for, so a value she refused visibly snaps back.
"""

import json
import logging

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve

import stt
import tts
import voice
import wake

HOST = "127.0.0.1"  # only programs on this computer can connect
PORT = 8765

# Browsers always tell us which page is connecting (the "Origin" header).
# Only DONNA's own UI may connect; this stops random websites you visit from
# talking to DONNA. None = no Origin header = a non-browser client like chat.py.
ALLOWED_ORIGINS = [
    None,
    "http://localhost:5173",  # Vite dev server (npm run dev)
    "http://127.0.0.1:5173",
    "tauri://localhost",  # Tauri app window (macOS/Linux)
    "http://tauri.localhost",  # Tauri app window (Windows)
    "https://tauri.localhost",
]


# One utterance arrives as one frame, and the library's default is 1 MiB --
# which is 32.8 seconds of PCM16 at 16 kHz. Going over it closes the
# connection, so the limit sits above anything voice.py will accept.
MAX_FRAME_BYTES = 2**21

# Audio for the words shown while you are still speaking carries this in
# front. Only partials are marked, so a finished utterance stays byte for
# byte what it always was -- which is what keeps DONNA_STT=fake, chat.py's
# /say and the socket tests working untouched. Eight bytes, so the PCM16
# behind it stays two-byte aligned.
PARTIAL_PREFIX = b"DONNAPRT"


def is_settings_change(message):
    return (
        isinstance(message, dict)
        and message.get("type") == "settings_change"
        and isinstance(message.get("settings"), dict)
    )


def is_user_message(message):
    return (
        isinstance(message, dict)
        and message.get("type") == "user_message"
        and isinstance(message.get("text"), str)
        and message["text"].strip() != ""
    )


def handle_connection(websocket):
    """Runs once per connected client, in its own thread, top to bottom."""
    history = []  # this connection's conversation

    def send(message):
        # Binary means audio, JSON means everything else.
        websocket.send(message if isinstance(message, bytes) else json.dumps(message))

    session = voice.Session(send, history)
    session.send_settings()  # so the window can draw its controls

    try:
        for raw in websocket:  # loops until the client disconnects
            if isinstance(raw, bytes):
                if raw.startswith(PARTIAL_PREFIX):
                    session.on_partial(raw[len(PARTIAL_PREFIX) :])
                else:
                    session.on_audio(raw)  # one binary frame is one whole utterance
                continue

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                send({"type": "error", "text": "That wasn't valid JSON."})
                continue

            if is_user_message(message):
                session.on_text(message["text"].strip())
            elif is_settings_change(message):
                session.on_settings(message["settings"])
            else:
                send({"type": "error", "text": "Expected a user_message or a settings_change."})
    except ConnectionClosed:
        pass  # the client vanished without saying goodbye (app closed, network dropped)


def make_server(port=PORT):
    return serve(
        handle_connection, HOST, port, origins=ALLOWED_ORIGINS, max_size=MAX_FRAME_BYTES
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    # Load the wake word, the ears and the voice now: between them they take
    # about 17 seconds, and paying that on your first sentence would ruin it.
    wake.warm()
    stt.warm()
    tts.warm()
    with make_server() as server:
        print(f"DONNA backend listening on ws://{HOST}:{PORT}  (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nBye.")
