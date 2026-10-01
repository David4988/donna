# DONNA

> *"I'm Donna. I know everything."*

DONNA is a mostly-local, voice-driven personal assistant for the desktop. You talk to it; it understands, acts on your machine, and shows what it's doing through a golden, orb-style 3D interface.

Named after Donna Paulsen from *Suits*: the assistant who knows what you need before you finish asking.

> **Status:** Planning. No code yet.

---

## Goals (v1)

- **Voice in, voice out**: push-to-talk first, wake word later.
- **Tools**: web search, open apps, find files, open results.
- **Local first**: LLM, speech-to-text, and text-to-speech all run on this machine. Only web search touches the internet.
- **OS-like 3D interface**: a glowing golden orb that reacts to state and voice, with floating HUD panels for transcripts, tool activity, and results.

### Non-goals (v1)

Gestures, cameras, projector UI, file moves/deletes, long-term memory, semantic file search. These are planned for later and are listed under [Roadmap](#roadmap-beyond-v1).

---

## Target hardware

| Component | Spec | Role |
|---|---|---|
| CPU | Ryzen 7 5800X | STT, TTS, VAD, tools |
| GPU | Radeon RX 580 (8 GB) | LLM + 3D rendering |
| RAM | 32 GB DDR4 | Headroom |
| OS | Windows | |

---

## Architecture

```text
┌──────────── TAURI APP (thin Rust + React/R3F) ────────────┐
│  Rust:  window, tray, global hotkey, launches core sidecar  │
│  React: golden orb, HUD panels, transcript, settings        │
└─────────────────────────────┬──────────────────────────────┘
                              │  WebSocket  ws://127.0.0.1:<port>
┌─────────────────────────────┴───────────── PYTHON CORE ────┐
│  audio:  mic → VAD → STT            TTS → speakers + levels │
│  agent:  state machine + loop → Ollama (localhost:11434)    │
│  tools:  open_app · find_files · open_path · web_search     │
└─────────────────────────────────────────────────────────────┘
```

### Principles

- **Python owns the brain.** Audio, agent, tools, and the LLM client all live in the core.
- **Rust stays thin.** Only what Tauri is good at: window, tray, hotkey, sidecar.
- **The frontend decides nothing.** It renders events from the core.
- **The event protocol is the contract.** Everything hangs off it.
- **The LLM sits behind an OpenAI-compatible interface**, so swapping models (or adding an optional cloud fallback) is a config change, not a rewrite.

### State machine

```text
IDLE → LISTENING → THINKING → EXECUTING → SPEAKING → IDLE
                       └──────────→ ERROR ──────────┘
```

---

## Event protocol

The single source of truth lives in `protocol/` and is mirrored as Pydantic models (core) and TypeScript types (desktop).

| Direction | Event | Payload |
|---|---|---|
| UI → Core | `ptt.down` / `ptt.up` | — |
| UI → Core | `text.input` | `{ text }` |
| UI → Core | `cancel` | — |
| Core → UI | `state` | `{ value: IDLE \| LISTENING \| THINKING \| EXECUTING \| SPEAKING \| ERROR }` |
| Core → UI | `transcript` | `{ text, final }` |
| Core → UI | `reply.delta` | `{ text }` (streamed tokens) |
| Core → UI | `tool.start` | `{ id, name, args }` |
| Core → UI | `tool.end` | `{ id, ok, summary }` |
| Core → UI | `results` | `{ kind: files \| apps \| web, items[] }` |
| Core → UI | `audio.level` | `{ rms }` (~30 Hz) |
| Core → UI | `error` | `{ message }` |

`text.input` lets the whole brain be tested by typing, with no microphone.

---

## Stack

| Piece | Choice | Runs on |
|---|---|---|
| Desktop shell | Tauri + React + React Three Fiber | — |
| LLM runtime | Ollama | GPU |
| LLM model | **TBD**, see [Model selection](#model-selection) | GPU |
| VAD | Silero VAD | CPU |
| Activation | Push-to-talk (Tauri global shortcut), openWakeWord later | CPU |
| STT | faster-whisper (`small.en` / `distil-small.en`, int8) | CPU |
| TTS | Piper first, Kokoro later | CPU |
| Web search | SearXNG (self-hosted) or DuckDuckGo, **TBD** | — |
| File search | Everything (voidtools) via `es.exe` | CPU |
| App launch | Start Menu `.lnk` + `shell:AppsFolder` index, fuzzy matched | CPU |

---

## Tools (v1)

| Tool | Args | Implementation | Guardrail |
|---|---|---|---|
| `open_app` | `name` | Fuzzy match against the indexed Start Menu apps | Launches indexed entries only, no arbitrary paths |
| `find_files` | `query`, `limit` | `es.exe` | Read-only; returns paths and metadata, not contents |
| `open_path` | `path` | `os.startfile` | Only paths returned by an earlier `find_files` call |
| `web_search` | `query` | Search, then fetch and extract text from the top 1–2 pages | Page size capped |

### Safety rules

- No generic shell or command execution tool.
- No moves, renames, or deletes in v1. When they are added, they go behind explicit confirmation.
- **Fast path:** obvious commands ("open X") are matched without calling the LLM.

---

## Model selection

**Undecided.** This is chosen by measurement, not by leaderboard.

| Candidate | Notes |
|---|---|
| `qwen3.5:4b` | Default pick: fits comfortably in VRAM, fast |
| `qwen3.5:9b` | Tight on 8 GB, especially alongside 3D rendering |
| `qwen3.6:35b` (MoE) | "Big brain" option; few active params, heavy RAM offload |
| 27B dense | Likely ~3–4 tok/s with CPU offload; probably too slow for voice |

Rules:

- **Thinking mode OFF** for voice commands.
- Keep the system prompt and tool schemas short. Prompt processing is where latency hides on this GPU.
- Set `keep_alive` so the model stays loaded.

### Evaluation

1. `ollama run <model> --verbose` and record the eval rate (tok/s).
2. `ollama ps` and confirm the model sits 100% on GPU.
3. Run a ~20-utterance eval set (`eval/`) through the agent loop. For each utterance, record: correct tool, usable args, time to first token, total time. Include no-tool cases such as "hi".

The eval set doubles as a regression test for prompt and model changes.

---

## Latency budget

Target: **under ~2 s from end of speech to first audio.**

| Stage | Budget |
|---|---|
| End-of-speech detection | ~300 ms |
| STT | ~300 ms |
| LLM first token | ~300–800 ms |
| TTS first audio | ~200 ms |

Every stage streams. TTS speaks sentence by sentence as tokens arrive.

---

## Milestones

| # | Goal | Done when |
|---|---|---|
| 0 | Benchmarks | Model tok/s measured, `es.exe` works, Piper speaks a line |
| 1 | Brain in a terminal | A typed "find my TrialGuard docs" produces a tool call and a sensible answer |
| 2 | Voice | Hold the hotkey, speak, hear a streamed reply within the latency budget |
| 3 | Tauri shell | Window connects over WebSocket and shows state and transcript |
| 4 | The orb | R3F orb reacts to state and `audio.level`, with bloom |
| 5 | HUD | Results render as panels; clicking one opens it |
| 6 | Polish | Wake word, Kokoro voice, cancel/barge-in, sidecar packaging |

Milestones 1–2 are the hard ones. 4–5 are the fun ones. Don't let the fun ones jump the queue.

---

## Repository layout

```text
donna/
├── desktop/                 # Tauri + React + R3F
│   ├── src-tauri/           # Rust: hotkey, window, tray, sidecar
│   └── src/
│       ├── scene/           # Orb, shaders, HUD panels
│       ├── core-client/     # WebSocket client + typed events
│       └── state/           # Store driven by core events
├── core/                    # Python
│   ├── agent/               # Loop, state machine, LLM client, prompts
│   ├── audio/               # VAD, STT, TTS, player
│   ├── tools/               # Registry, open_app, find_files, web_search
│   └── server/              # WebSocket + event bus
├── protocol/                # Event schema (source of truth)
├── eval/                    # Tool-call eval set + results
└── docs/                    # Design notes, decisions
```

---

## Open decisions

- [ ] LLM model (benchmark first)
- [ ] SearXNG vs DuckDuckGo
- [ ] Push-to-talk hotkey
- [ ] Wake phrase ("Donna"?)
- [ ] Optional cloud fallback for a "think hard / research" mode (separate API billing)

---

## Roadmap beyond v1

- Local file index (SQLite + extracted text + semantic search). Possibly the front door to a deliberate notes vault.
- Conversation memory.
- File operations with confirmation.
- Windows UI Automation, plus screenshot-and-vision fallback for desktop control.
- Gesture recognition (MediaPipe), with gestures resolved to semantic events independently of the LLM.
- Multi-camera and stereo experiments with existing webcams.
- Projected desk UI with camera–projector calibration.
- Tablet as status console.
- Distributed nodes (vision, Windows automation) over the network.

**Budget rule: ₹0 first.** Prototype on existing hardware before buying anything.
