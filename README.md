<div align="center">

# 🟡 D.O.N.N.A.

### **D**efinitely **O**verengineered **N**eural **N**ervous-system **A**ssistant

*She knows what you need before you do. Mostly because you told her. Out loud. Via push-to-talk.*

<br/>

![Status](https://img.shields.io/badge/status-STEALTH%20MODE-FFB300?style=for-the-badge)
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

What emerged is **DONNA**: a voice-first, mostly-local, golden-sphere-powered desktop intelligence that hears you, thinks, acts on your machine, and talks back. Named after the greatest executive assistant in television history, because naming it after a billionaire's butler felt derivative.

This is not a side project.
This is not a hackathon project.
This is a **paradigm shift** that happens to currently live in a README.

---

## 🧠 What DONNA Does

| Capability | Description | Status |
|---|---|---|
| 🎙️ **Voice Input** | Hold a key, speak your will into existence | 🗺️ Manifesting |
| 🔊 **Voice Output** | She talks back. Respectfully. For now. | 🗺️ Manifesting |
| 🌐 **Web Search** | Researches things instead of hallucinating confidently like *some* models | 🗺️ Manifesting |
| 🚀 **App Launching** | "Open VS Code." Done. No clicking. Clicking is for the weak. | 🗺️ Manifesting |
| 📁 **File Finding** | Finds that PDF you swear you saved somewhere in 2024 | 🗺️ Manifesting |
| 🟡 **Golden Sphere UI** | A shader-driven orb that pulses when she speaks. Investors weep. | 🗺️ Manifesting |
| ✋ **Gesture Control** | Pinch to select. Fist to cancel. Become the conductor. | 🔮 Prophesied |
| 📽️ **Projected Desk UI** | A keyboard made of light on your desk. Yes, really. Eventually. | 🔮 Prophesied |

> **Legend:** ✅ Works · 🚧 Building · 🗺️ Manifesting (planned) · 🔮 Prophesied (planned, but further)
>
> *Honest status as of today: the vibes are production-ready. The code is not. There is no code. This README is the MVP.*

---

## 🏗️ Architecture

Engineered with the rigor of a Fortune 500 company and the budget of a college canteen.

```text
┌────────────────── TAURI DESKTOP APP ──────────────────┐
│  Rust (thin): window · tray · global hotkey · sidecar  │
│  React + R3F: 🟡 golden sphere · HUD panels · vibes    │
└───────────────────────────┬────────────────────────────┘
                            │  WebSocket (localhost)
                            │  typed event protocol
┌───────────────────────────┴──────────── PYTHON CORE ───┐
│                                                         │
│  🎙️ Mic → VAD → STT ──► 🧠 Agent Loop ──► TTS → 🔊      │
│                              │                          │
│                        🛠️ Tool Router                   │
│            ┌──────────┬──────┴─────┬────────────┐       │
│        open_app   find_files   open_path   web_search   │
│                                                         │
│  State: IDLE → LISTENING → THINKING → EXECUTING → SPEAKING
└─────────────────────────────────────────────────────────┘
                            │
                     🦙 Ollama (local LLM)
```

### The Golden Rule

**The frontend decides nothing.** It is a beautiful, obedient renderer of events. The Python core is the brain. Separation of concerns so clean you could eat off it.

### 📡 Event Protocol

| Direction | Events |
|---|---|
| Core → UI | `state` · `transcript` · `reply.delta` · `tool.start` · `tool.end` · `results` · `audio.level` · `error` |
| UI → Core | `ptt.down` · `ptt.up` · `text.input` · `cancel` |

---

## ⚙️ Tech Stack

*Every tool hand-picked through rigorous evaluation (I read a lot of Reddit threads).*

<div align="center">

![Tauri](https://img.shields.io/badge/Tauri-24C8D8?style=for-the-badge&logo=tauri&logoColor=white)
![Rust](https://img.shields.io/badge/Rust-000000?style=for-the-badge&logo=rust&logoColor=white)
![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white)
![Three.js](https://img.shields.io/badge/Three.js-000000?style=for-the-badge&logo=threedotjs&logoColor=white)
![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=FFD43B)
![Ollama](https://img.shields.io/badge/Ollama-000000?style=for-the-badge&logo=ollama&logoColor=white)
![Windows](https://img.shields.io/badge/Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)
![WebSocket](https://img.shields.io/badge/WebSocket-FFB300?style=for-the-badge)

</div>

| Layer | Weapon of Choice | Why |
|---|---|---|
| 🖥️ Desktop Shell | **Tauri** | Electron was too mainstream |
| 🎨 UI | **React + React Three Fiber** | Because a flat UI is a cry for help |
| 🧠 LLM Runtime | **Ollama** | Local. Sovereign. Free. |
| 🤖 Model | **TBD** (qwen3.5:4b vs 9b vs a 27B vs qwen3.6 MoE) | Being decided by benchmarks, not feelings. A first for me. |
| 👂 VAD | **Silero VAD** | Knows when you've stopped talking. Unlike my group project members. |
| 📝 Speech-to-Text | **faster-whisper** (CPU) | Hears everything. Judges nothing. |
| 🗣️ Text-to-Speech | **Piper** → **Kokoro** | Piper for speed, Kokoro for that executive-assistant elegance |
| 🔔 Wake Word | Push-to-talk → **openWakeWord** | Summoning rituals come later |
| 🔍 File Search | **Everything** (`es.exe`) | Searches my entire disk faster than I can regret its contents |
| 🌐 Web Search | **SearXNG** or **DuckDuckGo** | Self-hosted search. Big Tech is shaking. |
| 🚀 App Index | Start Menu + `shell:AppsFolder`, fuzzy matched | "vs code" → Visual Studio Code. She just *knows*. |

---

## 💻 The Hardware ("Our Infrastructure")

| Component | Spec | Role |
|---|---|---|
| CPU | Ryzen 7 5800X | Runs speech, voice, tools. The quiet hero. |
| GPU | Radeon RX 580 (8GB) | Runs the LLM. Has seen things. Refuses to retire. |
| RAM | 32GB DDR4 | Headroom for ambition |
| Cameras | eMeet 1080p + 2 vintage webcams | Future stereo vision. Present dust collectors. |
| Speakers | Creative Pebbles | DONNA's voice. Small but mighty. Like the founder. |
| Data Center | My bedroom | Tier 4 uptime (when the power doesn't cut) |

---

## 🛡️ Security & Guardrails

DONNA is powerful. DONNA is also **not** getting `rm -rf` privileges.

- 🚫 **No shell access.** The LLM never gets unrestricted access to the machine.
- ✅ `open_app` only launches **indexed** apps.
- 👀 `find_files` is **read-only**.
- 🔒 `open_path` only opens paths from **previous search results**.
- 📏 `web_search` has **capped page size**, so context windows survive.
- ⚡ **Fast path:** obvious commands like "open X" skip the LLM entirely. Instant. Surgical.
- 🗑️ Move/delete come **later**, behind confirmation. Trust is earned.

---

## 🗺️ Roadmap to World Domination

| # | Milestone | Done When |
|---|---|---|
| 0 | 📊 **Benchmarks** | Model tok/s measured, `es.exe` works, Piper says hello |
| 1 | 🧠 **Brain in a Terminal** | Typed command → tool call → correct answer |
| 2 | 🎙️ **Voice** | Hold hotkey, speak, hear a reply in under ~2s |
| 3 | 🖥️ **Tauri Shell** | App connects over WebSocket, shows state + transcript |
| 4 | 🟡 **The Sphere** | Golden orb reacts to state and voice. Goosebumps. |
| 5 | 🪟 **HUD Panels** | Results float around the sphere and open on click |
| 6 | ✨ **Polish** | Wake word, Kokoro, barge-in, packaging |
| 7+ | 🔮 **The Prophecy** | Gestures · projected desk UI · stereo webcams · second brain · tablet console · IPO |

---

## 📂 Planned Repo Structure

*Planned. Aspirational. Load-bearing optimism.*

```text
donna/
├── desktop/                 # Tauri + React + R3F
│   ├── src-tauri/           # Rust: hotkey, window, tray, sidecar
│   └── src/
│       ├── scene/           # 🟡 Sphere, shaders, HUD panels
│       ├── core-client/     # WebSocket client + typed events
│       └── state/           # Store driven by events
├── core/                    # Python
│   ├── server.py            # WebSocket + event bus
│   ├── agent/               # loop, state machine, ollama client, prompt
│   ├── audio/               # vad, stt, tts, player
│   └── tools/               # registry, open_app, find_files, web_search
└── protocol/                # event schema (single source of truth)
```

---

## 🧭 Founding Principles

1. **Local-first.** Your data stays on your machine. Revolutionary concept, apparently.
2. **Latency is the product.** A smart assistant that takes 20 seconds is just a very polite fax machine.
3. **The LLM gets tools, not keys to the kingdom.**
4. **Build the loop before the eye candy.** No gorgeous sphere that can't open Notepad.
5. **₹0 first.** No buying hardware until existing hardware begs for mercy.

---

## ❓ Open Decisions (The Board Is Deliberating)

- [ ] Which model gets the crown
- [ ] SearXNG vs DuckDuckGo
- [ ] The sacred push-to-talk hotkey
- [ ] The wake phrase *(working theory: "Donna." Simple. Iconic.)*

---

## 🏃 Getting Started

**Not yet.** Come back after Milestone 1.

---

## 💼 We're Hiring!

No we're not. It's just me. But DMs are open for:
- 🧑‍💻 Co-founders (equity: 0% of ₹0)
- 💸 VCs (please)
- 🎮 Anyone with a spare GPU that isn't from 2017

---

## 🙏 Acknowledgements

- My RX 580, for not exploding
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
