"""The only file that knows where DONNA's settings live.

    current()          what she is set to now
    update(changes)    change some of it, and save

Settings live in a small JSON file next to her voice, not in the browser.
chat.py has no browser at all, so a browser-owned setting would mean the
terminal client and the window disagreeing about which voice is playing --
and it would make the frontend the source of truth for something, which is
the one thing the frontend is not supposed to be.
"""

import json
import logging
import os
from pathlib import Path

import tts

PATH = Path(os.environ.get("DONNA_SETTINGS", "~/.cache/donna/settings.json")).expanduser()

SPEED = (0.5, 2.0)  # how fast she may be asked to talk


class SettingsError(Exception):
    """The settings file couldn't be written."""


def defaults():
    # DONNA_VOICE still picks the voice she STARTS with; once you choose one
    # in the window, the file wins. Otherwise the panel would show one voice
    # while you listened to another.
    return {"voice": tts.DEFAULT_VOICE, "speed": 1.0}


def current():
    """What she is set to, with anything missing or broken falling back."""
    settings = defaults()
    try:
        saved = json.loads(PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return settings
    except (OSError, ValueError) as error:
        # A half-written or hand-edited file must not stop her starting.
        logging.warning("Ignoring %s: %s", PATH, error)
        return settings
    settings.update(clean(saved) if isinstance(saved, dict) else {})
    return settings


def clean(changes):
    """Keep only the settings we know, in the range we allow."""
    kept = {}
    voices = tts.installed_voices()
    if "voice" in changes and changes["voice"] in voices:
        kept["voice"] = changes["voice"]
    elif "voice" in changes:
        logging.warning("No voice called %r is installed.", changes["voice"])
    try:
        kept["speed"] = min(SPEED[1], max(SPEED[0], float(changes["speed"])))
    except (KeyError, TypeError, ValueError):
        pass
    return kept


def update(changes):
    """Merge in what changed, save, and return everything."""
    settings = current()
    settings.update(clean(changes))
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        # Write beside it and rename, so a crash can't leave half a file.
        beside = PATH.with_suffix(".json.new")
        beside.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        os.replace(beside, PATH)
    except OSError as error:
        raise SettingsError(f"Couldn't save your settings to {PATH}: {error}") from None
    return settings
