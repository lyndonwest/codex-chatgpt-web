import { expect, test } from "bun:test";
import { exactTool } from "../src/adapters/chatgpt-web/mcp-server";
import type { ChatGptTurnEnvironment } from "../src/adapters/chatgpt-web/environment";
import type { CodexTool } from "../src/types";

function tool(namespace: string | undefined, name = "exec_command"): CodexTool {
  return {
    ...(namespace ? { namespace } : {}),
    name,
    description: "test command",
    parameters: { type: "object" },
  };
}

function environment(tools: CodexTool[]): ChatGptTurnEnvironment {
  return {
    cwd: "/repo",
    roots: ["/repo"],
    writableRoots: ["/repo"],
    sandboxPolicy: { type: "dangerFullAccess" },
    tools,
  };
}

test("exact native tools accept Codex's functions namespace", () => {
  const plain = tool(undefined);
  const functions = tool("functions");
  const unrelated = tool("mcp__other");

  expect(exactTool(environment([plain]), "exec_command")).toBe(plain);
  expect(exactTool(environment([functions]), "exec_command")).toBe(functions);
  expect(exactTool(environment([unrelated]), "exec_command")).toBeUndefined();
});
