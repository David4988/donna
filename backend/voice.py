"""The voice session: who may talk, and when.

One Session per connection. It is the voice-shaped front door to the same
agent that typing uses, so `agent.handle` needs no idea that any of this
exists.

    ASLEEP ──("...Donna, open notepad")──▶ AWAKE ──▶ SPEAKING
       ▲                                     │          │
       └──── SILENCE_SECONDS with nothing ───┘          │
       ▲                                                │
       └──────────── her audio finished playing ────────┘

While ASLEEP an utterance is checked by the wake word model (wake.py) and
thrown away unless someone said "Hey Jarvis" -- it is never transcribed. An
utterance that is dropped starts no turn and sends NOTHING AT ALL: an open mic
that answers things not addressed to it is unusable.

Nothing here imports websockets, so the whole state machine is testable
without a socket.
"""

import logging
import time

import agent
import settings
import speech_text
import stt
import tts
import wake

ASLEEP, AWAKE, SPEAKING = "asleep", "awake", "speaking"
DEAF, MUTE = "deaf", "mute"  # one-shot capability notices, not session states

SILENCE_SECONDS = 30  # how long she stays awake with nothing said to her
MAX_UTTERANCE_BYTES = 20 * stt.SAMPLE_RATE * 2  # 20s; the socket dies at 32.8s
TAIL_SECONDS = 0.25  # let her last word finish before the mic counts again

# Module level so tests can replace them, the way the other fakes work.
_now = time.monotonic
_sleep = time.sleep


class Session:
    """One connection's conversation. `send` takes a dict (JSON) or bytes (audio)."""

    def __init__(self, send, history):
        self._send = send
        self._history = history  # the same list the typed path uses
        self._state = ASLEEP
        self._last_heard = _now()
        self._playback_ends = 0.0
        self._said = ""  # the last thing she said, for the echo check
        self._cant = set()  # capability notices already sent

    # ------------------------------------------------------------ incoming

    def on_audio(self, pcm):
        """One binary frame is one whole utterance."""
        if self._state == SPEAKING:
            return logging.debug("ignored %d bytes of audio while speaking", len(pcm))
        if len(pcm) > MAX_UTTERANCE_BYTES:
            return logging.warning("ignored a %.1fs utterance: too long", len(pcm) / 32000)
        if self._state == AWAKE and _now() - self._last_heard > SILENCE_SECONDS:
            self._set_state(ASLEEP)

        if self._state == ASLEEP:
            # The whole point of the wake word: while she is asleep, Whisper
            # does not run at all. Everything said in the room is checked by a
            # small model that only knows one phrase, and is thrown away.
            try:
                if not wake.heard_wake_word(pcm):
                    return logging.debug("ignored %d bytes: nobody said her name", len(pcm))
            except wake.WakeError as error:
                return self._cannot(DEAF, error)

        try:
            heard = stt.transcribe(pcm)
        except stt.SttError as error:
            return self._cannot(DEAF, error)

        if speech_text.is_garbage(heard):
            return logging.debug("ignored %r: no speech in it", heard)
        if speech_text.echoes(self._said, heard):
            return logging.debug("ignored %r: that was her own voice", heard)

        # Awake, every word is for her. Asleep, the wake word already fired,
        # so all that is left is to take the summons off the front.
        command = heard if self._state == AWAKE else speech_text.strip_wake_phrase(heard)

        self._set_state(AWAKE)
        self._last_heard = _now()
        self._send({"type": "transcript", "text": heard})
        if command:
            self._run(command)
        else:
            self._answer("Yes?")  # her name, and nothing else

    def on_settings(self, changes):
        """A control moved. Not a turn: nothing is said and nothing is remembered."""
        try:
            now = settings.update(changes)
        except settings.SettingsError as error:
            logging.error("%s", error)
            now = settings.current()
        try:
            tts.configure(voice=now["voice"], speed=now["speed"])
        except tts.TtsError as error:
            logging.error("%s", error)  # keep the old voice; the reply tells the truth
        self.send_settings()

    def send_settings(self):
        """Tell the window what she is set to, and what else she could sound like."""
        try:
            voices = tts.installed_voices()
        except Exception as error:  # a missing voice folder must not kill the connection
            logging.error("%s", error)
            voices = []
        self._send({"type": "settings", "settings": settings.current(), "voices": voices})

    def on_text(self, text):
        """A typed message: the same turn, without transcription or a wake word."""
        self._set_state(AWAKE)
        self._last_heard = _now()
        self._run(text)

    # ------------------------------------------------------------ a turn

    def _run(self, command):
        if speech_text.is_small_talk(command):
            # Don't hand "Hello." to the model: with the tools attached it
            # opens something at random rather than just saying hello back.
            return self._answer("Hello. What can I do for you?")

        self._set_state(SPEAKING)
        reply = _ReplyVoice(self._send, self._speak)
        try:
            agent.handle(command, self._history, reply.on_message)
        finally:
            self._finish_speaking()

    def _answer(self, text):
        """Say something DONNA decided herself, without troubling the model."""
        self._set_state(SPEAKING)
        try:
            self._send({"type": "assistant_message", "text": text})
            self._speak(text)
        finally:
            self._finish_speaking()

    def _finish_speaking(self):
        remaining = self._playback_ends + TAIL_SECONDS - _now()
        if remaining > 0:
            _sleep(remaining)
        self._set_state(AWAKE)
        self._last_heard = _now()

    # ------------------------------------------------------------ speaking

    def _speak(self, sentence):
        spoken = speech_text.for_speech(sentence)
        if not spoken:
            return
        try:
            audio = tts.synthesise(spoken)
        except tts.TtsError as error:
            return self._cannot(MUTE, error)  # the turn still finishes, in text
        self._said = spoken
        self._send(audio)
        # Playback is a schedule, not a total: sentence four starts when
        # sentence three finishes, which may be after it was sent.
        self._playback_ends = max(_now(), self._playback_ends) + len(audio) / 2 / tts.SAMPLE_RATE

    # ------------------------------------------------------------ plumbing

    def _set_state(self, state):
        if state != self._state:
            self._state = state
            self._send({"type": "state", "name": state})

    def _cannot(self, what, error):
        """Tell the UI once that she can't hear or can't speak, and carry on.

        This rides the state channel on purpose. An `error` frame here would
        be a second final reply for the turn, and chat.py, App.tsx and the
        server tests all treat `error` as the end of a turn.
        """
        logging.error("%s", error)
        if what not in self._cant:
            self._cant.add(what)
            self._send({"type": "state", "name": what})


class _ReplyVoice:
    """Every message the agent sends passes through here on its way to the UI,
    and the pieces of the answer also become spoken sentences.

    A sentence is spoken the moment it is complete, which is what makes her
    first word arrive while the model is still writing the rest.
    """

    def __init__(self, send, speak):
        self._send = send
        self._speak = speak
        self._unspoken = ""
        self._spoke_something = False

    def on_message(self, message):
        kind = message["type"]
        self._send(message)  # the text reaches the screen before we synthesise

        if kind == "assistant_delta":
            self._unspoken += message["text"]
            sentences, self._unspoken = speech_text.take_sentences(self._unspoken)
            for sentence in sentences:
                self._speak(sentence)
                self._spoke_something = True
        elif kind in ("assistant_message", "error"):
            tail, self._unspoken = self._unspoken.strip(), ""
            if tail:
                self._speak(tail)  # the last sentence has no space after it
            elif not self._spoke_something:
                # Nothing streamed at all. agent.py sends the "I got stuck"
                # message and every error this way, and without this she would
                # simply go quiet while you stand across the room.
                self._speak(message["text"])
        else:
            # A tool round ended. Whatever half-sentence it left was a preamble
            # cut mid-word, and the answer that follows streams separately.
            self._unspoken = ""
            self._spoke_something = False
