import { expect, test } from "bun:test";
import { CHATGPT_WEB_MODEL_ID } from "../src/adapters/chatgpt-web/model";
import {
  ChatGptTextFeed,
  ChatGptTraceFeed,
  chatGptTurnExecutionKey,
  chatGptTurnSessions,
} from "../src/adapters/chatgpt-web/turn-execution";
import type { CodexParsedRequest, CodexTool } from "../src/types";

const threadId = "thread_native_compaction_refresh_123";
const tools: CodexTool[] = [
  { name: "write_stdin", description: "Continue command", parameters: { type: "object" } },
];

function request(turnId = "turn_test_123"): CodexParsedRequest {
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
    content: JSON.stringify({ output: "post-compaction command complete", exit_code: 0 }),
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

test("the first post-compaction tool result retires the preserved browser alias and starts fresh", () => {
  const firstRequest = request();
  const firstExecutionKey = chatGptTurnExecutionKey(firstRequest);
  let cancelled = false;
  const preserved = chatGptTurnSessions.getOrCreate(firstExecutionKey, () => ({
    mode: "read-only",
    browser: new Promise<string>(() => {}),
    trace: new ChatGptTraceFeed(),
    text: new ChatGptTextFeed(),
    cancel: () => {
      cancelled = true;
    },
  }));

  try {
    // This test owns the post-compaction alias mechanics. Establish the same pending alias that the
    // preservation path creates after it has rescued a real in-flight native-tool handoff.
    expect(chatGptTurnSessions.markNativeCompactionContinuation(threadId, firstExecutionKey)?.session).toBe(preserved);

    const postCompactionTurnId = "turn_after_compaction_789";
    const postCompactionRound = request(postCompactionTurnId);
    expect(chatGptTurnExecutionKey(postCompactionRound)).toBe(firstExecutionKey);

    const callId = "call_after_compaction";
    preserved.setOutstanding([{
      callId,
      wireName: "write_stdin",
      freeform: false,
      arguments: { session_id: 42, chars: "" },
    }]);

    // A replay of the same provider round has no result yet, so the retained browser remains
    // authoritative and its tool request stays replayable.
    expect(chatGptTurnExecutionKey(request(postCompactionTurnId))).toBe(firstExecutionKey);
    expect(cancelled).toBeFalse();

    // Once Codex returns the complete result batch, the canonical compacted history contains the
    // handoff and result. Retire the nearly-full browser before it consumes that result; this round
    // must receive an unaliased execution key and therefore start a fresh Temporary Chat.
    const toolResultRound = request(postCompactionTurnId);
    appendToolResult(toolResultRound, callId);
    const freshExecutionKey = chatGptTurnExecutionKey(toolResultRound);
    expect(freshExecutionKey).not.toBe(firstExecutionKey);
    expect(cancelled).toBeTrue();

    let freshStarted = false;
    const fresh = chatGptTurnSessions.getOrCreate(freshExecutionKey, () => {
      freshStarted = true;
      return {
        mode: "read-only",
        browser: new Promise<string>(() => {}),
        trace: new ChatGptTraceFeed(),
        text: new ChatGptTextFeed(),
        cancel: () => {},
      };
    });
    expect(freshStarted).toBeTrue();
    expect(fresh).not.toBe(preserved);

    // Reconnects for the refreshed round stay on its fresh execution key instead of reviving the
    // retired pre-compaction browser alias.
    expect(chatGptTurnExecutionKey(toolResultRound)).toBe(freshExecutionKey);
  } finally {
    chatGptTurnSessions.clear();
  }
});
