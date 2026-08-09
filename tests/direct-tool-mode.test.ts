import { describe, expect, test } from "bun:test";
import { CHATGPT_WEB_MODEL_ROUTES } from "../src/chatgpt-web-models";
import { defaultConfig } from "../src/config";
import { exactTool } from "../src/adapters/chatgpt-web/mcp-server";
import type { ChatGptTurnEnvironment } from "../src/adapters/chatgpt-web/environment";
import { buildChatGptWebModel } from "../src/model-catalog";

function nativeTemplate() {
  return {
    slug: "gpt-5.6-sol",
    display_name: "5.6 Sol",
    visibility: "list",
    supported_in_api: true,
    multi_agent_version: "v1",
    tool_mode: "code_mode_only",
    supported_reasoning_levels: [
      { effort: "high", description: "High" },
    ],
  };
}

function environment(tools: ChatGptTurnEnvironment["tools"]): ChatGptTurnEnvironment {
  return {
    cwd: "/workspace",
    roots: ["/workspace"],
    writableRoots: ["/workspace"],
    sandboxPolicy: { type: "workspaceWrite", writableRoots: ["/workspace"], networkAccess: true },
    tools,
  };
}

describe("Full Harness Direct-mode compatibility", () => {
  test("does not inherit code_mode_only onto routed Web models", () => {
    const config = defaultConfig("full");
    const route = CHATGPT_WEB_MODEL_ROUTES.find(candidate => candidate.codexEffort === "high")!;
    const model = buildChatGptWebModel(nativeTemplate(), route, config);

    expect(model.tool_mode).toBeNull();
  });

  test("recognizes ordinary Codex tools in the functions namespace", () => {
    const execCommand = {
      namespace: "functions",
      name: "exec_command",
      description: "run command",
      parameters: { type: "object" },
    };
    const env = environment([execCommand]);

    expect(exactTool(env, "exec_command")).toBe(execCommand);
  });

  test("keeps exact unnamespaced tool lookup working", () => {
    const execGateway = {
      name: "exec",
      description: "native exec gateway",
      parameters: {},
      freeform: true,
    };
    const env = environment([execGateway]);

    expect(exactTool(env, "exec")).toBe(execGateway);
  });

  test("does not treat arbitrary namespaces as native exact tools", () => {
    const env = environment([{
      namespace: "other",
      name: "exec_command",
      description: "not the native command tool",
      parameters: { type: "object" },
    }]);

    expect(exactTool(env, "exec_command")).toBeUndefined();
  });
});
