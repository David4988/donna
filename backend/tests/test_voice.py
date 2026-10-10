import pytest

import agent
import speech_text
import stt
import tts
import voice
import wake


def fake_voice(monkeypatch, *, heard=(), reply=(), wakes=None):
    """Replace the ears, the voice, the agent and the clock with scripted fakes.

    Returns (sent, spoken, slept, clock): everything that went out, every
    sentence handed to Piper, every second she waited for playback, and a
    one-item list holding the fake time so tests can move it.
    """
    heard, sent, spoken, slept, clock = list(heard), [], [], [], [1000.0]
    wakes = None if wakes is None else list(wakes)
    transcribed = []

    def transcribe(pcm):
        transcribed.append(pcm)
        return heard.pop(0) if heard else ""

    def heard_wake_word(pcm):
        return wakes.pop(0) if wakes else True

    monkeypatch.setattr(wake, "heard_wake_word", heard_wake_word)
    fake_voice.transcribed = transcribed

    def synthesise(text):
        spoken.append(text)
        return b"\0\0" * tts.SAMPLE_RATE  # exactly one second of audio

    monkeypatch.setattr(stt, "transcribe", transcribe)
    monkeypatch.setattr(tts, "synthesise", synthesise)
    monkeypatch.setattr(agent, "handle", lambda text, history, send: _play(reply, text, send))
    monkeypatch.setattr(voice, "_now", lambda: clock[0])
    monkeypatch.setattr(voice, "_sleep", lambda s: (slept.append(s), clock.__setitem__(0, clock[0] + s)))
    return sent, spoken, slept, clock


def _play(reply, text, send):
    _play.asked.append(text)
    for message in reply:
        send(dict(message))


_play.asked = []


@pytest.fixture(autouse=True)
def _forget_what_was_asked():
    _play.asked = []


def session(sent, history=None):
    return voice.Session(sent.append, history if history is not None else [])


def types(sent):
    return [m["type"] for m in sent if isinstance(m, dict)]


HELLO = [
    {"type": "assistant_delta", "text": "Hello."},
    {"type": "assistant_message", "text": "Hello."},
]


# ---------------------------------------------------------------- asleep


def test_an_overheard_remark_is_ignored_while_asleep(monkeypatch):
    """The behaviour an open mic lives or dies on: she says nothing whatsoever."""
    sent, spoken, _, _ = fake_voice(
        monkeypatch, heard=["what time is the train"], reply=HELLO, wakes=[False]
    )
    session(sent).on_audio(b"x" * 20000)
    assert sent == []
    assert spoken == []
    assert _play.asked == []


def test_whisper_never_runs_while_asleep(monkeypatch):
    """The whole point of the wake word, stated as a test.

    Before this change every sound in the room cost a full Whisper pass. Now
    nothing is transcribed until the wake model has fired.
    """
    sent, _, _, _ = fake_voice(monkeypatch, heard=["anything at all"], wakes=[False])
    session(sent).on_audio(b"x" * 20000)
    assert fake_voice.transcribed == [], "she transcribed something while asleep"


def test_a_missing_wake_model_is_reported_once_and_starts_no_turn(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch)
    monkeypatch.setattr(
        wake, "heard_wake_word", lambda pcm: (_ for _ in ()).throw(wake.WakeError("not installed"))
    )
    donna = session(sent)
    donna.on_audio(b"x" * 20000)
    donna.on_audio(b"x" * 20000)
    assert sent == [{"type": "state", "name": "deaf"}]
    assert fake_voice.transcribed == []
    assert _play.asked == []


def test_hearing_her_name_wakes_her_and_runs_the_command(monkeypatch):
    sent, spoken, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, open notepad"], reply=HELLO)
    session(sent).on_audio(b"x" * 20000)
    assert types(sent) == [
        "state",  # awake
        "transcript",
        "state",  # speaking
        "assistant_delta",
        "assistant_message",
        "state",  # awake again
    ]
    assert sent[1] == {"type": "transcript", "text": "Hey Jarvis, open notepad"}
    assert _play.asked == ["open notepad"]  # the summons is stripped
    assert spoken == ["Hello."]


def test_her_name_alone_gets_an_answer_without_troubling_the_model(monkeypatch):
    sent, spoken, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis"])
    session(sent).on_audio(b"x" * 20000)
    assert _play.asked == []
    assert [m for m in sent if isinstance(m, dict) and m["type"] == "assistant_message"] == [
        {"type": "assistant_message", "text": "Yes?"}
    ]
    assert spoken == ["Yes?"]


# ---------------------------------------------------------------- awake


def test_while_awake_no_name_is_needed(monkeypatch):
    sent, _, _, _ = fake_voice(
        monkeypatch, heard=["Hey Jarvis, what time is it", "and now"], reply=HELLO
    )
    donna = session(sent)
    donna.on_audio(b"x" * 20000)
    donna.on_audio(b"x" * 20000)
    assert _play.asked == ["what time is it", "and now"]


def test_she_needs_her_name_again_after_the_silence(monkeypatch):
    sent, _, _, clock = fake_voice(
        monkeypatch,
        heard=["Hey Jarvis, what time is it", "and now"],
        reply=HELLO,
        wakes=[True, False],  # the second one didn't say her name
    )
    donna = session(sent)
    donna.on_audio(b"x" * 20000)
    clock[0] += voice.SILENCE_SECONDS + 1
    sent.clear()
    donna.on_audio(b"x" * 20000)
    assert _play.asked == ["what time is it"]  # the second one was not for her
    assert {"type": "state", "name": "asleep"} in sent


def test_audio_is_ignored_while_speaking(monkeypatch):
    sent, spoken, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, what time is it"])
    donna = session(sent)
    donna._state = voice.SPEAKING
    donna.on_audio(b"x" * 20000)
    assert sent == []
    assert spoken == []


def test_a_too_long_utterance_is_dropped_before_it_kills_the_socket(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, what time is it"])
    session(sent).on_audio(b"\0" * (voice.MAX_UTTERANCE_BYTES + 2))
    assert sent == []


def test_her_own_voice_does_not_wake_her(monkeypatch):
    sent, _, _, _ = fake_voice(
        monkeypatch, heard=["Hey Jarvis, what time is it", "Hello."], reply=HELLO
    )
    donna = session(sent)
    donna.on_audio(b"x" * 20000)  # she replies "Hello." and says it out loud
    donna._state = voice.AWAKE
    sent.clear()
    _play.asked.clear()
    donna.on_audio(b"x" * 20000)  # the speakers leak it back
    assert _play.asked == []


# ---------------------------------------------------------------- speaking


def test_each_sentence_is_spoken_as_it_streams(monkeypatch):
    sent, spoken, _, _ = fake_voice(
        monkeypatch,
        heard=["Hey Jarvis, what time is it"],
        reply=[
            {"type": "assistant_delta", "text": "Hello there. "},
            {"type": "assistant_delta", "text": "VS Code is open."},
            {"type": "assistant_message", "text": "Hello there. VS Code is open."},
        ],
    )
    session(sent).on_audio(b"x" * 20000)
    assert spoken == ["Hello there.", "VS Code is open."]

    kinds = [("audio" if isinstance(m, bytes) else m["type"]) for m in sent]
    assert kinds.index("audio") < kinds.index("assistant_message"), (
        "the first audio must go out before the final reply, or there is no latency win"
    )


def test_the_final_reply_is_not_spoken_twice(monkeypatch):
    sent, spoken, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, what time is it"], reply=HELLO)
    session(sent).on_audio(b"x" * 20000)
    assert spoken == ["Hello."]


def test_a_reply_that_never_streamed_is_still_spoken(monkeypatch):
    """agent.py sends the 'I got stuck' message with no deltas at all."""
    stuck = "Sorry, I got stuck trying to do that."
    sent, spoken, _, _ = fake_voice(
        monkeypatch, heard=["Hey Jarvis, what time is it"], reply=[{"type": "assistant_message", "text": stuck}]
    )
    session(sent).on_audio(b"x" * 20000)
    assert spoken == [stuck]


def test_an_error_is_spoken_and_she_goes_back_to_listening(monkeypatch):
    sent, spoken, _, _ = fake_voice(
        monkeypatch,
        heard=["Hey Jarvis, what time is it"],
        reply=[{"type": "error", "text": "Can't reach the model."}],
    )
    session(sent).on_audio(b"x" * 20000)
    assert spoken == ["Can't reach the model."]
    assert sent[-1] == {"type": "state", "name": "awake"}


def test_a_tool_preamble_is_not_mixed_into_the_answer(monkeypatch):
    sent, spoken, _, _ = fake_voice(
        monkeypatch,
        heard=["Hey Jarvis, find my files"],
        reply=[
            {"type": "assistant_delta", "text": "Let me check. "},
            {"type": "tool_call", "name": "find_files", "args": {"query": "x"}},
            {"type": "tool_result", "name": "find_files", "result": "Found 3."},
            {"type": "assistant_delta", "text": "I found 3 files."},
            {"type": "assistant_message", "text": "I found 3 files."},
        ],
    )
    session(sent).on_audio(b"x" * 20000)
    assert spoken == ["Let me check.", "I found 3 files."]


def test_speaking_lasts_as_long_as_the_audio(monkeypatch):
    sent, spoken, slept, _ = fake_voice(
        monkeypatch,
        heard=["Hey Jarvis, what time is it"],
        reply=[
            {"type": "assistant_delta", "text": "One. Two. Three. "},
            {"type": "assistant_message", "text": "One. Two. Three."},
        ],
    )
    session(sent).on_audio(b"x" * 20000)
    assert len(spoken) == 3
    assert sum(slept) == pytest.approx(3 + voice.TAIL_SECONDS)
    assert sent[-1] == {"type": "state", "name": "awake"}


def test_a_synthesis_failure_does_not_lose_the_reply(monkeypatch):
    sent, spoken, _, _ = fake_voice(
        monkeypatch,
        heard=["Hey Jarvis, what time is it"],
        reply=[
            {"type": "assistant_delta", "text": "One. Two. "},
            {"type": "assistant_message", "text": "One. Two."},
        ],
    )

    def break_on_the_second(text):
        spoken.append(text)
        if len(spoken) > 1:
            raise tts.TtsError("no voice")
        return b"\0\0" * tts.SAMPLE_RATE

    monkeypatch.setattr(tts, "synthesise", break_on_the_second)
    session(sent).on_audio(b"x" * 20000)
    assert {"type": "state", "name": "mute"} in sent
    assert {"type": "assistant_message", "text": "One. Two."} in sent
    assert sent[-1] == {"type": "state", "name": "awake"}


def test_she_only_says_she_is_mute_once(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, open notepad", "open notepad"], reply=HELLO)
    monkeypatch.setattr(tts, "synthesise", lambda text: (_ for _ in ()).throw(tts.TtsError("no")))
    donna = session(sent)
    donna.on_audio(b"x" * 20000)
    donna.on_audio(b"x" * 20000)
    assert sum(1 for m in sent if isinstance(m, dict) and m.get("name") == "mute") == 1


def test_deafness_is_reported_once_and_starts_no_turn(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch)
    monkeypatch.setattr(
        stt, "transcribe", lambda pcm: (_ for _ in ()).throw(stt.SttError("no model"))
    )
    session(sent).on_audio(b"x" * 20000)
    assert sent == [{"type": "state", "name": "deaf"}]
    assert _play.asked == []


# ---------------------------------------------------------------- typed


def test_a_typed_message_is_answered_out_loud(monkeypatch):
    sent, spoken, _, _ = fake_voice(monkeypatch, reply=HELLO)
    session(sent).on_text("what time is it")
    assert _play.asked == ["what time is it"]
    assert spoken == ["Hello."]


def test_a_voice_turn_and_a_typed_turn_share_the_conversation(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, what time is it"], reply=HELLO)
    history = []
    seen = []
    monkeypatch.setattr(agent, "handle", lambda text, h, send: seen.append(h))
    donna = voice.Session(sent.append, history)
    donna.on_audio(b"x" * 20000)
    donna.on_text("and again")
    assert seen == [history, history]  # the same list object both times


# ---------------------------------------------------------------- invariant


@pytest.mark.parametrize(
    "reply",
    [
        HELLO,
        [{"type": "assistant_message", "text": "Sorry, I got stuck trying to do that."}],
        [{"type": "error", "text": "Can't reach the model."}],
        [
            {"type": "assistant_delta", "text": "A. B. "},
            {"type": "assistant_message", "text": "A. B."},
        ],
    ],
)
def test_a_voice_turn_sends_exactly_one_final_reply(monkeypatch, reply):
    sent, _, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, what time is it"], reply=reply)
    session(sent).on_audio(b"x" * 20000)
    finals = [
        m for m in sent if isinstance(m, dict) and m["type"] in ("assistant_message", "error")
    ]
    assert len(finals) == 1


def test_one_state_message_per_real_change(monkeypatch):
    """No flicker: she never announces a state she is already in."""
    sent, _, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, what time is it"], reply=HELLO)
    session(sent).on_audio(b"x" * 20000)
    states = [m["name"] for m in sent if isinstance(m, dict) and m["type"] == "state"]
    assert states == ["awake", "speaking", "awake"]
    assert all(a != b for a, b in zip(states, states[1:]))


# ---------------------------------------------------------------- partials


def partials(monkeypatch, heard):
    """Fake the partial transcriber, and report what it was asked for."""
    asked = []

    def transcribe_partial(pcm):
        asked.append(pcm)
        return heard.pop(0) if heard else ""

    monkeypatch.setattr(stt, "transcribe_partial", transcribe_partial)
    return asked


def test_a_partial_never_reaches_the_agent(monkeypatch):
    """The guarantee: live words put text on screen and do nothing else."""
    sent, spoken, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, hello"], reply=HELLO)
    partials(monkeypatch, ["open", "open not", "open notepad"])
    donna = session(sent)
    donna.on_audio(b"x" * 20000)  # wake her; she greets back
    sent.clear()
    spoken.clear()
    _play.asked.clear()

    for _ in range(3):
        donna.on_partial(b"x" * 20000)

    assert [m["type"] for m in sent] == ["partial_transcript"] * 3
    assert [m["text"] for m in sent] == ["open", "open not", "open notepad"]
    assert _play.asked == [], "a partial started a turn"
    assert spoken == [], "a partial made her speak"


def test_partials_are_ignored_while_asleep(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch)
    asked = partials(monkeypatch, ["something"])
    session(sent).on_partial(b"x" * 20000)
    assert sent == []
    assert asked == [], "she transcribed a partial while asleep"


def test_partials_are_ignored_while_speaking(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch)
    asked = partials(monkeypatch, ["something"])
    donna = session(sent)
    donna._state = voice.SPEAKING
    donna.on_partial(b"x" * 20000)
    assert sent == []
    assert asked == []


def test_a_partial_does_not_keep_her_awake(monkeypatch):
    """Deliberate: on_partial must touch no session state, timer included."""
    sent, _, _, clock = fake_voice(monkeypatch, heard=["Hey Jarvis, hello"], reply=HELLO)
    partials(monkeypatch, ["still talking"])
    donna = session(sent)
    donna.on_audio(b"x" * 20000)
    before = donna._last_heard
    clock[0] += 5
    donna.on_partial(b"x" * 20000)
    assert donna._last_heard == before


def test_her_own_voice_is_not_shown_as_your_words(monkeypatch):
    sent, _, _, _ = fake_voice(monkeypatch, heard=["Hey Jarvis, hello"], reply=HELLO)
    partials(monkeypatch, ["Hello."])  # the speakers leaking back
    donna = session(sent)
    donna.on_audio(b"x" * 20000)
    donna._state = voice.AWAKE
    sent.clear()
    donna.on_partial(b"x" * 20000)
    assert sent == []
