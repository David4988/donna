"""The only file that knows faster-whisper exists.

    transcribe(pcm) -> str

`pcm` is raw PCM16 mono at SAMPLE_RATE: exactly what the window's microphone
sends, and exactly what Whisper wants.

Which ears answer is chosen with the DONNA_STT environment variable:
    DONNA_STT=whisper  (default) the real model, on the CPU
    DONNA_STT=fake     the audio bytes ARE the text, so the whole voice path
                       can be tested with no model, no network and no audio

faster-whisper is NOT in requirements.txt: see requirements-voice.txt for why.
Every import of it here is inside a function, so this module imports fine on a
machine that has never installed it.
"""

import logging
import os

SAMPLE_RATE = 16000  # what the window sends, and what Whisper wants
MIN_SECONDS = 0.3  # shorter than this is a cough, a click or a door
MODEL = os.environ.get("DONNA_WHISPER_MODEL", "base.en")

# Nudges Whisper towards spelling the summons the way speech_text.JARVIS expects.
# Measured on this PC: base.en transcribes a 3.5s utterance in 0.44s, against
# 0.21s for tiny.en and 1.32s for small.en, all three word-perfect.
NAME_HINT = "Hey Jarvis."

_model = None


class SttError(Exception):
    """DONNA can't hear: the model is missing, or wouldn't load."""


def transcribe(pcm):
    """Turn one spoken utterance into text. Never raises on bad audio."""
    if os.environ.get("DONNA_STT", "whisper") == "fake":
        return pcm.decode("utf-8", "ignore").strip()
    return whisper_transcribe(pcm)


def warm():
    """Load the model now, so the first thing you say isn't the slow one.

    Loading base.en takes about 15 seconds, and the first run downloads
    roughly 75 MB.
    """
    if os.environ.get("DONNA_STT", "whisper") == "fake":
        return
    logging.info("Loading Whisper %r (the first run downloads ~75 MB)...", MODEL)
    load()
    logging.info("DONNA can hear you.")


def load():
    global _model
    if _model is not None:
        return _model
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise SttError(
            "DONNA can't hear you: faster-whisper isn't installed. "
            "Run  pip install -r requirements-voice.txt"
        ) from None
    try:
        _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    except Exception as error:
        raise SttError(f"DONNA couldn't load the {MODEL!r} speech model: {error}") from None
    return _model


def whisper_transcribe(pcm):
    import numpy

    try:
        samples = numpy.frombuffer(pcm, dtype="<i2").astype("float32") / 32768.0
    except ValueError:
        return ""  # not PCM16 at all: a buggy client, not a crash
    if len(samples) < MIN_SECONDS * SAMPLE_RATE:
        return ""

    segments, _ = load().transcribe(
        samples,
        language="en",
        beam_size=1,  # speed over the last fraction of accuracy
        vad_filter=False,  # the window already decided this was speech
        condition_on_previous_text=False,  # stops the repetition hallucinations
        initial_prompt=NAME_HINT,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


if __name__ == "__main__":  # python stt.py some.wav
    import sys
    import wave

    with wave.open(sys.argv[1], "rb") as audio:
        print(transcribe(audio.readframes(audio.getnframes())))
