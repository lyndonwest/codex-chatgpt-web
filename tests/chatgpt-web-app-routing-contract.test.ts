import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const worker = readFileSync("src/adapters/chatgpt-web/browser-worker.ts", "utf8");
const adapter = readFileSync("src/adapters/chatgpt-web/index.ts", "utf8");
const helperClient = readFileSync("src/adapters/chatgpt-web/launcher-helper-client.ts", "utf8");
const helperMain = readFileSync("src/adapters/chatgpt-web/browser-helper-main.ts", "utf8");

describe("GitHub-first Web app routing contract", () => {
  test("normal turns attach GitHub and Native2 remains directive-gated", () => {
    expect(adapter).toContain("chatGptNative2Allowed(parsed)");
    expect(adapter).toContain("useGitHubApp: !parsed._compactionRequest");
    expect(worker).toContain('CHATGPT_GITHUB_CONNECTOR_NAME = "GitHub"');
    expect(worker).toContain("...(useGitHubApp ? [CHATGPT_GITHUB_CONNECTOR_NAME] : [])");
    expect(worker).toContain("...(localTools ? [this.config.appName] : [])");
  });

  test("launcher helper preserves the GitHub-app flag", () => {
    expect(helperClient).toContain("turn.useGitHubApp ? { useGitHubApp: true }");
    expect(helperMain).toContain("useGitHubApp?: boolean");
    expect(helperMain).toContain("message.turn.useGitHubApp ? { useGitHubApp: true }");
  });
});
