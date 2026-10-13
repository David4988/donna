import logging

import pytest

import about
import agent


@pytest.fixture(autouse=True)
def _her_own_files(monkeypatch, tmp_path):
    """Never the real ~/.cache/donna: these tests write to those paths."""
    monkeypatch.setattr(about, "HOME", tmp_path)
    monkeypatch.setattr(about, "ABOUT_PATH", tmp_path / "ABOUT_ME.md")
    monkeypatch.setattr(about, "STATE_PATH", tmp_path / "USER_STATE.md")
    monkeypatch.setattr(
        about,
        "HEADINGS",
        {about.ABOUT_PATH: "Who you are talking to.", about.STATE_PATH: "What they are doing."},
    )
    monkeypatch.setattr(about, "_warned", set())
    return about.ABOUT_PATH, about.STATE_PATH


def test_knowing_nothing_about_you_is_not_an_error():
    """She must behave exactly as she did before this file existed."""
    assert about.context() == ""
    assert "None" not in agent.system_prompt()


def test_either_file_alone_is_enough(_her_own_files):
    me, state = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    assert "I am Crimson." in about.context()
    me.unlink()
    state.write_text("Building DONNA.", encoding="utf-8")
    assert "Building DONNA." in about.context()


def test_both_files_arrive_with_the_stable_one_first(_her_own_files):
    me, state = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    state.write_text("Building DONNA.", encoding="utf-8")
    context = about.context()
    assert context.index("I am Crimson.") < context.index("Building DONNA.")


def test_each_document_is_framed_so_she_knows_what_it_is_for(_her_own_files):
    """Unlabelled, a biography reads as something to discuss, not to use."""
    me, state = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    state.write_text("Building DONNA.", encoding="utf-8")
    context = about.context()
    assert "Who you are talking to." in context
    assert "What they are doing." in context


def test_markdown_headings_survive(_her_own_files):
    """Unlike SOUL.md: here '#' is structure, not a note to the editor."""
    me, _ = _her_own_files
    me.write_text("# About me\n\n## How I work\n\nDirectly.", encoding="utf-8")
    context = about.context()
    assert "# About me" in context
    assert "## How I work" in context


def test_html_comments_are_notes_to_you_and_she_never_sees_them(_her_own_files):
    me, _ = _her_own_files
    me.write_text(
        "<!-- a reminder to myself\n   over two lines -->\nI am Crimson.", encoding="utf-8"
    )
    context = about.context()
    assert "reminder to myself" not in context
    assert "I am Crimson." in context


def test_a_file_of_only_notes_counts_as_empty(_her_own_files):
    me, _ = _her_own_files
    me.write_text("<!-- nothing filled in yet -->\n\n", encoding="utf-8")
    assert about.context() == ""


@pytest.mark.parametrize(
    "written",
    [
        "# About me\n\n- **Name:**\n- **Where I am:**\n\n## How I work\n",
        "## What is due\n\n## What I am stuck on\n",
        "- Name:\n- Where:\n",
    ],
)
def test_an_unfilled_template_says_nothing(_her_own_files, written):
    """Otherwise it is ~100 tokens of empty scaffolding in every prompt."""
    me, _ = _her_own_files
    me.write_text(written, encoding="utf-8")
    assert about.context() == ""


def test_one_filled_field_is_enough_and_keeps_its_headings(_her_own_files):
    """Partial information is still information, and structure aids reading."""
    me, _ = _her_own_files
    me.write_text("# About me\n\n- **Name:** Crimson\n- **Where I am:**\n", encoding="utf-8")
    context = about.context()
    assert "Crimson" in context
    assert "# About me" in context


def test_an_unreadable_file_does_not_stop_her_answering(monkeypatch, _her_own_files):
    me, _ = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")

    def refuse(*args, **kwargs):
        raise OSError("permission denied")

    monkeypatch.setattr(type(me), "read_text", refuse)
    assert about.context() == ""  # carries on knowing nothing


def test_too_much_about_you_is_warned_about_once(caplog, _her_own_files):
    """The prompt budget is real: 239 tokens of tools are in there too."""
    me, _ = _her_own_files
    me.write_text("x" * (about.LOUD_ENOUGH + 1), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        about.context()
        about.context()  # again, to prove it doesn't nag every turn
    assert len(caplog.records) == 1
    assert "tokens" in caplog.text
    assert "routing benchmark" in caplog.text  # ...and what to do about it


def test_ensure_writes_templates_with_nobody_s_details_in_them(_her_own_files):
    """The repository is PUBLIC. The templates must carry no personal data."""
    me, state = _her_own_files
    about.ensure()
    for path in (me, state):
        written = path.read_text(encoding="utf-8")
        assert "<!--" in written  # the notes explaining how to edit it
        assert "Crimson" not in written
        assert "Chennai" not in written
    assert about.context() == ""  # a blank template says nothing about you


def test_ensure_never_overwrites_what_you_wrote(_her_own_files):
    me, _ = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    about.ensure()
    assert me.read_text(encoding="utf-8") == "I am Crimson."


# ---------------------------------------------------------------- the prompt


def test_the_measured_rules_still_come_last(_her_own_files):
    """A biography in front of them is exactly when they are most at risk."""
    me, state = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    state.write_text("Building DONNA.", encoding="utf-8")
    prompt = agent.system_prompt()
    assert prompt.index("I am Crimson.") < prompt.index("Never guess at a tool.")
    assert prompt.index("Building DONNA.") < prompt.index("Never guess at a tool.")
    assert prompt.rstrip().endswith("rather than '14C'.")


def test_her_character_still_comes_before_who_you_are(_her_own_files):
    me, _ = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    prompt = agent.system_prompt()
    assert prompt.index("You are DONNA") < prompt.index("I am Crimson.")


def test_editing_what_she_knows_takes_effect_without_a_restart(_her_own_files):
    me, _ = _her_own_files
    me.write_text("I am Crimson.", encoding="utf-8")
    assert "I am Crimson." in agent.system_prompt()
    me.write_text("I am someone else now.", encoding="utf-8")
    assert "I am someone else now." in agent.system_prompt()
