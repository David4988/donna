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
VOICE_DIR = VOICE.parent  # every voice she can switch to lives here
DEFAULT_VOICE = VOICE.stem

# Measured on this PC: about 0.1s to synthesise a 4s sentence, roughly 40x
# faster than real time, so synthesis never falls behind playback.
FAKE_SPEED = 14  # characters per second of "speech", for the fake voice

_voice = None
_loaded = None  # which voice _voice actually is
_speed = 1.0
_wanted = DEFAULT_VOICE  # the voice we have been asked for


class TtsError(Exception):
    """DONNA can't speak: the voice is missing, or wouldn't load."""


def synthesise(text):
    """Turn one sentence into raw PCM16 bytes."""
    if os.environ.get("DONNA_TTS", "piper") == "fake":
        seconds = max(0.2, len(text) / FAKE_SPEED / _speed)
        return b"\0\0" * int(seconds * SAMPLE_RATE)
    return piper_synthesise(text)


def warm():
    """Load the voice now: the first sentence otherwise costs about 2 seconds."""
    if os.environ.get("DONNA_TTS", "piper") == "fake":
        return
    logging.info("Loading the voice %s...", VOICE.name)
    loaded = load()
    rate = loaded.config.sample_rate
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


def configure(voice=None, speed=None):
    """Point her at another voice, or change how fast she talks.

    Speed is free. A voice change means Piper loads a new model, about two
    seconds, so it is paid here -- while she is idle and you have just clicked
    something -- and never in the middle of a sentence.
    """
    global _wanted, _speed
    if speed is not None:
        _speed = float(speed)
    if voice is not None and voice != _wanted:
        _wanted = voice
        load()  # pay the two seconds now


def installed_voices():
    """Every usable voice sitting next to the configured one.

    Voices that speak at another sample rate are left out: the window creates
    its speaker at SAMPLE_RATE, so offering one would make her sound like a
    chipmunk with no clue why.
    """
    import json

    found = []
    for onnx in sorted(VOICE_DIR.glob("*.onnx")):
        settings = onnx.with_suffix(".onnx.json")
        if not settings.exists():
            continue  # a half-finished download isn't a voice
        try:
            rate = json.loads(settings.read_text(encoding="utf-8"))["audio"]["sample_rate"]
        except (OSError, ValueError, KeyError):
            continue
        if rate != SAMPLE_RATE:
            logging.info(
                "%s speaks at %s Hz and DONNA needs %d, so it isn't offered.",
                onnx.stem,
                rate,
                SAMPLE_RATE,
            )
            continue
        found.append(onnx.stem)
    return found


def load():
    global _voice, _loaded
    # Checking which voice is loaded, rather than merely that one is, means
    # the cache cannot get out of step with the chosen voice.
    if _voice is not None and _loaded == _wanted:
        return _voice
    try:
        from piper import PiperVoice
    except ImportError:
        raise TtsError(
            "DONNA can't speak: piper-tts isn't installed. "
            "Run  pip install -r requirements-voice.txt"
        ) from None
    path = VOICE_DIR / f"{_wanted}.onnx"
    if not path.exists():
        raise TtsError(
            f"DONNA can't speak: no voice at {path}. Run  "
            f"python -m piper.download_voices {_wanted} --download-dir {VOICE_DIR}"
        )
    try:
        _voice, _loaded = PiperVoice.load(str(path)), _wanted
    except Exception as error:
        raise TtsError(f"DONNA couldn't load the voice {path.name}: {error}") from None
    return _voice


def piper_synthesise(text):
    from piper import SynthesisConfig

    voice = load()
    # length_scale is duration, so faster means a smaller number. Start from
    # the voice's own pacing rather than 1.0: some voices ship their own, and
    # a bare reciprocal would silently throw it away.
    base = getattr(voice.config, "length_scale", None) or 1.0
    config = SynthesisConfig(length_scale=base / _speed)
    try:
        return b"".join(chunk.audio_int16_bytes for chunk in voice.synthesize(text, config))
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
