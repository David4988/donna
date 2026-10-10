# Voice 10A: DONNA hears you and talks back

**Status:** design agreed, not yet built
**Scope:** Step 10A in `PLAN.md`. Half-duplex spoken conversation.
**Not in scope:** barge-in (10B), a trained "Hey Donna" wake-word model (10C).

---

## 1. Why, and what "done" means

DONNA should hold a spoken conversation: you talk, she answers or does the task, and you keep
going without re-triggering anything. Typed chat already works; this gives it ears and a voice.

**The budget is ≤5 seconds from the moment you stop speaking to the moment she starts
speaking** — her *first word*, not the end of her answer. This is measured the way streaming
text is measured to the first token, and it is the number that decides whether the thing feels
alive or broken.

Expected chain on the measured hardware (RX 580, `qwen3.5:4b`, warm cache — see `PLAN.md` §6a):

| Stage | Expected |
|---|---|
| VAD decides you've stopped | 0.3–0.5s |
| Whisper transcribes | 0.5–1.0s |
| Model's first token | 0.2–0.5s |
| Model *completes* the first sentence (10–20 tok @ 17 tok/s) | 0.6–1.2s |
| Piper synthesises it | 0.1–0.5s |
| **First word you hear** | **1.7–3.7s** |

Note the fourth row: speech cannot start on a token, only on a finished sentence. That is the
difference between this budget and the text-streaming one, and it is why Stage 0 exists.

**10A is done when:** you speak her name, she wakes, you ask for something, she does it and
says so out loud, you ask a follow-up without saying her name again, and she goes back to sleep
after you stop. Measured first-word latency is recorded in `PLAN.md` §6a.

**10A is explicitly not:** interruptible. She finishes a sentence before listening again.

---

## 2. The shape of a turn

No hotkey and no wake-word model. **Whisper itself is the wake word**: the window's
voice-activity detector catches an utterance, Python transcribes it, and if it begins with her
name she wakes. Any words after the name are the first command, so "Hey Donna, open notepad" is
one step rather than two.

```text
            ┌─────────── Tauri window (a sensor) ───────────┐
            │  mic always on (echo cancellation + denoise)  │
            │        │                                      │
            │   Silero VAD ──▶ one finished utterance ──────┼──▶ binary PCM16 @16k
            │   speaker  ◀── scheduled audio queue ◀────────┼─── binary PCM16 @22050
            └───────────────────────────────────────────────┘

   Python, per connection:

        ASLEEP ──("…Donna, open notepad")──▶ AWAKE ──▶ SPEAKING
           ▲                                   │           │
           └────── 30s with nothing said ──────┘           │
           ▲                                               │
           └──────────── audio finished playing ───────────┘
```

- **ASLEEP** — every utterance still arrives and is transcribed, but it is discarded unless it
  starts with her name. Nothing reaches the agent and **nothing at all goes back over the
  socket**. An open mic that answers things not addressed to it is unusable.
- **AWAKE** — no name needed; every utterance is a command.
- **SPEAKING** — utterances arriving while she talks are dropped. That is the half-duplex rule
  and the safety net for anything her own voice leaks past echo cancellation.

**The load-bearing idea: `agent.handle` does not change.** `voice.py` wraps the `send` callback.
Messages still flow to the UI exactly as they do for typed chat; voice additionally watches the
`assistant_delta` stream and, whenever a sentence completes, hands it to Piper. The same trick
as streaming — a side-channel on an existing callback, not a parallel pipeline.

**A typed message takes the same path**, so she answers out loud whatever you ask. This also
means the entire speaking path can be built and verified before a microphone exists.

### Concurrency: none added

Half-duplex is strictly sequential — listen, then think, then speak, then listen. The browser
senses and sends one finished utterance, so Python never listens and thinks at the same time.
The existing one-thread-per-connection sync server is kept unchanged, and `PLAN.md` decision 1
("plain synchronous Python, no asyncio") survives into voice. **Barge-in in 10B is what will
finally force that conversation.**

### One button, once per launch

`AudioContext` starts suspended under the browser autoplay policy, so a user gesture is needed
to resume it. The frontend therefore has a single "Start voice" control per launch, which also
triggers the microphone permission prompt in the same gesture. This is not a hotkey and not
per-utterance — but without it the failure is total silence with no error anywhere, which is a
baffling bug, so it is a deliberate part of the design.

---

## 3. The protocol

Today: six message types, all JSON. This adds **two JSON types downward and zero upward**, plus
one rule.

### Binary means audio

`websockets.sync` already yields `str` for text frames and `bytes` for binary, so there is no
envelope to invent and no base64 (which would cost 33% for nothing). One rule in both
directions:

| Direction | Payload |
|---|---|
| UI → backend | PCM16 mono **16 kHz** — one frame is one whole utterance |
| backend → UI | PCM16 mono **22050 Hz** — one frame is one spoken sentence |

The rate is a shared constant rather than described on the wire. `tts.warm()` reads the loaded
Piper voice's actual rate and **logs loudly if it is not 22050**, so a voice swap fails as one
startup line instead of chipmunk audio at runtime.

### Two new messages, backend → UI

| `type` | Fields | Why |
|---|---|---|
| `transcript` | `text` | What she heard. For a spoken turn your own line must come from Python, because only Python knows what Whisper decided. Carries the **raw** transcription, not the extracted command — when she does the wrong thing, what the microphone actually heard is the thing you need to see. |
| `state` | `name` | `asleep` / `awake` / `speaking`, plus `deaf` / `mute` as one-shot capability notices (§5). Drives the header pill today and the golden sphere in Step 11. |

Both names come from `README.md:99`, which already lists `state` and `transcript` in its event
vocabulary — this moves the implemented protocol toward the vision rather than inventing words.

**Nothing new goes up.** The frontend never announces "voice mode on" or "I started speaking".
It sends utterances, always, and Python decides what they mean. The frontend stays a sensor,
not a decider.

### The invariant, restated

> Every **turn** — a typed `user_message`, or a spoken utterance that reaches the agent — gets
> exactly ONE final reply (`assistant_message` or `error`), followed by one `state` returning to
> `awake`. An utterance that is dropped (asleep and unaddressed, arriving while speaking,
> garbage, too long) **starts no turn and sends nothing at all**.

### A spoken turn on the wire

```text
UI → ░░░ binary ░░░                               "Hey Donna, open notepad"
  ← {"type":"state","name":"awake"}
  ← {"type":"transcript","text":"Hey Donna, open notepad"}
  ← {"type":"state","name":"speaking"}
  ← {"type":"tool_call","name":"open_app","args":{"app":"notepad"}}
  ← {"type":"tool_result","name":"open_app","result":"Opened Notepad."}
  ← {"type":"assistant_delta","text":"Notepad"}      ─┐ text and audio interleave;
  ← ░░░ binary ░░░      "Notepad is open."            │ the socket preserves order
  ← {"type":"assistant_delta","text":" is open."}    ─┘
  ← {"type":"assistant_message","text":"Notepad is open."}
  ← {"type":"state","name":"awake"}
```

Deltas still flow, so the text appears on screen while she is still speaking it.

### The 1 MiB cliff — a real failure, fixed in three layers

`websockets.sync.server.serve()` defaults `max_size=1048576`. PCM16 mono 16 kHz is 32,000 B/s,
so **32.77 seconds of speech exceeds it**, the server closes with 1009, and the session resets
to ASLEEP. With "sleeps after 30s of silence" the design sits right against that wall, and the
symptom would be *"the app randomly disconnects when I talk a lot"*.

1. The frontend caps a single utterance at 20s.
2. `voice.Session.on_audio` drops anything over `MAX_UTTERANCE_BYTES` (20s) and logs a warning.
3. `server.make_server` passes `max_size=2**21` so even a bug cannot close the connection.

---

## 4. Modules

Four new backend files, following the convention the repo already uses: *one file per external
thing we talk to*, plus *one file for the rules*, plus *one file for the state*.

```
backend/
  speech_text.py   pure text rules       — no I/O, no dependencies
  stt.py           audio bytes -> text   — the only file that knows faster-whisper exists
  tts.py           text -> audio bytes   — the only file that knows Piper exists
  voice.py         the session           — who may talk, and when
  server.py        (modified, ~8 lines)  — binary means audio
```

### 4.1 `speech_text.py` — the rules, with no I/O

Every rule with real edge cases lives here, with zero dependencies, so CI imports it freely and
its tests are table-driven and instant. This is the highest bug density in the project and it is
100% unit-testable.

```python
NAMES: frozenset[str]            # her name as Whisper spells it
MAX_SENTENCE_CHARS = 240

wake(heard) -> str | None        # None = not for her; "" = name only; else the command
take_sentences(buffer) -> (list[str], str)
for_speech(text) -> str
is_garbage(heard) -> bool
echoes(said, heard) -> bool
```

**`wake` — an explicit allow-list, and it must stay one.** Fuzzy matching cannot do this job.
Measured with `difflib.SequenceMatcher` against `"donna"`:

| heard | ratio | | heard | ratio |
|---|---|---|---|---|
| `dona` | 0.889 | | `gonna` | **0.800** |
| `donnna` | 0.909 | | `madonna` | 0.833 |
| `danna` | 0.800 | | `dawn` | **0.444** |
| `donner` | 0.727 | | `open` | **0.444** |

The realistic Whisper mis-hearing `"dawn"` scores **identically to `"open"`**, while `"gonna"` —
an extremely common word — scores the same as the real mis-hearing `"danna"`. **No threshold
separates them.** The module carries this reasoning as a comment so nobody later "improves" it
into fuzzy matching.

Only the **first two words** are examined, and a name in second position requires a greeting
first. That one rule makes "I was talking to Dave about dinner" and "Madonna is on the radio"
free.

**`take_sentences` — a sentence ends only once whitespace follows its terminator.** Mid-stream,
`"I found report."` may still be becoming `"report.pdf"`, and `"It costs 3."` may be becoming
`"3.5"`. Waiting for the space costs about 60ms on a real stream and removes every decimal- and
filename-splitting bug at once. `MAX_SENTENCE_CHARS` is load-bearing for the latency budget, not
defensive padding: without it a reply with no punctuation delays her first word until the model
finishes.

**`for_speech` — required, not a nicety.** Nothing in `agent.SYSTEM_PROMPT` forbids markdown, so
Piper would read "asterisk asterisk V S Code asterisk asterisk" and spell out URLs. Strips code
fences, backticks, emphasis, bullets and emoji; replaces URLs with "the link"; shortens long
paths to the filename. **The screen keeps the markup; only the spoken copy is cleaned.** Applied
per sentence *after* splitting, because the splitter needs the original punctuation.

**`is_garbage` — structural only.** Returns true when there is no actual word, after stripping
bracketed tags like `[BLANK_AUDIO]`. A blocklist of Whisper's silence hallucinations
(`"Thank you."`, `"Thanks for watching!"`) was considered and **rejected**: while asleep `wake()`
already filters 100% of them, and while awake such a blocklist creates a real bug — she ignores
you when you thank her.

**`echoes` — the only defence against a self-trigger loop.** If she hears her own tail and it
contains her name, she wakes herself. ~8 pure lines comparing a transcript against what she just
finished saying.

### 4.2 `stt.py` — the only file that knows faster-whisper exists

Mirrors `llm.py`'s role, including its env-var escape hatch.

```python
MODEL = os.environ.get("DONNA_WHISPER_MODEL", "base.en")   # size confirmed by Stage 0
SAMPLE_RATE, MIN_SECONDS = 16000, 0.3
class SttError(Exception): ...
transcribe(pcm) -> str      # DONNA_STT=fake makes the audio bytes BE the text
warm()                      # load at startup so your first sentence isn't the slow one
```

Three deliberate choices:

- **`DONNA_STT=fake` decodes the bytes as UTF-8** — the same kind of deliberately dumb stand-in
  as `DONNA_LLM=fake`'s keyword rules. This is what lets the whole voice path run over a real
  socket with no model, no network and no audio fixtures.
- **The "too short" and "not even PCM" guards live here**, not in `voice` — that is Whisper's
  business, and keeping them here is what lets a 13-byte fake frame work.
- **`initial_prompt="Donna."`** biases transcription toward the right spelling of her name: a
  free reliability lever on the exact thing the measurements say is fragile. Also
  `beam_size=1`, `vad_filter=False` (the window already did that) and
  `condition_on_previous_text=False` (stops repetition hallucinations).

### 4.3 `tts.py` — the only file that knows Piper exists

`synthesise(text) -> bytes` of raw PCM16 at `SAMPLE_RATE`, no WAV header, ready to go straight
out as a binary frame. Plus `warm()`, `TtsError`, and `DONNA_TTS=fake` returning silence of a
plausible length so the timing arithmetic stays exercised.

`piper-tts` ships a native `win_amd64` wheel, so it runs **in-process** — no subprocess spawn per
sentence.

Two files rather than one `audio.py`: different libraries, different failure modes, different
lifecycles, opposite ends of a turn, and 10B rewrites `tts` (streaming, cancellable) without
touching `stt`.

### 4.4 `voice.py` — the session

The only stateful new file. It sits above `agent`, at the same level as `server`, and imports
`speech_text`, `stt`, `tts`, `agent` — deliberately **not** `websockets`, so the whole state
machine is testable without a socket.

```python
ASLEEP, AWAKE, SPEAKING = "asleep", "awake", "speaking"
SILENCE_SECONDS = 30
MAX_UTTERANCE_BYTES = 20 * 16000 * 2     # 20s
TAIL_SECONDS = 0.25                      # let her last word finish before the mic reopens

class Session:
    def __init__(self, send, history): ...
    def on_audio(self, pcm): ...         # one binary frame = one whole utterance
    def on_text(self, text): ...         # a typed message: same turn, no transcription
```

Decisions baked in:

- **`history` is the same list object the connection already owns**, so you can type a question
  and ask a spoken follow-up.
- **No fourth "thinking" state.** The UI already shows "DONNA is thinking…" while waiting with
  no text; it sets that flag when a `transcript` arrives. The 1.7–3.7s gap is covered with zero
  extra protocol.
- **Sleep expiry is lazy** — checked on the next utterance, not by a timer. No thread, no
  timeout loop, honouring "no concurrency added". The cost: the header pill does not flip to
  "asleep" until you next speak.
- **`_now` / `_sleep` are module-level names** so tests monkeypatch them, which is the house
  style rather than constructor injection.

**Ending SPEAKING.** Nothing tells Python when playback finished, so it is computed — and *not*
as `total_samples / rate`. She sends sentence 1 at t=1s and sentence 4 at t=4s, and playback is
a schedule, so Python mirrors the browser's scheduler exactly:

```python
self._playback_ends = max(_now(), self._playback_ends) + len(audio) / 2 / tts.SAMPLE_RATE
```

`max(_now(), ...)` is the whole trick, and it is the same line the frontend's player uses.
`TAIL_SECONDS` then keeps the mic from reopening on her own last syllable.

**`_ReplyVoice`** — the `send` wrapper, a small private class in the same file. It forwards every
message unchanged, accumulates `assistant_delta` text, and speaks each sentence as it completes.
Three things in it are load-bearing:

1. **A `spoke_something` flag prevents double-speaking.** Deltas produce "Hello.", then
   `assistant_message` carries the same "Hello."; without the flag you cannot tell that from
   "no deltas ever arrived" and she says it twice.
2. **A reply that never streamed is spoken whole.** `agent.py` sends `"Sorry, I got stuck trying
   to do that."` and every `error` as an `assistant_message` with **no deltas at all**. Without
   this branch both are completely silent — she just stops responding while you are across the
   room. This branch is required, not defensive.
3. **Any non-delta message resets the buffer**, keeping the accounting per tool round. The
   agent sends only the last round's content as `assistant_message` while deltas accumulate
   across all rounds.

Accepted consequence: a model that writes a preamble before calling a tool will say it out loud,
then say the answer — two spoken utterances, still exactly one `assistant_message`. That is how
a person sounds.

### 4.5 `server.py` — about eight lines

```python
MAX_FRAME_BYTES = 2 ** 21      # the default 1 MiB closes the connection at 32.8s of speech

def send(message):
    # Binary means audio, JSON means everything else.
    websocket.send(message if isinstance(message, bytes) else json.dumps(message))

for raw in websocket:
    if isinstance(raw, bytes):
        session.on_audio(raw)
        continue
    ...                        # existing JSON path, unchanged
```

`send` embodies the protocol rule in one line in one place, which is why `voice.Session` takes a
single `send` rather than two callbacks: a test's fake `send` stays `sent.append`, so tests see
the real interleaving of JSON and audio in one list.

The protocol table in the module docstring must be updated **together with** `PLAN.md` §5 —
`PLAN.md:107` requires both copies to match. Six message types becomes eight.

---

## 5. Error handling

The organizing principle: **an open mic hears everything, so "nothing to do" must be completely
silent.** An `error` every time you cough would make the panel unusable. And an error during a
spoken turn should be *spoken*, because you are across the room — except when the broken thing
is her ability to speak.

| Failure | Protocol | What you get |
|---|---|---|
| No mic permission / no device | none — the backend cannot know | A panel line and a Retry on the Start-voice button. Frontend state, deliberately not an `error` frame. |
| Whisper model missing on first run | `state {deaf}`, once | Header reads "can't hear". Mostly prevented: `warm()` at startup prints "first run downloads ~75 MB", moving the wait out of your first sentence. Typing still works. |
| Whisper returns empty or garbage | **nothing** | Silence. Logged at DEBUG so near-misses can be grepped. |
| Piper voice missing | `state {mute}`, once | Header reads "voice unavailable". **The turn still completes** as text; she is a typed assistant until it is fixed. |
| Synthesis fails mid-reply | one `state {mute}` | She says sentence 1, goes quiet, the full text is on screen. Must **not** abort the turn — the next sentence may work. |
| Audio arrives while SPEAKING | **nothing** | Dropped. The frontend also gates on `state`; two independent guards, neither trusted alone. |
| Utterance shorter than 0.3s | **nothing** | A cough, a click, a door. |
| Utterance longer than 20s | **nothing**, logged WARNING | Dropped before it can hit the frame cliff. |
| Non-PCM or odd-length frame | **nothing** | A buggy or hostile client is ignored, not a crash. |
| Ollama unreachable | existing `error`, **unchanged** | Shown in red *and spoken*, via the no-deltas branch. Zero new code. |
| `MAX_TOOL_ROUNDS` hit | existing `assistant_message` | Spoken, for the same reason. This is the case that proves the no-deltas branch is necessary. |
| Socket drops mid-reply | connection ends | The UI reconnects in 2s and the session resets to ASLEEP. No persistent state to clean up. |
| You type while she speaks | — | The playback wait blocks the read loop, so the message is answered when she finishes. The UI must disable Send while `state === "speaking"`. |

**Keeping "exactly ONE final reply" true.** The hard case is a capability failure *during* a turn
that also ends in `assistant_message`. An `error` frame there would be a second final reply, and
`chat.py`, `App.tsx` and `test_server.py` all treat `error` as terminal. The fix needs no new
type: capability notices ride the existing `state` channel as `deaf` / `mute`. This slightly
mixes capability into a state channel; the alternative — relaxing the one-final-reply rule — is
far worse, and breaks three clients.

---

## 6. Testing, dependencies and build assets

### Pure, no dependencies, table-driven

`wake`, `take_sentences`, `for_speech`, `is_garbage`, `echoes`. The highest-value tests in the
project, because this is where the edge cases live.

The two that matter most:

- **`test_wake`** includes `"Gonna open VS Code" -> None` and `"Madonna is on the radio" -> None`.
  These are the regression test for the fuzzy-matching measurement, and the reason the
  implementation must stay an allow-list.
- **A property test on splitting:** for every case, `" ".join(sentences + [rest]).split() ==
  buffer.split()`. Whatever the rules decide, no word may be lost or duplicated. It applies to
  cases nobody thought of, and a splitter bug almost always shows up this way.

### Needs fakes — monkeypatch, existing house style

`voice.Session` with a fake `stt.transcribe`, fake `tts.synthesise`, fake `agent.handle` and a
fake clock. The tests worth naming:

| test | asserts |
|---|---|
| an overheard remark while asleep | `sent == []` — **not one byte**. The single most important behaviour of an open mic. |
| hearing her name wakes her | the exact message sequence, `transcript` carrying the raw text, and that the agent received only the command |
| no name needed while awake | the second utterance runs without one |
| she sleeps again after 30s | clock advanced; a nameless utterance is then ignored |
| audio ignored while speaking | `stt.transcribe` never called |
| each sentence spoken as it streams | **the first audio frame appears before the `assistant_message`** — the latency win, asserted by index |
| the final reply is not spoken twice | deltas "Hello." + `assistant_message` "Hello." → spoken once |
| a reply that never streamed is still spoken | the `MAX_TOOL_ROUNDS` message is spoken |
| an error is spoken | and state returns to `awake` |
| speaking lasts as long as the audio | the computed sleep matches the scheduled duration |
| exactly one final reply | across every scripted reply |

Over a real socket, with `DONNA_STT=fake`, the standout is
**`test_an_overheard_remark_produces_no_traffic_at_all`**: `recv(timeout=0.5)` must raise
`TimeoutError`. "She is completely silent" is the behaviour an open mic lives or dies on, and it
is hard to assert any other way.

### The frontend gap, stated plainly

**There is no frontend test runner, so voice behaviour there will be 0% covered.** `npm run
build` checks types and bundles; it proves nothing about behaviour. Expect these to be caught
only by ear:

- wrong sample rate → chipmunk or baritone (obvious)
- Float32→Int16 scaling or endianness → static (obvious)
- VAD firing on her own voice → she talks to herself (obvious, and the worst)
- **the mic actually running at 48 kHz because the constraint was ignored → Whisper transcribes
  gibberish (not obvious — this one costs an hour)**

Four mitigations that need no test runner: put the one arguable piece (`toPcm16`) in a pure
exported function; lean on the existing exhaustive `never` switch, which will refuse to build
until the UI handles `transcript` and `state`; assert `len(frame) % 2 == 0` from the Python
side; and log the received byte count and its implied duration at DEBUG, which turns Stage 7a
into a one-breath check.

### Dependencies must not reach CI

`backend/requirements.txt` **does not change.** The CI pip cache is keyed on its hash, so
leaving it alone keeps backend CI exactly as fast as today; adding faster-whisper and piper-tts
would mean ~250 MB of wheels on every push for code CI never runs.

- New `backend/requirements-voice.txt`, installed only on the machine with a microphone.
- Every heavy import is lazy, inside a function, so `import stt` is safe with nothing installed.
- A missing package raises `SttError`/`TtsError` naming the file to install — the same shape as
  the "run `ollama pull`" message. **No silent fallback to the fake:** on your PC a broken
  install must say so, not quietly transcribe nothing.
- `.gitignore` gains `*.onnx` / `*.onnx.json` as a tripwire. Models live in `~/.cache`.

### Frontend assets

`@ricky0123/vad-react` fetches a Silero `.onnx` (~1.8 MB) **and onnxruntime-web's WASM binaries
(~10–25 MB)** — the latter is the decisive number, an order of magnitude larger than the model
everyone focuses on. Copy both from `node_modules` at build time with a small script wired into
`dev` and `build`; `frontend/public/` is gitignored. **The script throws on a missing source
file**, which makes `npm run build` in CI the only automated check the frontend voice work gets.
`onnxruntime-web` becomes a direct devDependency so the copy path is stable across installs.

Rejected: committing the assets (27 MB in git forever, and they silently mismatch when the
dependency is bumped) and the CDN default (a local-first assistant that needs jsdelivr to hear
you contradicts the premise, and the offline failure is silent). The CDN is fine for one smoke
test in Stage 7 before debugging the asset plumbing.

---

## 7. Staging

Each stage ends in something runnable, and each failure lands on a small surface.

| | |
|---|---|
| **0** | **Measure Whisper and Piper on the real PC before writing any protocol code.** The design rests on 1.7–3.7s. If `base.en` takes 2.5s instead of 0.7s, the model choice and possibly the sentence granularity change — a one-constant fix now versus a redesign at Stage 7. Throwaway script; the output is numbers in `PLAN.md` §6a and a value for `stt.MODEL`. |
| 1 | `speech_text.py` + tests. Pure, no deps, no protocol. |
| 2 | `stt.py`, `tts.py` (fakes), `voice.py` + tests. No socket, no audio. The state machine and the one-final-reply rule are proven. |
| 3 | `server.py` binary routing + socket tests + `/say` in `chat.py`. **The full voice path, runnable from the terminal, with no microphone, no model and no frontend.** |
| 4 | Real `stt.py` on the Windows PC. First heavy dependency. |
| 5 | Real `tts.py`. **The entire backend is now complete and verified with no frontend in existence** — all Python risk retired before any audio plumbing. |
| 6 | Frontend playback only, no mic. Type a message, hear the answer. |
| 7 | Microphone + VAD. **7a:** mic → `toPcm16` → send with fake STT; say "one two three" and confirm the log says ~1.5s — this catches the 48 kHz, Float32 and endianness bugs in one breath. **7b:** real Whisper; tune `NAMES` from real mis-hearings. |
| 8 | Measure end-of-speech → first spoken word against the ≤5s budget. Record in `PLAN.md` §6a; update the protocol table in both places. |

---

## 8. Risks and the constants to tune

- **Echo cancellation is an assumption, not a fact**, and it is the risk most likely to make 10A
  feel broken. With external speakers at volume, AEC can fail, and the failure is a loop: she
  hears her own tail, it contains her name, she wakes herself. Four defences: AEC itself,
  `TAIL_SECONDS`, dropping frames while SPEAKING, and `echoes()`.
- **Nothing but arithmetic ends SPEAKING.** `TAIL_SECONDS` too small and she clips her last word
  or wakes on it; too large and she feels sluggish. One constant, tuned by ear at Stage 8, and
  load-bearing for the risk above.
- **The wake word's false-negative rate is unknowable before Stage 7b**, and it changes with the
  Whisper model — swapping `stt.MODEL` can silently break waking. Every rejected transcript is
  logged at DEBUG so `NAMES` can be tuned from real data. **Expect to edit that set**, which is
  why it is a one-line module constant with a comment saying so.
- **Whisper latency is the budget's biggest unknown** and the one thing software cannot fix
  later. Stage 0 exists solely for it.
- **An open mic in a room with a TV pins a core** — Whisper runs on every utterance, not just
  yours. Acceptable on a 5800X, and precisely why a real wake-word model (10C) is worth having
  eventually. It is a CPU optimisation, not a missing capability.
- **Two clients at once means two voices.** `agent.handle` now holds its connection thread for
  15+ seconds. Nobody runs the UI and `chat.py` simultaneously; noted rather than defended
  against.

### Constants that will need tuning

| | default | tuned at |
|---|---|---|
| `stt.MODEL` | `base.en` | Stage 0 |
| `voice.SILENCE_SECONDS` | 30 | Stage 8, by feel |
| `voice.TAIL_SECONDS` | 0.25 | Stage 8, by ear |
| `speech_text.NAMES` | 10 spellings | Stage 7b, from real data |
| `speech_text.MAX_SENTENCE_CHARS` | 240 | only if a reply stalls |
