# Development

The software skeleton runs with **no hardware, no Ollama and no model**: a
deterministic `FakeLLM` and mock OS backends stand in for them.

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- Node 22+
- Rust (stable) + [Tauri v2 system deps](https://v2.tauri.app/start/prerequisites/) — only for the desktop window

## Run it

```bash
# 1. The core (Python): binds 127.0.0.1 only, random port, random per-launch token
cd core && uv sync
uv run donna-core --simulate-speech          # --simulate-speech: SPEAKING lasts a while, so you can barge in

# 2a. CLI client (reads ~/.donna/session.json for port + token)
uv run donna-cli                             # interactive; -v shows states and routes
uv run donna-cli --once "find my TrialGuard files"

# 2b. Desktop window (Tauri reads the same session file via a Rust command)
cd desktop && npm install
npm run tauri dev

# 2c. Or the UI in a plain browser (dev only)
uv run donna-core --print-ui-url             # prints http://localhost:1420/#port=…&token=…
cd desktop && npm run dev                    # then open the printed URL
```

Try: `hello`, `open VS Code` (fast path, skips the LLM), `find my TrialGuard files`,
`find my TrialGuard files and open the first one` (multi-step via result ids),
`open r_4` (an .exe is revealed, never run), `search the web for tauri`, `open it`.
Type while DONNA is "speaking" to cancel the turn (barge-in), or use `/cancel`.

## Checks (what CI runs)

```bash
cd core && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv run --project core python evals/run_eval.py
scripts/check_protocol.sh                    # generated schema/TS types are up to date
cd desktop && npm run typecheck && npm test && npx vite build
cd desktop/src-tauri && cargo fmt --check && cargo clippy --all-targets -- -D warnings && cargo test
```

## Where things live

| Path | What |
|---|---|
| `core/src/donna_core/protocol/` | Pydantic wire protocol (source of truth) + codec |
| `core/src/donna_core/server/` | WebSocket gateway, token + Origin auth, session file |
| `core/src/donna_core/bus.py` | In-process event bus |
| `core/src/donna_core/agent/` | State machine, turns (cancellation), agent loop, fast path, speaker seam |
| `core/src/donna_core/llm/` | `LLM` interface, `FakeLLM`, placeholder for the Qwen3.6-35B-A3B client |
| `core/src/donna_core/tools/` | Tool interface, router, result registry, app catalog, mock backends |
| `core/src/donna_core/app.py` | Composition root: the one place concrete classes are chosen |
| `core/src/donna_core/cli/` | `donna-cli` |
| `protocol/` | Generated JSON Schema |
| `desktop/src/` | React renderer: core client, pure reducer, components |
| `desktop/src-tauri/` | Thin Rust shell (`core_session` command) |
| `evals/` | Deterministic agent-loop eval cases + runner |

## Swapping in real implementations later

Everything is injected in `core/src/donna_core/app.py`:

- `FakeLLM` → `OpenAICompatLLM` (Qwen3.6-35B-A3B via Ollama / llama-server)
- `MockFileSearcher` → Everything (`es.exe`), `MockAppLauncher` → Start Menu index,
  `MockOpener` → `os.startfile` / Explorer reveal, `MockWebSearcher` → a search provider
- `InstantSpeaker` / `SimulatedSpeaker` → Piper / Kokoro TTS
- Microphone, wake word, gestures: new adapters that publish input and drive
  `LISTENING`; new protocol messages are added in `protocol/messages.py`.
