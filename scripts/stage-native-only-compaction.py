from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def replace_once(path, old, new):
    p = ROOT / path
    text = p.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"{path}: expected one match, found {text.count(old)} for {old[:80]!r}")
    p.write_text(text.replace(old, new, 1))

def append_once(path, marker, addition):
    p = ROOT / path
    text = p.read_text()
    if marker in text:
        raise SystemExit(f"{path}: marker already present: {marker}")
    p.write_text(text.rstrip() + "\n\n" + addition.strip() + "\n")

replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    '''  private settledBrowserOutcome?: ChatGptBrowserOutcome;
  private tail: Promise<void> = Promise.resolve();
''',
    '''  private settledBrowserOutcome?: ChatGptBrowserOutcome;
  private nativeCompactionResumePending = false;
  private tail: Promise<void> = Promise.resolve();
''',
)

replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    '''  isActive(): boolean {
    return this.settledBrowserOutcome === undefined;
  }

  setOutstanding(requests: BrokerToolRequest[], reasoning: string[] = [], prelude: AdapterEvent[] = []): void {
''',
    '''  isActive(): boolean {
    return this.settledBrowserOutcome === undefined;
  }

  markNativeCompactionBoundary(): void {
    this.nativeCompactionResumePending = true;
    this.touch();
  }

  hasNativeCompactionBoundary(): boolean {
    return this.nativeCompactionResumePending;
  }

  clearNativeCompactionBoundary(): void {
    this.nativeCompactionResumePending = false;
    this.touch();
  }

  setOutstanding(requests: BrokerToolRequest[], reasoning: string[] = [], prelude: AdapterEvent[] = []): void {
''',
)

replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    '''  activeForBrowserSession(browserSessionId: string): { key: string; session: ChatGptTurnSession } | undefined {
    this.prune();
    let active: { key: string; session: ChatGptTurnSession } | undefined;
    for (const [key, session] of this.entries) {
      if (session.browserSessionId !== browserSessionId || !session.isActive()) continue;
      if (active) {
        throw new Error(`ChatGPT browser session ${browserSessionId} has multiple active executions`);
      }
      active = { key, session };
    }
    return active;
  }

  async waitForRetirement(key: string): Promise<void> {
''',
    '''  activeForBrowserSession(browserSessionId: string): { key: string; session: ChatGptTurnSession } | undefined {
    this.prune();
    let active: { key: string; session: ChatGptTurnSession } | undefined;
    for (const [key, session] of this.entries) {
      if (session.browserSessionId !== browserSessionId || !session.isActive()) continue;
      if (active) {
        throw new Error(`ChatGPT browser session ${browserSessionId} has multiple active executions`);
      }
      active = { key, session };
    }
    return active;
  }

  nativeCompactionContinuationForBrowserSession(
    browserSessionId: string,
  ): { key: string; session: ChatGptTurnSession } | undefined {
    this.prune();
    let continuation: { key: string; session: ChatGptTurnSession } | undefined;
    for (const [key, session] of this.entries) {
      if (session.browserSessionId !== browserSessionId || !session.hasNativeCompactionBoundary()) continue;
      if (continuation) {
        throw new Error(`ChatGPT browser session ${browserSessionId} has multiple native-compaction continuations`);
      }
      continuation = { key, session };
    }
    return continuation;
  }

  async waitForRetirement(key: string): Promise<void> {
''',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''export function createChatGptWebAdapter(provider: CodexProviderConfig): ProviderAdapter {
  const worker = ChatGptBrowserWorker.forProvider(provider);
  const broker = TurnBroker.forSocket(brokerSocketPath(provider));
  const timeoutMs = provider.chatgptWeb?.turnTimeoutMs;
  const configuredCapabilities: ChatGptWebCapabilities = {
    localToolsEnabled: provider.chatgptWeb?.localToolsEnabled === true,
    proAvailable: provider.chatgptWeb?.proAvailable === true,
  };
  const executionNamespace = createHash("sha256").update(JSON.stringify({
    baseUrl: provider.baseUrl,
    chatgptWeb: provider.chatgptWeb ?? {},
  })).digest("hex");
  const environmentStore = new ChatGptThreadEnvironmentStore(
''',
    '''function executionNamespaceForProvider(provider: CodexProviderConfig): string {
  return createHash("sha256").update(JSON.stringify({
    baseUrl: provider.baseUrl,
    chatgptWeb: provider.chatgptWeb ?? {},
  })).digest("hex");
}

export function chatGptBrowserSessionId(
  provider: CodexProviderConfig,
  parsed: CodexParsedRequest,
): string | undefined {
  const threadId = extractChatGptTurnIdentity(parsed).threadId;
  if (!threadId) return undefined;
  return createHash("sha256")
    .update(`${executionNamespaceForProvider(provider)}:browser-thread:${threadId}`)
    .digest("hex")
    .slice(0, 24);
}

export async function continueChatGptWebAcrossNativeCompaction(
  parsed: CodexParsedRequest,
  provider: CodexProviderConfig,
): Promise<{ activeBrowserSession: boolean; deliveredToolResults: number }> {
  const browserSessionId = chatGptBrowserSessionId(provider, parsed);
  if (!browserSessionId) return { activeBrowserSession: false, deliveredToolResults: 0 };
  const active = chatGptTurnSessions.activeForBrowserSession(browserSessionId);
  if (!active) return { activeBrowserSession: false, deliveredToolResults: 0 };

  return active.session.runExclusive(async () => {
    active.session.markNativeCompactionBoundary();
    const outstanding = active.session.outstanding();
    if (outstanding.length === 0) {
      return { activeBrowserSession: true, deliveredToolResults: 0 };
    }
    if (active.session.runtime.mode !== "tools") {
      throw new Error("Native Codex compaction found outstanding tools on a read-only ChatGPT Web runtime");
    }
    const results = currentToolResults(parsed, active.session);
    if (results.length !== outstanding.length) {
      throw new Error(
        `Native Codex compaction carried ${results.length} of ${outstanding.length} completed ChatGPT tool results`,
      );
    }
    const broker = TurnBroker.forSocket(brokerSocketPath(provider));
    const turnToken = await active.session.runtime.token;
    for (const message of results) {
      broker.completeTool(turnToken, message.toolCallId, brokerResult(message));
      active.session.markResultDelivered(message.toolCallId);
    }
    console.warn(
      `[chatgpt-web] continued live browser execution across native Codex compaction `
      + `(browser_session=${browserSessionId}, delivered_results=${results.length})`,
    );
    return { activeBrowserSession: true, deliveredToolResults: results.length };
  });
}

export function createChatGptWebAdapter(provider: CodexProviderConfig): ProviderAdapter {
  const worker = ChatGptBrowserWorker.forProvider(provider);
  const broker = TurnBroker.forSocket(brokerSocketPath(provider));
  const timeoutMs = provider.chatgptWeb?.turnTimeoutMs;
  const configuredCapabilities: ChatGptWebCapabilities = {
    localToolsEnabled: provider.chatgptWeb?.localToolsEnabled === true,
    proAvailable: provider.chatgptWeb?.proAvailable === true,
  };
  const executionNamespace = executionNamespaceForProvider(provider);
  const environmentStore = new ChatGptThreadEnvironmentStore(
''',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''  const browserSessionId = (parsed: CodexParsedRequest): string | undefined => {
    const threadId = extractChatGptTurnIdentity(parsed).threadId;
    if (!threadId) return undefined;
    return createHash("sha256")
      .update(`${executionNamespace}:browser-thread:${threadId}`)
      .digest("hex")
      .slice(0, 24);
  };

''',
    "",
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''      if (parsed._opaqueMultiAgentV2Payload) {
        throw new Error(
          "ChatGPT Web subagents currently require a V1-rooted task. "
          + "Start a new task with a ChatGPT Web model before spawning ChatGPT Web Pro. "
          + "Codex MultiAgent V2 currently encrypts cross-backend task payloads.",
        );
      }
      const turnCapabilities = parsed._compactionRequest
''',
    '''      if (parsed._opaqueMultiAgentV2Payload) {
        throw new Error(
          "ChatGPT Web subagents currently require a V1-rooted task. "
          + "Start a new task with a ChatGPT Web model before spawning ChatGPT Web Pro. "
          + "Codex MultiAgent V2 currently encrypts cross-backend task payloads.",
        );
      }
      if (parsed._compactionRequest) {
        throw new Error("ChatGPT Web compaction must be handled by the bridge without opening or retiring a browser turn");
      }
      const turnCapabilities = parsed._compactionRequest
''',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''      if (parsed._compactionRequest) {
        const responseExecutionKey = `${executionNamespace}:${chatGptCompactionSourceExecutionKey(parsed)}`;
        await chatGptTurnSessions.retireAndWait(responseExecutionKey);
      }
      let executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;
      const persistentSessionId = browserSessionId(parsed);
      if (!parsed._compactionRequest && persistentSessionId) {
        const activeBrowserExecution = chatGptTurnSessions.activeForBrowserSession(persistentSessionId);
        if (activeBrowserExecution && activeBrowserExecution.key !== executionKey) {
          const matchingToolResults = currentToolResults(parsed, activeBrowserExecution.session);
          if (activeBrowserExecution.session.outstanding().length > 0 && matchingToolResults.length > 0) {
            console.warn(
              `[chatgpt-web] rebound changed-key tool-result round to active browser execution `
              + `(browser_session=${persistentSessionId}, matching_results=${matchingToolResults.length})`,
            );
            executionKey = activeBrowserExecution.key;
          } else {
            await chatGptTurnSessions.retireAndWait(activeBrowserExecution.key);
          }
        }
      }
''',
    '''      let executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;
      const persistentSessionId = chatGptBrowserSessionId(provider, parsed);
      if (persistentSessionId) {
        const compactContinuation = chatGptTurnSessions.nativeCompactionContinuationForBrowserSession(persistentSessionId);
        if (compactContinuation && compactContinuation.key !== executionKey) {
          console.warn(
            `[chatgpt-web] rebound post-compaction provider round to retained browser execution `
            + `(browser_session=${persistentSessionId})`,
          );
          executionKey = compactContinuation.key;
        } else {
          const activeBrowserExecution = chatGptTurnSessions.activeForBrowserSession(persistentSessionId);
          if (activeBrowserExecution && activeBrowserExecution.key !== executionKey) {
            const matchingToolResults = currentToolResults(parsed, activeBrowserExecution.session);
            if (activeBrowserExecution.session.outstanding().length > 0 && matchingToolResults.length > 0) {
              console.warn(
                `[chatgpt-web] rebound changed-key tool-result round to active browser execution `
                + `(browser_session=${persistentSessionId}, matching_results=${matchingToolResults.length})`,
              );
              executionKey = activeBrowserExecution.key;
            } else {
              await chatGptTurnSessions.retireAndWait(activeBrowserExecution.key);
            }
          }
        }
      }
''',
)

p = ROOT / "src/adapters/chatgpt-web/index.ts"
text = p.read_text()
old = '''            emitBrowserCompletion(settled, estimateChatGptWebUsage(parsed, { answer: settled.answer, reasoning }, turnCapabilities), emit);
            return;
'''
if text.count(old) != 1:
    raise SystemExit("index.ts: settled completion match failed")
text = text.replace(old, '''            session.clearNativeCompactionBoundary();
            emitBrowserCompletion(settled, estimateChatGptWebUsage(parsed, { answer: settled.answer, reasoning }, turnCapabilities), emit);
            return;
''', 1)
old = '''                emitBrowserCompletion(
                  next.outcome,
'''
if text.count(old) != 1:
    raise SystemExit("index.ts: live completion match failed")
text = text.replace(old, '''                session.clearNativeCompactionBoundary();
                emitBrowserCompletion(
                  next.outcome,
''', 1)
p.write_text(text)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''import { ChatGptTextFeed, ChatGptTraceFeed, chatGptCompactionQueue, chatGptCompactionQueueKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey, chatGptTurnSessions, type ChatGptBrowserOutcome, type ChatGptTraceEvent, type ChatGptTurnRuntime, type ChatGptTurnSession } from "./turn-execution";
''',
    '''import { ChatGptTextFeed, ChatGptTraceFeed, chatGptCompactionQueue, chatGptCompactionQueueKey, chatGptTurnExecutionKey, chatGptTurnSessions, type ChatGptBrowserOutcome, type ChatGptTraceEvent, type ChatGptTurnRuntime, type ChatGptTurnSession } from "./turn-execution";
''',
)

append_once(
    "src/responses/compaction.ts",
    "buildNativeOnlyCompactionSummary",
    r'''
const NATIVE_ONLY_RECOVERY_MAX_CHARS = 16_000;
const NATIVE_ONLY_RECOVERY_ITEM_MAX_CHARS = 3_000;

function compactRecoveryValue(value: unknown, maxChars = NATIVE_ONLY_RECOVERY_ITEM_MAX_CHARS): string {
  let text: string;
  if (typeof value === "string") text = value;
  else {
    try {
      text = JSON.stringify(value);
    } catch {
      text = String(value);
    }
  }
  text = text.replace(/data:image\/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=]+/g, "[image attachment]");
  return text.length <= maxChars ? text : `${text.slice(0, maxChars)}…`;
}

function recoveryItemText(value: unknown): string | undefined {
  if (!value || typeof value !== "object" || Array.isArray(value)) return undefined;
  const item = value as Record<string, unknown>;
  const type = typeof item.type === "string" ? item.type : "message";

  if (type === "compaction_trigger") return undefined;
  if (type === "compaction" && typeof item.encrypted_content === "string") {
    const decoded = decodeCompactionSummary(item.encrypted_content);
    return decoded ? `Previous compact checkpoint:\n${compactRecoveryValue(decoded)}` : undefined;
  }
  if (type === "message") {
    if (item.role !== "assistant") return undefined;
    return `Recent assistant state:\n${compactRecoveryValue(item.content)}`;
  }
  if (type === "agent_message") {
    return `Recent agent state:\n${compactRecoveryValue(item.content ?? item)}`;
  }
  if (
    type === "function_call"
    || type === "function_call_output"
    || type === "custom_tool_call"
    || type === "custom_tool_call_output"
    || type === "tool_search_call"
    || type === "tool_search_output"
    || type === "local_shell_call"
  ) {
    return `Recent native tool state (${type}):\n${compactRecoveryValue(item)}`;
  }
  return undefined;
}

export function buildNativeOnlyCompactionSummary(input: unknown): string {
  const header = [
    "Codex-only context checkpoint for a persistent ChatGPT Web execution.",
    "The retained ChatGPT browser conversation continues independently and remains authoritative for in-flight model state.",
    "This native checkpoint exists for Codex bookkeeping and fresh-chat recovery; do not repeat completed work merely because Codex compacted its local history.",
  ].join(" ");

  if (!Array.isArray(input)) return `${header}\n\nNo additional native recovery tail was available.`;

  const newestFirst: string[] = [];
  let remaining = NATIVE_ONLY_RECOVERY_MAX_CHARS;
  for (let index = input.length - 1; index >= 0 && remaining > 0; index -= 1) {
    const text = recoveryItemText(input[index]);
    if (!text) continue;
    const bounded = text.length <= remaining ? text : `${text.slice(0, Math.max(0, remaining - 1))}…`;
    if (!bounded) break;
    newestFirst.push(bounded);
    remaining -= bounded.length;
  }

  if (newestFirst.length === 0) return `${header}\n\nNo additional native recovery tail was available.`;
  return `${header}\n\nRecent native recovery tail:\n\n${newestFirst.reverse().join("\n\n")}`;
}
''',
)

replace_once(
    "src/server.ts",
    '''import { createChatGptWebAdapter } from "./adapters/chatgpt-web";
''',
    '''import { continueChatGptWebAcrossNativeCompaction, createChatGptWebAdapter } from "./adapters/chatgpt-web";
''',
)

replace_once(
    "src/server.ts",
    '''  buildCompactV1Output,
  COMPACT_PROMPT,
  decodeCompactionSummary,
  extractCompactUserMessages,
''',
    '''  buildCompactV1Output,
  buildNativeOnlyCompactionSummary,
  decodeCompactionSummary,
  extractCompactUserMessages,
''',
)

replace_once(
    "src/server.ts",
    '''  const compaction = parsed._compactionRequest === true;
  if (compaction) {
    // History compaction is a dedicated summarization turn. It must never bind the active Codex
    // tool bridge or continue an in-flight MCP round; the returned summary becomes the next turn's
    // replacement history through the Responses compaction contract.
    delete parsed.context.tools;
    delete parsed.options.toolChoice;
    delete parsed.options.parallelToolCalls;
    parsed.context.messages.push({ role: "user", content: COMPACT_PROMPT, timestamp: Date.now() });
  }

  const adapter = adapterFactory(providerConfig(config));
''',
    '''  const compaction = parsed._compactionRequest === true;
  if (compaction) {
    const provider = providerConfig(config);
    let continuation: { activeBrowserSession: boolean; deliveredToolResults: number };
    try {
      continuation = await continueChatGptWebAcrossNativeCompaction(parsed, provider);
    } catch (error) {
      return formatErrorResponse(
        502,
        "upstream_error",
        error instanceof Error ? error.message : String(error),
      );
    }

    const rawBody = parsed._rawBody && typeof parsed._rawBody === "object" && !Array.isArray(parsed._rawBody)
      ? parsed._rawBody as { input?: unknown }
      : {};
    const summary = buildNativeOnlyCompactionSummary(rawBody.input);
    const events: AdapterEvent[] = [
      { type: "text_delta", text: summary, phase: "final_answer" },
      {
        type: "done",
        stopReason: "stop",
        endTurn: true,
        usage: { inputTokens: 0, outputTokens: 0, totalTokens: 0, estimated: true },
      },
    ];
    const responseModel = route.slug;
    console.warn(
      `[chatgpt-web] handled native Codex compaction without browser turn `
      + `(active_browser=${continuation.activeBrowserSession}, delivered_results=${continuation.deliveredToolResults}, summary_chars=${summary.length})`,
    );

    if (parsed.stream) {
      const queue = new AsyncEventQueue<AdapterEvent>();
      for (const event of events) queue.push(event);
      queue.close();
      const stream = bridgeToResponsesSSE(
        queue,
        responseModel,
        undefined,
        undefined,
        undefined,
        undefined,
        2_000,
        { hideThinkingSummary: parsed.options.hideThinkingSummary, compaction: true },
      );
      return new Response(stream, {
        headers: {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          "Connection": "keep-alive",
          "X-Accel-Buffering": "no",
        },
      });
    }

    return Response.json(buildResponseJSON(events, responseModel, {
      hideThinkingSummary: parsed.options.hideThinkingSummary,
      compaction: true,
    }));
  }

  const adapter = adapterFactory(providerConfig(config));
''',
)

server_test = r'''import { expect, test } from "bun:test";
import type { ProviderAdapter } from "../src/adapters/base";
import { defaultConfig } from "../src/config";
import { SUMMARY_PREFIX, decodeCompactionSummary } from "../src/responses/compaction";
import { compactRequest, responseRequest } from "../src/server";

const model = "chatgpt-web/high";

function forbiddenBrowserFactory(counter: { calls: number }) {
  return (): ProviderAdapter => {
    counter.calls += 1;
    return {
      name: "forbidden-browser-compactor",
      async runTurn() {
        throw new Error("browser adapter must not run for ChatGPT Web compaction");
      },
    };
  };
}

test("v1 compaction is answered locally without opening a browser turn", async () => {
  const counter = { calls: 0 };
  const response = await compactRequest(new Request("http://127.0.0.1:17841/v1/responses/compact", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      input: [
        { type: "message", role: "user", content: [{ type: "input_text", text: "First request" }] },
        { type: "message", role: "assistant", content: [{ type: "output_text", text: "Implementation is halfway complete" }] },
        { type: "message", role: "user", content: [{ type: "input_text", text: "Latest request" }] },
      ],
    }),
  }), defaultConfig("full"), forbiddenBrowserFactory(counter));

  expect(response.status).toBe(200);
  expect(counter.calls).toBe(0);
  const body = await response.json() as { output: Array<{ role: string; content: Array<{ text: string }> }> };
  expect(body.output.slice(0, 2).map(item => item.content[0]!.text)).toEqual(["First request", "Latest request"]);
  const summary = body.output.at(-1)!.content[0]!.text;
  expect(summary.startsWith(`${SUMMARY_PREFIX}\n`)).toBe(true);
  expect(summary).toContain("Codex-only context checkpoint");
  expect(summary).toContain("Implementation is halfway complete");
});

test("v2 compaction returns exactly one local compaction item without browser inference", async () => {
  const counter = { calls: 0 };
  const response = await responseRequest(new Request("http://127.0.0.1:17841/v1/responses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      stream: false,
      tools: [{ type: "function", name: "codex_exec", description: "Run", parameters: { type: "object" } }],
      input: [
        { type: "message", role: "user", content: [{ type: "input_text", text: "Inspect the project" }] },
        { type: "message", role: "assistant", content: [{ type: "output_text", text: "Found the relevant implementation" }] },
        { type: "function_call", call_id: "call_1", name: "codex_exec", arguments: "{\"cmd\":\"true\"}" },
        { type: "function_call_output", call_id: "call_1", output: "{\"exit_code\":0}" },
        { type: "compaction_trigger" },
      ],
    }),
  }), defaultConfig("full"), forbiddenBrowserFactory(counter));

  expect(response.status).toBe(200);
  expect(counter.calls).toBe(0);
  const body = await response.json() as {
    status: string;
    output: Array<{ type: string; encrypted_content?: string }>;
  };
  expect(body.status).toBe("completed");
  expect(body.output).toHaveLength(1);
  expect(body.output[0]!.type).toBe("compaction");
  const summary = decodeCompactionSummary(body.output[0]!.encrypted_content ?? "");
  expect(summary).toContain("Found the relevant implementation");
  expect(summary).toContain("function_call_output");
});

test("streaming v2 compaction emits one compaction item and no assistant message", async () => {
  const counter = { calls: 0 };
  const response = await responseRequest(new Request("http://127.0.0.1:17841/v1/responses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      stream: true,
      input: [
        { type: "message", role: "assistant", content: [{ type: "output_text", text: "Keep this recovery state" }] },
        { type: "compaction_trigger" },
      ],
    }),
  }), defaultConfig("full"), forbiddenBrowserFactory(counter));

  expect(response.status).toBe(200);
  expect(counter.calls).toBe(0);
  const sse = await response.text();
  expect(sse).toContain('"type":"compaction"');
  expect(sse).toContain("response.completed");
  expect(sse).not.toContain("response.output_text.delta");
  expect(sse.match(/\\"type\\":\\"compaction\\"/g)).toHaveLength(2);
});

test("rejects an unknown routed compact model instead of treating it as ChatGPT Web", async () => {
  const response = await compactRequest(new Request("http://127.0.0.1:17841/v1/responses/compact", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: "chatgpt-web/not-enabled", input: [] }),
  }), defaultConfig("browser-only"));

  expect(response.status).toBe(400);
  const body = await response.json() as { error: { message: string } };
  expect(body.error.message).toContain("model is not enabled");
});

test("rejects Pro-only routed models before compaction handling when the account has no Pro access", async () => {
  for (const [routedModel, label] of [
    ["chatgpt-web/extra-high", "Extra High"],
    ["chatgpt-web/pro", "Pro"],
  ] as const) {
    const response = await responseRequest(new Request("http://127.0.0.1:17841/v1/responses", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: routedModel, input: [{ type: "compaction_trigger" }], stream: false }),
    }), defaultConfig("browser-only"));

    expect(response.status).toBe(400);
    const body = await response.json() as { error: { message: string } };
    expect(body.error.message).toContain(`${label} is not available for this account`);
  }
});
'''
(ROOT / "tests/server-compaction.test.ts").write_text(server_test)

rebind_test = r'''import { afterAll, expect, test } from "bun:test";
import { mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ChatGptBrowserWorker, type BrowserTurn } from "../src/adapters/chatgpt-web/browser-worker";
import {
  continueChatGptWebAcrossNativeCompaction,
  createChatGptWebAdapter,
} from "../src/adapters/chatgpt-web/index";
import { CHATGPT_WEB_MODEL_ID } from "../src/adapters/chatgpt-web/model";
import { chatGptTurnExecutionKey, chatGptTurnSessions } from "../src/adapters/chatgpt-web/turn-execution";
import { callTurnBroker, TurnBroker, type BrokerToolResult } from "../src/adapters/chatgpt-web/turn-broker";
import { defaultBrokerEndpoint } from "../src/config";
import type { AdapterEvent, CodexParsedRequest, CodexProviderConfig, CodexTool } from "../src/types";

const tempRoot = join(tmpdir(), `cgw-persistent-rebind-${process.pid}-${Date.now()}`);
mkdirSync(tempRoot, { recursive: true });
afterAll(() => rmSync(tempRoot, { recursive: true, force: true }));

const tools: CodexTool[] = [
  { name: "write_stdin", description: "Continue command", parameters: { type: "object" } },
];

const environmentXml = `<environment_context>
  <cwd>${tempRoot}</cwd>
  <filesystem><workspace_roots><root>${tempRoot}</root></workspace_roots><permission_profile type="disabled"><file_system type="unrestricted" /></permission_profile></filesystem>
</environment_context>`;

function brokerEndpoint(): string {
  const name = `cgw-persistent-rebind-${process.pid}-${Date.now()}`;
  return process.platform === "win32"
    ? defaultBrokerEndpoint(join(tmpdir(), name), "win32")
    : join(tmpdir(), `${name}.sock`);
}

function request(turnId = "turn_test_123"): CodexParsedRequest {
  const threadId = "thread_persistent_rebind_123";
  return {
    modelId: CHATGPT_WEB_MODEL_ID,
    stream: true,
    context: {
      tools,
      messages: [{ role: "user", content: "Continue the running command", timestamp: 1 }],
    },
    options: { reasoning: "high" },
    _rawBody: {
      prompt_cache_key: threadId,
      client_metadata: {
        "x-codex-turn-metadata": JSON.stringify({ thread_id: threadId, turn_id: turnId }),
      },
      input: [
        {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: environmentXml }],
          internal_chat_message_metadata_passthrough: { turn_id: turnId },
        },
        {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: "Continue the running command" }],
          internal_chat_message_metadata_passthrough: { turn_id: turnId },
        },
      ],
    },
  };
}

function appendToolResult(parsed: CodexParsedRequest, callId: string): void {
  const toolCall = {
    role: "assistant" as const,
    content: [{
      type: "toolCall" as const,
      id: callId,
      name: "write_stdin",
      arguments: { session_id: 42, chars: "" },
    }],
    timestamp: 2,
  };
  const result = {
    role: "toolResult" as const,
    toolCallId: callId,
    toolName: "write_stdin",
    content: JSON.stringify({ output: "command complete", exit_code: 0 }),
    isError: false,
    timestamp: 3,
  };
  parsed.context.messages.push(toolCall, result);
  const raw = parsed._rawBody as { input: unknown[] };
  raw.input.push(
    {
      type: "function_call",
      call_id: callId,
      name: "write_stdin",
      arguments: JSON.stringify({ session_id: 42, chars: "" }),
    },
    {
      type: "function_call_output",
      call_id: callId,
      output: result.content,
    },
  );
}

test("native Codex compaction delivers completed tool results and leaves the Web execution running", async () => {
  const socketPath = brokerEndpoint();
  const provider: CodexProviderConfig = {
    adapter: "chatgpt-web",
    baseUrl: "browser://persistent-tool-result-rebind-test",
    chatgptWeb: {
      brokerSocketPath: socketPath,
      turnTimeoutMs: 30_000,
      localToolsEnabled: true,
      proAvailable: true,
    },
  };
  const worker = ChatGptBrowserWorker.forProvider(provider);
  const originalRun = worker.run.bind(worker);
  let browserStarts = 0;

  (worker as unknown as { run: (turn: BrowserTurn) => Promise<string> }).run = async turn => {
    browserStarts += 1;
    if (browserStarts > 1) throw new Error("duplicate persistent browser runtime started");
    const prepared = await turn.prepare();
    try {
      const token = prepared.text.match(/turn_token (turn_[A-Za-z0-9_-]+)/)?.[1];
      if (!token) throw new Error("turn token missing from compiled prompt");
      const claimed = await callTurnBroker<{ bindingId: string }>(socketPath, { method: "claim", token });
      const nativeResult = await callTurnBroker<BrokerToolResult>(socketPath, {
        method: "invoke",
        bindingId: claimed.bindingId,
        wireName: "write_stdin",
        freeform: false,
        arguments: { session_id: 42, chars: "" },
      }, 30_000);
      const output = (nativeResult.structuredContent as { output: string }).output;
      const answer = `Tool result resumed: ${output}`;
      turn.onTextDelta(answer);
      return answer;
    } finally {
      prepared.release();
    }
  };

  const adapter = createChatGptWebAdapter(provider);
  const firstRequest = request();
  const firstEvents: AdapterEvent[] = [];
  try {
    await adapter.runTurn!(firstRequest, { headers: new Headers() }, event => firstEvents.push(event));
    expect(browserStarts).toBe(1);
    const callStart = firstEvents.find(
      (event): event is Extract<AdapterEvent, { type: "tool_call_start" }> => event.type === "tool_call_start",
    );
    expect(callStart?.name).toBe("write_stdin");
    expect(firstEvents.at(-1)).toMatchObject({ type: "done", stopReason: "tool_use", endTurn: false });

    const compactRequest = request("turn_compaction_456");
    compactRequest._compactionRequest = true;
    appendToolResult(compactRequest, callStart!.id);

    const continued = await continueChatGptWebAcrossNativeCompaction(compactRequest, provider);
    expect(continued).toEqual({ activeBrowserSession: true, deliveredToolResults: 1 });
    expect(browserStarts).toBe(1);

    const postCompactRequest = request("turn_after_compaction_789");
    expect(chatGptTurnExecutionKey(postCompactRequest)).not.toBe(chatGptTurnExecutionKey(firstRequest));

    const resultEvents: AdapterEvent[] = [];
    await adapter.runTurn!(postCompactRequest, { headers: new Headers() }, event => resultEvents.push(event));

    expect(browserStarts).toBe(1);
    expect(resultEvents.filter(
      (event): event is Extract<AdapterEvent, { type: "text_delta" }> => event.type === "text_delta",
    ).map(event => event.text).join("")).toBe("Tool result resumed: command complete");
    expect(resultEvents.at(-1)).toMatchObject({ type: "done", stopReason: "stop", endTurn: true });
  } finally {
    chatGptTurnSessions.clear();
    (worker as unknown as { run: (turn: BrowserTurn) => Promise<string> }).run = originalRun;
    await TurnBroker.forSocket(socketPath).close();
  }
});
'''
(ROOT / "tests/persistent-tool-result-rebind.test.ts").write_text(rebind_test)

summary_test = r'''import { expect, test } from "bun:test";
import { buildNativeOnlyCompactionSummary } from "../src/responses/compaction";

test("native-only compaction summary keeps recent assistant/tool state bounded", () => {
  const huge = "x".repeat(50_000);
  const summary = buildNativeOnlyCompactionSummary([
    { type: "message", role: "user", content: [{ type: "input_text", text: "User request remains separately retained" }] },
    { type: "message", role: "assistant", content: [{ type: "output_text", text: "Implemented half of the task" }] },
    { type: "function_call", call_id: "call_1", name: "exec_command", arguments: "{\"cmd\":\"test\"}" },
    { type: "function_call_output", call_id: "call_1", output: huge },
    { type: "compaction_trigger" },
  ]);

  expect(summary).toContain("Codex-only context checkpoint");
  expect(summary).toContain("Implemented half of the task");
  expect(summary).toContain("function_call");
  expect(summary).toContain("function_call_output");
  expect(summary).not.toContain("User request remains separately retained");
  expect(summary.length).toBeLessThan(17_000);
});
'''
(ROOT / "tests/native-compaction-summary.test.ts").write_text(summary_test)

server = (ROOT / "src/server.ts").read_text()
if 'parsed.context.messages.push({ role: "user", content: COMPACT_PROMPT' in server:
    raise SystemExit("server still appends browser compaction prompt")

print("native-only compaction patch applied")
