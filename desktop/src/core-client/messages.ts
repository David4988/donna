import type {
  ClientMessage,
  ServerMessage,
  SessionHello,
  UserCancel,
  UserText,
} from "../protocol/generated";

export const PROTOCOL_VERSION = 1;

const SERVER_TYPES = new Set<ServerMessage["type"]>([
  "session.ready",
  "turn.started",
  "turn.completed",
  "turn.cancelled",
  "turn.failed",
  "assistant.state",
  "assistant.text",
  "tool.request",
  "tool.result",
  "tool.error",
  "error",
]);

/** Light structural check. The core is trusted; this guards against garbage. */
export function parseServerMessage(raw: string): ServerMessage | null {
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    return null;
  }
  if (typeof data !== "object" || data === null) return null;
  const msg = data as Record<string, unknown>;
  if (msg.v !== PROTOCOL_VERSION) return null;
  if (typeof msg.type !== "string" || !SERVER_TYPES.has(msg.type as ServerMessage["type"])) {
    return null;
  }
  if (typeof msg.payload !== "object" || msg.payload === null) return null;
  return data as ServerMessage;
}

const envelope = () => ({ v: 1 as const, turn: null, ts: new Date().toISOString() });

export const hello = (token: string): SessionHello => ({
  ...envelope(),
  type: "session.hello",
  payload: { token, client: { name: "desktop", version: "0.1.0" } },
});

export const userText = (text: string): UserText => ({
  ...envelope(),
  type: "user.text",
  payload: { text },
});

export const userCancel = (): UserCancel => ({ ...envelope(), type: "user.cancel", payload: {} });

export const encode = (msg: ClientMessage): string => JSON.stringify(msg);
