from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:120]!r}")
    file.write_text(text.replace(old, new, 1))


replace_once(
    "src/model-catalog.ts",
    '''    // Keep every routed Web model inside Codex's native code-mode and subagent model registry.
    // Pro's lack of local computer tools is enforced by the adapter runtime; `requiresPro` is only
    // an account-entitlement gate and must not make the model disappear from native orchestration.
    tool_mode: null,''',
    '''    // Keep routed Web models on Codex's ordinary V1 tool surface. Advertising native
    // code_mode here changes how Codex packages tools before this bridge sees them; the browser
    // adapter owns its Full Harness tool exposure instead.
    tool_mode: null,''',
)

replace_once(
    "src/adapters/chatgpt-web/mcp-server.ts",
    'function exactTool(environment: ChatGptTurnEnvironment, name: string): CodexTool | undefined {',
    'export function exactTool(environment: ChatGptTurnEnvironment, name: string): CodexTool | undefined {',
)

Path("tests/mcp-server.test.ts").write_text('''import { expect, test } from "bun:test";
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
''')
