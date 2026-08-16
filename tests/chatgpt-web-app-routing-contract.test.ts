import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const worker = readFileSync("src/adapters/chatgpt-web/browser-worker.ts", "utf8");
const adapter = readFileSync("src/adapters/chatgpt-web/index.ts", "utf8");
const helperClient = readFileSync("src/adapters/chatgpt-web/launcher-helper-client.ts", "utf8");
const helperMain = readFileSync("src/adapters/chatgpt-web/browser-helper-main.ts", "utf8");

describe("GitHub-first Web app routing contract", () => {
  test("normal turns attach Native2 then GitHub while compaction remains tool-free", () => {
    expect(adapter).toContain("const turnCapabilities = parsed._compactionRequest");
    expect(adapter).toContain("? { ...configuredCapabilities, localToolsEnabled: false }");
    expect(adapter).toContain(": configuredCapabilities;");
    expect(adapter).not.toContain("chatGptNative2Allowed(parsed)");
    expect(adapter).toContain("useGitHubApp: !parsed._compactionRequest");
    expect(worker).toContain('CHATGPT_GITHUB_CONNECTOR_NAME = "GitHub"');
    expect(worker).toContain("...(localTools ? [this.config.appName] : [])");
    expect(worker).toContain("...(useGitHubApp ? [CHATGPT_GITHUB_CONNECTOR_NAME] : [])");
    const native2First = worker.indexOf("...(localTools ? [this.config.appName] : [])");
    const githubSecond = worker.indexOf("...(useGitHubApp ? [CHATGPT_GITHUB_CONNECTOR_NAME] : [])", native2First);
    expect(native2First).toBeGreaterThan(-1);
    expect(githubSecond).toBeGreaterThan(native2First);
  });

  test("launcher helper preserves the GitHub-app flag", () => {
    expect(helperClient).toContain("turn.useGitHubApp ? { useGitHubApp: true }");
    expect(helperMain).toContain("useGitHubApp?: boolean");
    expect(helperMain).toContain("message.turn.useGitHubApp ? { useGitHubApp: true }");
  });
});
