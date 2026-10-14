<div align="center">

# 🟡 D.O.N.N.A.

### **D**efinitely **O**verengineered **N**eural **N**ervous-system **A**ssistant

*She knows what you need before you do. Mostly because you told her. Out loud. Starting with "Hey Jarvis", which is a whole story.*

<br/>

[![Tests](https://github.com/David4988/donna/actions/workflows/test.yml/badge.svg)](https://github.com/David4988/donna/actions/workflows/test.yml)
![Status](https://img.shields.io/badge/status-working%20prototype-FFB300)
![Platform](https://img.shields.io/badge/platform-Windows%2011-0078D6)
![Models](https://img.shields.io/badge/models-run%20locally-2E7D32)

<br/>

<img src="https://skillicons.dev/icons?i=python,react,ts,tauri,rust,windows&theme=dark" />

</div>

---

**DONNA is a voice-first desktop assistant that runs on your own PC.** Say "Hey Jarvis", ask for something out loud, and she answers out loud. She can also do a few real things on the machine: open any app in your Start Menu, find files by name, and search the web. Speech recognition, the language model and her voice all run locally. The only things that reach the internet are web searches and the one-time model downloads.

I'm a final-year engineering student, and I'm building DONNA to understand how AI agents actually work by building one end to end, on hardware I already own (a Ryzen 7 5800X and an RX 580 from 2017). Every design decision and measurement is written down in [`PLAN.md`](PLAN.md), including the ones I got wrong.

- **Status:** working prototype. The voice loop and the tools marked ✅ below work on my PC today. Interrupting her, wider PC control and the 3D avatar are planned, not built.
- **Platform:** Windows 11, the only OS I develop and test on. App launching is Windows-only by design. The backend test suite also runs on Linux in CI with fake models, but running DONNA itself on Linux or macOS is untested.
- **Control:** the language model never gets a shell. It can only call a short list of tools, and Python decides what each one is allowed to do. See [Security and privacy](#security-and-privacy).

## Contents

- [Feature status](#feature-status)
- [Quickstart](#quickstart) · [Prerequisites](#prerequisites) · [Running the tests](#running-the-tests) · [Offline mode](#offline-mode) · [Troubleshooting](#troubleshooting)
- [Configuration](#configuration)
- [How it works](#how-it-works)
- [Hardware and performance](#hardware-and-performance)
- [Security and privacy](#security-and-privacy)
- [Roadmap](#roadmap)
- [Repository structure](#repository-structure)
- [Why DONNA, and the rules it's built by](#why-donna-and-the-rules-its-built-by)
- [Development](#development)
- [Acknowledgements](#acknowledgements)

---

## Feature status

| Feature | What it does today | Status |
|---|---|---|
| **Wake word** | Say "Hey Jarvis" and she wakes up. Not "Hey Donna": no pretrained model exists for her name, and training one buys a nicer name rather than a better assistant | ✅ Works |
| **Voice input** | Open mic, no key to hold. Whisper transcribes on the CPU and shows your words while you're still speaking | ✅ Works |
| **Voice output** | Piper and Kokoro voices, switchable in the window, with a speed slider (0.5×–2×) | ✅ Works |
| **Conversation** | After the wake word she stays awake until 30 seconds pass with nothing said, so follow-up questions don't need it | ✅ Works |
| **Text chat** | Type in the window instead of talking, or use `chat.py` from a terminal | ✅ Works |
| **Streaming replies** | Text appears as the model writes it; speech starts after the first sentence instead of the whole answer | ✅ Works |
| **App launching** | "Open WhatsApp." Any app in your Start Menu, by name. If a name fits several apps, she asks which one | ✅ Works (Windows only) |
| **File finding** | Searches file *names* in Desktop, Documents and Downloads (including OneDrive's copies). Read-only | ✅ Works |
| **Web search** | Searches the web and answers from the snippets | ⚠️ Works, with limits: snippets are page descriptions, so live numbers like weather or prices usually aren't in them |
| **Editable character** | Her personality is a Markdown file. Edit it and she changes on your next sentence | ✅ Works |
| **Knows who you are** | Two Markdown files about you, so she stops answering every question as a stranger | ✅ Works |
| **Subtitles in sync with her voice** | On-screen text currently runs ahead of the audio, because generating is faster than speaking | 🐛 Known issue |
| **Macros** | One sentence runs a hand-written list of steps ("work setup") | 📋 Planned, next |
| **More of the PC** | Volume, media keys, clipboard, windows, battery, free VRAM | 📋 Planned |
| **Barge-in** | Cut her off mid-sentence, the way you would a person | 📋 Planned |
| **Golden sphere UI** | A 3D orb that reacts when she listens, thinks and speaks | 📋 Planned (design in progress) |
| **Seeing your screen** | Tested in an experiment: the model read a screenshot *correctly*, in 26–222 seconds. Not part of DONNA, because that's far too slow for a conversation on this GPU | 🧪 Experiment |
| **Gestures, projected desk UI** | Pinch to select, fist to cancel, a keyboard made of light. Eventually | 💭 Idea |

> **Legend:** ✅ works · ⚠️ works, with limits · 🐛 known issue · 📋 planned · 🧪 tried as an experiment · 💭 long-term idea

---

## Quickstart

**It runs now.** Which still surprises me.

All commands below are for **PowerShell on Windows**. They call the virtual environment's Python directly instead of activating it, because activation scripts are blocked by Windows' default execution policy.

### Prerequisites

| You need | Version | For |
|---|---|---|
| Windows 11 | — | Everything below. App launching uses the Start Menu, so it's Windows-only |
| [Python](https://www.python.org/downloads/) | 3.11 (what CI runs) | The backend |
| [Node.js](https://nodejs.org/) | 22 (what CI runs; Vite 8 needs ≥ 20.19) | The window |
| [Ollama](https://ollama.com/) | tested with 0.33 | Runs the language model |
| A GPU with ~3.5 GB free VRAM | optional | Speed. Without one, Ollama uses the CPU (see [Hardware and performance](#hardware-and-performance)) |
| Microphone and speakers | — | Voice. Typing works without them |
| [Rust](https://rustup.rs/) (MSVC toolchain) | stable | **Only** the desktop window. See [Tauri's prerequisites](https://v2.tauri.app/start/prerequisites/); WebView2 already ships with Windows 11 |

### 1. Get the model

```powershell
ollama pull qwen3.5:4b          # ~3.3 GB
```

### 2. Set up the backend

```powershell
cd backend
python -m venv .venv            # or: py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m pip install -r requirements-voice.txt    # ears and voice, ~250 MB
```

`requirements.txt` is the core (and all CI needs). `requirements-voice.txt` adds faster-whisper, Piper, Kokoro and openWakeWord.

### 3. Download a voice

DONNA looks for Piper voices in `~/.cache/donna/`, and starts in `en_US-amy-medium` unless you pick another:

```powershell
.\.venv\Scripts\python -m piper.download_voices en_US-amy-medium --download-dir "$HOME\.cache\donna"
```

Any other Piper voice works the same way and shows up in the window's voice menu. Kokoro (optional, nicer, +0.55s before she starts talking) needs two model files in `~/.cache/donna/kokoro/`:

```powershell
$k = "$HOME\.cache\donna\kokoro"; New-Item -ItemType Directory -Force $k | Out-Null
$base = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
curl.exe -L -o "$k\kokoro-v1.0.onnx" "$base/kokoro-v1.0.onnx"     # 326 MB
curl.exe -L -o "$k\voices-v1.0.bin"  "$base/voices-v1.0.bin"      # 28 MB
```

That adds Kokoro's 28 English voices to the menu.

### 4. Start the backend

```powershell
.\.venv\Scripts\python server.py
```

It listens on `ws://127.0.0.1:8765`. The first start downloads two Whisper models (`base.en` and `tiny.en`) and the wake-word model. After that, startup takes about 45 seconds on my PC: it loads the wake word, both Whisper models and a voice, and has the language model read her instructions in advance, so your first sentence doesn't have to wait for that.

### 5. Open the window, in a second terminal

**In a browser:**

```powershell
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**. Use that exact address: the backend only accepts browser connections from port 5173, and Vite is pinned to it.

**Or as a desktop app (Tauri):**

```powershell
cd frontend
npm install
npm run tauri dev
```

This starts Vite itself and opens a **DONNA** window. The first run compiles the Rust side, which takes a while; later runs took about 30 seconds here. The backend is not started for you, so keep step 4 running.

### 6. Talk to her

Click **Start voice** (the browser needs one click before it allows the microphone), then say *"Hey Jarvis."* She acknowledges, and then you can just talk. Or type in the box at the bottom.

### Running the tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest
```

The suite needs no model, no internet and no microphone: every model has a fake (see below), and the tests that touch Windows swap in a made-up Start Menu. At the time of writing that's 314 tests, all passing locally. [CI](https://github.com/David4988/donna/actions/workflows/test.yml) runs the same suite on Ubuntu on every push, and also runs:

```powershell
cd frontend
npm run build                   # type-checks with tsc, then builds
```

There are no frontend unit tests yet; the build's type check is the frontend's safety net.

### Offline mode

Every model has a fake, so you can run the whole path (WebSocket, agent, tools, voice session) with no Ollama, no Whisper, no voice and no microphone. This needs only `requirements.txt`:

```powershell
cd backend
$env:DONNA_LLM = "fake"; $env:DONNA_STT = "fake"; $env:DONNA_TTS = "fake"; $env:DONNA_WAKE = "fake"
.\.venv\Scripts\python server.py
```

Then, in another terminal, `.\.venv\Scripts\python chat.py` and type `hello`, or `/say Hey Jarvis` to drive the voice path with text standing in for audio. The fake brain understands `hello`, `open <app>`, `find <files>` and `search the web for <topic>`. Those tools are real, so "open notepad" really opens Notepad. The `$env:` variables last until you close that PowerShell window. (On Linux or macOS: `DONNA_LLM=fake DONNA_STT=fake DONNA_TTS=fake DONNA_WAKE=fake python server.py`.)

### Troubleshooting

| Symptom | Likely cause |
|---|---|
| The window says *disconnected* | The backend isn't running. It retries every 2 seconds, so starting `server.py` is enough |
| The browser connects to the page but never to DONNA | You opened something other than `http://localhost:5173` (or `127.0.0.1:5173`). Other origins are rejected on purpose |
| The header says *voice unavailable* | No Piper voice in `~/.cache/donna/`. Run step 3 |
| She doesn't wake up | Check the backend's log: a near miss is logged with its score and a `DONNA_WAKE_THRESHOLD` to try. `$env:DONNA_LOG = "debug"` shows every score |
| Replies are much slower than expected | Run `ollama ps`. The PROCESSOR column should say `100% GPU`. Once, a failed AMD driver load (Code 31 in Device Manager) silently put everything on the CPU; a reboot fixed it |

---

## Configuration

Everything is set with environment variables (`$env:NAME = "value"` in PowerShell). None are required.

| Variable | Default | What it does |
|---|---|---|
| `DONNA_LLM` | `ollama` | `fake` swaps in the keyword-rule brain |
| `DONNA_MODEL` | `qwen3.5:4b` | The model Ollama runs |
| `DONNA_FALLBACK_MODEL` | `qwen3.5:9b` | Used automatically if the main model isn't pulled |
| `DONNA_LLM_URL` | `http://127.0.0.1:11434/v1/chat/completions` | Any OpenAI-compatible server (Ollama, llama.cpp, LM Studio) |
| `DONNA_THINK` | off | `1` lets Qwen reason before answering. About 3× slower, so it's off |
| `DONNA_STT` | `whisper` | `fake` treats the audio bytes as the text |
| `DONNA_WHISPER_MODEL` | `base.en` | The model for what you said |
| `DONNA_WHISPER_PARTIAL_MODEL` | `tiny.en` | The model for live words while you speak. `""` turns them off |
| `DONNA_TTS` | `piper` | Real voices (Piper and Kokoro). `fake` speaks silence of a plausible length |
| `DONNA_VOICE` | `~/.cache/donna/en_US-amy-medium.onnx` | The default Piper voice. Its folder is where every Piper voice is found |
| `DONNA_KOKORO` | `~/.cache/donna/kokoro` | Where Kokoro's two model files live |
| `DONNA_KOKORO_ALL` | off | `1` also lists Kokoro's non-English voices |
| `DONNA_WAKE` | `jarvis` | `fake` makes the bytes decide; `off` treats every utterance as a summons |
| `DONNA_WAKE_THRESHOLD` | `0.5` | Lower it if she misses you, raise it if the TV wakes her |
| `DONNA_LOG` | `info` | `debug` to watch her think, including wake-word scores |
| `DONNA_SOUL` | `~/.cache/donna/SOUL.md` | Her character file |
| `DONNA_ABOUT_DIR` | `~/.cache/donna` | Where `ABOUT_ME.md` and `USER_STATE.md` live |
| `DONNA_SETTINGS` | `~/.cache/donna/settings.json` | The voice and speed you picked in the window |

### Her character is a file

`~/.cache/donna/SOUL.md`. Edit it and she changes on your **next sentence**, no restart.
She writes it there herself on first run, with notes on how to edit it.

The idea is lifted from [Nous Research's Hermes Agent](https://github.com/NousResearch/hermes-agent)
(MIT), which keeps its whole persona in a `SOUL.md`. The useful part isn't the filename.
It's that an assistant's character should be **data, not code**, so you can change who she
sounds like without touching Python.

**Keep it short.** Hermes does this in about **167 tokens** and reads better for it. The
longest example measured, a Tony Stark tribute, spent **1,114 tokens** to sound worse, and
told its model to invent stock prices to stay in character. She warns you past ~400 tokens.

**What the file can't do** is change the rules. Brevity, when to use a tool, and writing
for the ear all live in `agent.py` and are always appended after your character. That split
is deliberate and measured: the tool-discipline paragraph took tool routing from **30/40 to
39/40** on `qwen3.5:4b`, and adding a worked example to it once took it *down* to **46/60**.
If a persona could delete those rules, the first interesting one anybody wrote would quietly
stop her opening files.

So: describe **how she talks**, not what her tools are.

### And one for you

`~/.cache/donna/ABOUT_ME.md` and `~/.cache/donna/USER_STATE.md`. The first is who you are:
how you want to be answered, what's actually constrained, what you're working toward. The
second is what's happening *now*.

Two files rather than one, because a biography and a status report have different half-lives.
One file rots, and then she starts treating a finished project as live and last term's
timetable as today's.

Neither is in this repo. They're yours, they stay on your machine, and the only thing that
reads them is a model running on localhost.

---

## How it works

```text
┌──────────────────── TAURI WINDOW (or a browser tab) ───────────────────┐
│  React + TS: transcript · settings strip · (the sphere, someday)       │
│  mic → energy gate → one finished utterance        speaker ← audio     │
└───────────────────────────────┬────────────────────────────────────────┘
                                │  WebSocket (127.0.0.1:8765)
                                │  binary = audio, JSON = everything else
┌───────────────────────────────┴────────────────────── PYTHON CORE ─────┐
│                                                                        │
│   utterance ──▶ 🔔 wake.py ("Hey Jarvis") ──▶ 👂 faster-whisper (CPU)  │
│                                                       │                │
│                     🛠️ open_app · find_files ◀── 🧠 agent loop          │
│                        web_search                     │                │
│                                                       ▼                │
│                                          🗣️ Piper / Kokoro, sentence    │
│                                             by sentence                │
│                                                                        │
│   Session: ASLEEP ⇄ AWAKE → SPEAKING                                   │
└───────────────────────────────┬────────────────────────────────────────┘
                                │
                  🦙 Ollama · qwen3.5:4b · every layer in VRAM (Vulkan)
```

**The agent is one loop:** ask the model → if it asks for a tool, run it and ask again → otherwise that's the reply. It's about 40 lines in `agent.py`, with no agent framework, because a framework would hide exactly the part I wanted to understand.

**The window decides nothing.** It's a microphone, a speaker and a transcript; the Python core is the brain. The one deliberate exception is the energy gate that decides when you've finished speaking. It runs in the window because that's where the echo-cancelled microphone signal exists. The UI makes no Tauri API calls at all, so it runs identically in a browser, which is how CI checks it.

**Plain synchronous Python, no asyncio.** One thread per connection. Streaming and voice were both expected to force a rewrite, and neither did. Barge-in is the first feature that genuinely needs concurrency.

### The protocol

Nine messages down, two up, plus audio as raw bytes. One rule: **binary means audio, JSON means everything else.**

| Direction | Messages |
|---|---|
| Core → UI | `state` · `transcript` · `partial_transcript` · `assistant_delta` · `assistant_message` · `tool_call` · `tool_result` · `settings` · `error` · *binary: one spoken sentence* |
| UI → Core | `user_message` · `settings_change` · *binary: one finished utterance* · *binary with a `DONNAPRT` prefix: what you've said so far* |

**One final reply per turn.** `assistant_delta` is advisory, `assistant_message` is the truth, `error` ends things. There are tests that enforce this, because I broke it twice.

### Tech stack

| Layer | Choice | Why |
|---|---|---|
| Desktop shell | **Tauri 2** | A native window around the web UI, with about 20 lines of Rust |
| UI | **React + TypeScript + Vite** | R3F arrives with the sphere. A flat UI that works beats a sphere that doesn't |
| LLM runtime | **Ollama** (Vulkan on the RX 580) | Local and free. Vulkan because ROCm dropped this generation of AMD cards years ago |
| Model | **`qwen3.5:4b`** | Decided by benchmarks, not feelings. It beat both `9b` and `2b`; see below |
| Voice activity | **An energy gate**, ~90 lines in `audio.ts` | Silero needed an ONNX model Vite refused to ship. The wake word decides who she answers, so a rough gate costs CPU, not correctness. The bundle went from 657 kB to 225 kB |
| Speech-to-text | **faster-whisper** on the CPU | `base.en` for what you said, `tiny.en` for live words while you speak |
| Text-to-speech | **Piper** and **Kokoro** | Piper for speed (~0.07s a sentence), Kokoro for a less read-aloud sound (~0.62s) |
| Wake word | **openWakeWord**, `hey_jarvis` | Pretrained, nothing to train. It also means Whisper doesn't run at all while she's asleep |
| File search | `os.walk` over Desktop, Documents and Downloads | Everything (`es.exe`) when this gets too slow. It hasn't yet |
| Web search | **`ddgs`**, Yahoo first, then a broader set | No API key. SearXNG is still an open question |
| App index | Start Menu (`Get-StartApps`) + `shell:AppsFolder` | Read at startup in about 2 seconds. Matched strictest-first, **not** fuzzy: a similarity score can't tell that "zen" means Zen and not Zenless Zone Zero |
| Tests | **pytest** with fakes for every model, GitHub Actions | Runs on Linux with no GPU, no model and no network |

---

## Hardware and performance

What I develop on:

| Component | Spec | Role |
|---|---|---|
| CPU | Ryzen 7 5800X | Whisper, the voices, the tools. Runs the language model at **12.1 tok/s** when it has to, only ~20% behind the GPU |
| GPU | Radeon RX 580 (8 GB) | Runs the language model at **15.1 tok/s** in 3.1 GB of VRAM, every layer resident. Has seen things. Refuses to retire |
| RAM | 32 GB DDR4 | Headroom |
| Cameras | eMeet 1080p + 2 older webcams | Future gesture and stereo vision work. Currently unused |
| Speakers | Creative Pebbles | Her voice |

**What you need to run it:** `qwen3.5:4b` is a 3.3 GB download and uses about 3.1 GB of VRAM. Any GPU that Ollama supports, with that much free, should work. Without one, Ollama runs the model on the CPU, which on my 5800X was only about 20% slower. Whisper and the voices always run on the CPU.

### Things I measured instead of guessing

Because "it feels faster" is not a unit. Details and method for each are in [`PLAN.md`](PLAN.md).

| | |
|---|---|
| `qwen3.5:4b` vs `9b` on tool routing | **15/15** vs 14/15, and 9b once said it had opened Notepad *without calling the tool* |
| `qwen3.5:4b` vs `2b` on tool routing | **40/40** vs 28/40. Every 2b failure was a *missed* tool call |
| Routing after replacing the 6-app list with the whole Start Menu | 39/40 before, **40/40** after |
| Streaming the reply | first word **6.2s → 0.19s** |
| Turning off Qwen's "thinking" | "Capital of France?" **7.3s → 1.2s** |
| Web search turn | first word **11.98s → 8.48s** after capping snippets at 300 characters |
| Reading your bio at startup | first word **25.45s → 4.43s** |
| Wake word | a bare "Hey Jarvis" scored **0.95** against a 0.5 threshold; "Travis called earlier" scored 0.000 |
| Vision, 1024×576 screenshot | **221.8s**, and the answer was *correct*. The GPU is the problem, not the idea |

---

## Security and privacy

DONNA can act on your PC, so the limits are built into the code, not left to the model.

- **No shell access, ever.** Text written by the model never reaches a shell. It picks a *name* from a list, and Python decides what that name does
- **`open_app` only launches what's in your Start Menu.** The model supplies a name; the AppID that runs comes from Windows' own list, so a name that matches nothing opens nothing. Uninstallers and "reset" shortcuts are excluded entirely
- **`find_files` is read-only** and returns names, never contents
- **`web_search` caps each snippet at 300 characters**, because one GitHub README once arrived as 8,111 characters of `<div>` soup. Web text is treated as information, never as instructions
- **A turn stops after 5 rounds of tool use**, so a confused model can't loop forever
- **Moving and deleting files come later**, behind a spoken confirmation, and deletes will go to the Recycle Bin
- **Admin-level actions are planned for a separate elevated helper** with a fixed list of actions, so the normal-user side can never ask it for anything it doesn't already know how to do
- **The backend listens on `127.0.0.1` only**, and rejects browser connections from any page except DONNA's own window
- **Your personal context lives in `~/.cache/donna/`** and is not in this repo, which is public
- **What leaves your PC:** web-search queries (to the search engines `ddgs` uses) and the one-time model downloads. The language model, speech recognition and voices run locally

---

## Roadmap

| # | Milestone | Done when | Status |
|---|---|---|---|
| 0 | **Benchmarks** | Model speed measured, Piper says hello | ✅ |
| 1 | **Brain in a terminal** | Typed command → tool call → correct answer | ✅ |
| 2 | **Voice** | Speak and hear a reply. About 1.4s to the first word on a direct answer, adding up the measured stages | ✅ |
| 3 | **Tauri shell** | The window connects over WebSocket and shows state and transcript | ✅ |
| 3.5 | **Wake word and voices** | "Hey Jarvis", Piper + Kokoro, live transcription, a settings strip | ✅ |
| 3.75 | **A soul and a you** | `SOUL.md` and `ABOUT_ME.md`: she has a character and knows whose desk this is | ✅ |
| 4 | **Every installed app** | Any Start Menu app by name, with ambiguity handled by asking | ✅ |
| 5 | **Macros** | One sentence runs a hand-written recipe of steps | 🔜 Next |
| 6 | **More of the PC** | Volume, media keys, clipboard, windows, battery, VRAM, in one `computer` tool | 📋 |
| 7 | **Ask before acting** | A spoken "are you sure?" for anything that changes things | 📋 |
| 8 | **Barge-in** | Cut her off mid-sentence | 📋 |
| 9 | **The sphere** | A golden orb that reacts to her state and voice | 📋 |
| 10 | **HUD panels** | Results float around the sphere and open on click | 💭 |
| 11+ | **Later** | Gestures · projected desk UI · stereo webcams · "Hey Donna" trained properly | 💭 |

The order and the reasoning behind it are in [`PLAN.md`](PLAN.md). New tools land in small batches, and each batch has to keep the routing benchmark at 38/40 or better.

---

## Repository structure

```text
donna/
├── backend/                 # Python. Flat, synchronous, no asyncio. On purpose
│   ├── server.py            # WebSocket, origin allow-list, warms everything at startup
│   ├── agent.py             # the tool loop + the measured RULES prompt
│   ├── llm.py               # the only file that talks to Ollama (and the fake brain)
│   ├── voice.py             # the session: asleep ⇄ awake → speaking
│   ├── wake.py              # the only file that knows openWakeWord
│   ├── stt.py  tts.py       # the only files that know Whisper / Piper + Kokoro
│   ├── speech_text.py       # pure text rules. No I/O, so it's cheap to test
│   ├── soul.py  about.py    # her character, and who you are
│   ├── settings.py          # voice + speed, atomically written
│   ├── tools.py             # open_app · find_files · web_search. The safety boundary
│   ├── chat.py              # terminal client, for when the window is overkill
│   ├── bench/routing.py     # the routing benchmark (needs Ollama; not part of pytest)
│   └── tests/               # pytest; runs without any model
├── frontend/                # React + TS + Vite
│   ├── src/audio.ts         # energy gate, resampling, scheduled playback
│   ├── src/App.tsx          # the socket and the transcript
│   ├── src/Settings.tsx     # voice and speed
│   └── src-tauri/           # about 20 lines of Rust. It opens a window
├── .github/workflows/       # CI: backend tests + frontend build
├── PLAN.md                  # every decision, every measurement, every correction
└── docs/superpowers/specs/  # the voice design doc
```

---

## Why DONNA, and the rules it's built by

Most assistants live in the cloud, send your voice somewhere else, and still can't open VS Code without asking whether you meant *Visual Studio Code* or *Very Suspicious Code*. I wanted to see how far a fully local one could get on a mid-range PC I already own, and the best way I know to understand AI agents is to build one, measure it, and write down what breaks.

She's named after the greatest executive assistant in television history, because naming her after a billionaire's butler felt derivative. (She still answers to "Hey Jarvis". That's the whole story.)

1. **Local-first.** Your data stays on your machine.
2. **Latency is the product.** A smart assistant that takes 20 seconds is just a very polite fax machine. The budget is ≤5 seconds to her *first* spoken word.
3. **The model gets tools, not keys to the kingdom.**
4. **Build the loop before the eye candy.** No gorgeous sphere that can't open Notepad.
5. **₹0 first.** No buying hardware until the existing hardware begs for mercy.
6. **Measure it or don't claim it.** PLAN.md is full of things I was confidently wrong about, kept in with strikethrough, because the mistakes are the useful part.

### Open decisions

- [x] ~~Which model~~: `qwen3.5:4b`, by a margin, in both directions
- [x] ~~The wake phrase~~: "Hey Jarvis" for now. "Hey Donna" needs a trained model and is its own project
- [x] ~~Push-to-talk hotkey~~: dropped. You just talk
- [x] ~~A tiny model on the idle CPU picking which tools the big one sees~~: shelved until there are more than 8 tool definitions or routing drops below 38/40. Macros solve the same problem more cheaply for now
- [ ] SearXNG vs `ddgs`
- [ ] How much of the OS she gets to touch, and how loudly she asks first
- [ ] Whether the sphere is Three.js or raw WebGL

---

## Development

A few pointers if you want to read or change the code:

- **Start with `backend/agent.py` and `backend/tools.py`.** The first is the whole agent loop; the second is everything she can do to your computer, and so the safety boundary. If it isn't in `tools.py`, the model can't do it.
- **[`PLAN.md`](PLAN.md) is the design record.** Why each piece exists, what was measured, and what turned out wrong.
- **Every model has a fake** (`DONNA_LLM`, `DONNA_STT`, `DONNA_TTS`, `DONNA_WAKE`), so new behaviour can be tested without hardware. See [Running the tests](#running-the-tests).
- **Changing the prompt or adding a tool?** Run the routing benchmark against the real model before and after. It's the one thing that has regressed on "harmless" prompt changes before:

  ```powershell
  cd backend
  .\.venv\Scripts\python bench\routing.py
  ```

It's a personal learning project, so it moves at the pace of my coursework. If you spot something wrong or have an idea, opening an issue is the best way to tell me.

---

## Acknowledgements

- The open-source projects doing the heavy lifting: [Ollama](https://ollama.com/), [Qwen](https://github.com/QwenLM), [faster-whisper](https://github.com/SYSTRAN/faster-whisper), [Piper](https://github.com/OHF-Voice/piper1-gpl), [Kokoro](https://github.com/thewh1teagle/kokoro-onnx), [openWakeWord](https://github.com/dscripka/openWakeWord), [Tauri](https://tauri.app/) and [`ddgs`](https://github.com/deedy5/ddgs)
- [Nous Research's Hermes Agent](https://github.com/NousResearch/hermes-agent), for the `SOUL.md` idea
- My RX 580, for not exploding
- My 5800X, for turning out to be nearly as fast and far less dramatic
- The Instagram reel that started this whole thing
- *Suits*, for teaching me what a real assistant looks like
- Everyone who said "bro just use ChatGPT" (you are the reason I persist)

---

<div align="center">

**Built with 💛 and not enough sleep by a final-year CSE student who should probably be doing placement prep.**

*DONNA is not affiliated with Suits, USA Network, or anyone who has a working production version of this.*

</div>
