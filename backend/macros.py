"""The only file that knows where your macros live.

    load(functions)   your macros, checked: {name: [(tool, args), ...]}
    ensure()          put a template on disk so there is something to fill in

A macro is a name and a list of steps, and every step is one of her own tools
with that tool's arguments. You write them; she runs them. "Run work setup"
becomes ONE tool call that does every step, instead of a trip through the
model per step -- 4 to 8 seconds each, and capped at agent.MAX_TOOL_ROUNDS
= 5 a reply, so a six-step recipe used to be impossible rather than slow.

Deliberately not a scripting language: steps run in order, there is no if
and no loop, and a macro can't run another macro. A recipe that needs a
decision has stopped being configuration. It belongs in tools.py as a tool
of its own, which then becomes usable as a step here without changing this
file.

Like settings.json it lives in ~/.cache/donna/, not in this public repo.
"""

import inspect
import logging
import os
import tomllib
from pathlib import Path

import once

PATH = Path(os.environ.get("DONNA_MACROS", "~/.cache/donna/macros.toml")).expanduser()

# The one tool a step may never use: if macros could run macros, a recipe
# could end up running itself forever.
SELF = "run_macro"


def load(functions):
    """Your macros, every step checked against the tools that exist.

    `functions` is tools.FUNCTIONS. It is passed in rather than imported
    because tools.py imports this file. Read fresh on every call -- which is
    every turn -- so an edit applies to your next sentence. It's a small
    file; the read costs nothing next to a trip to the model.
    """
    try:
        with PATH.open("rb") as file:
            written = tomllib.load(file)
    except FileNotFoundError:
        return {}
    except OSError as error:
        once.warn(f"Couldn't read {PATH}: {error}. Carrying on with no macros.")
        return {}
    except tomllib.TOMLDecodeError as error:
        once.warn(f"{PATH.name} isn't valid TOML ({error}), so no macro will run until it's fixed.")
        return {}

    recipes = {}
    for name, body in written.items():
        steps = body.get("steps") if isinstance(body, dict) else None
        if not isinstance(steps, list):
            once.warn(f'Macro "{name}" in {PATH.name} has no list of steps, so it was skipped.')
            continue
        # Like settings.clean(): drop what's wrong, keep the rest. One typo
        # shouldn't cost you the other five steps of a recipe.
        kept = [check(name, number, step, functions) for number, step in enumerate(steps, 1)]
        kept = [step for step in kept if step]
        if kept:
            recipes[name] = kept
        else:
            once.warn(f'Macro "{name}" in {PATH.name} has no step that can run, so it was skipped.')
    return recipes


def check(name, number, step, functions):
    """One step as (tool, args), or None with the reason in the log.

    Wrong arguments are caught here, when the file is read, rather than
    halfway through a run: `ap = "Chrome"` fails before VS Code has opened.
    """

    def skip(why):
        once.warn(f'Skipping step {number} of macro "{name}": {why}.')

    if not isinstance(step, dict) or not isinstance(step.get("do"), str):
        return skip('every step needs do = "<tool>"')
    tool = step["do"]
    args = {key: value for key, value in step.items() if key != "do"}
    if tool == SELF:
        return skip("a macro can't run another macro")
    if tool not in functions:
        others = ", ".join(known for known in functions if known != SELF)
        return skip(f"there's no tool called '{tool}' (there is {others})")
    try:
        inspect.signature(functions[tool]).bind(**args)
    except TypeError as error:  # "missing a required argument: 'app'"
        return skip(f"wrong arguments for {tool}: {error}")
    return tool, args


def ensure():
    """Write the template if nothing is there. Never overwrites your macros.

    The template defines none -- its example is commented out -- so until you
    write one she behaves exactly as she did before macros existed.
    """
    if PATH.exists():
        return
    try:
        PATH.parent.mkdir(parents=True, exist_ok=True)
        PATH.write_text(TEMPLATE, encoding="utf-8")
        logging.info("Write your own macros here: %s", PATH)
    except OSError as error:  # not being able to write it must not stop her
        logging.warning("Couldn't write %s: %s", PATH, error)


TEMPLATE = """\
# Your macros. One sentence runs a whole list of steps: say "run work setup"
# and she does every step under it, in order, as one action.
#
# Name a macro the way you'll say it. Each step is one of her tools, with
# that tool's own arguments:
#
#   { do = "open_app",   app = "Visual Studio Code" }   anything in your Start Menu
#   { do = "find_files", query = "resume" }             by file name
#   { do = "web_search", query = "weather today" }
#
# Steps run in order. If one fails the rest still run, and she tells you which
# one didn't. There is no if and no loop, and a macro can't run another macro.
#
# She reads this file every time you speak, so an edit works straight away.
# To try the example, remove the # from the start of its lines.

# ["work setup"]
# steps = [
#   { do = "open_app", app = "Visual Studio Code" },
#   { do = "open_app", app = "Google Chrome" },
#   { do = "open_app", app = "Terminal" },
# ]
"""
