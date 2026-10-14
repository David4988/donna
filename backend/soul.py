"""The only file that knows where DONNA's character lives.

    character()   who she is, in her own editable file
    ensure()      put the default on disk so there is something to edit

The idea is taken from Nous Research's Hermes Agent (MIT), which keeps its
whole persona in a `SOUL.md` at the repo root. The useful part is not the
filename: it is that an assistant's character is *data*, so it can be changed
by whoever is talking to her, without a code change and without waiting for
anyone. That is the one thing in a 1.2 GB platform that ports cleanly to
1,500 lines of synchronous Python.

What it deliberately does NOT own is the rules in agent.py. Her character is
tone; those rules are load-bearing and measured -- the tool-discipline
paragraph took routing from 30/40 to 39/40 on qwen3.5:4b, and a worked
example once took it DOWN to 46/60. If this file could replace them, the
first interesting persona anyone wrote would quietly stop her opening files.
So agent.py always appends them and this can only change who she sounds like.

Hermes's own SOUL.md is 667 bytes -- about 167 tokens -- and it is almost
entirely about what not to do. That is the model to copy. See LONG_ENOUGH.
"""

import logging
import os
from pathlib import Path

import once

PATH = Path(os.environ.get("DONNA_SOUL", "~/.cache/donna/SOUL.md")).expanduser()

# Her character if there is no file, which is also what ensure() writes.
# Short on purpose: Hermes does this in ~167 tokens, and the only other
# example to hand -- a Tony Stark tribute -- spent 1,114 tokens to be worse.
DEFAULT = (
    "You are DONNA, a helpful assistant running on the user's own computer. "
    "You are calm and brief, and you would rather say one useful sentence than "
    "three polite ones. No filler: never open with 'Great question' or restate "
    "what was asked. Say plainly when you don't know something or can't do it, "
    "rather than guessing to sound helpful."
)

# Past this, say something. The prompt prefix is re-read whenever the
# conversation is cold, at a measured 169 tokens/second, so 400 tokens of
# character is about 2.4 seconds before she speaks on the first turn of a
# conversation. Caching hides it after that, which is why this warns rather
# than refuses -- but the good examples are all far shorter than this.
LONG_ENOUGH = 1600  # characters, so roughly 400 tokens


def character():
    """Who she is. Her own file if she has one, the default if not."""
    try:
        written = PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return DEFAULT
    except OSError as error:
        once.warn(f"Couldn't read {PATH}: {error}. Using her default character.")
        return DEFAULT

    # Markdown comments and headings are for whoever is editing the file, not
    # for her: a line beginning # is a note to a human.
    lines = [line for line in written.splitlines() if not line.lstrip().startswith("#")]
    written = "\n".join(lines).strip()
    if not written:
        return DEFAULT

    if len(written) > LONG_ENOUGH:
        once.warn(
            f"{PATH.name} is {len(written)} characters, about {len(written) // 4} tokens. "
            f"That is roughly {len(written) / 4 / 169:.1f}s of extra thinking on the first "
            f"turn of a conversation, and a long character is also measurably worse at "
            f"leaving her tools alone. For comparison, Hermes Agent does this in 167 tokens."
        )
    return written


def ensure():
    """Write the default where it can be found, if nothing is there yet.

    Without this her character is editable in principle and invisible in
    practice: nobody edits a file they have not been told about.
    """
    if PATH.exists():
        return
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(HOW_TO_EDIT + DEFAULT + "\n", encoding="utf-8")
        logging.info("Her character is yours to edit: %s", PATH)
    except OSError as error:  # not being able to write it must not stop her
        logging.warning("Couldn't write %s: %s", PATH, error)


HOW_TO_EDIT = """\
# This is DONNA's character. Edit it and she changes on your next sentence --
# no restart. Lines starting with # are notes to you and she never sees them.
#
# Keep it short. Hermes Agent does this in about 167 tokens and reads better
# for it; the longest example we measured spent 1,114 tokens to sound worse,
# and a long character measurably degrades her ability to leave her tools
# alone. Describe how she talks, not what her tools are -- the rules about
# when to use a tool live in the code, are measured, and are always applied
# on top of whatever you write here.
#
# Delete everything below to go back to the default.

"""
