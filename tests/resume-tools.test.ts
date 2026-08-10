import { afterEach, expect, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { ChatGptThreadEnvironmentStore } from "../src/adapters/chatgpt-web/thread-environment";
import type { CodexParsedRequest, CodexTool } from "../src/types";

const root = resolve(process.cwd());
const temporaryRoots: string[] = [];
const environmentXml = `<environment_context>
  <cwd>${root}</cwd>
  <filesystem><workspace_roots><root>${root}</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
</environment_context>`;
const nativeTools: CodexTool[] = [
  { name: "exec", description: "Run nested native tools", parameters: {}, freeform: true },
  { name: "exec_command", description: "Run a command", parameters: { type: "object" } },
  { name: "apply_patch", description: "Apply a patch", parameters: {}, freeform: true },
];

afterEach(() => {
  for (const path of temporaryRoots.splice(0)) rmSync(path, { recursive: true, force: true });
});

function initialRequest(): CodexParsedRequest {
  return {
    modelId: "gpt-5.6-sol",
    stream: true,
    context: {
      tools: structuredClone(nativeTools),
      messages: [{ role: "user", content: "Inspect the workspace", timestamp: 1 }],
    },
    options: { reasoning: "high" },
    _rawBody: {
      tools: [{ type: "function", name: "exec_command" }],
      client_metadata: {
        "x-codex-turn-metadata": JSON.stringify({
          thread_id: "thread_resume_tools",
          turn_id: "turn_initial",
          sandbox: "none",
          workspaces: { [root]: { has_changes: false } },
        }),
      },
      input: [
        {
          type: "message",
          id: "msg_environment",
          role: "user",
          content: [{ type: "input_text", text: environmentXml }],
        },
        {
          type: "message",
          id: "msg_initial",
          role: "user",
          content: [{ type: "input_text", text: "Inspect the workspace" }],
        },
      ],
    },
  };
}

function resumedRequest(options: { tools?: CodexTool[]; explicitWireTools?: unknown[]; additionalWireTools?: unknown[] } = {}): CodexParsedRequest {
  return {
    modelId: "gpt-5.6-sol",
    stream: true,
    context: {
      ...(options.tools ? { tools: structuredClone(options.tools) } : {}),
      messages: [{ role: "user", content: "Continue after handoff", timestamp: 2 }],
    },
    options: { reasoning: "high" },
    _rawBody: {
      ...(options.explicitWireTools ? { tools: options.explicitWireTools } : {}),
      client_metadata: {
        "x-codex-turn-metadata": JSON.stringify({
          thread_id: "thread_resume_tools",
          turn_id: "turn_resumed",
        }),
      },
      input: [
        ...(options.additionalWireTools ? [{
          type: "additional_tools",
          role: "user",
          tools: options.additionalWireTools,
        }] : []),
        {
          type: "message",
          id: "msg_resumed",
          role: "user",
          content: [{ type: "input_text", text: "Continue after handoff" }],
        },
      ],
    },
  };
}

function statePath(): string {
  const stateRoot = mkdtempSync(join(tmpdir(), "codex-chatgpt-resume-tools-"));
  temporaryRoots.push(stateRoot);
  return join(stateRoot, "thread-environments.json");
}

test("restores persisted native tools when a resumed Codex request omits its tool registry", () => {
  const path = statePath();
  new ChatGptThreadEnvironmentStore(path).resolve(initialRequest());

  const resumed = new ChatGptThreadEnvironmentStore(path).resolve(resumedRequest());
  expect(resumed.tools).toEqual(nativeTools);
});

test("an explicit empty tool registry revokes persisted native tools", () => {
  const path = statePath();
  new ChatGptThreadEnvironmentStore(path).resolve(initialRequest());

  const cleared = new ChatGptThreadEnvironmentStore(path).resolve(resumedRequest({ explicitWireTools: [] }));
  expect(cleared.tools).toEqual([]);

  const later = new ChatGptThreadEnvironmentStore(path).resolve(resumedRequest());
  expect(later.tools).toEqual([]);
});

test("deferred tool-search additions merge with an omitted persisted base registry", () => {
  const path = statePath();
  new ChatGptThreadEnvironmentStore(path).resolve(initialRequest());
  const deferred: CodexTool = {
    name: "agent_wait",
    description: "Wait for a delegated agent",
    parameters: { type: "object" },
  };

  const resumed = new ChatGptThreadEnvironmentStore(path).resolve(resumedRequest({
    tools: [deferred],
    additionalWireTools: [{
      type: "function",
      name: "agent_wait",
      description: "Wait for a delegated agent",
      parameters: { type: "object" },
    }],
  }));
  expect(resumed.tools.map(tool => tool.name)).toEqual(["exec", "exec_command", "apply_patch", "agent_wait"]);
});
