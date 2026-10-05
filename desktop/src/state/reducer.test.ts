import { describe, expect, it } from "vitest";
import type { ServerMessage } from "../protocol/generated";
import { initialState, reducer, type UiState } from "./reducer";

const env = (turn: string | null = "t_1") => ({ v: 1 as const, turn, ts: "2026-10-05T00:00:00Z" });

function apply(...msgs: ServerMessage[]): UiState {
  return msgs.reduce((s, msg) => reducer(s, { kind: "server", msg }), initialState);
}

describe("reducer", () => {
  it("projects a full tool turn", () => {
    const s = apply(
      { ...env(), type: "turn.started", payload: { input: "find my TrialGuard files" } },
      { ...env(), type: "assistant.state", payload: { state: "THINKING", previous: "IDLE" } },
      { ...env(), type: "assistant.state", payload: { state: "EXECUTING", previous: "THINKING" } },
      {
        ...env(),
        type: "tool.request",
        payload: { call_id: "c1", tool: "find_files", args: { query: "TrialGuard" }, label: "Searching files..." },
      },
    );
    expect(s.assistantState).toBe("EXECUTING");
    expect(s.activeTurn).toBe("t_1");
    expect(s.messages).toEqual([{ id: 1, role: "user", text: "find my TrialGuard files", turn: "t_1" }]);
    expect(s.tools[0]).toMatchObject({ callId: "c1", status: "running", label: "Searching files..." });

    const done = [
      {
        ...env(),
        type: "tool.result",
        payload: {
          call_id: "c1",
          tool: "find_files",
          summary: "I found 1 file.",
          results: [{ id: "r_1", kind: "file", title: "TrialGuard_Proposal.pdf", subtitle: "Docs" }],
        },
      },
      { ...env(), type: "assistant.text", payload: { text: "I found 1 file.", final: true } },
      { ...env(), type: "assistant.state", payload: { state: "IDLE", previous: "SPEAKING" } },
      { ...env(), type: "turn.completed", payload: { route: "llm" } },
    ] satisfies ServerMessage[];
    const end = done.reduce((acc, msg) => reducer(acc, { kind: "server", msg }), s);
    expect(end.tools[0]).toMatchObject({ status: "done", summary: "I found 1 file." });
    expect(end.tools[0]?.results[0]?.id).toBe("r_1");
    expect(end.messages.at(-1)).toMatchObject({ role: "assistant", text: "I found 1 file." });
    expect(end.activeTurn).toBeNull();
    expect(end.assistantState).toBe("IDLE");
  });

  it("marks running tools cancelled when the turn is cancelled", () => {
    const s = apply(
      { ...env(), type: "turn.started", payload: { input: "find x" } },
      { ...env(), type: "tool.request", payload: { call_id: "c1", tool: "find_files", args: {}, label: "..." } },
      { ...env(), type: "turn.cancelled", payload: { reason: "superseded" } },
    );
    expect(s.tools[0]?.status).toBe("cancelled");
    expect(s.activeTurn).toBeNull();
    expect(s.messages.at(-1)).toMatchObject({ role: "system", text: "Cancelled (superseded)" });
  });

  it("records tool errors, turn failures and protocol errors", () => {
    const s = apply(
      { ...env(), type: "tool.request", payload: { call_id: "c1", tool: "open_app", args: {}, label: "..." } },
      {
        ...env(),
        type: "tool.error",
        payload: { call_id: "c1", tool: "open_app", code: "app_not_found", message: "No such app." },
      },
      { ...env(), type: "turn.failed", payload: { message: "boom" } },
    );
    expect(s.tools[0]).toMatchObject({ status: "error", summary: "No such app." });
    expect(s.lastError).toBe("boom");
    const e = reducer(s, {
      kind: "server",
      msg: { ...env(null), type: "error", payload: { code: "invalid_payload", message: "text: too short" } },
    });
    expect(e.lastError).toBe("invalid_payload: text: too short");
    expect(reducer(e, { kind: "dismissError" }).lastError).toBeNull();
  });

  it("takes the assistant state from session.ready and resets it on disconnect", () => {
    const ready = apply({
      ...env(null),
      type: "session.ready",
      payload: { session_id: "s_1", protocol_version: 1, server_version: "0.1.0", state: "SPEAKING", tools: [] },
    });
    expect(ready.assistantState).toBe("SPEAKING");
    const lost = reducer(ready, { kind: "connection", status: "disconnected" });
    expect(lost.connection).toBe("disconnected");
    expect(lost.assistantState).toBe("IDLE");
  });

  it("does not mutate the previous state", () => {
    const before = initialState;
    reducer(before, { kind: "server", msg: { ...env(), type: "turn.started", payload: { input: "hi" } } });
    expect(before.messages).toHaveLength(0);
  });
});

describe("tool activity identity", () => {
  it("treats equal call ids in different turns as different tools", () => {
    const req = (turn: string) =>
      ({ ...env(turn), type: "tool.request", payload: { call_id: "call_0", tool: "find_files", args: {}, label: "..." } }) as const;
    const s = apply(req("t_1"), req("t_2"), {
      ...env("t_2"),
      type: "tool.result",
      payload: { call_id: "call_0", tool: "find_files", summary: "done", results: [] },
    });
    expect(s.tools.map((t) => t.status)).toEqual(["running", "done"]);
  });
});
