"""The rules for turning speech into text and text into speech.

Nothing here touches a microphone, a model or a socket: it is all plain string
work, so it is cheap to test and the tests run without faster-whisper or Piper
installed.

    wake(heard)         is this for DONNA, and what is she being asked?
    take_sentences(s)   which part of a half-written reply can be spoken yet?
    for_speech(text)    the same words, with things Piper shouldn't read aloud removed
    is_garbage(heard)   did the microphone pick up anything that was actually speech?
    echoes(said, heard) is this DONNA hearing herself through the speakers?
"""

import re
import unicodedata

# How Whisper spells her name. Collected from real mis-hearings; add to this
# when she ignores you.
#
# This is an explicit list on purpose. Fuzzy matching cannot do this job:
# measured with difflib against "donna", the realistic mis-hearing "dawn"
# scores 0.444 -- exactly what "open" scores -- while "gonna" scores 0.800,
# the same as the real mis-hearing "danna". Every threshold low enough to
# catch what Whisper actually produces also wakes her on ordinary words, so
# please don't "improve" this into a similarity score.
NAMES = frozenset(
    {"donna", "dona", "donnna", "donah", "danna", "dawna", "dawn", "donner", "doner", "duna"}
)

# Words that may come before her name: "Hey Donna", "OK Donna", "Um, Donna".
GREETINGS = frozenset({"hey", "hi", "hello", "ok", "okay", "yo", "um", "uh", "so"})

MAX_SENTENCE_CHARS = 240  # a reply with no punctuation still has to get spoken

# Things people say that aren't asking for anything. An open mic produces a lot
# of these -- a greeting, an acknowledgement, or a half-heard "May Donna" that
# was really "Hey Donna".
PLEASANTRIES = GREETINGS | {
    "hello", "hiya", "morning", "afternoon", "evening", "good", "thanks",
    "thank", "you", "cheers", "there", "again", "donna", "please", "well",
}

TERMINATORS = ".!?"
NOT_THE_END = frozenset({"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "e.g", "i.e"})


def bare(word):
    """A word with its punctuation and capitals taken off."""
    return word.strip(" ,.?!;:\"'").lower()


# ---------------------------------------------------------------- wake


def wake(heard):
    """Is this addressed to DONNA, and what is she being asked?

        None  this wasn't for her
        ""    her name, and nothing else
        str   her name, and this is the command

    Only the first two words are looked at, which is what makes
    "I was talking to Dave about Donna" not an instruction.
    """
    words = heard.split()
    for position, word in enumerate(words[:2]):
        if bare(word) in NAMES:
            if position == 1 and bare(words[0]) not in GREETINGS:
                return None  # "...about Donna" is talking about her, not to her
            return " ".join(words[position + 1 :]).lstrip(",.;: ").strip()
    return None


def is_small_talk(text):
    """Is this a greeting rather than a request?

    Worth catching before the model sees it. Measured on qwen3.5:4b: given a
    contentless utterance like "Hello." with the tools attached, it opens a
    random application most of the time -- once passing the tool's own name as
    the app. It handles real requests and real questions perfectly; it is the
    empty ones it can't leave alone. An open mic produces a lot of empty ones.
    """
    words = [bare(word) for word in text.split()]
    words = [word for word in words if word]
    return bool(words) and all(word in PLEASANTRIES for word in words)


# ---------------------------------------------------------------- sentences


def take_sentences(buffer):
    """Split off every sentence that is finished, keeping what may still grow.

    Returns (sentences, rest). A sentence only counts as finished once
    whitespace follows its full stop, because mid-stream "I found report."
    may still be becoming "report.pdf" and "it costs 3." may be becoming
    "3.5". Waiting for the space costs a few tokens and removes every
    decimal-splitting and filename-splitting bug at once.

    The last sentence of a reply has no space after it, so the caller flushes
    whatever is left over when the reply ends.
    """
    sentences = []
    start = 0
    for i in range(len(buffer) - 1):
        if buffer[i] in TERMINATORS and buffer[i + 1].isspace() and really_the_end(buffer, start, i):
            sentences.append(buffer[start : i + 1].strip())
            start = i + 1

    rest = buffer[start:].lstrip() if sentences else buffer

    # A model that writes one endless comma-spliced line still has to be heard.
    while len(rest) > MAX_SENTENCE_CHARS:
        cut = rest.rfind(" ", 0, MAX_SENTENCE_CHARS)
        if cut <= 0:
            break  # one impossibly long word: leave it alone
        sentences.append(rest[:cut].strip())
        rest = rest[cut:].lstrip()

    return [sentence for sentence in sentences if sentence], rest


def really_the_end(buffer, start, i):
    """Is the full stop at buffer[i] the end of a sentence, or part of a word?"""
    if buffer[i] != ".":
        return True  # ! and ? are never abbreviations
    if i and buffer[i - 1] == ".":
        return False  # "..." is a pause, not an ending
    match = re.search(r"[\w.]+$", buffer[start:i])
    word = match.group(0).lower() if match else ""
    if word in NOT_THE_END:
        return False
    return not (len(word) == 1 and word.isalpha())  # "J. Smith"


# ---------------------------------------------------------------- for_speech

CODE_FENCE = re.compile(r"```.*?```", re.DOTALL)
URL = re.compile(r"\b(?:https?://|www\.)\S+")
WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[^\s,;]+")
MARKUP = re.compile(r"[*_`#>~|]+")
BULLET = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)


def for_speech(text):
    """The same words, with the things Piper should not read out loud removed.

    The screen keeps the markdown; only the spoken copy is cleaned. Nothing in
    the system prompt forbids the model from using markdown, so without this
    Piper cheerfully says "asterisk asterisk V S Code asterisk asterisk".
    """
    text = CODE_FENCE.sub(" some code ", text)
    text = URL.sub(" the link ", text)
    text = WINDOWS_PATH.sub(lambda match: " " + match.group(0).rsplit("\\", 1)[-1] + " ", text)
    text = BULLET.sub("", text)
    text = MARKUP.sub("", text)
    text = "".join(c for c in text if unicodedata.category(c) != "So")  # emoji
    return " ".join(text.split())


# ---------------------------------------------------------------- is_garbage

A_WORD = re.compile(r"[^\W\d_]{2,}")
TAG = re.compile(r"[\[(][^\])]*[\])]")  # [BLANK_AUDIO], (wind blowing)


def is_garbage(heard):
    """Did the microphone pick up anything that was actually speech?

    Structural only: no blocklist of Whisper's favourite silence hallucinations
    ("Thank you.", "Thanks for watching!"). While asleep, wake() already
    discards those because they don't contain her name; while awake, blocking
    them would mean she ignores you when you thank her.
    """
    return not A_WORD.search(TAG.sub(" ", heard))


# ---------------------------------------------------------------- echoes


def echoes(said, heard):
    """Is this DONNA hearing her own voice through the speakers?

    Echo cancellation in the window does most of this, but it works against
    the system's render stream and loud external speakers can defeat it. The
    failure it prevents is a loop: she says her own name, hears it, and wakes
    herself up.
    """
    spoken = set(bare(word) for word in said.split()) - {""}
    back = set(bare(word) for word in heard.split()) - {""}
    if not spoken or not back:
        return False
    return len(back & spoken) / len(back) >= 0.6
