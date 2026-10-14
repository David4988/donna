<div align="center">

# 🟡 D.O.N.N.A.

### **D**efinitely **O**verengineered **N**eural **N**ervous-system **A**ssistant

*She knows what you need before you do. Mostly because you told her. Out loud. Starting with "Hey Jarvis", which is a whole story.*

<br/>

![Status](https://img.shields.io/badge/status-SHE%20TALKS%20BACK-FFB300?style=for-the-badge)
![Tests](https://img.shields.io/badge/tests-280%20passing-success?style=for-the-badge)
![Funding](https://img.shields.io/badge/funding-%E2%82%B90%20pre--seed-8B0000?style=for-the-badge)
![Valuation](https://img.shields.io/badge/valuation-trust%20me%20bro-black?style=for-the-badge)
![Team](https://img.shields.io/badge/team%20size-1%20(10x)-FFD700?style=for-the-badge)
![Sleep](https://img.shields.io/badge/sleep-deprecated-red?style=for-the-badge)
![Vibes](https://img.shields.io/badge/vibes-immaculate-blueviolet?style=for-the-badge)

<br/>

<img src="https://skillicons.dev/icons?i=react,ts,rust,tauri,python,threejs,windows,git,github&theme=dark" />

<br/><br/>

> **"Siri walked so DONNA could sprint. In a golden sphere. Locally. On an RX 580."**
> — me, in the shower, at 3 AM

</div>

---

## 🚀 The Vision

The year is 2026. AI assistants live in the cloud, harvest your data, and can't even open VS Code without asking whether you meant *Visual Studio Code* or *Very Suspicious Code*.

**I said no.**

I locked myself in my room with a Ryzen 7, an RX 580 that has been through *things*, 32GB of DDR4, three webcams of questionable lineage, and an unreasonable amount of conviction.

What emerged is **DONNA**: a voice-first, fully-local, eventually-golden-sphere-powered desktop intelligence that hears you, thinks, acts on your machine, and talks back. Named after the greatest executive assistant in television history, because naming it after a billionaire's butler felt derivative.

This is not a side project.
This is not a hackathon project.
This is a **paradigm shift** that now, humiliatingly for my earlier README, actually runs.

You say "Hey Jarvis, what's the weather in London" and a voice answers out loud, on a graphics card from 2017, with nothing leaving the building. The golden sphere is still vapourware. Everything underneath it is not.

---

## 🧠 What DONNA Does

| Capability | Description | Status |
|---|---|---|
| 🔔 **Wake Word** | "Hey Jarvis" and she wakes up. Scores 0.95 on a bare summons, 0.000 on "Travis called earlier" | ✅ Works |
| 🎙️ **Voice Input** | Just talk. No key to hold. She hears you, transcribes, and shows your words as you speak | ✅ Works |
| 🔊 **Voice Output** | She talks back in one of **34 voices**, switchable mid-conversation | ✅ Works |
| 💬 **Conversation** | Say her name, she says "Yes?", then you just talk. No re-summoning for 30 seconds | ✅ Works |
| 🌐 **Web Search** | Researches things instead of hallucinating confidently like *some* models | ✅ Works |
| 🚀 **App Launching** | "Open WhatsApp." Done. No clicking. Clicking is for the weak. | ✅ Works (your whole Start Menu) |
| 📁 **File Finding** | Finds that PDF you swear you saved somewhere in 2024 | ✅ Works |
| 🎭 **Editable Soul** | Her character is a Markdown file. Edit it, she changes on your next sentence | ✅ Works |
| 🧍 **Knows Who You Are** | A second Markdown file so she stops answering every question as a stranger | ✅ Works |
| ✂️ **Barge-in** | Cut her off mid-sentence like a normal human conversation | 🚧 Building |
| 🛠️ **Reaching Your PC** | Volume, clipboard, windows, processes, VRAM, launching *everything* installed | 🚧 Building |
| 🟡 **Golden Sphere UI** | A shader-driven orb that pulses when she speaks. Investors weep. | 🗺️ Manifesting |
| 👁️ **Seeing Your Screen** | She *can* read a screenshot accurately. It takes 26 seconds. The GPU is the problem | 🗺️ Manifesting |
| ✋ **Gesture Control** | Pinch to select. Fist to cancel. Become the conductor. | 🔮 Prophesied |
| 📽️ **Projected Desk UI** | A keyboard made of light on your desk. Yes, really. Eventually. | 🔮 Prophesied |

> **Legend:** ✅ Works · 🚧 Building · 🗺️ Manifesting (planned) · 🔮 Prophesied (planned, but further)
>
> *Honest status as of today: the vibes remain production-ready, and the code has caught up. **280 passing tests.** The README is no longer the MVP, which I am choosing to see as growth.*

---

## 🏗️ Architecture

Engineered with the rigor of a Fortune 500 company and the budget of a college canteen.

```text
┌────────────────── TAURI DESKTOP APP ──────────────────┐
│  Rust (thin, honestly barely there): just a window    │
│  React + TS: transcript · settings strip · 🟡 someday │
└───────────────────────────┬────────────────────────────┘
                            │  WebSocket (localhost:8765)
                            │  binary = audio, JSON = everything else
┌───────────────────────────┴──────────── PYTHON CORE ───┐
│                                                         │
│  🎙️ mic → energy gate → one utterance ──┐              │
│                                          ▼              │
│                          🔔 wake.py ("Hey Jarvis")      │
│                                          │              │
│                          👂 faster-whisper (CPU)        │
│                                          │              │
│                          🧠 agent loop ──┴──▶ 🗣️ Piper  │
│                                │                Kokoro  │
│                          🛠️ open_app · find_files        │
│                             web_search                  │
│                                                         │
│  State: ASLEEP ⇄ AWAKE → SPEAKING                       │
└─────────────────────────────────────────────────────────┘
                            │
                     🦙 Ollama · qwen3.5:4b · all 34 layers in VRAM
```

### The Golden Rule

**The frontend decides nothing.** It is a microphone, a speaker and a transcript. The Python core is the brain. Separation of concerns so clean you could eat off it — and genuinely load-bearing: the UI has no Tauri API calls at all, so it runs identically in a browser, which is how CI works.

### 📡 Event Protocol

Nine messages down, two up, plus audio as raw bytes. One rule: **binary means audio, JSON means everything else.**

| Direction | Events |
|---|---|
| Core → UI | `state` · `transcript` · `partial_transcript` · `assistant_delta` · `assistant_message` · `tool_call` · `tool_result` · `settings` · `error` · *binary: one spoken sentence* |
| UI → Core | `user_message` · `settings_change` · *binary: one finished utterance* · *binary with a `DONNAPRT` prefix: what you've said so far* |

**One final reply per turn.** `assistant_delta` is advisory, `assistant_message` is the truth, `error` ends things. There are tests that enforce this, because I broke it twice.

---

## ⚙️ Tech Stack

*Every tool hand-picked through rigorous evaluation (I read a lot of Reddit threads, then benchmarked it anyway).*

<div align="center">

![Tauri](https://img.shields.io/badge/Tauri-24C8D8?style=for-the-badge&logo=tauri&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=FFD43B)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-FFB300?style=for-the-badge)

</div>

| Layer | Weapon of Choice | Why |
|---|---|---|
| 🖥️ Desktop Shell | **Tauri 2** | Electron was too mainstream |
| 🎨 UI | **React + TypeScript** | R3F arrives with the sphere. A flat UI is a cry for help, but a flat UI that works beats a sphere that doesn't |
| 🧠 LLM Runtime | **Ollama** (Vulkan) | Local. Sovereign. Free. Vulkan because ROCm abandoned Polaris years ago |
| 🤖 Model | **`qwen3.5:4b`** | Decided by benchmarks, not feelings. A first for me. It beat `9b` *and* `2b` — see below |
| 👂 VAD | ~~Silero~~ **a 90-line energy gate** | Silero needed an ONNX model Vite refused to ship. The wake word decides who she answers, so a rough gate costs CPU, not correctness. Bundle went 657kB → 225kB |
| 📝 Speech-to-Text | **faster-whisper** (CPU) | `base.en` for real, `tiny.en` for the live words. Hears everything. Judges nothing. |
| 🗣️ Text-to-Speech | **Piper** *and* **Kokoro** | Both, 34 voices, switchable in the window. Piper for speed (0.16s a sentence), Kokoro for the elegance (1.37s) |
| 🔔 Wake Word | **openWakeWord** — "Hey Jarvis" | Not "Hey Donna", because no pretrained model exists for it and training one buys a nicer name rather than a better assistant. She is still *called* DONNA |
| 🔍 File Search | `os.walk` over Desktop/Documents/Downloads | `es.exe` when this gets too slow. It hasn't yet |
| 🌐 Web Search | **`ddgs`**, Yahoo first then everything | Self-hosted search is next. Big Tech is shaking, slightly |
| 🚀 App Index | Start Menu + `shell:AppsFolder`, matched strictest-first | Read at startup in 1.7s. **Not** fuzzy, on purpose: a similarity score can't tell that "zen" means Zen and not Zenless Zone Zero. Two names fit? She asks |

---

## 💻 The Hardware ("Our Infrastructure")

| Component | Spec | Role |
|---|---|---|
| CPU | Ryzen 7 5800X | Speech, voice, tools — and **12.1 tok/s** on the main model, only 25% behind the GPU. The quiet hero, and the next big idea |
| GPU | Radeon RX 580 (8GB) | Runs the LLM at **15.1 tok/s**, 3.1GB VRAM, every layer resident. Has seen things. Refuses to retire |
| RAM | 32GB DDR4 | Headroom for ambition |
| Cameras | eMeet 1080p + 2 vintage webcams | Future stereo vision. Present dust collectors |
| Speakers | Creative Pebbles | DONNA's voice. Small but mighty. Like the founder |
| Data Center | My bedroom | Tier 4 uptime (when the power doesn't cut) |

### 📊 Things I Measured Instead Of Guessing

Because "it feels faster" is not a unit.

| | |
|---|---|
| `qwen3.5:4b` vs `9b` on tool routing | **15/15** vs 14/15 — and 9b once claimed it opened Notepad *without calling the tool* |
| `qwen3.5:4b` vs `2b` on tool routing | **40/40** vs 28/40 — every 2b failure was a *missed* tool call |
| Streaming the reply | first word **6.2s → 0.19s** |
| Web search turn | first word **11.98s → 8.48s** after capping snippets |
| Reading your bio at startup | first word **25.45s → 4.43s** |
| Vision, 1024×576 | **221.8s**, and the answer was *correct*. The GPU is the problem, not the idea |

---

## 🛡️ Security & Guardrails

DONNA is powerful. DONNA is also **not** getting `rm -rf` privileges.

- 🚫 **No shell access, ever.** Text written by the LLM never reaches a shell. It picks a *name* from a list; Python decides what that name does
- ✅ `open_app` only launches what's in your Start Menu. The model says a *name*; the AppID that runs comes from Windows' own list. Uninstallers and "reset" shortcuts are left out entirely
- 👀 `find_files` is **read-only** and returns names, never contents
- 📏 `web_search` caps each snippet at 300 characters, because one GitHub README once arrived as 8,111 characters of `<div>` soup
- 🗑️ Move/delete come **later**, behind confirmation, and deletes go to the Recycle Bin. Trust is earned
- 🔐 Privileged actions will live in a **separate elevated helper** with a fixed action table, so the unelevated side can never ask it for anything it doesn't already know how to do
- 🏠 `127.0.0.1` only, with an Origin allow-list
- 📄 Your personal context lives in `~/.cache/donna/` and is **not in this repo**, which is public

---

## 🗺️ Roadmap to World Domination

| # | Milestone | Done When | Status |
|---|---|---|---|
| 0 | 📊 **Benchmarks** | Model tok/s measured, Piper says hello | ✅ |
| 1 | 🧠 **Brain in a Terminal** | Typed command → tool call → correct answer | ✅ |
| 2 | 🎙️ **Voice** | Speak, hear a reply. Measured ~1.4s to the first word on a direct answer | ✅ |
| 3 | 🖥️ **Tauri Shell** | App connects over WebSocket, shows state + transcript | ✅ |
| 3.5 | 🔔 **Wake Word + Voices** | "Hey Jarvis", 34 voices, live transcription, a settings strip | ✅ |
| 3.75 | 🎭 **A Soul and a You** | `SOUL.md` and `ABOUT_ME.md` — she has a character and knows whose desk this is | ✅ |
| 4 | ✂️ **Barge-in** | Cut her off mid-sentence | 🚧 |
| 5 | 🛠️ **Reaching The Whole PC** | Volume, clipboard, windows, every installed app, macros | 🚧 |
| 6 | 🟡 **The Sphere** | Golden orb reacts to state and voice. Goosebumps | 🗺️ |
| 7 | 🪟 **HUD Panels** | Results float around the sphere and open on click | 🗺️ |
| 8+ | 🔮 **The Prophecy** | Gestures · projected desk UI · stereo webcams · "Hey Donna" trained properly · IPO | 🔮 |

---

## 📂 Repo Structure

*No longer aspirational. This is what is actually on disk.*

```text
donna/
├── backend/                 # Python. Flat, synchronous, no asyncio. On purpose
│   ├── server.py            # WebSocket, origin allow-list, warms everything
│   ├── agent.py             # the tool loop + the measured RULES prompt
│   ├── llm.py               # the only file that talks to Ollama
│   ├── voice.py             # the session: asleep ⇄ awake → speaking
│   ├── wake.py              # the only file that knows openWakeWord
│   ├── stt.py  tts.py       # the only files that know Whisper / Piper + Kokoro
│   ├── speech_text.py       # pure text rules. No I/O, so it is cheap to test
│   ├── soul.py  about.py    # her character, and who you are
│   ├── settings.py          # voice + speed, atomically written
│   ├── tools.py             # open_app · find_files · web_search
│   ├── chat.py              # terminal client, for when the window is overkill
│   └── tests/               # 280 of them
├── frontend/                # React + TS + Vite
│   ├── src/audio.ts         # energy gate, resampling, scheduled playback
│   ├── src/App.tsx          # the socket and the transcript
│   ├── src/Settings.tsx     # voice and speed
│   └── src-tauri/           # Rust: 16 lines. It opens a window
├── PLAN.md                  # every decision, every measurement, every correction
└── docs/superpowers/specs/  # the voice design doc
```

---

## 🧭 Founding Principles

1. **Local-first.** Your data stays on your machine. Revolutionary concept, apparently.
2. **Latency is the product.** A smart assistant that takes 20 seconds is just a very polite fax machine.
3. **The LLM gets tools, not keys to the kingdom.**
4. **Build the loop before the eye candy.** No gorgeous sphere that can't open Notepad.
5. **₹0 first.** No buying hardware until existing hardware begs for mercy.
6. **Measure it or don't claim it.** PLAN.md is full of things I was confidently wrong about, kept in with strikethrough, because the mistakes are the useful part.

---

## ❓ Open Decisions (The Board Is Deliberating)

- [x] ~~Which model gets the crown~~ — `qwen3.5:4b`, by a margin, in both directions
- [x] ~~The wake phrase~~ — "Hey Jarvis" for now; "Hey Donna" needs a trained model and is its own project
- [x] ~~Push-to-talk hotkey~~ — deleted the whole idea. You just talk
- [ ] Whether a tiny model on the idle CPU should pick which tools the big one sees *(this is the interesting one)*
- [ ] SearXNG vs `ddgs`
- [ ] How much of the OS she gets to touch, and how loudly she asks first
- [ ] Whether the sphere is Three.js or raw WebGL

---

## 🏃 Getting Started

**It runs now.** Which still surprises me.

```bash
# 1. The brain
ollama pull qwen3.5:4b

# 2. The backend
cd backend
python -m venv .venv && .\.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-voice.txt    # ears and voice, ~250MB
python server.py

# 3. The window, in another terminal
cd frontend && npm install && npm run dev
```

Then press **Start voice** and say *"Hey Jarvis."* She'll say "Yes?" and then you can just talk to her.

Startup takes ~45 seconds, because she loads a wake word, two Whisper models, a voice, and reads your biography so your first sentence doesn't have to wait for it. `DONNA_LOG=debug` if you want to watch her think.

**No microphone?** Every component has a fake: `DONNA_LLM=fake DONNA_STT=fake DONNA_TTS=fake DONNA_WAKE=fake python server.py`. The whole path runs over a real socket with no models at all. That's how CI tests it.

---

## 🎭 Her Character Is a File

`~/.cache/donna/SOUL.md`. Edit it and she changes on your **next sentence** — no restart.
She writes it there herself on first run, with notes on how to edit it.

The idea is lifted from [Nous Research's Hermes Agent](https://github.com/NousResearch/hermes-agent)
(MIT), which keeps its whole persona in a `SOUL.md`. The useful part isn't the filename —
it's that an assistant's character should be **data, not code**, so you can change who she
sounds like without touching Python.

**Keep it short.** Hermes does this in about **167 tokens** and reads better for it. The
longest example measured — a Tony Stark tribute — spent **1,114 tokens** to sound worse, and
told its model to invent stock prices to stay in character. She warns you past ~400 tokens.

**What the file can't do** is change the rules: brevity, when to use a tool, and writing
for the ear all live in `agent.py` and are always appended after your character. That split
is deliberate and measured — the tool-discipline paragraph took tool routing from **30/40 to
39/40** on `qwen3.5:4b`, and adding a worked example to it once took it *down* to **46/60**.
If a persona could delete those rules, the first interesting one anybody wrote would quietly
stop her opening files.

So: describe **how she talks**, not what her tools are.

### 🧍 And One For You

`~/.cache/donna/ABOUT_ME.md` and `~/.cache/donna/USER_STATE.md`. The first is who you are —
how you want to be answered, what's actually constrained, what you're working toward. The
second is what's happening *now*.

Two files rather than one, because a biography and a status report have different half-lives.
One file rots, and then she starts treating a finished project as live and last term's
timetable as today's.

Neither is in this repo. They're yours, they stay on your machine, and the only thing that
reads them is a model running on localhost.

---

## 💼 We're Hiring!

No we're not. It's just me. But DMs are open for:
- 🧑‍💻 Co-founders (equity: 0% of ₹0)
- 💸 VCs (please)
- 🎮 Anyone with a spare GPU that isn't from 2017

---

## 🙏 Acknowledgements

- My RX 580, for not exploding
- My 5800X, for turning out to be nearly as fast and infinitely less dramatic
- Caffeine, my true co-founder
- The Instagram reel that started this whole thing
- *Suits*, for teaching me what a real assistant looks like
- Everyone who said "bro just use ChatGPT" (you are the reason I persist)

---

<div align="center">

**Built with 💛, 🟡, and zero sleep by a final-year CSE student who should probably be doing placement prep.**

*DONNA is not affiliated with Suits, USA Network, or anyone who has a working production version of this.*

⭐ **Star this repo so I can screenshot it for LinkedIn.** ⭐

</div>
