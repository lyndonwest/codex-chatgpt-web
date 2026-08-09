import { afterAll, expect, test } from "bun:test";
import { mkdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { ChatGptBrowserWorker, type BrowserTurn } from "../src/adapters/chatgpt-web/browser-worker";
import {
  continueChatGptWebAcrossNativeCompaction,
  createChatGptWebAdapter,
} from "../src/adapters/chatgpt-web";
import { CHATGPT_WEB_MODEL_ID } from "../src/adapters/chatgpt-web/model";
import {
  ChatGptTextFeed,
  ChatGptTraceFeed,
  chatGptTurnExecutionKey,
  chatGptTurnSessions,
} from "../src/adapters/chatgpt-web/turn-execution";
import { callTurnBroker, TurnBroker, type BrokerToolResult } from "../src/adapters/chatgpt-web/turn-broker";
import { defaultBrokerEndpoint } from "../src/config";
import type { AdapterEvent, CodexParsedRequest, CodexProviderConfig, CodexTool } from "../src/types";

const tempRoot = join(tmpdir(), `cgw-native-compaction-${process.pid}-${Date.now()}`);
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
  const name = `cgw-native-compaction-${process.pid}-${Date.now()}`;
  return process.platform === "win32"
    ? defaultBrokerEndpoint(join(tmpdir(), name), "win32")
    : join(tmpdir(), `${name}.sock`);
}

function request(turnId = "turn_test_123"): CodexParsedRequest {
  const threadId = "thread_native_compaction_123";
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

function setHistoricalSourceTurn(parsed: CodexParsedRequest, turnId: string): void {
  const input = (parsed._rawBody as { input: unknown[] }).input;
  for (const value of input) {
    if (!value || typeof value !== "object" || Array.isArray(value)) continue;
    const item = value as { type?: string; role?: string; internal_chat_message_metadata_passthrough?: { turn_id?: string } };
    if (item.type !== "message" || item.role !== "user" || !item.internal_chat_message_metadata_passthrough) continue;
    item.internal_chat_message_metadata_passthrough.turn_id = turnId;
  }
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

test("native Codex compaction delivers completed tool results and rebinds the same live browser execution", async () => {
  const socketPath = brokerEndpoint();
  const provider: CodexProviderConfig = {
    adapter: "chatgpt-web",
    baseUrl: "browser://native-compaction-continuity-test",
    chatgptWeb: {
      brokerSocketPath: socketPath,
      turnTimeoutMs: 30_000,
      localToolsEnabled: true,
      solAvailable: true,
      proAvailable: true,
    },
  };
  const worker = ChatGptBrowserWorker.forProvider(provider);
  const originalRun = worker.run.bind(worker);
  let browserStarts = 0;

  (worker as unknown as { run: (turn: BrowserTurn) => Promise<string> }).run = async turn => {
    browserStarts += 1;
    if (browserStarts > 1) throw new Error("duplicate browser runtime started across native compaction");
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
  const firstExecutionKey = chatGptTurnExecutionKey(firstRequest);
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
    setHistoricalSourceTurn(compactRequest, "turn_test_123");
    appendToolResult(compactRequest, callStart!.id);

    const continued = await continueChatGptWebAcrossNativeCompaction(compactRequest, provider);
    expect(continued).toEqual({
      activeBrowserSession: true,
      deliveredToolResults: 1,
      browserCompactionRequired: false,
    });
    expect(browserStarts).toBe(1);

    const postCompactRequest = request("turn_after_compaction_789");
    expect(chatGptTurnExecutionKey(postCompactRequest)).toBe(firstExecutionKey);

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

test("a second native compaction on the same live browser execution escalates to browser compaction", async () => {
  const provider: CodexProviderConfig = {
    adapter: "chatgpt-web",
    baseUrl: "browser://native-compaction-second-boundary-test",
    chatgptWeb: {
      localToolsEnabled: true,
      solAvailable: true,
      proAvailable: true,
    },
  };
  const firstRequest = request();
  const firstExecutionKey = chatGptTurnExecutionKey(firstRequest);
  chatGptTurnSessions.getOrCreate(firstExecutionKey, () => ({
    mode: "read-only",
    browser: new Promise<string>(() => {}),
    trace: new ChatGptTraceFeed(),
    text: new ChatGptTextFeed(),
    cancel: () => {},
  }));

  try {
    const firstCompaction = request("turn_compaction_first");
    firstCompaction._compactionRequest = true;
    setHistoricalSourceTurn(firstCompaction, "turn_test_123");
    expect(await continueChatGptWebAcrossNativeCompaction(firstCompaction, provider)).toEqual({
      activeBrowserSession: true,
      deliveredToolResults: 0,
      browserCompactionRequired: false,
    });

    // Consume the one-shot alias exactly as the immediate post-compaction provider round does.
    expect(chatGptTurnExecutionKey(request("turn_after_first_compaction"))).toBe(firstExecutionKey);

    const secondCompaction = request("turn_compaction_second");
    secondCompaction._compactionRequest = true;
    setHistoricalSourceTurn(secondCompaction, "turn_test_123");
    expect(await continueChatGptWebAcrossNativeCompaction(secondCompaction, provider)).toEqual({
      activeBrowserSession: true,
      deliveredToolResults: 0,
      browserCompactionRequired: true,
    });
  } finally {
    chatGptTurnSessions.clear();
  }
});
