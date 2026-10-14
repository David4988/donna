"""The only file that knows where what DONNA knows about YOU lives.

    context()   who you are and what you are doing, for the prompt
    ensure()    put editable templates on disk so there is something to fill in

Two files, not one, and the split is the point:

    ABOUT_ME.md    who you are. Changes in years: name, how you like to be
                   answered, what you are working toward, the hardware and
                   money constraints that are actually real.
    USER_STATE.md  what is happening now. Changes in weeks: which project is
                   live, what is due, what you are stuck on.

One file would rot. A biography and a status report have completely different
half-lives, and the failure is specific and annoying: she keeps treating a
finished project as active and last term's timetable as today's.

NEITHER FILE IS IN THIS REPOSITORY, and that is deliberate -- the repo is
public. They live next to settings.json in ~/.cache/donna/, the templates
here contain nobody's details, and what you write stays on this machine. It
does reach the model, but the model is Ollama on localhost, so "local-first"
is true here rather than aspirational.

Unlike SOUL.md, a '#' line is NOT a note to the editor: these are long
documents where '#' is a markdown heading and throwing those away would
destroy the structure. Use an HTML comment for notes -- markdown hides it
anyway -- and this strips those.
"""

import logging
import os
import re
from pathlib import Path

import once

HOME = Path(os.environ.get("DONNA_ABOUT_DIR", os.path.expanduser("~/.cache/donna")))
ABOUT_PATH = HOME / "ABOUT_ME.md"
STATE_PATH = HOME / "USER_STATE.md"

COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)

# An untouched template is all structure and no information. Sending "-
# **Name:**" to the model is a hundred tokens of empty scaffolding that
# answers nothing and invites it to wonder why your name is blank, so a file
# with nothing filled in counts as no file at all.
HEADING = re.compile(r"^\s*#")
EMPTY_FIELD = re.compile(r"^\s*[-*]\s.*:\s*\**\s*$")  # "- **Name:**", "- Where:"


def says_anything(text):
    """Is there anything in here beyond headings and unfilled fields?"""
    for line in text.splitlines():
        line = line.strip()
        if line and not HEADING.match(line) and not EMPTY_FIELD.match(line):
            return True
    return False

# What the model is told these documents are. Without a frame it reads a
# biography as something to talk about rather than something to use.
HEADINGS = {
    ABOUT_PATH: "Here is who you are talking to. Use it when it is relevant and "
    "don't recite it back at them.",
    STATE_PATH: "Here is what they are working on right now. Prefer this over "
    "anything older if the two disagree.",
}

# Past this, say something. Measured: prompt processing is 169 tokens/second
# and the tool definitions are only 239 tokens, so a long biography both costs
# seconds on the first turn of a conversation and competes with the tools for
# a 4B model's attention -- which is the thing that has already been measured
# breaking tool routing once. 1200 tokens of context is about 7 seconds cold.
LOUD_ENOUGH = 4800  # characters, so roughly 1200 tokens


def read(path):
    """One document, stripped of its editor notes. "" if there isn't one."""
    try:
        written = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as error:
        once.warn(f"Couldn't read {path}: {error}. Carrying on without it.")
        return ""
    written = COMMENT.sub("", written).strip()
    # Keep the headings when there IS something to frame -- they make a long
    # document readable -- but treat a file of nothing but headings as empty.
    return written if says_anything(written) else ""


def context():
    """Everything she knows about you, ready to go in the prompt.

    Empty when neither file exists, so she behaves exactly as she did before
    this existed rather than apologising about missing context.
    """
    parts = []
    for path in (ABOUT_PATH, STATE_PATH):
        written = read(path)
        if written:
            parts.append(f"{HEADINGS[path]}\n\n{written}")
    if not parts:
        return ""

    together = "\n\n".join(parts)
    if len(together) > LOUD_ENOUGH:
        once.warn(
            f"What she knows about you is {len(together)} characters, about "
            f"{len(together) // 4} tokens. That is roughly "
            f"{len(together) / 4 / 169:.1f}s of extra thinking on the first turn of a "
            f"conversation, and it is {len(together) // 239}x the size of her tool "
            f"definitions, which measurably competes with them for a 4B model's "
            f"attention. Re-run the routing benchmark, or move the detail into "
            f"USER_STATE.md and keep ABOUT_ME.md to what is always true."
        )
    return together


def ensure():
    """Write the templates if nothing is there. Never overwrites your words."""
    for path, template in ((ABOUT_PATH, ABOUT_TEMPLATE), (STATE_PATH, STATE_TEMPLATE)):
        if path.exists():
            continue
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(template, encoding="utf-8")
            logging.info("Tell her about yourself: %s", path)
        except OSError as error:
            logging.warning("Couldn't write %s: %s", path, error)


ABOUT_TEMPLATE = """\
<!--
  Who you are. This changes in years, not weeks -- put anything that moves
  faster in USER_STATE.md, or she will keep believing last month's situation.

  She reads this every turn, so an edit lands on your next sentence. Keep it
  to what actually changes how she should answer you: your name, how you like
  to be told things, the constraints that are real (hardware, money, time),
  and what you are working toward. A fact she can never act on is just tokens.

  This file is on your machine only. It is not in the repository, which is
  public. It does go into the model's prompt -- that model is Ollama on
  localhost, so it does not leave this computer.

  Delete everything below to go back to her knowing nothing about you.
-->

# About me

- **Name:**
- **Where I am:**
- **What I do:**

## How I want to be answered

## What is actually constrained

## What I am working toward
"""

STATE_TEMPLATE = """\
<!--
  What is happening NOW. Expect to edit this often; that is its job.

  If something here has been true for a year, it belongs in ABOUT_ME.md. If
  something in ABOUT_ME.md keeps going stale, it belongs here.
-->

# Right now

## What I am building

## What is due

## What I am stuck on
"""
