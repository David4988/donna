"""The only file that knows Piper exists.

    synthesise(text) -> bytes

Raw PCM16 mono at SAMPLE_RATE, with no WAV header, ready to go straight out
as a binary frame.

Which voice answers is chosen with the DONNA_TTS environment variable:
    DONNA_TTS=piper  (default) the real voice
    DONNA_TTS=fake   silence of a plausible length, so the timing arithmetic
                     in voice.py stays exercised without a voice installed

piper-tts is NOT in requirements.txt: see requirements-voice.txt for why.
Every import of it here is inside a function.
"""

import logging
import os
from pathlib import Path

# Piper voices come in fixed sample rates: low voices are 16000, medium 22050.
# The window hardcodes this number, so warm() checks the loaded voice agrees
# and says so loudly if it doesn't -- a mismatch is a baffling audio bug at
# runtime and one obvious line at startup.
SAMPLE_RATE = 22050

VOICE = Path(
    os.environ.get("DONNA_VOICE", os.path.expanduser("~/.cache/donna/en_US-amy-medium.onnx"))
)

# Measured on this PC: about 0.1s to synthesise a 4s sentence, roughly 40x
# faster than real time, so synthesis never falls behind playback.
FAKE_SPEED = 14  # characters per second of "speech", for the fake voice

_voice = None


class TtsError(Exception):
    """DONNA can't speak: the voice is missing, or wouldn't load."""


def synthesise(text):
    """Turn one sentence into raw PCM16 bytes."""
    if os.environ.get("DONNA_TTS", "piper") == "fake":
        seconds = max(0.2, len(text) / FAKE_SPEED)
        return b"\0\0" * int(seconds * SAMPLE_RATE)
    return piper_synthesise(text)


def warm():
    """Load the voice now: the first sentence otherwise costs about 2 seconds."""
    if os.environ.get("DONNA_TTS", "piper") == "fake":
        return
    logging.info("Loading the voice %s...", VOICE.name)
    voice = load()
    rate = voice.config.sample_rate
    if rate != SAMPLE_RATE:
        logging.warning(
            "%s speaks at %d Hz but DONNA and the UI expect %d Hz. She will sound wrong. "
            "Set DONNA_VOICE to a %d Hz voice, or change tts.SAMPLE_RATE and the UI together.",
            VOICE.name,
            rate,
            SAMPLE_RATE,
            SAMPLE_RATE,
        )
    logging.info("DONNA can speak.")


def load():
    global _voice
    if _voice is not None:
        return _voice
    try:
        from piper import PiperVoice
    except ImportError:
        raise TtsError(
            "DONNA can't speak: piper-tts isn't installed. "
            "Run  pip install -r requirements-voice.txt"
        ) from None
    if not VOICE.exists():
        raise TtsError(
            f"DONNA can't speak: no voice at {VOICE}. Run  "
            f"python -m piper.download_voices en_US-amy-medium --download-dir {VOICE.parent}"
        )
    try:
        _voice = PiperVoice.load(str(VOICE))
    except Exception as error:
        raise TtsError(f"DONNA couldn't load the voice {VOICE.name}: {error}") from None
    return _voice


def piper_synthesise(text):
    try:
        return b"".join(chunk.audio_int16_bytes for chunk in load().synthesize(text))
    except TtsError:
        raise
    except Exception as error:
        raise TtsError(f"DONNA couldn't say that: {error}") from None


if __name__ == "__main__":  # python tts.py "Hello, I am DONNA."
    import sys
    import wave

    warm()
    pcm = synthesise(sys.argv[1] if len(sys.argv) > 1 else "Hello, I am DONNA.")
    with wave.open("donna.wav", "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(pcm)
    print(f"wrote donna.wav, {len(pcm) / 2 / SAMPLE_RATE:.1f}s")
