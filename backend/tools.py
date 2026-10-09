"""Everything DONNA can do to your computer.

If it isn't in this file, the LLM can't do it. There is deliberately no
"run a command" tool, and text written by the LLM never reaches a shell.

- Each tool is a plain function that returns text (errors start with "Error:").
- TOOLS describes the tools to the LLM (OpenAI "function" format).
- run_tool() is the only way the agent runs a tool.
"""

import subprocess
import sys

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
]

FUNCTIONS = {"open_app": open_app}


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
