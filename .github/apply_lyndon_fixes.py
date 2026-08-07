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
    '    tool_mode: config.mode === "full" ? template.tool_mode : null,',
    '    tool_mode: null,',
)

replace_once(
    "src/adapters/chatgpt-web/mcp-server.ts",
    '  return environment.tools.find(tool => !tool.namespace && tool.name === name);',
    '  return environment.tools.find(tool => (!tool.namespace || tool.namespace === "functions") && tool.name === name);',
)

replace_once(
    "src/chatgpt-web-models.ts",
    '    // Leave ten percent for Codex to submit and receive the compact checkpoint before the hard cap.\n'
    '    autoCompactTokenLimit: Math.floor(contextWindow * 0.9),',
    '    // Browser compaction replays the retained Codex history inside an additional transport\n'
    '    // envelope and must also leave room for ChatGPT product overhead plus the generated summary.\n'
    '    // Ten percent proved insufficient for long Full Harness turns, so compact conservatively\n'
    '    // before the browser request approaches the product\'s hard context limit.\n'
    '    autoCompactTokenLimit: Math.floor(contextWindow * 0.75),',
)

replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    '''export function chatGptCompactionSourceExecutionKey(parsed: CodexParsedRequest): string {
  const identity = extractChatGptTurnIdentity(parsed);
  if (!identity.turnId) throw new Error("ChatGPT web requires native Codex turn_id metadata for browser-session replay");
  const source = extractChatGptCompactionSourceRevision(parsed);
  return executionKey(parsed, {
    threadId: identity.threadId,
    turnId: source.turnId ?? identity.turnId,
    purpose: "response",
    revision: source.content,
  });
}
''',
    '''export function chatGptCompactionSourceExecutionKey(parsed: CodexParsedRequest): string {
  const identity = extractChatGptTurnIdentity(parsed);
  if (!identity.turnId) throw new Error("ChatGPT web requires native Codex turn_id metadata for browser-session replay");
  const source = extractChatGptCompactionSourceRevision(parsed);
  return executionKey(parsed, {
    threadId: identity.threadId,
    turnId: source.turnId ?? identity.turnId,
    purpose: "response",
    revision: source.content,
  });
}

/**
 * Deduplicate compaction for one source browser turn independently of the exact native history
 * revision. Codex can submit a slightly newer checkpoint request while the first compaction is
 * still in flight; keying by the entire compaction input allowed both requests to open browser
 * tabs concurrently. A failed retryable session is still explicitly retired by the adapter, so a
 * later retry can create one fresh browser turn without overlapping the previous attempt.
 */
export function chatGptCompactionExecutionKey(parsed: CodexParsedRequest): string {
  const identity = extractChatGptTurnIdentity(parsed);
  if (!identity.turnId) throw new Error("ChatGPT web requires native Codex turn_id metadata for browser-session replay");
  const source = extractChatGptCompactionSourceRevision(parsed);
  return executionKey(parsed, {
    threadId: identity.threadId,
    turnId: source.turnId ?? identity.turnId,
    purpose: "compaction",
  });
}
''',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    'import { ChatGptTextFeed, ChatGptTraceFeed, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey, chatGptTurnSessions, type ChatGptBrowserOutcome, type ChatGptTraceEvent, type ChatGptTurnRuntime, type ChatGptTurnSession } from "./turn-execution";',
    'import { ChatGptTextFeed, ChatGptTraceFeed, chatGptCompactionExecutionKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey, chatGptTurnSessions, type ChatGptBrowserOutcome, type ChatGptTraceEvent, type ChatGptTurnRuntime, type ChatGptTurnSession } from "./turn-execution";',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '      const executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;',
    '      const executionKey = `${executionNamespace}:${parsed._compactionRequest\n'
    '        ? chatGptCompactionExecutionKey(parsed)\n'
    '        : chatGptTurnExecutionKey(parsed)}`;',
)

replace_once(
    "tests/chatgpt-web-models.test.ts",
    '''        autoCompactTokenLimit: 135_000,
      });
    }
    expect(resolveChatGptWebContextLimits("high")).toEqual({
      contextWindow: 185_000,
      autoCompactTokenLimit: 166_500,
    });
    expect(resolveChatGptWebContextLimits("xhigh")).toEqual({
      contextWindow: 256_000,
      autoCompactTokenLimit: 230_400,
    });
    expect(resolveChatGptWebContextLimits("max")).toEqual({
      contextWindow: 272_000,
      autoCompactTokenLimit: 244_800,
''',
    '''        autoCompactTokenLimit: 112_500,
      });
    }
    expect(resolveChatGptWebContextLimits("high")).toEqual({
      contextWindow: 185_000,
      autoCompactTokenLimit: 138_750,
    });
    expect(resolveChatGptWebContextLimits("xhigh")).toEqual({
      contextWindow: 256_000,
      autoCompactTokenLimit: 192_000,
    });
    expect(resolveChatGptWebContextLimits("max")).toEqual({
      contextWindow: 272_000,
      autoCompactTokenLimit: 204_000,
''',
)

replace_once(
    "tests/model-catalog.test.ts",
    '''        slug: route.slug,
        display_name: route.displayName,
        tool_mode: "code_mode_only",
        default_reasoning_level: route.codexEffort,''',
    '''        slug: route.slug,
        display_name: route.displayName,
        tool_mode: null,
        default_reasoning_level: route.codexEffort,''',
)
replace_once(
    "tests/model-catalog.test.ts",
    '''      { contextWindow: 150_000, autoCompactTokenLimit: 135_000 },
      { contextWindow: 150_000, autoCompactTokenLimit: 135_000 },
      { contextWindow: 185_000, autoCompactTokenLimit: 166_500 },''',
    '''      { contextWindow: 150_000, autoCompactTokenLimit: 112_500 },
      { contextWindow: 150_000, autoCompactTokenLimit: 112_500 },
      { contextWindow: 185_000, autoCompactTokenLimit: 138_750 },''',
)
replace_once(
    "tests/model-catalog.test.ts",
    '    expect(web.every(model => model.tool_mode === "code_mode_only")).toBe(true);',
    '    expect(web.every(model => model.tool_mode === null)).toBe(true);',
)

replace_once(
    "tests/server-compaction.test.ts",
    'import { chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey } from "../src/adapters/chatgpt-web/turn-execution";',
    'import { chatGptCompactionExecutionKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey } from "../src/adapters/chatgpt-web/turn-execution";',
)
replace_once(
    "tests/server-compaction.test.ts",
    '''      expect(() => chatGptTurnExecutionKey(parsed)).not.toThrow();
      expect(() => chatGptCompactionSourceExecutionKey(parsed)).not.toThrow();
      emit({ type: "text_delta", text: summary, phase: "final_answer" });''',
    '''      expect(() => chatGptTurnExecutionKey(parsed)).not.toThrow();
      expect(() => chatGptCompactionSourceExecutionKey(parsed)).not.toThrow();
      const stableKey = chatGptCompactionExecutionKey(parsed);
      const revised = structuredClone(parsed);
      const raw = revised._rawBody as { input: unknown[] };
      raw.input = [
        ...raw.input,
        {
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: "A later transport revision" }],
        },
      ];
      expect(chatGptTurnExecutionKey(revised)).not.toBe(chatGptTurnExecutionKey(parsed));
      expect(chatGptCompactionExecutionKey(revised)).toBe(stableKey);
      emit({ type: "text_delta", text: summary, phase: "final_answer" });''',
)
