"""Talk to DONNA from the terminal. Start `python server.py` first, then:

    python chat.py
"""

import json
import sys

from websockets.sync.client import connect

URL = "ws://127.0.0.1:8765"

# Windows consoles default to a legacy codepage, but web results arrive in any
# alphabet, so printing them would raise UnicodeEncodeError.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def show(message):
    kind = message["type"]
    if kind == "tool_call":
        print(f"   [{message['name']}] {json.dumps(message['args'])}")
    elif kind == "tool_result":
        print("   " + message["result"].replace("\n", "\n   "))
    elif kind == "assistant_message":
        print(f"DONNA > {message['text']}")
    elif kind == "error":
        print(f"DONNA (error) > {message['text']}")


def main():
    try:
        websocket = connect(URL)
    except OSError:
        sys.exit(f"Can't reach DONNA at {URL}. Is `python server.py` running?")

    with websocket:
        print("Connected to DONNA. Type a message (Ctrl+C to quit).")
        while True:
            try:
                text = input("You > ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not text:
                continue
            if not sys.stdin.isatty():  # input is piped from a file: show it
                print(text)

            websocket.send(json.dumps({"type": "user_message", "text": text}))

            # Print everything DONNA sends until her final reply.
            while True:
                message = json.loads(websocket.recv())
                show(message)
                if message["type"] in ("assistant_message", "error"):
                    break


if __name__ == "__main__":
    main()
