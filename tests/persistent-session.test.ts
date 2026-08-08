import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { compileChatGptWebPrompt } from "../src/adapters/chatgpt-web/prompt";
import { CHATGPT_WEB_MODEL_ID } from "../src/adapters/chatgpt-web/model";
import type { CodexMessage, CodexParsedRequest } from "../src/types";

function request(messages: CodexMessage[], compaction = false): CodexParsedRequest {
  return {
    modelId: CHATGPT_WEB_MODEL_ID,
    context: {
      systemPrompt: ["system contract"],
      messages,
    },
    stream: true,
    options: { reasoning: "high" },
    ...(compaction ? { _compactionRequest: true } : {}),
  };
}

test("persistent continuation sends only the newest user revision instead of replaying old context", () => {
  const old = "old-tool-history-".repeat(20_000);
  const parsed = request([
    { role: "developer", content: "developer contract", timestamp: 1 },
    { role: "user", content: "initial request", timestamp: 2 },
    {
      role: "toolResult",
      toolCallId: "call_old",
      toolName: "exec_command",
      content: old,
      isError: false,
      timestamp: 3,
    },
    { role: "assistant", content: [{ type: "text", text: "progress" }], timestamp: 4 },
    { role: "user", content: "new steering instruction", timestamp: 5 },
  ]);
  const compiled = compileChatGptWebPrompt(
    parsed,
    { localToolsEnabled: true, proAvailable: true },
    "turn_12345678901234567890123456789012",
  );

  expect(compiled.text).toContain(old);
  expect(compiled.continuation).toBeDefined();
  expect(compiled.continuation!.text).toContain("new steering instruction");
  expect(compiled.continuation!.text).not.toContain("initial request");
  expect(compiled.continuation!.text).not.toContain(old);
  expect(compiled.continuation!.text).toContain("codex_bind_turn");
  expect(compiled.continuation!.text.length).toBeLessThan(compiled.text.length / 20);
});

test("persistent compaction is a tiny same-chat checkpoint with no replayed transcript or tools", () => {
  const huge = "historical-context-".repeat(30_000);
  const parsed = request([
    { role: "user", content: "do the task", timestamp: 1 },
    {
      role: "toolResult",
      toolCallId: "call_huge",
      toolName: "exec_command",
      content: huge,
      isError: false,
      timestamp: 2,
    },
  ], true);
  const compiled = compileChatGptWebPrompt(
    parsed,
    { localToolsEnabled: false, proAvailable: true },
  );

  expect(compiled.text).toContain(huge);
  expect(compiled.continuation).toBeDefined();
  expect(compiled.continuation!.text).toContain("history-compaction checkpoint");
  expect(compiled.continuation!.text).not.toContain(huge);
  expect(compiled.continuation!.text).not.toContain("<codex_context_json>");
  expect(compiled.continuation!.text).not.toContain("codex_bind_turn");
  expect(compiled.continuation!.images).toEqual([]);
  expect(compiled.continuation!.text.length).toBeLessThan(2_000);
});

test("launcher browser worker chooses the retained-chat continuation without navigating a new Temporary Chat", () => {
  const source = readFileSync(
    new URL("../src/adapters/chatgpt-web/browser-worker.ts", import.meta.url),
    "utf8",
  );
  expect(source).toContain("lease.reused === true");
  expect(source).toContain("const effectivePrepared = reuseExistingChat ? prepared.continuation! : prepared");
  expect(source).toContain('this.runStage(turn.traceId, "persistent_chat_settle"');
  expect(source).toContain("this.waitForExistingChatIdle(page)");
  expect(source).toContain("if (reuseExistingChat)");
  expect(source).toContain("persistent=${reuseExistingChat}");
});

test("adapter derives persistent browser identity from native thread metadata without replacing execution identity", () => {
  const source = readFileSync(
    new URL("../src/adapters/chatgpt-web/index.ts", import.meta.url),
    "utf8",
  );
  expect(source).toContain(":browser-thread:");
  expect(source).toContain("const persistentSessionId = browserSessionId(parsed)");
  expect(source).toContain("startRuntime(parsed, environment, traceId, turnCapabilities, persistentSessionId)");
  expect(source).toContain("const traceId = createHash");
});
