import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { compileChatGptWebPrompt } from "../src/adapters/chatgpt-web/prompt";
import { CHATGPT_WEB_MODEL_ID } from "../src/adapters/chatgpt-web/model";
import type { CodexParsedRequest } from "../src/types";

test("connector selection prefers the documented plus-More app path before mention fallback", () => {
  const source = readFileSync(
    new URL("../src/adapters/chatgpt-web/browser-worker.ts", import.meta.url),
    "utf8",
  );
  expect(source).toContain("selectConnectorFromToolsMenu");
  expect(source).toContain('button[data-testid="composer-plus-btn"]');
  expect(source).toContain('getByText("More", { exact: true })');
  expect(source).toContain("connector-tools-menu-triggered");
  expect(source).toContain("connector-tools-more-opened");
  expect(source).toContain("connector-tools-app-selected");

  const selectStart = source.indexOf("private async selectConnector(");
  const toolsAttempt = source.indexOf("this.selectConnectorFromToolsMenu(", selectStart);
  const mentionFallback = source.indexOf('composer.pressSequentially("@c"', selectStart);
  expect(selectStart).toBeGreaterThanOrEqual(0);
  expect(toolsAttempt).toBeGreaterThan(selectStart);
  expect(mentionFallback).toBeGreaterThan(toolsAttempt);
});

test("same-chat compaction requests a bounded concise checkpoint", () => {
  const parsed: CodexParsedRequest = {
    modelId: CHATGPT_WEB_MODEL_ID,
    stream: true,
    context: {
      messages: [{ role: "user", content: "Implement the task", timestamp: 1 }],
    },
    options: { reasoning: "high" },
    _compactionRequest: true,
  };
  const compiled = compileChatGptWebPrompt(parsed, { localToolsEnabled: false, proAvailable: true });
  expect(compiled.continuation?.text).toContain("1,500 words");
  expect(compiled.continuation?.text).toContain("dense bullets");
});
