// DONNA's whole UI: connect to the backend, show the conversation, send what
// you type, and carry the audio in both directions.
//
// It decides nothing — every reply, every tool run, and the decision about
// whether an utterance was even meant for her, all come from the Python
// backend. The window is a sensor and a speaker: it reports "someone finished
// speaking, here is the audio" and plays back what it is given.

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Mic, Speaker, toPcm16 } from "./audio";

const BACKEND_URL = "ws://127.0.0.1:8765";

// What the backend sends (same table as the top of backend/server.py).
// Audio arrives as binary frames, not as one of these.
type ServerMessage =
  | { type: "transcript"; text: string }
  | { type: "state"; name: string }
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; result: string }
  | { type: "assistant_delta"; text: string }
  | { type: "assistant_message"; text: string }
  | { type: "error"; text: string };

// One line in the conversation. Deltas build up the reply below rather than
// becoming lines, and `state` drives the header rather than the transcript.
type Line =
  | Exclude<ServerMessage, { type: "assistant_delta" } | { type: "state" }>
  | { type: "you"; text: string };

export default function App() {
  const [lines, setLines] = useState<Line[]>([]);
  const [connected, setConnected] = useState(false);
  const [waiting, setWaiting] = useState(false); // sent a message, no final reply yet
  const [reply, setReply] = useState(""); // the answer so far, arriving piece by piece
  const [draft, setDraft] = useState("");
  const [state, setState] = useState("asleep"); // what the backend says she's doing
  const [listening, setListening] = useState(false); // has the mic been switched on?
  const [micProblem, setMicProblem] = useState("");
  const socket = useRef<WebSocket | null>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const speaker = useRef(new Speaker());

  // Connect once, and reconnect every 2 seconds if the backend goes away.
  useEffect(() => {
    let stopped = false;
    let retryTimer: number | undefined;

    function connect() {
      const ws = new WebSocket(BACKEND_URL);
      ws.binaryType = "arraybuffer"; // her voice arrives as raw PCM16
      socket.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        if (event.data instanceof ArrayBuffer) {
          speaker.current.play(event.data); // a sentence of her reply
          return;
        }

        const message = JSON.parse(event.data) as ServerMessage;

        if (message.type === "assistant_delta") {
          setReply((old) => old + message.text);
          return; // a piece of the answer, not a line of its own
        }
        if (message.type === "state") {
          setState(message.name);
          if (message.name === "speaking") setWaiting(false);
          return; // the header, not the transcript
        }

        // Anything else ends the live reply. When it's the assistant_message it
        // holds the very same text, so clearing here cannot duplicate it.
        setReply("");
        setLines((old) => [...old, message]);
        if (message.type === "assistant_message" || message.type === "error") {
          setWaiting(false); // that was the final reply
        }
      };

      ws.onclose = () => {
        if (socket.current !== ws) return; // an old socket we already replaced
        setConnected(false);
        setWaiting(false);
        setReply("");
        setState("asleep");
        speaker.current.stop();
        if (!stopped) retryTimer = window.setTimeout(connect, 2000);
      };
    }

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      socket.current?.close();
    };
  }, []);

  // The microphone. The window decides only that someone finished speaking;
  // whether it was meant for her is the backend's call.
  const mic = useRef(
    new Mic((audio) => {
      // She can't hear while she's talking, and the backend drops it anyway --
      // but her own voice leaking past echo cancellation shouldn't even be sent.
      if (speaker.current.busy) return;
      socket.current?.send(toPcm16(audio));
    }),
  );

  // Switch the microphone off when the window goes away.
  useEffect(() => {
    const listener = mic.current;
    return () => listener.stop();
  }, []);

  // Keep the newest line in view.
  // The braces matter: scrollIntoView returns a Promise in current browsers, and a
  // useEffect that returns a non-function crashes React when it runs the cleanup.
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [lines, waiting, reply]);

  /** One click per launch: an AudioContext starts suspended, and the browser
   *  only asks for the microphone during a real gesture. */
  async function startVoice() {
    setMicProblem("");
    try {
      await speaker.current.start();
      await mic.current.start();
      setListening(true);
    } catch (error) {
      setMicProblem(
        error instanceof Error && error.name === "NotAllowedError"
          ? "DONNA can't hear you — microphone access was blocked."
          : `DONNA can't hear you — ${String(error)}`,
      );
    }
  }

  function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !connected || waiting || state === "speaking") return;
    socket.current?.send(JSON.stringify({ type: "user_message", text }));
    setLines((old) => [...old, { type: "you", text }]);
    setDraft("");
    setWaiting(true);
  }

  const busy = waiting || state === "speaking";

  return (
    <div className="app">
      <header>
        <span className="orb" />
        <h1>DONNA</h1>
        <span className={connected ? "status on" : "status"}>
          {connected ? statusWords(state, listening) : "disconnected"}
        </span>
      </header>

      <main>
        {!connected && (
          <p className="hint">
            Waiting for the backend at {BACKEND_URL}. Start it with <code>python server.py</code>.
          </p>
        )}
        {connected && !listening && (
          <p className="hint">
            <button type="button" onClick={startVoice}>
              Start voice
            </button>{" "}
            then say “Hey Donna”.
          </p>
        )}
        {micProblem && <p className="error">{micProblem}</p>}
        {lines.map((line, index) => (
          <LineView key={index} line={line} />
        ))}
        {reply.length > 0 && <p className="donna">{reply}</p>}
        {waiting && reply.length === 0 && <p className="thinking">DONNA is thinking…</p>}
        <div ref={bottom} />
      </main>

      <form onSubmit={send}>
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Try: Find my TrialGuard files"
          disabled={!connected}
          autoFocus
        />
        <button disabled={!connected || busy || !draft.trim()}>Send</button>
      </form>
    </div>
  );
}

/** What the header pill says. `deaf` and `mute` are one-shot notices from the
 *  backend rather than session states, so they stick until it says otherwise. */
function statusWords(state: string, listening: boolean) {
  switch (state) {
    case "deaf":
      return "can't hear";
    case "mute":
      return "voice unavailable";
    case "speaking":
      return "speaking";
    case "awake":
      return "listening";
    default:
      return listening ? "say “Hey Donna”" : "connected";
  }
}

function LineView({ line }: { line: Line }) {
  switch (line.type) {
    case "you":
      return <p className="you">{line.text}</p>;
    case "transcript":
      return <p className="you">{line.text}</p>;
    case "assistant_message":
      return <p className="donna">{line.text}</p>;
    case "tool_call":
      return (
        <p className="tool">
          ▸ {line.name} {JSON.stringify(line.args)}
        </p>
      );
    case "tool_result":
      return <pre className="tool">{line.result}</pre>;
    case "error":
      return <p className="error">{line.text}</p>;
    default: {
      // A message type with no case above would otherwise render as nothing at
      // all. This makes `tsc` refuse to build instead.
      const unhandled: never = line;
      return <p className="error">Unknown message: {JSON.stringify(unhandled)}</p>;
    }
  }
}
