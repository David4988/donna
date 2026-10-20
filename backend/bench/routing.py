"""Does she call the right tool exactly when she should -- and sound like speech?

Two scores, measured on the same questions:

  ROUTING -- did she call a tool when she should, and only then? This is the
             number the tool rules in agent.RULES were tuned on (30/40 with the
             old one-line prompt, 39-40/40 with today's), and the one that
             REGRESSED to 46/60 when a worked example was added. Run it every
             time the prompt or a tool definition changes.
  SPOKEN  -- of the replies that are words, how many read like speech rather
             than like a document: no markdown, no paths, not a lecture.

A second group, APPS, asks for apps that were never in the old hand-written
list of six. It measures whether she still reaches for open_app when the
schema no longer names any apps. A third, MACROS, runs with two known macros
on offer (bench/macros.toml) -- as does everything else here, since a user
with macros has one more tool for her to tell apart.

It talks to the real model, so Ollama has to be running. It is not a test:
pytest only collects tests/, and nothing here runs in CI.

    cd backend
    .venv\\Scripts\\python bench\\routing.py            # 2 repeats: "x/40"
    .venv\\Scripts\\python bench\\routing.py 3          # more repeats

This file lived in throwaway scratch folders twice and was lost both times.
It is the gate for adding tools (PLAN.md): if ROUTING drops below 38/40,
the tool list has outgrown the model.
"""

import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/

import agent  # noqa: E402
import llm  # noqa: E402
import macros  # noqa: E402
import tools  # noqa: E402

# Measure against two known macros, not whatever is in your own macros.toml:
# with any macros at all, run_macro is one more tool to tell apart.
macros.PATH = Path(__file__).resolve().parent / "macros.toml"

# (what you said, the tool she should call -- or None for a plain reply)
CASES = [
    ("Hello.", None),
    ("Hey, how are you?", None),
    ("Thanks, that's great.", None),
    ("Good morning.", None),
    ("You're awesome.", None),
    ("What's the capital of France?", None),
    ("How many days are in a leap year?", None),
    ("Explain what RAM is.", None),
    ("What does the acronym CPU stand for?", None),
    ("Tell me a short joke.", None),
    ("Open Notepad.", "open_app"),
    ("Launch Chrome for me.", "open_app"),
    ("Can you open the calculator?", "open_app"),
    ("Find my tax files.", "find_files"),
    ("Search my documents for anything called budget.", "find_files"),
    ("Do I have a file named resume anywhere?", "find_files"),
    ("Search the web for the latest Tauri release.", "web_search"),
    ("What's the weather in London right now?", "web_search"),
    ("Look up who won the 2026 Super Bowl.", "web_search"),
    ("Find me news about the RX 580.", "web_search"),
]

# Apps outside the old hand-written six. Before the catalogue, the schema
# listed exactly which apps existed; these show whether she still knows
# open_app is the tool once it lists none.
APPS = [
    ("Open WhatsApp.", "open_app"),
    ("Can you launch Steam?", "open_app"),
    ("Start Task Manager.", "open_app"),
    ("Open the control panel.", "open_app"),
]

# Your own macros (bench/macros.toml: "work setup" and "study mode").
# The paraphrase asks whether a name alone is enough for her to find one; the
# last asks whether a macro that happens to contain VS Code steals the plain
# request for VS Code.
MACROS = [
    ("Run work setup.", "run_macro"),
    ("Start study mode.", "run_macro"),
    ("Set up my desk for work.", "run_macro"),
    ("Open VS Code.", "open_app"),
]

MARKDOWN = re.compile(r"\*\*|^\s*[-*+]\s|^\s*\d+\.\s|```|^#", re.MULTILINE)
# A drive letter or a web address. (An earlier copy wrote this without the
# raw string, lost the backslash, and so only ever matched the text "C:|".)
PATHS = re.compile(r"\b[A-Za-z]:\\|https?://")
TOO_LONG = 400  # characters; about three spoken sentences


def spoken_problems(text):
    """Why this reply would sound like someone reading a document aloud."""
    problems = []
    if MARKDOWN.search(text):
        problems.append("markdown")
    if PATHS.search(text):
        problems.append("path/url")
    if len(text) > TOO_LONG:
        problems.append(f"long({len(text)})")
    return problems


def called(reply):
    """Which tool she reached for first, or None if she just answered."""
    calls = reply.get("tool_calls") or []
    return calls[0]["function"]["name"] if calls else None


def score(label, cases, prompt, repeats):
    routed = wrong_tool = spoken_ok = spoken_n = total = 0
    failures = []
    started = time.time()
    for attempt in range(repeats):
        for text, wanted in cases:
            reply = llm.ask(
                [{"role": "system", "content": prompt}, {"role": "user", "content": text}],
                tools.offered(),
            )
            got = called(reply)
            total += 1
            if (got is None) == (wanted is None):
                routed += 1
                if got != wanted:
                    wrong_tool += 1
                    failures.append(f"WRONG TOOL {got} (wanted {wanted}) <- {text!r}")
            else:
                failures.append(f"ROUTE {'called ' + got if got else 'no tool'} <- {text!r}")
            if got is None:  # style only applies to replies that are words
                body = reply.get("content") or ""
                spoken_n += 1
                problems = spoken_problems(body)
                if not problems:
                    spoken_ok += 1
                elif attempt == 0:
                    failures.append(f"STYLE {problems} <- {text!r}: {body[:80]!r}")

    print(f"\n=== {label} ===  ({time.time() - started:.0f}s)")
    print(f"  ROUTING {routed}/{total}   (wrong tool, counted as routed: {wrong_tool})")
    if spoken_n:
        print(f"  SPOKEN  {spoken_ok}/{spoken_n} of the spoken replies are clean")
    for failure in dict.fromkeys(failures):  # each distinct failure once
        print(f"    - {failure}")
    return routed, total


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    repeats = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    prompt = agent.system_prompt()
    names = [t["function"]["name"] for t in tools.offered()]
    print(f"model={llm.active_model}  tools={len(names)} {names}  repeats={repeats}")
    print(f"prompt: {len(prompt)} characters")
    score("ROUTING (the gate)", CASES, prompt, repeats)
    score("APPS (beyond the old six)", APPS, prompt, repeats)
    score("MACROS (your own recipes)", MACROS, prompt, repeats)
