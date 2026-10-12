"""The only file that knows Piper and Kokoro exist.

    synthesise(text) -> bytes        raw PCM16 mono, no WAV header
    sample_rate()    -> int          what THAT audio is, in Hz

Two engines, because they are a real trade and neither wins outright:

    Piper medium   0.07s a sentence   41x realtime   22050 Hz   63 MB
    Piper high     0.33s a sentence   7.3x realtime  22050 Hz  114 MB
    Kokoro         0.62s a sentence   3.8x realtime  24000 Hz  326 MB

Measured on this PC, identical sentence, best of five warm runs. Kokoro costs
about +0.55s before she starts talking and sounds markedly less like someone
reading aloud, which was the complaint it exists to answer. 3.8x realtime
sounds tight next to 41x, but the only requirement is beating 1x: on a
three-sentence reply, sentences two and three were each ready well before the
previous finished playing. It is a first-word cost, never a stutter.

Kokoro also LOADS faster than Piper -- 0.95s against 2.9s -- despite being
five times the file.

Which voice answers is chosen in the window and stored by settings.py. Piper
voices are named by their file stem ("en_US-amy-medium"); Kokoro's are
prefixed ("kokoro:af_heart") so the two sets cannot collide and so an old
settings.json keeps working untouched.

    DONNA_TTS=piper   (default) the real voices
    DONNA_TTS=fake    silence of a plausible length, so the timing arithmetic
                      in voice.py stays exercised with no voice installed

Neither engine is in requirements.txt: see requirements-voice.txt for why.
Every import of them here is inside a function.
"""

import logging
import os
from pathlib import Path

# The rate of the DEFAULT voice, and of the fake one. It is no longer the
# rate of whatever is loaded -- ask sample_rate() for that. Kokoro speaks at
# 24000 and Piper's low voices at 16000, so a single constant was a lie that
# would have made her sound like a chipmunk.
SAMPLE_RATE = 22050

VOICE = Path(
    os.environ.get("DONNA_VOICE", os.path.expanduser("~/.cache/donna/en_US-amy-medium.onnx"))
)
VOICE_DIR = VOICE.parent  # every Piper voice she can switch to lives here
DEFAULT_VOICE = VOICE.stem

# Kokoro is one model file serving every one of its voices, so switching
# between them is free -- it is a different speaker embedding, not a reload.
KOKORO_DIR = Path(os.environ.get("DONNA_KOKORO", os.path.expanduser("~/.cache/donna/kokoro")))
KOKORO_MODEL = KOKORO_DIR / "kokoro-v1.0.onnx"
KOKORO_VOICES = KOKORO_DIR / "voices-v1.0.bin"
KOKORO_RATE = 24000
PREFIX = "kokoro:"

# Of Kokoro's 54 voices, these 28 are the English ones: 'a' is American and
# 'b' British, and the rest are Spanish, French, Hindi, Italian, Japanese,
# Portuguese and Chinese. Her rules are written in English and Whisper is an
# .en model, so offering a Japanese voice would only ever disappoint.
# DONNA_KOKORO_ALL=1 lists everything anyway.
ENGLISH = ("af_", "am_", "bf_", "bm_")

FAKE_SPEED = 14  # characters per second of "speech", for the fake voice

_piper = None  # the loaded PiperVoice, when a Piper voice is current
_kokoro = None  # the Kokoro model, loaded once and kept
_loaded = None  # which voice _piper/_kokoro is currently ready to speak as
_rate = SAMPLE_RATE  # the rate of that voice
_speed = 1.0
_wanted = DEFAULT_VOICE  # the voice we have been asked for


class TtsError(Exception):
    """DONNA can't speak: the voice is missing, or wouldn't load."""


def is_kokoro(name):
    return str(name).startswith(PREFIX)


def faking():
    return os.environ.get("DONNA_TTS", "piper") == "fake"


def sample_rate():
    """The rate of the audio synthesise() is currently producing.

    This is what goes out to the window with the settings, and what voice.py
    divides by to know when she will stop talking. Asking the loaded voice
    rather than assuming a constant is the whole reason Kokoro can be offered
    at all.
    """
    return SAMPLE_RATE if faking() else _rate


def synthesise(text):
    """Turn one sentence into raw PCM16 bytes."""
    if faking():
        seconds = max(0.2, len(text) / FAKE_SPEED / _speed)
        return b"\0\0" * int(seconds * SAMPLE_RATE)
    if is_kokoro(_wanted):
        return kokoro_synthesise(text)
    return piper_synthesise(text)


def warm():
    """Load the voice now: the first sentence otherwise costs about 2 seconds."""
    if faking():
        return
    logging.info("Loading the voice %s...", _wanted)
    load()
    logging.info("DONNA can speak, at %d Hz.", _rate)


def configure(voice=None, speed=None):
    """Point her at another voice, or change how fast she talks.

    Speed is free. A voice change may mean loading a model -- two seconds for
    Piper, one for Kokoro -- so it is paid here, while she is idle and you
    have just clicked something, and never in the middle of a sentence.
    """
    global _wanted, _speed
    if speed is not None:
        _speed = float(speed)
    if voice is not None and voice != _wanted:
        _wanted = voice
        load()  # pay the load now


def installed_voices():
    """Every voice she could be asked to use, Piper's and Kokoro's.

    No longer filtered by sample rate: the rate travels with the audio now,
    so a 24000 Hz Kokoro voice and a 16000 Hz Piper one are both fine.
    """
    return piper_voices() + kokoro_voices()


def piper_voices():
    """Usable Piper voices sitting next to the configured one."""
    import json

    found = []
    for onnx in sorted(VOICE_DIR.glob("*.onnx")):
        settings = onnx.with_suffix(".onnx.json")
        if not settings.exists():
            continue  # a half-finished download isn't a voice
        try:
            json.loads(settings.read_text(encoding="utf-8"))["audio"]["sample_rate"]
        except (OSError, ValueError, KeyError):
            continue
        found.append(onnx.stem)
    return found


def kokoro_voices():
    """Kokoro's English voices, or nothing at all if it isn't installed.

    Read from the 27 MB voice bank, which is an npz of speaker embeddings, and
    NOT by loading the model: that takes 0.038s instead of a second, and it
    keeps 326 MB out of memory for the many sessions that never pick a Kokoro
    voice. Every connection asks for this list.

    Never raises: not having the model is the normal case, not an error, and
    it must not stop the panel listing the Piper voices.
    """
    if not KOKORO_VOICES.exists() or not KOKORO_MODEL.exists():
        return []
    try:
        import numpy

        bank = numpy.load(KOKORO_VOICES, allow_pickle=True)
        names = sorted(bank.files if hasattr(bank, "files") else bank.keys())
    except Exception as error:
        logging.info("Kokoro's voice bank wouldn't open, so it isn't offered: %s", error)
        return []
    if not os.environ.get("DONNA_KOKORO_ALL"):
        names = [name for name in names if name.startswith(ENGLISH)]
    return [PREFIX + name for name in names]


def load():
    """Make _wanted ready to speak, and record what rate it speaks at."""
    global _loaded, _rate
    if _loaded == _wanted:
        return
    if is_kokoro(_wanted):
        load_kokoro()  # the model is shared; the voice is just an argument
        _rate = KOKORO_RATE
    else:
        _rate = load_piper(_wanted)
    _loaded = _wanted


def load_piper(name):
    """Load a Piper voice and return the rate it speaks at."""
    global _piper
    try:
        from piper import PiperVoice
    except ImportError:
        raise TtsError(
            "DONNA can't speak: piper-tts isn't installed. "
            "Run  pip install -r requirements-voice.txt"
        ) from None
    path = VOICE_DIR / f"{name}.onnx"
    if not path.exists():
        raise TtsError(
            f"DONNA can't speak: no voice at {path}. Run  "
            f"python -m piper.download_voices {name} --download-dir {VOICE_DIR}"
        )
    try:
        _piper = PiperVoice.load(str(path))
    except Exception as error:
        raise TtsError(f"DONNA couldn't load the voice {path.name}: {error}") from None
    return getattr(_piper.config, "sample_rate", SAMPLE_RATE) or SAMPLE_RATE


def load_kokoro():
    """The Kokoro model, loaded at most once. Every voice shares it."""
    global _kokoro
    if _kokoro is not None:
        return _kokoro
    try:
        from kokoro_onnx import Kokoro
    except ImportError:
        raise TtsError(
            "DONNA can't use Kokoro: kokoro-onnx isn't installed. "
            "Run  pip install -r requirements-voice.txt"
        ) from None
    if not KOKORO_MODEL.exists() or not KOKORO_VOICES.exists():
        raise TtsError(
            f"DONNA can't use Kokoro: no model in {KOKORO_DIR}. Download "
            f"kokoro-v1.0.onnx and voices-v1.0.bin from "
            f"https://github.com/thewh1teagle/kokoro-onnx/releases into that folder."
        )
    try:
        _kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VOICES))
    except Exception as error:
        raise TtsError(f"DONNA couldn't load Kokoro: {error}") from None
    return _kokoro


def piper_synthesise(text):
    from piper import SynthesisConfig

    load()
    # length_scale is duration, so faster means a smaller number. Start from
    # the voice's own pacing rather than 1.0: some voices ship their own, and
    # a bare reciprocal would silently throw it away.
    base = getattr(_piper.config, "length_scale", None) or 1.0
    config = SynthesisConfig(length_scale=base / _speed)
    try:
        return b"".join(chunk.audio_int16_bytes for chunk in _piper.synthesize(text, config))
    except TtsError:
        raise
    except Exception as error:
        raise TtsError(f"DONNA couldn't say that: {error}") from None


def kokoro_synthesise(text):
    """One sentence through Kokoro, as PCM16 at KOKORO_RATE."""
    import numpy

    load()
    name = _wanted[len(PREFIX) :]
    # 'b' voices are British and 'a' American, and telling Kokoro which it is
    # changes the pronunciation rather than just the accent of the voice.
    language = "en-gb" if name.startswith(("bf_", "bm_")) else "en-us"
    try:
        samples, rate = _kokoro.create(text, voice=name, speed=_speed, lang=language)
    except Exception as error:
        raise TtsError(f"DONNA couldn't say that: {error}") from None
    if rate != _rate:  # a new Kokoro release changing rate must not go unnoticed
        logging.warning("Kokoro returned %d Hz, not the %d Hz expected.", rate, _rate)
    return (numpy.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()


if __name__ == "__main__":  # python tts.py "Hello, I am DONNA." kokoro:af_heart
    import sys
    import wave

    if len(sys.argv) > 2:
        _wanted = sys.argv[2]
    warm()
    pcm = synthesise(sys.argv[1] if len(sys.argv) > 1 else "Hello, I am DONNA.")
    with wave.open("donna.wav", "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(sample_rate())
        out.writeframes(pcm)
    print(f"wrote donna.wav, {len(pcm) / 2 / sample_rate():.1f}s at {sample_rate()} Hz")
