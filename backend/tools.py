"""Everything DONNA can do to your computer.

If it isn't in this file, the LLM can't do it. There is deliberately no
"run a command" tool, and text written by the LLM never reaches a shell.

- Each tool is a plain function that returns text (errors start with "Error:").
- TOOLS describes the tools to the LLM (OpenAI "function" format).
- run_tool() is the only way the agent runs a tool.
"""

import os
import subprocess
import sys
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"


# ---------------------------------------------------------------- open_app

# The only apps DONNA may open: key -> (display name, what Windows' `start` runs).
# The LLM picks a key; the target always comes from this table.
APPS = {
    "vscode": ("Visual Studio Code", "code"),
    "chrome": ("Google Chrome", "chrome"),
    "notepad": ("Notepad", "notepad"),
    "terminal": ("Windows Terminal", "wt"),
    "explorer": ("File Explorer", "explorer"),
    "calculator": ("Calculator", "calc"),
}

# Other names people (or the LLM) use for the same apps.
ALIASES = {
    "vs code": "vscode",
    "visual studio code": "vscode",
    "code": "vscode",
    "google chrome": "chrome",
    "browser": "chrome",
    "windows terminal": "terminal",
    "file explorer": "explorer",
    "files": "explorer",
    "calc": "calculator",
}


def open_app(app):
    key = app.strip().lower()
    key = ALIASES.get(key, key)
    if key not in APPS:
        return f"Error: I can't open '{app}'. Apps I know: {', '.join(APPS)}."

    name, target = APPS[key]
    if not IS_WINDOWS:
        return f"Error: opening apps only works on Windows for now (wanted to open {name})."

    # `start` finds apps the same way the Win+R box does.
    subprocess.Popen(["cmd", "/c", "start", "", target])
    return f"Opened {name}."


# ---------------------------------------------------------------- find_files

# Read-only: returns file names and folders, never file contents.
SEARCH_FOLDERS = [Path.home() / "Desktop", Path.home() / "Documents", Path.home() / "Downloads"]
SKIP_FOLDERS = {"node_modules", "__pycache__", "venv", "AppData"}  # plus any hidden ".folder"
IGNORED_WORDS = {"my", "the", "all", "file", "files"}  # "find my TrialGuard files" -> "trialguard"
MAX_RESULTS = 10


def find_files(query):
    words = [w for w in query.lower().split() if w not in IGNORED_WORDS]
    if not words:
        return "Error: tell me what to search for."

    matches = []
    for folder in SEARCH_FOLDERS:
        for current, subfolders, filenames in os.walk(folder):
            # Editing `subfolders` in place tells os.walk not to go into those folders.
            subfolders[:] = [name for name in subfolders if not skip_folder(name)]
            for filename in filenames:
                if all(word in filename.lower() for word in words):
                    matches.append(Path(current) / filename)

    if not matches:
        places = ", ".join(folder.name for folder in SEARCH_FOLDERS)
        return f"No files matching '{query}' in {places}."

    matches.sort(key=modified_time, reverse=True)  # newest first
    shown = matches[:MAX_RESULTS]
    header = f"Found {len(matches)} file(s) matching '{query}'"
    if len(matches) > len(shown):
        header += f", showing the newest {len(shown)}"
    return header + ":\n" + "\n".join(f"{path.name}  ({path.parent})" for path in shown)


def skip_folder(name):
    return name in SKIP_FOLDERS or name.startswith(".")


def modified_time(path):
    try:
        return path.stat().st_mtime
    except OSError:  # e.g. a broken shortcut
        return 0


# ---------------------------------------------------------------- for the LLM

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open an application on the user's computer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app": {"type": "string", "enum": list(APPS), "description": "Which app."}
                },
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_files",
            "description": "Search the user's Desktop, Documents and Downloads by file name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Words that appear in the file name, e.g. 'trialguard'.",
                    }
                },
                "required": ["query"],
            },
        },
    },
]

FUNCTIONS = {"open_app": open_app, "find_files": find_files}


def run_tool(name, args):
    """Run a tool by name. Never raises: problems come back as "Error: ..." text."""
    function = FUNCTIONS.get(name)
    if function is None:
        return f"Error: there is no tool called '{name}'."
    if not isinstance(args, dict):
        return "Error: tool arguments must be a JSON object."
    try:
        return function(**args)
    except TypeError as error:
        return f"Error: wrong arguments for {name}: {error}"
    except Exception as error:
        return f"Error: {name} failed: {error}"
