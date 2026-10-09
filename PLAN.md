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
                                                   Ollama + Qwen3.6     ├─ find_files
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
| Tauri (Step 9) | Gives DONNA its own desktop window, and later the global push-to-talk hotkey. Until then the browser works fine. |

- **Why Python for the backend?** The AI pieces DONNA needs later (Whisper for speech-to-text, Piper for text-to-speech, MediaPipe for gestures) are Python-first, as the README already decided.
- **Why no agent framework (LangChain etc.)?** The loop is about 40 lines. A framework would hide exactly the part you want to understand.

## 5. The messages (this is the whole protocol)

Every message is JSON with a `type`.

| Direction | `type` | Fields | Example |
|---|---|---|---|
| UI → backend | `user_message` | `text` | `{"type": "user_message", "text": "Open VS Code"}` |
| backend → UI | `tool_call` | `name`, `args` | `{"type": "tool_call", "name": "open_app", "args": {"app": "vscode"}}` |
| backend → UI | `tool_result` | `name`, `result` | `{"type": "tool_result", "name": "open_app", "result": "Opened Visual Studio Code."}` |
| backend → UI | `assistant_message` | `text` | `{"type": "assistant_message", "text": "VS Code is open."}` |
| backend → UI | `error` | `text` | `{"type": "error", "text": "Can't reach the model. Is Ollama running?"}` |

**One rule:** every `user_message` gets exactly **one** final reply, either an `assistant_message` or an `error`. `tool_call` and `tool_result` messages may come before it. Clients show "thinking…" until the final reply arrives.

This table lives here and in a comment at the top of `server.py`. There are no schema files and no code generation: with five message types, a table is easier to keep correct. We'll revisit that only if the protocol grows a lot or starts breaking.

## 6. Key decisions (tell me if you disagree)

1. **Plain synchronous Python, no asyncio.** The `websockets` library has a threaded mode in which each connection runs top to bottom like a normal script. The trade-off: voice will need things to happen at the same time (listening while speaking, interrupting DONNA mid-sentence). That's the first feature that actually requires concurrency, so we revisit this then and not before.
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
5. **The LLM is reached through Ollama's OpenAI-compatible HTTP API using `httpx`.** That's about 20 lines, and you can see exactly what's sent to the model. The model name is one constant (overridable with an env var), so your laptop can use a small model and your desktop Qwen3.6-35B-A3B.
6. **Offline fake brain (`DONNA_LLM=fake`).** A few keyword rules inside `llm.py` let DONNA run without Ollama: on your laptop while you're away from the desktop, and in CI. Step 3 also uses it, before the real model is connected.
7. **No result IDs yet.** They only matter once DONNA can open a file it found ("open the second one"), and that isn't in v1. When we add it, it's a small dict of the last results.
8. **Folders are named `backend/` and `frontend/`.** That matches the mental model; the README's planned layout uses `core/` and `desktop/`. I'm leaving the README as it is.

## 7. Development steps (each one ends with something you can run)

| Step | Build | You can now… | Status |
|---|---|---|---|
| 1 | Skeleton: `backend/`, `requirements.txt`, `.gitignore`, venv instructions | run `pytest` (one smoke test passes) | ✅ done |
| 2 | `server.py` (echo) + `chat.py` | type "hi" in the terminal and get "You said: hi" back over the WebSocket | ✅ done |
| 3 | `agent.py` with the fake brain | "Hello Donna" → "Hello." through the real message flow | ✅ done |
| 4 | `llm.py` → Ollama + Qwen3.6-35B-A3B | actually chat with DONNA | ✅ done |
| 5 | `open_app` + the tool loop | "Open VS Code" opens VS Code | ✅ done |
| 6 | `find_files` | "Find my TrialGuard files" lists them | ✅ done |
| 7 | `web_search` | "Search the web for X" summarizes the results | ✅ done |
| 8 | React UI in the browser | use DONNA from a web page | ✅ done |
| 9 | Tauri window | use DONNA as a desktop app | ✅ done |
| 10 | Voice | push-to-talk, and DONNA talks back | later |
| 11 | 3D avatar | the golden sphere reacts to listening, thinking and speaking | later |
| 12 | Gestures | pinch and fist via webcam | later |
| 13 | Spatial / projector | projected desk UI | later |

**Steps 1–9 are DONNA v1, and they are built.** Steps 10–13 are deliberately not designed yet. Each gets its own short plan when we reach it, based on what v1 taught us.

I merged your "Python backend" and "WebSocket connection" steps into Step 2, because a backend you can't talk to isn't something you can run.

**Notes on the steps that need them:**
- **Step 4 (model reality check).**
  - Qwen3.6-35B-A3B has 35B parameters, but only about 3B are active per word, which is why it can be fast. At 4-bit it's still roughly 20 GB, so it won't fit in the RX 580's 8 GB. Most of it will sit in your 32 GB of system RAM, next to Windows, VS Code and Chrome.
  - Measure speed and memory first. If it's too heavy, develop with a smaller Qwen; it's a one-line change.
  - Turn "thinking" mode off for chat to get faster replies. I'll confirm the exact Ollama setting at this step.
- **Step 5.** `run_tool(name, args)` looks the tool up in a dict. An unknown tool, bad arguments or a crash returns an error text to the LLM instead of crashing DONNA.
- **Step 6.** A file matches when all the words in the query appear in its name (ignoring case). Results are newest first, with a maximum of 10.
- **Step 7.**
  - DuckDuckGo via `ddgs`, with no API key needed. The top 5 titles, links and snippets go to the LLM; we don't download the pages yet.
  - It's unofficial and may rate-limit. If that becomes a problem, we swap that one function for SearXNG (an open question in the README).
  - Web text is untrusted: a page could say "ignore your instructions…". That's acceptable now because DONNA's tools can't do damage, and it's the reason future risky tools (delete, move) will require your confirmation.
- **Step 8.** `npm create vite` (React + TypeScript), trimmed to the files we use. `App.tsx` opens the WebSocket, keeps the messages in `useState`, renders them by type and has an input box. The five messages get a hand-written TypeScript type. The UI shows connecting/disconnected and retries.
- **Step 9.** `tauri init` with default settings and no custom Rust. You start the backend yourself for now; auto-starting it comes later.

## 8. Testing (proportional)

Testing is `pytest` only. Tests never need Ollama, the internet or Windows:
- The LLM is swapped for a scripted fake.
- The real "launch the app" and "ask DuckDuckGo" calls are swapped for fakes.
- `find_files` runs against a temporary folder containing real files.

The initial set is about 12 tests, each one added in the step that builds the behavior:
- **agent:** plain reply; tool call → tool runs → final reply; unknown tool (the error goes back to the LLM and DONNA still answers); the step limit.
- **tools:** known app is launched (without a shell); unknown app is refused; `find_files` matches the right files and skips `node_modules`; `web_search` formats the results; bad arguments are handled.
- **server:** a round trip over a real socket; a connection from a foreign website's Origin is rejected.

One small GitHub Actions workflow runs `pytest` on every push from Step 3. From Step 8 it also builds the frontend.

## 9. What we are NOT building yet

| Not now | When it comes back |
|---|---|
| Voice: mic, speech-to-text, text-to-speech, wake word | Step 10 |
| 3D avatar / shaders | Step 11 |
| Gestures, cameras, MediaPipe | Step 12 |
| Projector, stereo cameras, spatial UI | Step 13 |
| State machine (IDLE → LISTENING → THINKING → SPEAKING) | When voice or the avatar need to show states. For typed chat, "waiting for a reply" is enough. |
| Interrupting DONNA (cancel / barge-in) | With voice; typed replies are short, so there's nothing to interrupt |
| Streaming replies word by word | If replies feel slow, or when text-to-speech needs sentences early |
| Fast path (skip the LLM for "open X") | Only if we measure that "open X" is too slow. Adding it now would be premature optimization. |
| Opening found files, result IDs | When we add "open that file" |
| Everything (`es.exe`), Start Menu app index, fuzzy app names | When the folder walk or the fixed app list is too slow or too limiting |
| Reading full web pages | When snippets aren't enough |
| Memory across sessions, moving/deleting files, desktop automation | Later (README roadmap). Risky actions will require your confirmation. |
| Installer, auto-starting the backend from Tauri | When you use DONNA daily |
| Auth tokens, protocol schemas and codegen, event bus, plugin system, dependency-injection framework, microservices | Only if a real problem forces one of them |

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
   `DONNA_MODEL` if it differs from `qwen3.5:9b`.
2. Measure speed and memory first (see Step 4 notes). Developing with a smaller Qwen is fine:
   `DONNA_MODEL=<smaller tag>`.
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
