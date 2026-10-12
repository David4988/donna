import pytest

import speech_text


# ---------------------------------------------------------------- strip_wake_phrase


@pytest.mark.parametrize(
    "heard, expected",
    [
        ("Hey Jarvis, open notepad", "open notepad"),
        ("Hey Jarvis. Open notepad.", "Open notepad."),
        ("Jarvis, open notepad", "open notepad"),
        ("hey jarvis open notepad", "open notepad"),
        ("Hey Javis, find my files", "find my files"),  # Whisper drops the r
        ("Hey Jarvis", ""),  # the summons and nothing else
        ("Jarvis?", ""),
        ("", ""),
    ],
)
def test_strip_wake_phrase(heard, expected):
    assert speech_text.strip_wake_phrase(heard) == expected


def test_a_misheard_summons_is_passed_through_whole():
    """wake.py already said she was called, so this must never answer "not for her".

    The model fires on a clipped "hey ja" and Whisper may write something else
    entirely. Dropping the command there would mean ignoring you right after
    her own wake word said you summoned her -- the worst failure available.
    """
    assert speech_text.strip_wake_phrase("Hey Marvin, open notepad") == "Hey Marvin, open notepad"
    assert speech_text.strip_wake_phrase("open notepad") == "open notepad"


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


# ---------------------------------------------------------------- say_numbers

# Each expectation here is what Piper was MEASURED to say wrong: "20C" came
# out as "twenty see", "12 mph" as "twelve em-pee-aitch".


@pytest.mark.parametrize(
    "written, spoken",
    [
        ("It's 20C out.", "It's 20 degrees Celsius out."),
        ("It's 20°C out.", "It's 20 degrees Celsius out."),
        ("It's 20 °C out.", "It's 20 degrees Celsius out."),
        ("A high of 68F.", "A high of 68 degrees Fahrenheit."),
        ("Down to -5C tonight.", "Down to -5 degrees Celsius tonight."),
        ("Around 21.5C.", "Around 21.5 degrees Celsius."),
        ("A 90° turn.", "A 90 degrees turn."),
        ("Winds at 12 mph.", "Winds at 12 miles per hour."),
        ("Doing 50km/h.", "Doing 50 kilometres per hour."),
        ("It weighs 1.5kg.", "It weighs 1.5 kilograms."),
        ("About 30cm wide.", "About 30 centimetres wide."),
        ("That costs $14.50.", "That costs 14 dollars 50."),
        ("That costs $14.", "That costs 14 dollars."),
        ("Exactly $14.00.", "Exactly 14 dollars."),
        ("It was £1,500.", "It was 1500 pounds."),
    ],
)
def test_piper_is_handed_words_instead_of_symbols(written, spoken):
    assert speech_text.for_speech(written) == spoken


@pytest.mark.parametrize(
    "text",
    [
        "The file is config.json.",
        "It runs at 3.4GHz.",
        "Battery is at 70%.",
        "The drive holds 500MB.",
        "Check the README.",
        "Qwen runs under Ollama.",
    ],
)
def test_what_piper_already_says_correctly_is_left_alone(text):
    """Measured as correct, so a rule for it could only make things worse."""
    assert speech_text.for_speech(text) == text


def test_a_unit_needs_a_number_in_front_of_it():
    """Otherwise ordinary words get mangled: "left" is not "lefeet"."""
    assert speech_text.for_speech("I left the ml file.") == "I left the ml file."


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


# Caught in a real log on 2026-10-12: she threw this question away TWICE,
# because the old set-overlap test scored 6/6 = 1.00 -- every word of the
# question appears somewhere in the reply she had just given. Any short
# question built from common words did this, and the longer she talked the
# more of them she discarded. It is indistinguishable from being ignored.
HER_LONG_REPLY = (
    "I don't know anything personal about you; I only see what you ask me "
    "to do on your computer at the moment."
)


@pytest.mark.parametrize(
    "heard",
    [
        "What do you know about me?",
        "What do you do?",
        "Do you know what time it is?",
        "What can you see on my computer?",
        "do you know me",
    ],
)
def test_a_question_made_of_her_own_words_is_still_a_question(heard):
    assert not speech_text.echoes(HER_LONG_REPLY, heard)


@pytest.mark.parametrize(
    "said, heard",
    [
        ("Hello. What can I do for you?", "What can I do for you"),
        ("Hello. What can I do for you?", "Hello. What can I do for you?"),
        ("Yes?", "Yes?"),
        ("It's fourteen degrees in London today.", "fourteen degrees in London today"),
    ],
)
def test_a_contiguous_run_of_her_own_words_is_an_echo(said, heard):
    """What an echo physically is: a stretch of her sentence, in her order."""
    assert speech_text.echoes(said, heard)


@pytest.mark.parametrize(
    "said, heard",
    [
        ("I can open applications like VS Code, Chrome, and notepad.", "open notepad"),
        ("I found three budget files in your Documents folder.", "open the budget file"),
        ("It's fourteen degrees in London today.", "what about tomorrow"),
    ],
)
def test_a_follow_up_about_what_she_just_said_is_not_an_echo(said, heard):
    """The case that matters most for a conversation: building on her answer."""
    assert not speech_text.echoes(said, heard)


# ---------------------------------------------------------------- is_small_talk


@pytest.mark.parametrize(
    "text",
    ["Hello", "hello.", "Hi there", "Hey", "Thanks!", "thank you", "Good morning",
     "Donna", "Jarvis", "hey jarvis", "hello again", "yo", "", "   "],
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
