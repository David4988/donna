import { describe, expect, it } from "vitest";
import { parseSessionHash } from "./session";

describe("parseSessionHash", () => {
  it("reads port and token", () => {
    expect(parseSessionHash("#port=4567&token=abc_DEF-1")).toEqual({
      url: "ws://127.0.0.1:4567",
      token: "abc_DEF-1",
    });
  });

  it.each(["", "#", "#port=4567", "#token=abc", "#port=0&token=a", "#port=99999&token=a", "#port=x&token=a"])(
    "rejects %j",
    (hash) => {
      expect(parseSessionHash(hash)).toBeNull();
    },
  );

  it("always targets 127.0.0.1", () => {
    expect(parseSessionHash("#port=1&token=t")?.url.startsWith("ws://127.0.0.1:")).toBe(true);
  });
});
