from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected exactly one match, found {count}: {old[:140]!r}")
    file.write_text(text.replace(old, new, 1))


replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    '''/**
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
    '''/** Keep compaction browser turns serial within one native Codex thread. */
export function chatGptCompactionQueueKey(parsed: CodexParsedRequest): string {
  const identity = extractChatGptTurnIdentity(parsed);
  const key = identity.threadId ?? identity.turnId;
  if (!key) throw new Error("ChatGPT web compaction requires native Codex thread or turn metadata");
  return key;
}

/**
 * Serialize work by key without memoizing its result. Revised compaction requests therefore wait
 * for the current browser checkpoint to finish, then run with their own complete input revision
 * instead of opening a second tab or replaying a stale checkpoint.
 */
export class ChatGptCompactionQueue {
  private readonly tails = new Map<string, Promise<void>>();

  run<T>(key: string, task: () => Promise<T>): Promise<T> {
    const previous = this.tails.get(key) ?? Promise.resolve();
    const run = previous.then(task, task);
    const tail = run.then(() => undefined, () => undefined);
    this.tails.set(key, tail);
    void tail.finally(() => {
      if (this.tails.get(key) === tail) this.tails.delete(key);
    });
    return run;
  }
}

export const chatGptCompactionQueue = new ChatGptCompactionQueue();
''',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    'import { ChatGptTextFeed, ChatGptTraceFeed, chatGptCompactionExecutionKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey, chatGptTurnSessions, type ChatGptBrowserOutcome, type ChatGptTraceEvent, type ChatGptTurnRuntime, type ChatGptTurnSession } from "./turn-execution";',
    'import { ChatGptTextFeed, ChatGptTraceFeed, chatGptCompactionQueue, chatGptCompactionQueueKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey, chatGptTurnSessions, type ChatGptBrowserOutcome, type ChatGptTraceEvent, type ChatGptTurnRuntime, type ChatGptTurnSession } from "./turn-execution";',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''    if (!mode.localTools) {
      const browser = worker.run({
        traceId,
        modelId: parsed.modelId,
        reasoning: parsed.options.reasoning,
        capabilities: turnCapabilities,
        prepare: async () => ({ ...compileChatGptWebPrompt(parsed, turnCapabilities), release: () => {} }),
        abortSignal: browserAbort.signal,
        onReasoningSummary: (text, continuation) => trace.push({ kind: "reasoning", text, ...(continuation ? { continuation: true } : {}) }),
        onCommentary: (text, continuation) => trace.push({ kind: "commentary", text, ...(continuation ? { continuation: true } : {}) }),
        onTextDelta: delta => text.push(delta),
      });
''',
    '''    if (!mode.localTools) {
      const runBrowser = () => worker.run({
        traceId,
        modelId: parsed.modelId,
        reasoning: parsed.options.reasoning,
        capabilities: turnCapabilities,
        prepare: async () => ({ ...compileChatGptWebPrompt(parsed, turnCapabilities), release: () => {} }),
        abortSignal: browserAbort.signal,
        onReasoningSummary: (text, continuation) => trace.push({ kind: "reasoning", text, ...(continuation ? { continuation: true } : {}) }),
        onCommentary: (text, continuation) => trace.push({ kind: "commentary", text, ...(continuation ? { continuation: true } : {}) }),
        onTextDelta: delta => text.push(delta),
      });
      const browser = parsed._compactionRequest
        ? chatGptCompactionQueue.run(
          `${executionNamespace}:${chatGptCompactionQueueKey(parsed)}`,
          runBrowser,
        )
        : runBrowser();
''',
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''      const executionKey = `${executionNamespace}:${parsed._compactionRequest
        ? chatGptCompactionExecutionKey(parsed)
        : chatGptTurnExecutionKey(parsed)}`;''',
    '''      const executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;''',
)

replace_once(
    "tests/server-compaction.test.ts",
    'import { chatGptCompactionExecutionKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey } from "../src/adapters/chatgpt-web/turn-execution";',
    'import { ChatGptCompactionQueue, chatGptCompactionQueueKey, chatGptCompactionSourceExecutionKey, chatGptTurnExecutionKey } from "../src/adapters/chatgpt-web/turn-execution";',
)

replace_once(
    "tests/server-compaction.test.ts",
    '''      const stableKey = chatGptCompactionExecutionKey(parsed);
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
''',
    '''      const queueKey = chatGptCompactionQueueKey(parsed);
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
      // Distinct checkpoint revisions keep distinct replay identities, while browser execution is
      // serialized by the stable native thread identity.
      expect(chatGptTurnExecutionKey(revised)).not.toBe(chatGptTurnExecutionKey(parsed));
      expect(chatGptCompactionQueueKey(revised)).toBe(queueKey);
''',
)

server_test = Path("tests/server-compaction.test.ts")
text = server_test.read_text()
anchor = 'test("returns exactly one native compaction item for a ChatGPT Web v2 request", async () => {'
if text.count(anchor) != 1:
    raise SystemExit("tests/server-compaction.test.ts: queue-test insertion anchor missing or ambiguous")
queue_test = '''test("serializes revised browser compactions without collapsing their work", async () => {
  const queue = new ChatGptCompactionQueue();
  const order: string[] = [];
  let releaseFirst!: () => void;
  const firstGate = new Promise<void>(resolve => { releaseFirst = resolve; });

  const first = queue.run("thread", async () => {
    order.push("first-start");
    await firstGate;
    order.push("first-end");
    return "first";
  });
  const second = queue.run("thread", async () => {
    order.push("second-start");
    return "second";
  });

  await Promise.resolve();
  await Promise.resolve();
  expect(order).toEqual(["first-start"]);
  releaseFirst();
  expect(await Promise.all([first, second])).toEqual(["first", "second"]);
  expect(order).toEqual(["first-start", "first-end", "second-start"]);
});

'''
server_test.write_text(text.replace(anchor, queue_test + anchor, 1))
