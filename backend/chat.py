"""Talk to DONNA from the terminal. Start `python server.py` first, then:

    python chat.py

Typing a line sends it as a typed message. /voice <name> and /speed <number>
change how she sounds. Starting a line with /say sends it as a spoken
utterance instead:

    /say Hey Donna, open notepad

With DONNA_STT=fake on the server, the bytes of that line are what she "hears",
so the whole voice path can be driven from here with no microphone and no
speech model. Audio she sends back is reported as its length.
"""

import json
import sys

from websockets.sync.client import connect

URL = "ws://127.0.0.1:8765"

# Windows consoles default to a legacy codepage, but web results arrive in any
# alphabet, so printing them would raise UnicodeEncodeError.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def show(message, streaming=False):
    """Print one message. `streaming` says a reply is already half-printed on the
    current line; returns whether it still is."""
    kind = message["type"]

    if kind == "assistant_delta":
        if not streaming:
            print("DONNA > ", end="")
        # flush: stdout is block-buffered when piped, so tokens would sit unseen.
        print(message["text"], end="", flush=True)
        return True

    if streaming:
        print()  # finish the half-printed reply
        if kind == "assistant_message":
            return False  # already printed, piece by piece

    if kind == "settings":
        voices = ", ".join(message["voices"]) or "none installed"
        print(f"   (voice {message['settings']['voice']}, "
              f"speed {message['settings']['speed']}x; available: {voices})")
    elif kind == "transcript":
        print(f"You (heard) > {message['text']}")
    elif kind == "state":
        print(f"   ({message['name']})")
    elif kind == "tool_call":
        print(f"   [{message['name']}] {json.dumps(message['args'])}")
    elif kind == "tool_result":
        print("   " + message["result"].replace("\n", "\n   "))
    elif kind == "assistant_message":
        print(f"DONNA > {message['text']}")
    elif kind == "error":
        print(f"DONNA (error) > {message['text']}")
    return False


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

            if text.startswith("/voice ") or text.startswith("/speed "):
                command, _, value = text.partition(" ")
                key = "voice" if command == "/voice" else "speed"
                websocket.send(json.dumps({"type": "settings_change",
                                           "settings": {key: value if key == "voice" else float(value)}}))
                show(json.loads(websocket.recv()))
                continue

            spoken = text.startswith("/say ")
            if spoken:
                # A spoken utterance. With DONNA_STT=fake these bytes are the
                # transcript, so this drives the voice path with no microphone.
                websocket.send(text[len("/say ") :].encode())
            else:
                websocket.send(json.dumps({"type": "user_message", "text": text}))

            # Print everything DONNA sends until the turn ends. A turn ends with
            # `state` going back to "awake" after the final reply, because her
            # last sentence is synthesised after its text is already on screen.
            # An utterance she wasn't meant to hear gets no reply at all, so the
            # first frame of a spoken turn is given a short deadline.
            streaming, final_seen, anything = False, False, False
            while True:
                try:
                    frame = websocket.recv(timeout=10 if spoken and not anything else 300)
                except TimeoutError:
                    print("   (she ignored that: not addressed to her, or no speech in it)")
                    break
                anything = True
                if isinstance(frame, bytes):
                    print(f"   [{len(frame) / 2 / 22050:.1f}s of audio]")
                    continue
                message = json.loads(frame)
                streaming = show(message, streaming)
                if message["type"] in ("assistant_message", "error"):
                    final_seen = True
                elif final_seen and message["type"] == "state":
                    break


if __name__ == "__main__":
    main()
