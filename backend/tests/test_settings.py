import json

import pytest

import settings
import tts


@pytest.fixture(autouse=True)
def somewhere_harmless(monkeypatch, tmp_path):
    """Never touch the real settings file, and pretend two voices exist."""
    monkeypatch.setattr(settings, "PATH", tmp_path / "settings.json")
    monkeypatch.setattr(tts, "installed_voices", lambda: ["en_US-amy-medium", "en_GB-alan-medium"])
    monkeypatch.setattr(tts, "DEFAULT_VOICE", "en_US-amy-medium")


def test_with_no_file_she_uses_the_defaults():
    assert settings.current() == {"voice": "en_US-amy-medium", "speed": 1.0}


def test_a_change_survives(tmp_path):
    settings.update({"speed": 1.5})
    assert settings.current()["speed"] == 1.5
    assert json.loads((settings.PATH).read_text())["speed"] == 1.5


def test_only_part_of_it_need_change():
    settings.update({"speed": 1.5})
    settings.update({"voice": "en_GB-alan-medium"})
    assert settings.current() == {"voice": "en_GB-alan-medium", "speed": 1.5}


@pytest.mark.parametrize("asked, got", [(99, 2.0), (0.01, 0.5), ("1.25", 1.25), (2.0, 2.0)])
def test_speed_is_clamped_to_something_listenable(asked, got):
    assert settings.update({"speed": asked})["speed"] == got


def test_a_voice_that_is_not_installed_is_refused():
    assert settings.update({"voice": "nonexistent"})["voice"] == "en_US-amy-medium"


def test_nonsense_is_ignored_rather_than_stored():
    saved = settings.update({"speed": "fast", "favourite_colour": "gold"})
    assert saved == {"voice": "en_US-amy-medium", "speed": 1.0}


def test_a_corrupt_file_does_not_stop_her_starting():
    """Half a file must fall back to the defaults, not raise on import."""
    settings.PATH.write_text("{this is not json")
    assert settings.current() == {"voice": "en_US-amy-medium", "speed": 1.0}
    assert settings.update({"speed": 1.2})["speed"] == 1.2  # and it heals
