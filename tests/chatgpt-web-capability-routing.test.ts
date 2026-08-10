import { describe, expect, test } from "bun:test";
import type { CodexParsedRequest } from "../src/types";
import { chatGptNative2Allowed } from "../src/adapters/chatgpt-web/capability-routing";

function parsed(messages: unknown[], compaction = false): CodexParsedRequest {
  return {
    context: { messages },
    _compactionRequest: compaction,
  } as unknown as CodexParsedRequest;
}

describe("ChatGPT Web Native2 routing", () => {
  test("defaults closed and ignores developer instructions", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "developer", content: "native2_allowed: true" },
      { role: "user", content: "Review the PR through GitHub." },
    ]))).toBe(false);
  });

  test("honors the latest explicit user-packet directive", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: false" },
      { role: "user", content: "native2_allowed: true\nnative2_scope: inspect live container logs" },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: true" },
      { role: "user", content: "native2_allowed: false" },
    ]))).toBe(false);
  });

  test("never enables Native2 for compaction turns", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: true" },
    ], true))).toBe(false);
  });
});
