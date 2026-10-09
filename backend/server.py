"""DONNA's backend: a WebSocket server that the UI (or chat.py) talks to.

Run it with:  python server.py

Every message is JSON with a "type":

    UI -> backend   user_message       {"text": "..."}
    backend -> UI   tool_call          {"name": "...", "args": {...}}
                    tool_result        {"name": "...", "result": "..."}
                    assistant_message  {"text": "..."}
                    error              {"text": "..."}

Rule: every user_message gets exactly ONE final reply (assistant_message or
error). tool_call / tool_result messages may come before it.
"""

import json
import logging

from websockets.sync.server import serve

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


def reply_to(text, history, send):
    """Step 2: just echo. The agent takes over in Step 3."""
    send({"type": "assistant_message", "text": f"You said: {text}"})


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
        websocket.send(json.dumps(message))

    for raw in websocket:  # loops until the client disconnects
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            send({"type": "error", "text": "That wasn't valid JSON."})
            continue

        if not is_user_message(message):
            send({"type": "error", "text": 'Expected {"type": "user_message", "text": "..."}'})
            continue

        reply_to(message["text"].strip(), history, send)


def make_server(port=PORT):
    return serve(handle_connection, HOST, port, origins=ALLOWED_ORIGINS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with make_server() as server:
        print(f"DONNA backend listening on ws://{HOST}:{PORT}  (Ctrl+C to stop)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nBye.")
