# DONNA

A mostly-local desktop AI assistant you talk to. It searches the web, opens apps and finds files. On screen it appears as a golden, Age-of-Ultron-style sphere in an OS-like 3D interface.

> **Status:** planning / pre-alpha. This README is the living design doc for v1. Update it as decisions get made.

**Later (post-v1):** hand gestures, a projector display and extra cameras.

---

## Table of contents

- [Hardware](#hardware)
- [Architecture](#architecture)
- [Event protocol](#event-protocol)
- [Stack](#stack)
- [Tools v1](#tools-v1)
- [Model selection](#model-selection)
- [About Claude](#about-claude)
- [Milestones](#milestones)
- [Open decisions](#open-decisions)

---

## Hardware

| Component | Spec |
|---|---|
| CPU | AMD Ryzen 7 5800X |
| GPU | AMD Radeon RX 580 (8 GB VRAM) |
| RAM | 32 GB DDR4 |
| OS | Windows |

**Resource split**

- **GPU:** the LLM and the sphere rendering.
- **CPU:** speech-to-text, text-to-speech, voice activity detection (VAD) and the tools.

---

## Architecture

```text
Tauri app (thin Rust + React/R3F)  ◄── WebSocket events ──►  Python core
 - window, tray, global hotkey                                - audio in/out
 - golden sphere + HUD panels                                 - agent loop + state machine
 - renders events, decides nothing                            - tools → Ollama
```

- **Rust stays thin.** It handles the push-to-talk hotkey, the frameless/transparent window and the tray. Later it will also launch the Python core as a sidecar.
- **Python owns the brain.** It does audio capture and playback, runs the agent and executes the tools.
- **The frontend only renders.** It receives events and audio levels and makes no decisions.

## Event protocol

The WebSocket protocol is the contract between the UI and the core.

| Direction | Event | Purpose |
|---|---|---|
| core → UI | `state` | Assistant state changes (idle, listening, thinking, speaking, …) |
| core → UI | `transcript` | What the user said (STT output) |
| core → UI | `reply.delta` | Streaming chunks of the assistant's reply |
| core → UI | `tool.start` / `tool.end` | A tool call began or finished |
| core → UI | `results` | Structured results for HUD panels (search hits, files, …) |
| core → UI | `audio.level` | Mic/speaker levels that drive the sphere |
| core → UI | `error` | Errors to surface |
| UI → core | `ptt` | Push-to-talk pressed/released |
| UI → core | `text.input` | Typed input. Lets you test the whole brain without a mic |
| UI → core | `cancel` | Abort the current turn |

---

## Stack

| Piece | Choice |
|---|---|
| LLM runtime | [Ollama](https://ollama.com), behind an OpenAI-compatible interface so a cloud model can be swapped in later |
| VAD | Silero VAD |
| Activation | Push-to-talk first, wake word ([openWakeWord](https://github.com/dscripka/openWakeWord)) later |
| STT | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) small/distil, on CPU |
| TTS | [Piper](https://github.com/rhasspy/piper) first, Kokoro later, on CPU |
| Web search | SearXNG or DuckDuckGo, plus page text extraction |
| Files | [Everything](https://www.voidtools.com/) (`es.exe`) |
| Apps | Start Menu + AppsFolder index, fuzzy matching |
| UI | [Tauri](https://tauri.app) + React + React Three Fiber, shader-driven sphere with bloom |

---

## Tools v1

Every tool has a guardrail:

| Tool | Guardrail |
|---|---|
| `open_app` | Only launches apps that are in the index |
| `find_files` | Read-only |
| `open_path` | Only opens paths returned by a previous search |
| `web_search` | Page size is capped |

Also:

- **No shell access**, and no move or delete operations in v1.
- **A fast path** handles obvious commands ("open X") without calling the LLM.

---

## Model selection

**Status: undecided. Benchmark first.**

The wish is a 27B model. The concern is that a dense 27B on 8 GB of VRAM likely runs at about 3–4 tokens/s. That works out to 20–30 s per voice command, which is too slow for conversation.

| Candidate | Notes |
|---|---|
| `qwen3.5:4b` | Default pick: fast and fits comfortably |
| `qwen3.5:9b` | Tight fit in 8 GB |
| `qwen3.6:35b` (MoE) | The "big brain" option. MoE suits this hardware better than a dense 27B |

Thinking mode stays **off** for voice.

**How to decide**

1. Run `ollama run <model> --verbose` for each candidate and record the tokens/s.
2. Write an eval of about 20 utterances that checks tool calls. It doubles as a regression test.

---

## About Claude

- Claude Pro has no API access, so it can't be the assistant's brain.
- Claude Code is used for plumbing. The agent loop and the protocol are written by hand.
- A cloud fallback, if added, would need separate pay-as-you-go API billing.

---

## Milestones

- [ ] **0. Benchmarks:** model speed, `es.exe` and Piper all working
- [ ] **1. Text-only agent loop in a terminal** *(the hard part)*
- [ ] **2. Voice:** push-to-talk, under ~2 s to first audio
- [ ] **3. Tauri shell** connected over WebSocket
- [ ] **4. Sphere** reacting to state and audio
- [ ] **5. HUD panels** for results
- [ ] **6. Polish:** wake word, Kokoro, barge-in, sidecar packaging

---

## Open decisions

- [ ] Which model (benchmark first)
- [ ] SearXNG vs DuckDuckGo
- [ ] The push-to-talk hotkey
- [ ] The assistant's name and wake phrase
