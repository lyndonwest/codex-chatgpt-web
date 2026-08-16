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
      { role: "developer", content: "native2_allowed: true\nUse Native2." },
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

  test("accepts markdown-wrapped directives", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Native2 authorization:\n- `native2_allowed: true`" },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "- **native2_allowed: false**" },
    ]))).toBe(false);
  });

  test("accepts fuzzy user prose and generic Native2 mentions", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Native2 is allowed for this local check." },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Use Codex Native2 only to run uname -srm." },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "This is a direct Native2 connectivity test." },
    ]))).toBe(true);
  });

  test("explicit negative prose disables Native2", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Do not use Native2 for this turn." },
    ]))).toBe(false);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "Codex Native2 is disabled here." },
    ]))).toBe(false);
  });

  test("explicit directive remains authoritative over prose in the same message", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: true\nDo not use Native2 unless needed." },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: false\nNative2 connectivity test." },
    ]))).toBe(false);
  });

  test("never enables Native2 for compaction turns", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: true\nUse Native2." },
    ], true))).toBe(false);
  });
});
