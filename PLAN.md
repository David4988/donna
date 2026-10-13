# DONNA: the simple build plan

> **Vision:** see README.md. **This file:** how we build the first working version, one small step at a time.

## 1. Vision vs. v1

The README describes the full DONNA, all running on student hardware (Ryzen 7 5800X, RX 580 8 GB, 32 GB RAM):
- a local, voice-first desktop assistant
- a 3D golden-sphere avatar
- computer control, file search and web search
- later: gestures, a projected desk UI and multi-camera spatial interaction

**v1 is the smallest useful slice of that: typed chat with four abilities.**

| You type | DONNA |
|---|---|
| "Hello Donna" | replies "Hello." |
| "Open VS Code" | launches VS Code |
| "Find my TrialGuard files" | lists matching files |
| "Search the web for X" | searches and summarizes the top results |

Voice, the avatar, gestures and the projector come later, one step at a time.

## 2. The whole system on one page

```text
┌───────────────────────┐   WebSocket (JSON)   ┌───────────────────────────────┐
│ Frontend              │ ───────────────────▶ │ Backend (Python)              │
│ React (later: Tauri)  │ ◀─────────────────── │  server.py ─▶ agent.py        │
│ shows messages,       │                      │                │       │      │
│ sends what you type   │                      │            llm.py   tools.py  │
└───────────────────────┘                      └────────────────┼───────┼──────┘
                                                                │       ├─ open_app
                                                   Ollama + Qwen3.5     ├─ find_files
                                                                        └─ web_search
```

**What happens when you type "Find my TrialGuard files":**

1. The frontend sends `{"type": "user_message", "text": "Find my TrialGuard files"}`.
2. `server.py` receives it and hands the text to the agent.
3. `agent.py` adds it to the conversation and asks the LLM, also telling it which tools exist.
4. The LLM doesn't answer with text. It answers *"call `find_files` with query = TrialGuard"*.
5. The agent tells the frontend what it's doing (`tool_call`), runs `find_files`, sends the result (`tool_result`), and adds the result to the conversation.
6. The agent asks the LLM again. This time it answers with text: *"I found 3 TrialGuard files: …"*
7. The agent sends that as `assistant_message`, and the frontend displays it.

For "Hello Donna" the LLM answers with text straight away, so steps 4–6 don't happen. **That loop (ask the LLM → maybe run a tool → ask again) is the entire agent.**

## 3. Folder structure (once Step 9 is done)

```text
donna/
├── README.md              vision (unchanged)
├── PLAN.md                this file
├── .gitignore
├── backend/
│   ├── server.py          WebSocket server: receive → agent → send
│   ├── agent.py           the loop: LLM ↔ tools, plus the conversation history
│   ├── llm.py             talks to the model; one function, ask()
│   ├── tools.py           open_app, find_files, web_search + their descriptions for the LLM
│   ├── chat.py            terminal client: use DONNA before the UI exists (and for debugging)
│   ├── requirements.txt   websockets, httpx, ddgs, pytest
│   └── tests/             test_agent.py, test_tools.py, test_server.py
├── frontend/
│   ├── src/App.tsx        the whole UI: connect, show messages, send text
│   ├── src/main.tsx, index.html, package.json, vite config
│   └── src-tauri/         Step 9: desktop window (default Tauri files, no custom Rust)
└── .github/workflows/test.yml   runs the tests on every push
```

That is roughly **300 lines of Python and 150 of TypeScript**. Folders are flat, with no packages inside packages, and you can say in one sentence what each file does.

## 4. Why each piece exists

| Piece | Why it exists |
|---|---|
| `server.py` | The UI runs as JavaScript in a window and the brain is Python, so they need a pipe between them. A WebSocket is one connection both sides can talk on. That matters because the backend has to *push* messages ("Searching files…" now, voice and avatar state later), which plain request/response HTTP can't do. |
| `agent.py` | Something has to run the loop (ask → tool → ask → reply) and remember the conversation. Keeping it separate means networking (server) and "how to call Ollama" (llm) don't get mixed into what DONNA *decides*. |
| `llm.py` | The only file that knows how to talk to a model. Ollama, llama.cpp's server and LM Studio all speak the same OpenAI-style HTTP API, so changing the model is one constant and changing the server is one URL. No class hierarchy needed. |
| `tools.py` | The complete list of what DONNA can do to your computer, which also makes it **the safety boundary**: if it isn't in this file, the LLM can't do it. |
| `chat.py` | Lets you use DONNA from a terminal in Steps 2–7, before there's a UI. About 40 lines, and it stays useful for debugging. |
| `tests/` | Prove the loop and the tools work without needing the model, the internet or Windows. |
| `frontend/` | Shows the conversation and sends what you type. It decides nothing. One component until it genuinely needs splitting. |
| Tauri (Step 9) | Gives DONNA its own desktop window, and for voice (Step 10) the microphone, the speakers and the global hotkey that starts a conversation. Until then the browser works fine. |

- **Why Python for the backend?** The AI pieces DONNA needs later (Whisper for speech-to-text, Piper for text-to-speech, MediaPipe for gestures) are Python-first, as the README already decided.
- **Why no agent framework (LangChain etc.)?** The loop is about 40 lines. A framework would hide exactly the part you want to understand.

## 5. The messages (this is the whole protocol)

Every message is JSON with a `type`.

| Direction | `type` | Fields | Example |
|---|---|---|---|
| UI → backend | `user_message` | `text` | `{"type": "user_message", "text": "Open VS Code"}` |
| backend → UI | `tool_call` | `name`, `args` | `{"type": "tool_call", "name": "open_app", "args": {"app": "vscode"}}` |
| backend → UI | `tool_result` | `name`, `result` | `{"type": "tool_result", "name": "open_app", "result": "Opened Visual Studio Code."}` |
| backend → UI | `assistant_delta` | `text` | `{"type": "assistant_delta", "text": "VS Code "}` |
| backend → UI | `assistant_message` | `text` | `{"type": "assistant_message", "text": "VS Code is open."}` |
| backend → UI | `error` | `text` | `{"type": "error", "text": "Can't reach the model. Is Ollama running?"}` |

**One rule:** every `user_message` gets exactly **one** final reply, either an `assistant_message` or an `error`. `tool_call`, `tool_result` and `assistant_delta` messages may come before it. Clients show "thinking…" until the first piece of the answer arrives.

`assistant_delta` carries the next piece of the answer as the model types it. Deltas are **additive and advisory**: the `assistant_message` that follows always holds the complete text, so a client may ignore them entirely and lose nothing. Any non-delta message ends the run of deltas before it. That is what keeps the one-final-reply rule true while the answer streams.

This table lives here and in a comment at the top of `server.py`. There are no schema files and no code generation: with six message types, a table is easier to keep correct. We'll revisit that only if the protocol grows a lot or starts breaking.

## 6. Key decisions (tell me if you disagree)

1. **Plain synchronous Python, no asyncio.** The `websockets` library has a threaded mode in which each connection runs top to bottom like a normal script. The trade-off: voice will need things to happen at the same time (listening while speaking, interrupting DONNA mid-sentence). That's the first feature that actually requires concurrency, so we revisit this then and not before.
   - Streaming did **not** force that conversation, which is worth recording. The token callback runs on the connection's own thread — the whole call stack is `handle_connection → agent.handle → llm.ask → read_stream → on_delta → send`. No queue, no event loop.
   - **Voice does not force it either, as it turns out.** Step 10A keeps plain synchronous Python. Half-duplex voice is strictly sequential — listen, then think, then speak, then listen — so it fits the existing one-thread-per-connection server unchanged. The browser does the sensing (voice-activity detection on the echo-cancelled signal) and sends one finished utterance, so Python never has to listen and think at the same time.
   - **Interruption** — listening *while* speaking — is the part that genuinely needs concurrency, and that is Step 10B. So this decision survives into voice and gets revisited at barge-in, which is later than this plan originally guessed.
   - The answer streams because `llm.py` reads Ollama's reply as it arrives rather than waiting for the end. The README calls this event `reply.delta`; the built protocol spells it `assistant_delta`, for the same reason `tool.start` is spelled `tool_call` — the README is the vision, this table is what exists.
2. **Security is localhost plus an Origin check, with no tokens.**
   - The server only listens on `127.0.0.1`, so nothing on your network can reach it.
   - The realistic remaining threat is a random website in your browser connecting to localhost, which browsers allow for WebSockets. The Origin check blocks that in one line.
   - A token would only stop other programs already running on your PC, and those can already do anything you can.
3. **The LLM can only call three functions.**
   - There is no "run command" tool, and model text never reaches a shell.
   - `open_app` launches only apps from a fixed list in `tools.py`, and that list is given to the LLM as the only allowed values.
   - `find_files` is read-only and returns names and paths, never file contents.
   - `web_search` only reads.
   - The agent stops after 5 tool rounds per message, so a confused model can't loop forever.
4. **File search starts as a plain Python folder walk** over Desktop, Documents and Downloads, skipping `node_modules`, `.git` and similar folders. It's easy to read and test and needs nothing installed. If it's too slow on your machine, we switch that one function to Everything (`es.exe`), as the README plans.
5. **The LLM is reached through Ollama's OpenAI-compatible HTTP API using `httpx`.** That's about 20 lines, and you can see exactly what's sent to the model. The model name is one constant (overridable with `DONNA_MODEL`), so a laptop can run a small model and the desktop a larger one.
   - **The model is Qwen3.5, not the Qwen3.6-35B-A3B this plan first assumed.** Measured on the RX 580 (see §6a), `qwen3.5:4b` beat `qwen3.5:9b` on *both* speed and tool-calling reliability, so 4b is the main model and what voice is designed around.
   - **`qwen3.5:9b` is the fallback.** If the main model isn't pulled, Ollama answers 404 and `llm.py` retries once with the fallback, logs a warning and remembers the choice, so later turns don't repeat the failed call. If neither is pulled you get one clear error telling you what to `ollama pull`. Both are overridable: `DONNA_MODEL`, `DONNA_FALLBACK_MODEL`.
6. **Offline fake brain (`DONNA_LLM=fake`).** A few keyword rules inside `llm.py` let DONNA run without Ollama: on your laptop while you're away from the desktop, and in CI. Step 3 also uses it, before the real model is connected.
7. **No result IDs yet.** They only matter once DONNA can open a file it found ("open the second one"), and that isn't in v1. When we add it, it's a small dict of the last results.
8. **Folders are named `backend/` and `frontend/`.** That matches the mental model; the README's planned layout uses `core/` and `desktop/`. I'm leaving the README as it is.

## 6a. What the hardware actually does (measured, 2026-10-09/10)

This plan guessed about the GPU and guessed wrong. The real numbers, measured on the
Ryzen 7 5800X + RX 580 8 GB:

| | `qwen3.5:4b` | `qwen3.5:9b` |
|---|---|---|
| Tool routing (same 15 prompts) | **15/15** | 14/15 |
| Generation | ~~17.0 tok/s~~ **15.1 tok/s** | 14.4 tok/s |
| Prompt processing | **169 tok/s** | 95 tok/s |
| VRAM used | **3.15 GB** | 5.50 GB |
| First word, cold, tools attached | **3.07s** | 5.43s |

The 17.0 was ~11% optimistic and every latency estimate in this document
inherited it. Re-measured 2026-10-12, best of three short generations with a tight
spread (15.1, 14.4, 15.0). Long outputs are slower still: an 826-token reply ran at
**12.9 tok/s**, so her "one to three sentences" rule is not only about not boring you.

Three findings that change decisions:

1. **The model runs entirely on the GPU.** Step 4 below assumed "most of it will sit in your
   32 GB of system RAM". Wrong: Ollama's **Vulkan** backend offloads all 34 layers to the
   RX 580, 0 bytes in system RAM. Vulkan matters — ROCm dropped Polaris years ago, so without
   it this card would be unusable.
2. **The fixed prefix costs seconds of prompt processing, but only on the first turn.** Within
   a continuing conversation the prefix is cached and turn 2 onward costs ~0.39s, taking a full
   round trip from 3.44s to **0.85s**. ~~Pre-warming the cache at startup therefore hides the
   whole cold cost~~ — which this document asserted for three days without it being implemented.
   It is now (`agent.warm()`), and it matters far more since the prefix grew from 496 to 2,744
   tokens with ABOUT_ME.md in it. Measured against a freshly restarted Ollama:

   | | first spoken word |
   |---|---|
   | no pre-warm | **25.45s** |
   | `agent.warm()` at startup | **4.43s** |

   The warm itself takes ~26s, so startup roughly doubles (~20s to ~46s) and 21 seconds move
   out of your first sentence. For something left running that is the right trade; a 25-second
   first reply is not an assistant. Note it runs before `serve()`, so nothing can connect until
   it finishes — moving it after would need a thread, and the log says what it is doing.
3. **The bigger model was the less reliable one.** On "Open notepad", 9b replied *"I'm opening
   Notepad for you now"* **without calling the tool** — it claimed to have done something it
   hadn't. 4b never did this. That, not speed, is why 4b is the choice.

Generation speed is memory-bandwidth bound on a 2016 card; ~15 tok/s is the ceiling and no
setting moves it. The lever is model size — but see §6a.3, which measures how little that
lever actually gives.

### 6a.3 Smaller did not work either (measured 2026-10-12)

4b beat 9b going up. The obvious next question is whether something smaller beats 4b going
down, so `qwen3.5:2b-q4_K_M` was pulled at **the same Q4_K_M quantisation** — the plain `2b`
tag is 2.7–3.1 GB at a higher quant, and comparing against it would have measured
quantisation rather than size.

| | routing | generation | tool call | VRAM |
|---|---|---|---|---|
| `qwen3.5:4b` | **40/40** | 15.1 tok/s | 4.94s | 3.1 GB, 100% GPU |
| `qwen3.5:2b-q4_K_M` | 28/40 | 17.3 tok/s | 3.20s | 1.6 GB, 100% GPU |

**All twelve failures were missed tool calls**, never a wrong tool or a mangled argument:

```
no tool <- 'Find my tax files.'
no tool <- "What's the weather in London right now?"
no tool <- 'Look up who won the 2026 Super Bowl.'
```

It kept all 20 no-tool cases correct and lost 12 of the 20 real requests — the worst failure
mode available, since she would simply chat instead of doing the thing. The reward was
**+15% generation**, not the 1.5–1.7× predicted from the bytes ratio (3.3/1.9 = 1.74×): there
is a fixed per-token cost that does not shrink with the model, so "just use a smaller model"
has sharply diminishing returns on this card.

So 4b is the sweet spot in both directions, and it is not close either way. This agrees with
an independent 13-model tool-calling test (March 2026) that ranked Qwen3.5 4B **first at
97.5%**, above GLM-4.7-Flash (18 GB, 95%) and Mistral Small 3.2 24B (15 GB, **42.5%**, 0/8 on
multi-tool), and found no correlation between model size and tool-calling quality.

Ruled out for this hardware, so nobody re-tries them: **9b** (measured worse), **anything
12–30B dense** (will not fit 8 GB), and **`qwen3.5:35b-a3b`** — the MoE with ~3B active
parameters that would generate at near-3B speed with 35B-class quality, and is 22 GB. That one
is a GPU question, not a model question.

### 6a.1 How she sounds (measured 2026-10-11)

Three complaints after the first real use of voice: web search felt slow, the voices were a
menu of one, and *"it doesn't feel like a conversation and more like blandly reading a
sentence."* All three were measured before anything was changed, and two of the three answers
were not what they looked like.

**Piper voices.** Synthesising one sentence, after a warm load:

| | load | one sentence | vs realtime |
|---|---|---|---|
| `medium` voices (amy, alan, jenny) | ~2.9s | **0.14s** | 40x |
| `high` voices (lessac, cori, ryan) | ~3.0s | **0.70s** | 7.2x |

A `high` voice therefore costs about **+0.55s before she starts talking**. It never starves
playback — 7x realtime is still far ahead of the speaker — so this is a first-word cost, not a
stuttering one. The default stays a `medium` voice and the menu says "richer" for the others.

**Pronunciation.** Phonemising candidates with the real voice shows what Piper does, rather
than what one would assume. Wrong, and now fixed in `speech_text.say_numbers()`:

| written | Piper said | now |
|---|---|---|
| `20C` / `20°C` | "twenty **see**" | "twenty degrees Celsius" |
| `20F` | "twenty **ef**" | "twenty degrees Fahrenheit" |
| `12 mph` | "twelve **em-pee-aitch**" | "twelve miles per hour" |
| `5 km/h` | "five **kay-em slash aitch**" | "five kilometres per hour" |
| `1.5kg` | "one point five **kay-jee**" | "one point five kilograms" |
| `$14.50` | "**dollar** fourteen point five zero" | "fourteen dollars fifty" |

Already correct and deliberately left alone: `3.4GHz` ("gigahertz"), `70%` ("percent"),
`500MB` ("em-bee", which is what people say), `e.g.` ("for example"), `JSON` ("jay-sawn"),
`README` ("reed-me"), and every name in this project — Ollama, Tauri, Qwen, Piper, DONNA,
Jarvis. Adding rules for those could only make them worse.

**Web search.** The network was the smaller half. Reading the results back is the cost: at
169 tok/s of prompt processing, every 170 tokens of snippet is another second of silence. Five
results for *"what is openwakeword"* came back as 8,918 characters — about 2,200 tokens, or
13 seconds — and 8,111 of those were one GitHub README dumped whole, while the other four
snippets were all under 240 characters. Hence the 300-character cap.

The engine choice corrected a guess made from a stale log. Pinning to DuckDuckGo — which that
log showed answering after Google and Brave were refused — **fails outright** from this PC now;
`auto` is what makes search work at all. But `auto` asks several engines in parallel and
averages 3.3s where `yahoo` alone averages 1.0s, and they are independently flaky, each failing
on queries the other answered. So: quick engine first, broad set as the fallback.

Interleaved old-vs-new over three queries, in one process:

| | first spoken word | handed to the model |
|---|---|---|
| 5 results, uncapped, `auto` | 11.98s | 378 tokens |
| 4 results, 300 chars, `yahoo`→`auto` | **8.48s** | **280 tokens** |

**A search turn cannot meet the 5s first-word budget on this hardware, and the search is no
longer why.** The model spends 4–5s just deciding to call the tool: ~500 prompt tokens of tool
definitions plus ~30 generated tokens of call at 17 tok/s. The budget in §9 is for a direct
answer. Speaking a holding phrase while the tool runs is the only lever left worth much, and it
is a voice-layer change rather than a search one — see §10B.

Two things found by running it live rather than on the bench, both worth knowing:

**Search time is genuinely variable, and the timeout is not the lever.** The same query took
16.3s and then 3.4s a minute apart, as engines rate-limit per IP. Capping `TIMEOUT_SECONDS`
looks like the obvious fix and measures the opposite, because a short timeout makes the quick
engine give up and forces the slow fallback:

| | mean | worst | failed |
|---|---|---|---|
| `timeout=10s` | **2.41s** | **4.53s** | **0/6** |
| `timeout=5s` | 2.92s | 5.21s | 3/6 |
| `timeout=3s` | 4.05s | 7.35s | 2/6 |

So it stays at 10, with a comment in `tools.py` saying why. One slow search is not evidence of
anything — measure over several queries.

**`web_search` cannot answer "what's the weather", and that is not a latency problem.** Real
snippets are page *descriptions*, not data: "Hourly weather forecast in London. Check current
conditions", "14-day weather forecast for London". Not one contains a temperature. Asked live,
she correctly said she has no real-time weather access and named two sites — honest, and the
right behaviour. Worth noting because the style benchmark fed her *synthetic* snippets
containing "Today 14C with light rain", so it was measuring a best case that search does not
actually deliver. Anything needing live numbers — weather, prices, scores — needs a real API,
not a snippet.

**The flatness is Piper itself, not the script.** The words were a smaller part of it than
expected: 11/12 of the model's tool-result summaries were already clean conversational prose
before the prompt was touched. The spoken-style paragraph takes that to 12/12 and buys real
brevity, but a fast VITS model reads rather than converses whichever voice it wears.

### 6a.2 Kokoro: measured, and cheaper than feared (2026-10-11)

The README has planned *"Piper → Kokoro — Piper for speed, Kokoro for that executive-assistant
elegance"* since before voice existed. This is the speed half of that trade, measured on the
identical sentence, best of five runs after a warm load:

| engine / voice | synthesis | plays for | vs realtime | rate |
|---|---|---|---|---|
| piper `en_US-amy-medium` | **0.07s** | 2.86s | 41x | 22050 Hz |
| piper `en_US-lessac-high` | 0.33s | 2.39s | 7.3x | 22050 Hz |
| kokoro `af_heart` | 0.62s | 2.35s | 3.8x | **24000 Hz** |
| kokoro `bf_emma` | 0.66s | 2.41s | 3.6x | **24000 Hz** |

**Switching to Kokoro costs +0.55s on the first spoken word.** That is the whole latency
argument, and it is affordable: a direct answer is STT 0.44s + model ~0.9s warm + TTS 0.07s
≈ 1.4s today, so Kokoro makes it ≈1.95s against a 5s budget. The earlier worry that Kokoro
"would eat into the budget" was overcautious — it costs about the same as a Piper `high` voice
(+0.26s) and buys considerably more.

Two findings that were not expected:

1. **Kokoro loads faster than Piper** — 0.95s against ~2.9s — so startup gets *better*, not
   worse, despite a 326 MB model against Piper's 63 MB.
2. **Synthesis stays ahead of playback.** 3.8x realtime sounds tight next to Piper's 41x, but
   the only requirement is beating 1x: on a three-sentence reply, sentences 2 and 3 were each
   ready well before the previous one finished playing (0.76s of synthesis for 2.97s of audio).
   So this is purely a first-word cost, never a stutter.

**The blocker is the sample rate, not the speed.** Kokoro is 24000 Hz. `tts.SAMPLE_RATE` and
`audio.ts`'s `VOICE_RATE` are both hardcoded to 22050, with `installed_voices()` actively
filtering out anything else — so dropping Kokoro in today makes her a chipmunk. Carrying the
rate on the wire is the unblocking change, and the 10A design already flagged it. It also
retires `installed_voices()`'s rate filter and opens up Piper's `low` (16000 Hz) voices.

Not adopted yet: it is a 326 MB model and a protocol change, and the quality half of the trade
is the user's ear to judge, not a number. `kokoro-onnx` is installed in the backend venv for
this evaluation and is deliberately **not** in `requirements-voice.txt`.

## 7. Development steps (each one ends with something you can run)

| Step | Build | You can now… | Status |
|---|---|---|---|
| 1 | Skeleton: `backend/`, `requirements.txt`, `.gitignore`, venv instructions | run `pytest` (one smoke test passes) | ✅ done |
| 2 | `server.py` (echo) + `chat.py` | type "hi" in the terminal and get "You said: hi" back over the WebSocket | ✅ done |
| 3 | `agent.py` with the fake brain | "Hello Donna" → "Hello." through the real message flow | ✅ done |
| 4 | `llm.py` → Ollama + Qwen3.5 | actually chat with DONNA | ✅ done |
| 5 | `open_app` + the tool loop | "Open VS Code" opens VS Code | ✅ done |
| 6 | `find_files` | "Find my TrialGuard files" lists them | ✅ done |
| 7 | `web_search` | "Search the web for X" summarizes the results | ✅ done |
| 8 | React UI in the browser | use DONNA from a web page | ✅ done |
| 9 | Tauri window | use DONNA as a desktop app | ✅ done |
| 9.5 | Streaming replies | watch the answer being typed instead of waiting for it | ✅ done |
| 10A | Voice: she hears you and talks back | hold a conversation out loud, hands free | ✅ done |
| 10B | Voice: she can be interrupted | cut her off mid-sentence, like Claude voice | **next**, see 9a.4 |
| ~~10C~~ | ~~"Hey Donna" wake word~~ | ~~summon her by her own name~~ | **dropped from this plan** -- a separate project |
| 11 | 3D avatar | the golden sphere reacts to listening, thinking and speaking | after 10B; **the user is drafting the design** |
| 12 | Gestures | pinch and fist via webcam | later |
| 13 | Spatial / projector | projected desk UI | later |

**Steps 1–9.5 are DONNA v1, and 10A is built too** -- she hears you, answers out loud, shows your words as you speak and lets you pick a voice. 10B onward and 11–13 are not. Each gets its own short plan when we reach it, based on what the previous step taught us.

I merged your "Python backend" and "WebSocket connection" steps into Step 2, because a backend you can't talk to isn't something you can run.

**Notes on the steps that need them:**
- **Step 4 (model reality check).** This note was written before the hardware was measured, and
  it was wrong on every count. Kept here with the corrections, because the mistakes are
  instructive. See §6a for the numbers.
  - ~~Qwen3.6-35B-A3B … roughly 20 GB, so it won't fit in the RX 580's 8 GB. Most of it will sit
    in your 32 GB of system RAM.~~ We never used that model. `qwen3.5:4b` is 3.32 GB and runs
    **entirely in VRAM** via Ollama's Vulkan backend — nothing in system RAM.
  - ~~If it's too heavy, develop with a smaller Qwen.~~ Right instinct, wrong reason: the smaller
    model won on *accuracy* as well as speed.
  - ~~Turn "thinking" mode off … I'll confirm the exact Ollama setting at this step.~~ Confirmed:
    `reasoning_effort: "none"` on the OpenAI-compatible route. Ollama's native `{"think": false}`
    is **silently ignored** there, which cost an afternoon of confusing benchmarks.
- **Step 5.** `run_tool(name, args)` looks the tool up in a dict. An unknown tool, bad arguments or a crash returns an error text to the LLM instead of crashing DONNA.
- **Step 6.** A file matches when all the words in the query appear in its name (ignoring case). Results are newest first, with a maximum of 10.
- **Step 7.**
  - DuckDuckGo via `ddgs`, with no API key needed. The top 5 titles, links and snippets go to the LLM; we don't download the pages yet.
  - It's unofficial and may rate-limit. If that becomes a problem, we swap that one function for SearXNG (an open question in the README).
  - Web text is untrusted: a page could say "ignore your instructions…". That's acceptable now because DONNA's tools can't do damage, and it's the reason future risky tools (delete, move) will require your confirmation.
- **Step 8.** `npm create vite` (React + TypeScript), trimmed to the files we use. `App.tsx` opens the WebSocket, keeps the messages in `useState`, renders them by type and has an input box. The five messages get a hand-written TypeScript type. The UI shows connecting/disconnected and retries.
- **Step 9.** `tauri init` with default settings and no custom Rust. You start the backend yourself for now; auto-starting it comes later.
- **Step 9.5 (streaming).** `llm.py` reads Ollama's reply as it arrives and the agent forwards
  each piece as `assistant_delta`. First word in **0.19s** instead of 6.2s of blank panel. It
  needed no concurrency — see decision 1.
- **Step 10 (voice).** Full design: [`docs/superpowers/specs/2026-10-10-voice-10a-design.md`](docs/superpowers/specs/2026-10-10-voice-10a-design.md).
  ~~Push-to-talk.~~ **Not push-to-talk.** The goal is a conversation: you
  talk, she answers, you keep going without re-triggering anything — the way Claude's or
  ChatGPT's voice mode feels. Decided so far:

  | Decision | Choice |
  |---|---|
  | Interaction | **Open mic session.** Enter it once, then talk freely; she sleeps again after a stretch of silence. Not hold-to-talk. |
  | Entering the session | ~~A hotkey for now.~~ **"Hey Jarvis"**, using openWakeWord's pretrained model -- no training needed, and it means Whisper never runs while she is asleep. "Hey Donna" needs a custom model and is now a separate project rather than a step. She is still *called* DONNA; only the summons changed. |
  | Audio ownership | **Captured and played in the Tauri window**, streamed to Python over the existing WebSocket. The webview gives us echo cancellation and device handling for free; Python still decides everything. |
  | Speech-to-text | **faster-whisper on the CPU**, as the README planned. The 5800X carries it so the GPU stays free for the model. |
  | Text-to-speech | **Both.** Piper first (fast) and ~~Kokoro later~~ **Kokoro now**, selectable per voice. See 6a.2 -- it cost +0.55s to the first word, which the budget absorbs, and the sample rate travels with the audio instead of being a constant. |
  | Budget | **≤5s from you stopping to her FIRST spoken word** — not to the end of her answer. Measured to first audio, the way streaming is measured to first token. |
  | Shape | Split in two: **10A** she hears and speaks (half-duplex, strictly sequential), **10B** she can be interrupted. 10A is built so 10B slots in rather than forcing a rewrite. |
  | Concurrency | **None added in 10A.** The browser runs voice-activity detection and sends one finished utterance, so Python stays synchronous (decision 1). Barge-in in 10B is what needs concurrency. |
  | Where VAD runs | **In the browser**, using Silero through `@ricky0123/vad-react`, which hands over 16 kHz audio — exactly Whisper's input. It sits on the echo-cancelled signal, which is also what makes 10B's barge-in fast: the window can report "the user started talking" in ~100ms instead of shipping audio to Python to analyse. |

  Why the budget is reachable: with the cache warm (§6a), the model contributes ~0.9s to a
  reply. That leaves roughly 0.3–0.5s to notice you stopped, 0.5–1.0s for Whisper and
  0.1–0.5s for Piper — about **1.8–2.9s to the first word**. The 2.35 GB of VRAM that
  dropping to 4b frees is what leaves room for Whisper alongside the model.

  Why "Hey Donna" is a separate project: openWakeWord ships only `alexa`, `hey mycroft`,
  `hey jarvis` and `hey rhasspy`. A custom phrase needs synthetic-data training, and local
  training wants an NVIDIA GPU with CUDA — which this machine does not have — so it means
  Colab, roughly 1.5 hours, with reports of custom models recognising their phrase only
  50–60% of the time. That is too much uncertainty to put on the critical path.

  The frontend stays a **sensor, not a decider**: it reports "speech started", "speech ended,
  here is the audio". Python still decides what any of it means. That is a slight bend in the
  README's "the frontend decides nothing" rule, taken deliberately because the echo-cancelled
  microphone signal only exists in the webview.

  Still open while 10A is being designed: the exact new protocol messages, and how the
  spoken reply is cut into sentences for Piper.

## 8. Testing (proportional)

Testing is `pytest` only. Tests never need Ollama, the internet or Windows:
- The LLM is swapped for a scripted fake.
- The real "launch the app" and "ask DuckDuckGo" calls are swapped for fakes.
- `find_files` runs against a temporary folder containing real files.

The initial set was about 12 tests, each one added in the step that builds the behavior. It is
**55** now, the growth mostly from streaming (stream parsing, tool-call reassembly, mid-stream
failure) and the Windows fixes:
- **agent:** plain reply; tool call → tool runs → final reply; unknown tool (the error goes back to the LLM and DONNA still answers); the step limit.
- **tools:** known app is launched (without a shell); unknown app is refused; `find_files` matches the right files and skips `node_modules`; `web_search` formats the results; bad arguments are handled.
- **server:** a round trip over a real socket; a connection from a foreign website's Origin is rejected.

One small GitHub Actions workflow runs `pytest` on every push from Step 3. From Step 8 it also builds the frontend.

## 9. What we are NOT building yet

| Not now | When it comes back |
|---|---|
| Voice: mic, speech-to-text, text-to-speech | ~~Step 10A — being designed now.~~ **Built.** |
| Wake word ("Hey Donna") | ~~Step 10C.~~ **A separate project.** 10A ships openWakeWord's pretrained **"Hey Jarvis"**, measured at 0.950 on a bare summons, so her own name is a nicety and not a blocker. |
| 3D avatar / shaders | Step 11 |
| Gestures, cameras, MediaPipe | Step 12 |
| Projector, stereo cameras, spatial UI | Step 13 |
| State machine (IDLE → LISTENING → THINKING → SPEAKING) | **Step 10B.** Voice needs it, exactly as this row predicted: something has to own who is allowed to talk. |
| Interrupting DONNA (cancel / barge-in) | **Step 10B.** Now that replies are spoken rather than short and typed, there is something to interrupt. |
| ~~Streaming replies word by word~~ | **Built.** The trigger ("if replies feel slow") fired: on `qwen3.5:9b` at ~12.5 tok/s a short answer meant 6 seconds of blank panel. See §6. |
| Fast path (skip the LLM for "open X") | Only if we measure that "open X" is too slow. Adding it now would be premature optimization. |
| Opening found files, result IDs | When we add "open that file" |
| Everything (`es.exe`), Start Menu app index, fuzzy app names | When the folder walk or the fixed app list is too slow or too limiting |
| Reading full web pages | ~~When snippets aren't enough~~ **The trigger fired:** snippets are page descriptions, which is why "what's the weather" fails. See 9a.2. |
| Memory across sessions, moving/deleting files, desktop automation | **Started:** 9a.3 adds who *you* are, by hand; what she learns herself comes after. More of this PC in 9a.2. Risky actions will still require your confirmation. |
| Installer, auto-starting the backend from Tauri | When you use DONNA daily |
| Auth tokens, protocol schemas and codegen, event bus, plugin system, dependency-injection framework, microservices | Only if a real problem forces one of them |

## 9a. What's next, and in what order (planned 2026-10-13)

10A is built and Kokoro is in. The complaint now is not that she is slow or flat — it is that
**she doesn't know anything about the person she is talking to, and there is very little of
this computer she can actually touch.** Three tools (`open_app`, `find_files`, `web_search`) is
thin for something called a desktop assistant.

Order below is deliberate: the things that change how she *feels* first, because they are small
and we already know they work; the things that need a measurement last.

### 9a.1 Subtitles, not a chat log

**The bug:** the text races the voice. Deltas appear as the model generates; audio plays at
speaking speed, and speaking is far slower than generating. From the measured rates (15.1 tok/s
generating, one 14-word sentence taking 5.58s to say at 1.0x):

| speed | one sentence: say vs write | after three sentences |
|---|---|---|
| 1.0x | 5.6s vs 1.2s — **4.7x ahead** | text leads by **13.2s** |
| **1.3x** (what she is set to) | 4.3s vs 1.2s — **3.6x ahead** | text leads by **9.3s** |
| 2.0x | 2.8s vs 1.2s — 2.3x ahead | text leads by 4.8s |

**So a fixed 2-second delay does not fix this.** It corrects the first second and leaves seven
more of drift, and the drift grows with the length of the reply. The lag is not an offset, it is
a *rate* difference.

**The fix is to treat the text as what it is — a subtitle.** Reveal each sentence when its own
audio actually starts playing. The window already knows that moment exactly: `Speaker.play()`
computes `startAt` from the AudioContext clock to schedule the sentence. So:

- each audio frame is preceded by a small JSON message carrying the text of that frame
- the window holds the text and reveals it at `startAt`, using the same clock that plays it
- `assistant_delta` keeps streaming for the **typed** path, where there is no audio to sync to

That is the honest version of what was asked for, it self-corrects instead of drifting, and it
needs no new binary framing — only one more JSON message type.

### 9a.2 More of this computer she can reach

Each of these is small on its own. **The constraint is not the code, it is the prompt:** three
tools is 239 tokens and routing measures 40/40, and tool-calling guides are unanimous that
accuracy falls as the tool count rises. So they go in **small batches with the 40-case routing
benchmark re-run after each one**, and if routing drops the batch gets grouped or trimmed rather
than kept.

| | why |
|---|---|
| `get_current_time` | two lines, and she cannot tell you the time today — she will invent it |
| `open_file` / `open_folder` | the natural other half of `find_files`; §9 always had this waiting for "open that file" |
| `read_file` | she can find a text file and still not tell you what is in it |
| `fetch_page` | **the trigger in §9 has fired** — snippets are page *descriptions*, which is why she cannot answer "what's the weather" |
| `get_world_news` | RSS. Measured 1.12s for four feeds sequentially, real content, no asyncio needed |
| clipboard read/write | cheap, and immediately useful to someone working at a keyboard |

`fetch_page` needs care. FRIDAY's version returns `response.text[:4000]` — raw HTML, so about a
thousand tokens of `<div>` soup, six seconds of her reading markup. It needs real text
extraction, **hand-rolled on `html.parser`**: a dependency is not available here, because
`requirements.txt` must not change (CI's pip cache is keyed on its hash) and this is not a voice
dependency either. Output capped like `web_search`'s snippets are.

The existing rules still hold: no shell, no command tool, the LLM's text never reaches a shell,
and anything destructive asks first.

### 9a.3 Who you are

`SOUL.md` is who *she* is. Nothing anywhere says who *you* are, which is most of why the brain
feels underused: it is answering every question as a stranger.

`~/.cache/donna/ABOUT-ME.md`, mirroring `soul.py` exactly — written on first run with notes,
re-read every turn, prepended to the prompt, warned about past a token budget. Your name, how
you like to be answered, what you are working on, what this machine is.

This is the half of "memory" you can write by hand, and it is worth doing first because it is an
afternoon's work and needs no design. The *earned* half — her noticing and recording things
herself — is a larger piece that should follow it, not precede it.

### 9a.4 Step 10B: interruption

Cut her off mid-sentence. The design is settled and the blocker is a measurement:

- **The window does the interrupting.** It owns playback, so flushing the scheduled audio the
  moment you start talking is instant and needs no round trip. She stops *immediately*.
- **The backend then stops generating**, so the compute is not wasted. Either a non-blocking
  socket check between sentences (keeps one thread) or a reader thread (two per connection — a
  change to decision 1, but still not asyncio).
- **Blocked on the TV test.** If her own voice through the speakers trips the gate she will
  interrupt herself on every sentence. The last log was encouraging — not one
  `ignored … while speaking` line in a whole session — but the user may simply have been quiet.

### 9a.5 Step 11: the sphere

**Design comes from the user**, who is drafting it. Nothing to plan here until it arrives; the
state machine it would react to (`asleep`/`awake`/`speaking`) already exists and is already sent
to the window.

### Parked

**Step 10C ("Hey Donna")** is no longer a step in this plan — it is a separate project for
later. "Hey Jarvis" works, measured at 0.950 and 0.847 on a bare summons, and training a custom
wake word buys a nicer name rather than a better assistant.

## 10. Starting point

This plan starts from a clean repository: only README.md was kept. An earlier, more elaborate
skeleton was removed on purpose (it is still in git history at commit `8c0877b` if we ever want
to look at it). We are not building on it.

## 11. How to run DONNA (Steps 1–9)

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt     # Windows: .venv\Scripts\pip install -r requirements.txt
.venv/bin/pytest                              # all tests; no model, internet or Windows needed
.venv/bin/python server.py                    # with Ollama running
DONNA_LLM=fake .venv/bin/python server.py     # without a model (Windows PowerShell: $env:DONNA_LLM="fake")
```

**Talk to it:**

```bash
.venv/bin/python chat.py                      # terminal client (in backend/, while server.py runs)
cd frontend && npm install && npm run dev     # browser UI at http://localhost:5173
cd frontend && npm run tauri dev              # desktop window (needs Rust + Tauri's system packages)
```

**On your Windows PC with the real model:**
1. Install Ollama and pull the model. Then check the exact tag with `ollama list` and set
   `DONNA_MODEL` if it differs from the default in `llm.py`.
2. Speed and memory are measured — see §6a. `qwen3.5:4b` is the main model and `qwen3.5:9b`
   the automatic fallback, so `ollama pull qwen3.5:4b` is enough to get going. Force the
   bigger one with `DONNA_MODEL=qwen3.5:9b`.
   - The model store lives on **`E:\Ollama\models`**, not the default under `C:`, because the
     C: drive filled up. `OLLAMA_MODELS` is set permanently for the user.
3. Still to check on your PC (can't be done in the cloud):
   - ~~whether Qwen's "thinking" mode slows replies~~ it does: ~3x the tokens for a short
     answer. DONNA now sends `reasoning_effort: "none"`; set `DONNA_THINK=1` to re-enable it;
   - that `open_app` launches each app in the `APPS` table in `backend/tools.py`. Edit the table to match your PC.

**What was verified where:**
- In the cloud (Linux, no GPU, network limited to package registries):
  - every test
  - the terminal client
  - the browser UI (headless Chromium)
  - the Tauri window (virtual display)
  - with the fake brain: file search for real; "open app" giving its Windows-only message; web search failing politely, because the network is blocked there
- Only on your PC: the real model, launching apps, and live web search.

**Small things that differ from the plan above:**
- `ddgs` is a metasearch library: it tries DuckDuckGo and similar engines.
- `open_app` launches through Windows' `start` command, with a target taken from the `APPS` table.
- The UI doesn't use React's `<StrictMode>`. Its dev-only double mount opened and killed a
  WebSocket on every load, which filled the backend's terminal with errors.
