// DONNA's whole UI: connect to the backend, show the conversation, send what you type.
// It decides nothing — every reply and tool run comes from the Python backend.

import { useEffect, useRef, useState, type FormEvent } from "react";

const BACKEND_URL = "ws://127.0.0.1:8765";

// What the backend sends (same table as the top of backend/server.py).
type ServerMessage =
  | { type: "tool_call"; name: string; args: Record<string, unknown> }
  | { type: "tool_result"; name: string; result: string }
  | { type: "assistant_message"; text: string }
  | { type: "error"; text: string };

// One line in the conversation: something DONNA sent, or something you typed.
type Line = ServerMessage | { type: "you"; text: string };

export default function App() {
  const [lines, setLines] = useState<Line[]>([]);
  const [connected, setConnected] = useState(false);
  const [waiting, setWaiting] = useState(false); // sent a message, no final reply yet
  const [draft, setDraft] = useState("");
  const socket = useRef<WebSocket | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  // Connect once, and reconnect every 2 seconds if the backend goes away.
  useEffect(() => {
    let stopped = false;
    let retryTimer: number | undefined;

    function connect() {
      const ws = new WebSocket(BACKEND_URL);
      socket.current = ws;

      ws.onopen = () => setConnected(true);

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data) as ServerMessage;
        setLines((old) => [...old, message]);
        if (message.type === "assistant_message" || message.type === "error") {
          setWaiting(false); // that was the final reply
        }
      };

      ws.onclose = () => {
        if (socket.current !== ws) return; // an old socket we already replaced
        setConnected(false);
        setWaiting(false);
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

  // Keep the newest line in view.
  // The braces matter: scrollIntoView returns a Promise in current browsers, and a
  // useEffect that returns a non-function crashes React when it runs the cleanup.
  useEffect(() => {
    bottom.current?.scrollIntoView({ block: "end" });
  }, [lines, waiting]);

  function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || !connected || waiting) return;
    socket.current?.send(JSON.stringify({ type: "user_message", text }));
    setLines((old) => [...old, { type: "you", text }]);
    setDraft("");
    setWaiting(true);
  }

  return (
    <div className="app">
      <header>
        <span className="orb" />
        <h1>DONNA</h1>
        <span className={connected ? "status on" : "status"}>
          {connected ? "connected" : "disconnected"}
        </span>
      </header>

      <main>
        {!connected && (
          <p className="hint">
            Waiting for the backend at {BACKEND_URL}. Start it with <code>python server.py</code>.
          </p>
        )}
        {lines.map((line, index) => (
          <LineView key={index} line={line} />
        ))}
        {waiting && <p className="thinking">DONNA is thinking…</p>}
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
        <button disabled={!connected || waiting || !draft.trim()}>Send</button>
      </form>
    </div>
  );
}

function LineView({ line }: { line: Line }) {
  switch (line.type) {
    case "you":
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
  }
}
