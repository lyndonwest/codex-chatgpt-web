import { describe, expect, test } from "bun:test";
import { createHash } from "node:crypto";
import { chatGptTurnExecutionKey } from "../src/adapters/chatgpt-web/turn-execution";

describe("ChatGPT Web trace correlation", () => {
  test("trace identity remains the execution-key hash contract", () => {
    const executionNamespace = "namespace";
    const parsed = {
      modelId: "chatgpt-web/high",
      previousResponseId: "response-1",
      context: { system: [], messages: [], tools: [] },
      options: { reasoning: "high" },
    } as any;
    const executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;
    const traceId = createHash("sha256").update(executionKey).digest("hex").slice(0, 12);
    expect(traceId).toHaveLength(12);
    expect(traceId).toMatch(/^[a-f0-9]{12}$/);
  });
});
