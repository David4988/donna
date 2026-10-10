"""The only file that knows openWakeWord exists.

    heard_wake_word(pcm) -> bool

Was DONNA actually being summoned? `pcm` is the whole utterance, raw PCM16
mono at 16 kHz -- the same bytes stt.transcribe gets.

This is the gate that stops Whisper running on every sound in the room. It is
about five times cheaper (93 ms against 440 ms for the same utterance,
measured), and unlike reading her name out of a transcript it does not need
the audio transcribed at all.

Which ears answer is chosen with the DONNA_WAKE environment variable:
    DONNA_WAKE=jarvis  (default) the real model
    DONNA_WAKE=fake    the bytes decide, so the whole path can be tested
                       with no model and no audio
    DONNA_WAKE=off     every utterance counts as a summons (debugging)

openwakeword is NOT in requirements.txt: see requirements-voice.txt for why.
Every import of it is inside a function, so this module imports fine on a
machine that has never installed it.
"""

import logging
import os

import stt

MODEL_NAME = "hey_jarvis"

# Measured on Piper speech replayed through the model: the four wake phrases
# scored 0.996-0.999 and six ordinary sentences scored 0.000-0.005. Nothing
# landed in between, so the default threshold has enormous headroom. Lower it
# if she misses you, raise it if the television wakes her.
THRESHOLD = float(os.environ.get("DONNA_WAKE_THRESHOLD", "0.5"))

FRAME_SAMPLES = 1280  # 80ms at 16 kHz; openWakeWord accepts no other size

# The classifier sees roughly two seconds of context, and a tight cut at the
# start of "Hey Jarvis" might not give it that. Measured: padding made no
# difference at all on synthesised speech (0.997 either way), so this is cheap
# insurance for the real microphone rather than something we know we need.
PAD_SECONDS = 0.25

_model = None


class WakeError(Exception):
    """The wake-word model is missing, or wouldn't load."""


def heard_wake_word(pcm):
    """Was that DONNA being called?"""
    mode = os.environ.get("DONNA_WAKE", "jarvis")
    if mode == "off":
        return True
    if mode == "fake":
        return "jarvis" in pcm.decode("utf-8", "ignore").lower()
    return score(pcm) >= THRESHOLD


def score(pcm):
    """How sure the model is, 0 to 1, over the whole utterance."""
    import numpy

    samples = numpy.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="<i2")
    if PAD_SECONDS:
        pad = numpy.zeros(int(PAD_SECONDS * stt.SAMPLE_RATE), dtype="<i2")
        samples = numpy.concatenate([pad, samples])

    model = load()
    model.reset()  # or the last utterance's tail sits against this one's head

    best = 0.0
    for at in range(0, len(samples) - FRAME_SAMPLES + 1, FRAME_SAMPLES):
        scores = model.predict(samples[at : at + FRAME_SAMPLES])
        # One model is loaded, so take the only value rather than indexing the
        # name: openWakeWord has spelled the key "hey_jarvis_v0.1" before.
        best = max(best, max(scores.values()))
    return best


def warm():
    """Load the model now. It is small, but the first run downloads ~5 MB."""
    if os.environ.get("DONNA_WAKE", "jarvis") in ("fake", "off"):
        return
    logging.info("Loading the wake word %r...", MODEL_NAME)
    load()
    logging.info("DONNA is listening for 'Hey Jarvis'.")


def load():
    global _model
    if _model is not None:
        return _model
    try:
        from openwakeword.model import Model
        from openwakeword.utils import download_models
    except ImportError:
        raise WakeError(
            "DONNA can't hear you: openwakeword isn't installed. "
            "Run  pip install -r requirements-voice.txt"
        ) from None
    try:
        download_models(model_names=[MODEL_NAME])  # a no-op once they're there
        # onnx, not the tflite default: modern tflite has no Windows build.
        _model = Model(wakeword_models=[MODEL_NAME], inference_framework="onnx")
    except Exception as error:
        raise WakeError(f"DONNA couldn't load the {MODEL_NAME!r} wake word: {error}") from None
    return _model
