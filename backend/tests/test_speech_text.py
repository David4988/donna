import pytest

import speech_text


# ---------------------------------------------------------------- wake


@pytest.mark.parametrize(
    "heard, expected",
    [
        ("Donna, open VS Code", "open VS Code"),
        ("Hey Donna, open VS Code", "open VS Code"),
        ("Hey, Donna. Open VS Code.", "Open VS Code."),
        ("donna open vs code", "open vs code"),
        ("OK Donna, hello", "hello"),
        ("Dona, what time is it?", "what time is it?"),  # Whisper spells it short
        ("Hey Dawn, find my files", "find my files"),  # a different word entirely
        ("Donner, open notepad", "open notepad"),
        ("Donna", ""),  # her name and nothing else
        ("Donna?", ""),
        ("Open VS Code", None),  # no name: not for her
        ("I was talking to Dave about dinner", None),
        ("Gonna open VS Code", None),
        ("Madonna is on the radio", None),
        ("", None),
    ],
)
def test_wake(heard, expected):
    assert speech_text.wake(heard) == expected


def test_the_name_list_is_not_a_similarity_score():
    """Regression for the measurement that says fuzzy matching cannot work here.

    difflib scores "gonna" against "donna" at 0.800 -- the same as the real
    mis-hearing "danna" -- and "dawn" at 0.444, exactly what "open" scores.
    Any threshold that catches the real mistakes also catches these.
    """
    assert speech_text.wake("Gonna grab a coffee") is None
    assert speech_text.wake("Madonna is on the radio") is None
    assert speech_text.wake("Dawn, find my files") == "find my files"


# ---------------------------------------------------------------- take_sentences

CASES = [
    ("Hello there. How are", ["Hello there."], "How are"),
    ("One. Two! Three? Four", ["One.", "Two!", "Three?"], "Four"),
    ("No punctuation yet", [], "No punctuation yet"),
    ("Done.", [], "Done."),  # the space may still be coming
    ("I found report.pdf here. Open it?", ["I found report.pdf here."], "Open it?"),
    ("It costs 3.5 dollars. Cheap.", ["It costs 3.5 dollars."], "Cheap."),
    ("e.g. this one. Next", ["e.g. this one."], "Next"),
    ("Wait... I see. Now", ["Wait... I see."], "Now"),
    ("Mr. Smith called. Good", ["Mr. Smith called."], "Good"),
    ("", [], ""),
]


@pytest.mark.parametrize("buffer, sentences, rest", CASES)
def test_take_sentences(buffer, sentences, rest):
    assert speech_text.take_sentences(buffer) == (sentences, rest)


@pytest.mark.parametrize("buffer, _sentences, _rest", CASES)
def test_splitting_never_loses_a_word(buffer, _sentences, _rest):
    """Whatever the rules decide, every word has to come out somewhere."""
    sentences, rest = speech_text.take_sentences(buffer)
    assert " ".join(sentences + [rest]).split() == buffer.split()


def test_a_very_long_run_is_broken_at_a_word_boundary():
    sentences, rest = speech_text.take_sentences("word " * 80)
    assert sentences, "a reply with no punctuation must still be speakable"
    assert len(sentences[0]) <= speech_text.MAX_SENTENCE_CHARS
    assert sentences[0].endswith("word")  # never mid-word
    assert " ".join(sentences + [rest]).split() == ("word " * 80).split()


# ---------------------------------------------------------------- for_speech


def test_piper_never_reads_markup_aloud():
    spoken = speech_text.for_speech("**VS Code** is open. See https://x.dev/a `now`")
    assert "*" not in spoken
    assert "`" not in spoken
    assert "http" not in spoken
    assert "VS Code is open." in spoken


def test_a_windows_path_is_shortened_to_the_filename():
    spoken = speech_text.for_speech(r"I found Notion.lnk in C:\Users\maste\OneDrive\Desktop")
    assert "Users" not in spoken
    assert "Desktop" in spoken


def test_emoji_are_not_read_out():
    assert "sparkle" not in speech_text.for_speech("Done ✨").lower()
    assert speech_text.for_speech("Done ✨") == "Done"


# ---------------------------------------------------------------- is_garbage


@pytest.mark.parametrize(
    "text", ["", "   ", ".", "...", "!?", "[BLANK_AUDIO]", "♪", "♪♪♪", "(wind blowing)", "-", "7"]
)
def test_non_speech_is_garbage(text):
    assert speech_text.is_garbage(text)


@pytest.mark.parametrize("text", ["Hi.", "No.", "Open VS Code", "Thank you."])
def test_words_are_not_garbage(text):
    """"No." is a real one-word answer, and she must not ignore being thanked."""
    assert not speech_text.is_garbage(text)


# ---------------------------------------------------------------- echoes


def test_her_own_voice_coming_back_is_recognised():
    assert speech_text.echoes("Notepad is open.", "Notepad is open")
    assert speech_text.echoes("I'm DONNA, your assistant.", "I'm Donna your assistant")


def test_what_you_actually_say_is_not_an_echo():
    assert not speech_text.echoes("Notepad is open.", "Donna, find my files")
    assert not speech_text.echoes("Notepad is open.", "thanks")
    assert not speech_text.echoes("", "Donna, hello")


# ---------------------------------------------------------------- is_small_talk


@pytest.mark.parametrize(
    "text",
    ["Hello", "hello.", "Hi there", "Hey", "Thanks!", "thank you", "Good morning",
     "Donna", "hello again", "yo", "", "   "],
)
def test_a_greeting_never_reaches_the_model(text):
    """qwen3.5:4b opens a random app when handed a contentless utterance."""
    assert speech_text.is_small_talk(text) or not text.strip()


@pytest.mark.parametrize(
    "text",
    ["open notepad", "find my notion files", "what time is it",
     "hello, open notepad", "thanks, now find my files", "search the web for tauri"],
)
def test_a_real_request_is_not_small_talk(text):
    assert not speech_text.is_small_talk(text)
