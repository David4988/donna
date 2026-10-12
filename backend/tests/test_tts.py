"""Two engines at two sample rates, and the rate has to travel with the audio.

Nothing here needs piper-tts or kokoro-onnx installed, which is the point:
CI has neither, and the rate plumbing is the part that breaks silently.
"""

import json

import pytest

import tts


@pytest.fixture(autouse=True)
def _a_clean_voice_folder(monkeypatch, tmp_path):
    """Her real voices are 500 MB on this machine; tests use an empty folder."""
    monkeypatch.setattr(tts, "VOICE_DIR", tmp_path)
    monkeypatch.setattr(tts, "KOKORO_DIR", tmp_path / "kokoro")
    monkeypatch.setattr(tts, "KOKORO_MODEL", tmp_path / "kokoro" / "kokoro-v1.0.onnx")
    monkeypatch.setattr(tts, "KOKORO_VOICES", tmp_path / "kokoro" / "voices-v1.0.bin")
    monkeypatch.setattr(tts, "_loaded", None)
    monkeypatch.setattr(tts, "_rate", tts.SAMPLE_RATE)
    monkeypatch.setattr(tts, "_wanted", tts.DEFAULT_VOICE)
    monkeypatch.setattr(tts, "_speed", 1.0)
    return tmp_path


def a_piper_voice(folder, name, rate=22050):
    (folder / f"{name}.onnx").write_bytes(b"not really a model")
    (folder / f"{name}.onnx.json").write_text(
        json.dumps({"audio": {"sample_rate": rate}}), encoding="utf-8"
    )


# ---------------------------------------------------------------- naming


@pytest.mark.parametrize(
    "name, kokoro",
    [
        ("kokoro:af_heart", True),
        ("kokoro:bm_george", True),
        ("en_US-amy-medium", False),
        ("en_GB-cori-high", False),
    ],
)
def test_the_prefix_says_which_engine_speaks(name, kokoro):
    assert tts.is_kokoro(name) is kokoro


def test_an_old_settings_file_still_names_a_piper_voice():
    """Kokoro's names are prefixed precisely so nothing had to be migrated."""
    assert not tts.is_kokoro("en_US-amy-medium")
    assert tts.DEFAULT_VOICE == "en_US-amy-medium"


# ---------------------------------------------------------------- the rate


def test_the_fake_voice_reports_a_rate(monkeypatch):
    monkeypatch.setenv("DONNA_TTS", "fake")
    assert tts.sample_rate() == tts.SAMPLE_RATE
    audio = tts.synthesise("a sentence of some length")
    assert len(audio) / 2 / tts.sample_rate() > 0.2  # a plausible duration


def test_the_rate_follows_the_loaded_voice(monkeypatch):
    """The whole reason Kokoro can be offered at all."""
    monkeypatch.setattr(tts, "_rate", tts.KOKORO_RATE)
    assert tts.sample_rate() == 24000
    monkeypatch.setattr(tts, "_rate", 16000)
    assert tts.sample_rate() == 16000


def test_faking_overrides_whatever_was_loaded(monkeypatch):
    monkeypatch.setattr(tts, "_rate", tts.KOKORO_RATE)
    monkeypatch.setenv("DONNA_TTS", "fake")
    assert tts.sample_rate() == tts.SAMPLE_RATE  # the fake makes 22050 bytes


# ---------------------------------------------------------------- listing


def test_a_voice_at_another_rate_is_offered_now(_a_clean_voice_folder):
    """It used to be filtered out, because the window hardcoded 22050."""
    a_piper_voice(_a_clean_voice_folder, "en_US-amy-low", rate=16000)
    assert tts.installed_voices() == ["en_US-amy-low"]


def test_a_half_finished_download_is_not_a_voice(_a_clean_voice_folder):
    (_a_clean_voice_folder / "en_US-whoever-medium.onnx").write_bytes(b"partial")
    assert tts.installed_voices() == []


def test_unreadable_voice_settings_are_skipped(_a_clean_voice_folder):
    (_a_clean_voice_folder / "broken-medium.onnx").write_bytes(b"x")
    (_a_clean_voice_folder / "broken-medium.onnx.json").write_text("{not json", encoding="utf-8")
    assert tts.installed_voices() == []


def test_without_the_kokoro_model_only_piper_is_offered(_a_clean_voice_folder):
    """The normal case: 326 MB is an opt-in, not a requirement."""
    a_piper_voice(_a_clean_voice_folder, "en_US-amy-medium")
    assert tts.installed_voices() == ["en_US-amy-medium"]
    assert tts.kokoro_voices() == []


def test_a_broken_voice_bank_does_not_stop_the_panel(_a_clean_voice_folder):
    a_piper_voice(_a_clean_voice_folder, "en_US-amy-medium")
    tts.KOKORO_DIR.mkdir(parents=True)
    tts.KOKORO_MODEL.write_bytes(b"not an onnx file")
    tts.KOKORO_VOICES.write_bytes(b"not an npz file")
    assert tts.installed_voices() == ["en_US-amy-medium"]  # listed anyway


# ---------------------------------------------------------------- dispatch


def test_a_kokoro_voice_goes_to_kokoro(monkeypatch):
    monkeypatch.delenv("DONNA_TTS", raising=False)
    monkeypatch.setattr(tts, "_wanted", "kokoro:af_heart")
    monkeypatch.setattr(tts, "kokoro_synthesise", lambda text: b"kokoro said " + text.encode())
    monkeypatch.setattr(tts, "piper_synthesise", lambda text: pytest.fail("wrong engine"))
    assert tts.synthesise("hello") == b"kokoro said hello"


def test_a_piper_voice_goes_to_piper(monkeypatch):
    monkeypatch.delenv("DONNA_TTS", raising=False)
    monkeypatch.setattr(tts, "_wanted", "en_US-amy-medium")
    monkeypatch.setattr(tts, "piper_synthesise", lambda text: b"piper said " + text.encode())
    monkeypatch.setattr(tts, "kokoro_synthesise", lambda text: pytest.fail("wrong engine"))
    assert tts.synthesise("hello") == b"piper said hello"


def test_she_starts_in_the_voice_you_chose(monkeypatch, tmp_path):
    """She used to start in the default and show the one you picked."""
    import server
    import settings

    monkeypatch.setattr(settings, "PATH", tmp_path / "settings.json")
    (tmp_path / "settings.json").write_text(
        json.dumps({"voice": "kokoro:bf_emma", "speed": 1.3}), encoding="utf-8"
    )
    monkeypatch.setattr(tts, "installed_voices", lambda: ["kokoro:bf_emma", tts.DEFAULT_VOICE])
    loaded = {}
    monkeypatch.setattr(tts, "load", lambda: loaded.setdefault("voice", tts._wanted))

    server.start_as_she_was_left()
    assert loaded["voice"] == "kokoro:bf_emma"
    assert tts._speed == 1.3


def test_a_saved_voice_that_will_not_load_does_not_stop_her_starting(monkeypatch, tmp_path):
    import server
    import settings

    monkeypatch.setattr(settings, "PATH", tmp_path / "settings.json")
    (tmp_path / "settings.json").write_text(
        json.dumps({"voice": "kokoro:bf_emma", "speed": 1.0}), encoding="utf-8"
    )
    monkeypatch.setattr(tts, "installed_voices", lambda: ["kokoro:bf_emma", tts.DEFAULT_VOICE])
    tried = []

    def refuse():
        tried.append(tts._wanted)
        if tts._wanted != tts.DEFAULT_VOICE:
            raise tts.TtsError("that model is corrupt")

    monkeypatch.setattr(tts, "load", refuse)
    server.start_as_she_was_left()  # must not raise
    assert tried == ["kokoro:bf_emma", tts.DEFAULT_VOICE]


def test_a_missing_kokoro_install_is_a_polite_error(monkeypatch, _a_clean_voice_folder):
    monkeypatch.setattr(tts, "_kokoro", None)
    monkeypatch.setitem(__import__("sys").modules, "kokoro_onnx", None)
    with pytest.raises(tts.TtsError) as refused:
        tts.load_kokoro()
    assert "kokoro-onnx" in str(refused.value)
