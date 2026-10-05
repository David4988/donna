import { describe, expect, it } from "vitest";
import { encode, hello, parseServerMessage, userCancel, userText } from "./messages";

describe("parseServerMessage", () => {
  it("accepts a valid server message", () => {
    const raw = JSON.stringify({ v: 1, type: "assistant.text", turn: "t_1", ts: "x", payload: { text: "Hello.", final: true } });
    expect(parseServerMessage(raw)?.type).toBe("assistant.text");
  });

  it.each([
    ["not json", "{"],
    ["wrong version", JSON.stringify({ v: 2, type: "assistant.text", payload: {} })],
    ["unknown type", JSON.stringify({ v: 1, type: "gesture.detected", payload: {} })],
    ["client type", JSON.stringify({ v: 1, type: "user.text", payload: { text: "x" } })],
    ["missing payload", JSON.stringify({ v: 1, type: "error" })],
    ["not an object", "42"],
  ])("rejects %s", (_name, raw) => {
    expect(parseServerMessage(raw)).toBeNull();
  });
});

describe("client message builders", () => {
  it("build complete v1 envelopes", () => {
    for (const msg of [hello("tok"), userText("hi"), userCancel()]) {
      const parsed = JSON.parse(encode(msg));
      expect(parsed).toMatchObject({ v: 1, turn: null });
      expect(typeof parsed.ts).toBe("string");
    }
    expect(hello("tok").payload.token).toBe("tok");
  });
});
