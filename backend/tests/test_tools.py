import os
import subprocess

import pytest

import tools


@pytest.fixture
def launched(monkeypatch):
    """Pretend we're on Windows and record what would be launched."""
    calls = []
    monkeypatch.setattr(tools, "IS_WINDOWS", True)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kwargs: calls.append((args, kwargs)))
    return calls


@pytest.mark.parametrize("name", ["vscode", "VS Code", "visual studio code", " Code "])
def test_open_known_app(launched, name):
    assert tools.open_app(name) == "Opened Visual Studio Code."
    # The command comes from the APPS table, not from the model, and uses no shell=True.
    assert launched == [(["cmd", "/c", "start", "", "code"], {})]


def test_unknown_app_is_refused(launched):
    result = tools.open_app("rm -rf /")
    assert result.startswith("Error: I can't open")
    assert launched == []


def test_open_app_on_linux_is_a_polite_error(monkeypatch):
    monkeypatch.setattr(tools, "IS_WINDOWS", False)
    assert "only works on Windows" in tools.open_app("chrome")


def test_llm_is_only_offered_known_apps():
    [open_app] = [t for t in tools.TOOLS if t["function"]["name"] == "open_app"]
    assert open_app["function"]["parameters"]["properties"]["app"]["enum"] == list(tools.APPS)


def test_run_tool_unknown_tool():
    assert tools.run_tool("run_shell", {"command": "del *"}) == (
        "Error: there is no tool called 'run_shell'."
    )


@pytest.mark.parametrize("args", [None, "vscode", {"wrong": "arg"}, {}])
def test_run_tool_bad_arguments(launched, args):
    assert tools.run_tool("open_app", args).startswith("Error:")
    assert launched == []


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake home folder with some files in it."""
    files = {
        "Documents/TrialGuard/TrialGuard_Proposal.pdf": 300,
        "Documents/notes/trialguard-notes.md": 200,
        "Downloads/TrialGuard_Setup.exe": 100,
        "Downloads/holiday.jpg": 100,
        "Documents/code/node_modules/trialguard.js": 400,  # skipped folder
        "Desktop/.secret/trialguard.txt": 400,  # hidden folder
    }
    for name, age in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
        os.utime(path, (1_000_000 - age, 1_000_000 - age))  # bigger age = older
    monkeypatch.setattr(
        tools, "SEARCH_FOLDERS", [tmp_path / "Desktop", tmp_path / "Documents", tmp_path / "Downloads"]
    )
    return tmp_path


def test_find_files_newest_first(home):
    result = tools.find_files("my TrialGuard files")
    lines = result.splitlines()
    assert lines[0] == "Found 3 file(s) matching 'my TrialGuard files':"
    assert [line.split("  ")[0] for line in lines[1:]] == [
        "TrialGuard_Setup.exe",
        "trialguard-notes.md",
        "TrialGuard_Proposal.pdf",
    ]


def test_find_files_skips_node_modules_and_hidden_folders(home):
    result = tools.find_files("trialguard")
    assert "node_modules" not in result
    assert ".secret" not in result


def test_find_files_all_words_must_match(home):
    assert "TrialGuard_Proposal.pdf" in tools.find_files("trialguard proposal")
    assert "notes" not in tools.find_files("trialguard proposal")


def test_find_files_limit(home, monkeypatch):
    monkeypatch.setattr(tools, "MAX_RESULTS", 2)
    result = tools.find_files("trialguard")
    assert "showing the newest 2" in result
    assert len(result.splitlines()) == 3


def test_find_files_nothing_found(home):
    assert tools.find_files("tax return").startswith("No files matching")


def test_find_files_needs_a_query(home):
    assert tools.find_files("my files").startswith("Error:")
