import logging
import re

import pytest

import agent
import macros
import once
import tools

WORK_SETUP = """
["work setup"]
steps = [
  { do = "open_app", app = "Visual Studio Code" },
  { do = "open_app", app = "Google Chrome" },
]

["study mode"]
steps = [{ do = "find_files", query = "lecture notes" }]
"""


@pytest.fixture(autouse=True)
def macro_file(monkeypatch, tmp_path):
    """Never the real ~/.cache/donna/macros.toml: these tests write to it."""
    monkeypatch.setattr(macros, "PATH", tmp_path / "macros.toml")
    monkeypatch.setattr(once, "_warned", set())
    return macros.PATH


@pytest.fixture
def ran(monkeypatch):
    """Her tools, replaced by ones that only record what they were asked."""
    calls = []

    def open_app(app):
        calls.append(("open_app", app))
        return f"Opened {app}."

    def find_files(query):
        calls.append(("find_files", query))
        return f"Found 2 file(s) matching '{query}':\nnotes.pdf  (Documents)\nweek1.md  (Documents)"

    monkeypatch.setitem(tools.FUNCTIONS, "open_app", open_app)
    monkeypatch.setitem(tools.FUNCTIONS, "find_files", find_files)
    return calls


def write(path, text):
    path.write_text(text, encoding="utf-8")


# ---- reading the file


def test_no_file_means_no_macros_and_nothing_new_offered():
    """Until you write one, she behaves exactly as before macros existed."""
    assert macros.load(tools.FUNCTIONS) == {}
    assert tools.offered() == tools.TOOLS


def test_your_macros_are_read_as_steps(macro_file):
    write(macro_file, WORK_SETUP)
    assert macros.load(tools.FUNCTIONS) == {
        "work setup": [
            ("open_app", {"app": "Visual Studio Code"}),
            ("open_app", {"app": "Google Chrome"}),
        ],
        "study mode": [("find_files", {"query": "lecture notes"})],
    }


def test_broken_toml_means_no_macros_and_one_warning(macro_file, caplog):
    write(macro_file, '["work setup"\nsteps = [')
    with caplog.at_level(logging.WARNING):
        assert macros.load(tools.FUNCTIONS) == {}
        assert macros.load(tools.FUNCTIONS) == {}  # read every turn; said once
    assert len(caplog.records) == 1
    assert "isn't valid TOML" in caplog.text


def test_an_unreadable_file_means_no_macros(macro_file):
    macro_file.mkdir()  # a folder where the file should be: reading it fails
    assert macros.load(tools.FUNCTIONS) == {}


@pytest.mark.parametrize(
    "bad_step, why",
    [
        ('{ do = "delete_everything", path = "C:/" }', "no tool called 'delete_everything'"),
        ('{ do = "run_macro", name = "work setup" }', "can't run another macro"),
        ('{ do = "open_app", ap = "Chrome" }', "wrong arguments for open_app"),
        ('{ app = "Chrome" }', 'needs do = "<tool>"'),
        ('"open chrome"', 'needs do = "<tool>"'),
    ],
)
def test_a_bad_step_is_dropped_and_the_rest_kept(macro_file, caplog, bad_step, why):
    write(
        macro_file,
        f'["work setup"]\nsteps = [\n  {bad_step},\n  {{ do = "open_app", app = "Notepad" }},\n]\n',
    )
    with caplog.at_level(logging.WARNING):
        recipes = macros.load(tools.FUNCTIONS)
    assert recipes == {"work setup": [("open_app", {"app": "Notepad"})]}
    assert why in caplog.text
    assert "step 1" in caplog.text  # which step, so you can find it


def test_a_macro_with_no_good_steps_is_dropped(macro_file, caplog):
    write(macro_file, '["broken"]\nsteps = [{ do = "nope" }]\n' + WORK_SETUP)
    with caplog.at_level(logging.WARNING):
        recipes = macros.load(tools.FUNCTIONS)
    assert list(recipes) == ["work setup", "study mode"]
    assert 'Macro "broken"' in caplog.text


def test_a_macro_without_a_list_of_steps_is_skipped(macro_file):
    write(macro_file, 'steps = "open chrome"\n["notes"]\ntitle = "x"\n' + WORK_SETUP)
    assert list(macros.load(tools.FUNCTIONS)) == ["work setup", "study mode"]


# ---- running one


def test_steps_run_in_order_as_one_tool_call(macro_file, ran):
    write(macro_file, WORK_SETUP)
    result = tools.run_macro("work setup")
    assert ran == [("open_app", "Visual Studio Code"), ("open_app", "Google Chrome")]
    assert result == (
        "Ran your 'work setup' macro:\n"
        "- Opened Visual Studio Code.\n"
        "- Opened Google Chrome."
    )


def test_a_failing_step_does_not_stop_the_rest(macro_file, ran, monkeypatch):
    def broken(query):
        raise RuntimeError("no internet")

    monkeypatch.setitem(tools.FUNCTIONS, "web_search", broken)
    write(
        macro_file,
        '["morning"]\nsteps = [\n'
        '  { do = "web_search", query = "weather" },\n'
        '  { do = "open_app", app = "Google Chrome" },\n]\n',
    )
    result = tools.run_macro("morning")
    assert "- Error: web_search failed: no internet" in result
    assert result.endswith("- Opened Google Chrome.")
    assert ran == [("open_app", "Google Chrome")]


def test_a_long_step_result_stays_under_its_own_bullet(macro_file, ran):
    write(macro_file, WORK_SETUP)
    assert tools.run_macro("study mode").splitlines()[1:] == [
        "- Found 2 file(s) matching 'lecture notes':",
        "  notes.pdf  (Documents)",
        "  week1.md  (Documents)",
    ]


@pytest.mark.parametrize("said", ["work setup", "Work Setup", "run work setup", "work-setup"])
def test_the_name_needs_only_the_right_words(macro_file, ran, said):
    write(macro_file, WORK_SETUP)
    assert tools.run_macro(said).startswith("Ran your 'work setup' macro:")


def test_an_unknown_macro_runs_nothing_and_says_what_exists(macro_file, ran):
    write(macro_file, WORK_SETUP)
    assert tools.run_macro("good night") == (
        "Error: you have no macro called 'good night'. Your macros are: work setup, study mode."
    )
    assert ran == []


def test_with_no_macros_at_all_run_macro_is_a_plain_error(ran):
    assert tools.run_macro("work setup") == "Error: you have no macro called 'work setup'."


# ---- what the model is shown


def test_the_model_is_offered_your_macro_names_and_nothing_else(macro_file):
    write(macro_file, WORK_SETUP)
    offered = tools.offered()
    assert offered[: len(tools.TOOLS)] == tools.TOOLS
    [run_macro] = offered[len(tools.TOOLS) :]
    assert run_macro["function"]["name"] == "run_macro"
    assert run_macro["function"]["parameters"]["properties"]["name"]["enum"] == [
        "work setup",
        "study mode",
    ]


def test_the_rules_she_was_measured_on_do_not_change(macro_file):
    """The names travel in the tool definition, never in the system prompt."""
    before = agent.system_prompt()
    write(macro_file, WORK_SETUP)
    assert agent.system_prompt() == before


def test_she_runs_a_macro_end_to_end_with_the_offline_brain(macro_file, ran, monkeypatch):
    monkeypatch.setenv("DONNA_LLM", "fake")
    write(macro_file, WORK_SETUP)
    sent = []
    agent.handle("Run work setup", [], sent.append)
    assert sent[0] == {"type": "tool_call", "name": "run_macro", "args": {"name": "work setup"}}
    assert sent[1]["type"] == "tool_result"
    assert sent[1]["result"].startswith("Ran your 'work setup' macro:")
    assert sent[-1] == {"type": "assistant_message", "text": "Ran your 'work setup' macro"}
    assert ran == [("open_app", "Visual Studio Code"), ("open_app", "Google Chrome")]


# ---- the template


def test_ensure_writes_a_template_that_defines_no_macros(macro_file):
    macros.ensure()
    assert "run work setup" in macro_file.read_text(encoding="utf-8")
    assert macros.load(tools.FUNCTIONS) == {}


def test_ensure_never_overwrites_your_macros(macro_file):
    write(macro_file, WORK_SETUP)
    macros.ensure()
    assert macro_file.read_text(encoding="utf-8") == WORK_SETUP


def test_the_template_example_works_once_uncommented(macro_file):
    """The example you're told to try must actually be a valid macro."""
    notes, example = macros.TEMPLATE.rsplit("\n\n", 1)
    write(macro_file, notes + "\n\n" + re.sub(r"^# ?", "", example, flags=re.MULTILINE))
    assert macros.load(tools.FUNCTIONS) == {
        "work setup": [
            ("open_app", {"app": "Visual Studio Code"}),
            ("open_app", {"app": "Google Chrome"}),
            ("open_app", {"app": "Terminal"}),
        ]
    }
