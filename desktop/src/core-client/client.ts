/**
 * WebSocket client for the core. Transport only: it forwards server messages to
 * listeners and sends user intents. It makes no decisions about what DONNA does.
 */
import type { ServerMessage } from "../protocol/generated";
import { encode, hello, parseServerMessage, userCancel, userText } from "./messages";
import { loadSession, type CoreSession } from "./session";

export type ConnectionStatus = "connecting" | "connected" | "disconnected" | "unauthorized";

export interface ClientCallbacks {
  onMessage: (msg: ServerMessage) => void;
  onStatus: (status: ConnectionStatus, detail?: string) => void;
}

const CLOSE_UNAUTHORIZED = 4401;
const MAX_BACKOFF_MS = 5000;

export class CoreClient {
  private ws: WebSocket | null = null;
  private stopped = false;
  private attempt = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;

  constructor(
    private readonly callbacks: ClientCallbacks,
    private readonly getSession: () => Promise<CoreSession | null> = loadSession,
  ) {}

  start(): void {
    this.stopped = false;
    void this.connect();
  }

  stop(): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.ws?.close(1000, "client closing");
    this.ws = null;
  }

  sendText(text: string): void {
    this.send(encode(userText(text)));
  }

  cancel(): void {
    this.send(encode(userCancel()));
  }

  private send(data: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(data);
  }

  private async connect(): Promise<void> {
    if (this.stopped) return;
    this.callbacks.onStatus("connecting");
    const session = await this.getSession();
    // stop() may have been called while we were waiting (e.g. React StrictMode
    // mounting effects twice). Don't open a second, orphaned socket.
    if (this.stopped) return;
    if (!session) {
      this.callbacks.onStatus(
        "disconnected",
        "No core session found. Start the core (donna-core --print-ui-url).",
      );
      this.retry();
      return;
    }

    const ws = new WebSocket(session.url);
    this.ws = ws;
    ws.onopen = () => ws.send(encode(hello(session.token)));
    ws.onmessage = (ev: MessageEvent<string>) => {
      const msg = parseServerMessage(ev.data);
      if (!msg) return;
      if (msg.type === "session.ready") {
        this.attempt = 0;
        this.callbacks.onStatus("connected");
      }
      this.callbacks.onMessage(msg);
    };
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (ev.code === CLOSE_UNAUTHORIZED) {
        this.callbacks.onStatus("unauthorized", "The core rejected our token.");
      } else {
        this.callbacks.onStatus("disconnected");
      }
      this.retry();
    };
  }

  private retry(): void {
    if (this.stopped) return;
    const delay = Math.min(MAX_BACKOFF_MS, 250 * 2 ** this.attempt++);
    this.timer = setTimeout(() => void this.connect(), delay);
  }
}
