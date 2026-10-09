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
