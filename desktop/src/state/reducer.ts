/**
 * UI state is a pure projection of core events. No agent logic lives here:
 * the reducer only records what the core says happened.
 */
import type { ConnectionStatus } from "../core-client/client";
import type { AssistantState, ResultItem, ServerMessage } from "../protocol/generated";

export interface ChatMessage {
  id: number;
  role: "user" | "assistant" | "system";
  text: string;
  turn: string | null;
}

export interface ToolActivity {
  callId: string;
  tool: string;
  label: string;
  status: "running" | "done" | "error" | "cancelled";
  summary: string;
  results: ResultItem[];
  turn: string | null;
}

export interface UiState {
  connection: ConnectionStatus;
  connectionDetail: string | null;
  assistantState: AssistantState;
  activeTurn: string | null;
  messages: ChatMessage[];
  tools: ToolActivity[];
  lastError: string | null;
}

export type Action =
  | { kind: "connection"; status: ConnectionStatus; detail?: string }
  | { kind: "server"; msg: ServerMessage }
  | { kind: "dismissError" };

export const initialState: UiState = {
  connection: "connecting",
  connectionDetail: null,
  assistantState: "IDLE",
  activeTurn: null,
  messages: [],
  tools: [],
  lastError: null,
};

const MAX_MESSAGES = 200;
const MAX_TOOLS = 20;

function addMessage(state: UiState, role: ChatMessage["role"], text: string, turn: string | null) {
  const id = (state.messages.at(-1)?.id ?? 0) + 1;
  return [...state.messages, { id, role, text, turn }].slice(-MAX_MESSAGES);
}

/** Call ids come from the model and are only unique within a turn. */
export const toolKey = (t: { turn: string | null; callId: string }) => `${t.turn}:${t.callId}`;

function updateTool(
  tools: ToolActivity[],
  turn: string | null,
  callId: string,
  patch: Partial<ToolActivity>,
): ToolActivity[] {
  return tools.map((t) => (t.turn === turn && t.callId === callId ? { ...t, ...patch } : t));
}

export function reducer(state: UiState, action: Action): UiState {
  switch (action.kind) {
    case "connection":
      return {
        ...state,
        connection: action.status,
        connectionDetail: action.detail ?? null,
        // If we lost the core, we no longer know its state.
        ...(action.status !== "connected" && { assistantState: "IDLE", activeTurn: null }),
      };
    case "dismissError":
      return { ...state, lastError: null };
    case "server":
      return applyServerMessage(state, action.msg);
  }
}

function applyServerMessage(state: UiState, msg: ServerMessage): UiState {
  switch (msg.type) {
    case "session.ready":
      return { ...state, assistantState: msg.payload.state, lastError: null };
    case "turn.started":
      return {
        ...state,
        activeTurn: msg.turn,
        messages: addMessage(state, "user", msg.payload.input, msg.turn),
      };
    case "assistant.state":
      return { ...state, assistantState: msg.payload.state };
    case "assistant.text":
      return { ...state, messages: addMessage(state, "assistant", msg.payload.text, msg.turn) };
    case "tool.request": {
      const activity: ToolActivity = {
        callId: msg.payload.call_id,
        tool: msg.payload.tool,
        label: msg.payload.label,
        status: "running",
        summary: "",
        results: [],
        turn: msg.turn,
      };
      return { ...state, tools: [...state.tools, activity].slice(-MAX_TOOLS) };
    }
    case "tool.result":
      return {
        ...state,
        tools: updateTool(state.tools, msg.turn, msg.payload.call_id, {
          status: "done",
          summary: msg.payload.summary,
          results: msg.payload.results,
        }),
      };
    case "tool.error":
      return {
        ...state,
        tools: updateTool(state.tools, msg.turn, msg.payload.call_id, {
          status: "error",
          summary: msg.payload.message,
        }),
      };
    case "turn.cancelled":
      return {
        ...state,
        activeTurn: null,
        messages: addMessage(state, "system", `Cancelled (${msg.payload.reason})`, msg.turn),
        tools: state.tools.map((t) =>
          t.turn === msg.turn && t.status === "running" ? { ...t, status: "cancelled" } : t,
        ),
      };
    case "turn.completed":
      return { ...state, activeTurn: null };
    case "turn.failed":
      return { ...state, activeTurn: null, lastError: msg.payload.message };
    case "error":
      return { ...state, lastError: `${msg.payload.code}: ${msg.payload.message}` };
  }
}
