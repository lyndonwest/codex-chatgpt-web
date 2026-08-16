import { describe, expect, test } from "bun:test";
import type { CodexParsedRequest } from "../src/types";
import { chatGptNative2Allowed } from "../src/adapters/chatgpt-web/capability-routing";

function parsed(messages: unknown[] = [], compaction = false): CodexParsedRequest {
  return {
    context: { messages },
    _compactionRequest: compaction,
  } as unknown as CodexParsedRequest;
}

describe("ChatGPT Web Native2 routing", () => {
  test("enables Native2 for ordinary Web turns without an authorization directive", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Get an implementer web agent to say hi." },
    ]))).toBe(true);
  });

  test("task prose no longer controls Native2 availability", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: false\nDo not use Native2." },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "developer", content: "native2_allowed: true" },
      { role: "user", content: "Review the PR through GitHub." },
    ]))).toBe(true);
  });

  test("keeps Native2 disabled for compaction turns", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Use Native2." },
    ], true))).toBe(false);
  });
});
