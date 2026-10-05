/* Generated from protocol/donna.schema.json by json-schema-to-typescript. Do not edit; run scripts/gen_protocol.sh. */

/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "AssistantState".
 */
export type AssistantState = "IDLE" | "LISTENING" | "THINKING" | "EXECUTING" | "SPEAKING" | "ERROR";
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ClientMessage".
 */
export type ClientMessage = SessionHello | UserText | UserCancel;
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ServerMessage".
 */
export type ServerMessage =
  | SessionReady
  | TurnStarted
  | TurnCompleted
  | TurnCancelled
  | TurnFailed
  | AssistantStateChanged
  | AssistantText
  | ToolRequest
  | ToolResult
  | ToolError
  | Error;

/**
 * DONNA wire protocol v1. Generated from Pydantic.
 */
export interface DonnaProtocol {
  [k: string]: unknown;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "AssistantStateChanged".
 */
export interface AssistantStateChanged {
  v: 1;
  turn: string | null;
  ts: string;
  type: "assistant.state";
  payload: AssistantStatePayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "AssistantStatePayload".
 */
export interface AssistantStatePayload {
  state: AssistantState;
  previous: AssistantState;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "AssistantText".
 */
export interface AssistantText {
  v: 1;
  turn: string | null;
  ts: string;
  type: "assistant.text";
  payload: AssistantTextPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "AssistantTextPayload".
 */
export interface AssistantTextPayload {
  text: string;
  final: boolean;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ClientInfo".
 */
export interface ClientInfo {
  name: string;
  version: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "SessionHello".
 */
export interface SessionHello {
  v: 1;
  turn: string | null;
  ts: string;
  type: "session.hello";
  payload: SessionHelloPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "SessionHelloPayload".
 */
export interface SessionHelloPayload {
  token: string;
  client: ClientInfo;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "UserText".
 */
export interface UserText {
  v: 1;
  turn: string | null;
  ts: string;
  type: "user.text";
  payload: UserTextPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "UserTextPayload".
 */
export interface UserTextPayload {
  text: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "UserCancel".
 */
export interface UserCancel {
  v: 1;
  turn: string | null;
  ts: string;
  type: "user.cancel";
  payload: UserCancelPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "UserCancelPayload".
 */
export interface UserCancelPayload {}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "Error".
 */
export interface Error {
  v: 1;
  turn: string | null;
  ts: string;
  type: "error";
  payload: ErrorPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ErrorPayload".
 */
export interface ErrorPayload {
  code: string;
  message: string;
}
/**
 * What clients and the LLM may see about a result. Never the raw path/URL.
 *
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ResultItem".
 */
export interface ResultItem {
  id: string;
  kind: "file" | "app" | "web";
  title: string;
  subtitle: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "SessionReady".
 */
export interface SessionReady {
  v: 1;
  turn: string | null;
  ts: string;
  type: "session.ready";
  payload: SessionReadyPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "SessionReadyPayload".
 */
export interface SessionReadyPayload {
  session_id: string;
  protocol_version: number;
  server_version: string;
  state: AssistantState;
  tools: string[];
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnStarted".
 */
export interface TurnStarted {
  v: 1;
  turn: string | null;
  ts: string;
  type: "turn.started";
  payload: TurnStartedPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnStartedPayload".
 */
export interface TurnStartedPayload {
  input: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnCompleted".
 */
export interface TurnCompleted {
  v: 1;
  turn: string | null;
  ts: string;
  type: "turn.completed";
  payload: TurnCompletedPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnCompletedPayload".
 */
export interface TurnCompletedPayload {
  route: "fast_path" | "llm";
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnCancelled".
 */
export interface TurnCancelled {
  v: 1;
  turn: string | null;
  ts: string;
  type: "turn.cancelled";
  payload: TurnCancelledPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnCancelledPayload".
 */
export interface TurnCancelledPayload {
  reason: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnFailed".
 */
export interface TurnFailed {
  v: 1;
  turn: string | null;
  ts: string;
  type: "turn.failed";
  payload: TurnFailedPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "TurnFailedPayload".
 */
export interface TurnFailedPayload {
  message: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ToolRequest".
 */
export interface ToolRequest {
  v: 1;
  turn: string | null;
  ts: string;
  type: "tool.request";
  payload: ToolRequestPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ToolRequestPayload".
 */
export interface ToolRequestPayload {
  call_id: string;
  tool: string;
  args: {
    [k: string]: unknown;
  };
  label: string;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ToolResult".
 */
export interface ToolResult {
  v: 1;
  turn: string | null;
  ts: string;
  type: "tool.result";
  payload: ToolResultPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ToolResultPayload".
 */
export interface ToolResultPayload {
  call_id: string;
  tool: string;
  summary: string;
  results: ResultItem[];
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ToolError".
 */
export interface ToolError {
  v: 1;
  turn: string | null;
  ts: string;
  type: "tool.error";
  payload: ToolErrorPayload;
}
/**
 * This interface was referenced by `DonnaProtocol`'s JSON-Schema
 * via the `definition` "ToolErrorPayload".
 */
export interface ToolErrorPayload {
  call_id: string;
  tool: string;
  code: string;
  message: string;
}
