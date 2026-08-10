#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

index_base = ROOT / "src/adapters/chatgpt-web/index-base.ts"
index_path = ROOT / "src/adapters/chatgpt-web/index.ts"
index_text = index_base.read_text(encoding="utf-8")
trace_anchor = '      const traceId = createHash("sha256").update(executionKey).digest("hex").slice(0, 12);\n'
trace_block = trace_anchor + '''      const correlationIdentity = extractChatGptTurnIdentity(parsed);
      console.info(
        `[chatgpt-web] trace correlation trace=${traceId}`
        + ` thread=${correlationIdentity.threadId ?? "none"}`
        + ` turn=${correlationIdentity.turnId ?? "none"}`
        + ` previous_response_id=${parsed.previousResponseId ?? "none"}`
        + ` compaction=${parsed._compactionRequest ? 1 : 0}`,
      );
'''
if index_text.count(trace_anchor) != 1:
    raise SystemExit(f"index trace anchor count={index_text.count(trace_anchor)}")
index_path.write_text(index_text.replace(trace_anchor, trace_block, 1), encoding="utf-8")
index_base.unlink()

helper_base = ROOT / "src/adapters/chatgpt-web/launcher-helper-client-base.ts"
helper_path = ROOT / "src/adapters/chatgpt-web/launcher-helper-client.ts"
helper_text = helper_base.read_text(encoding="utf-8")

import_anchor = '''import {
  parseChatGptLunaCheckpoint,
  type ChatGptLunaCheckpoint,
} from "./rolling-checkpoint";
'''
helper_functions = import_anchor + '''
export const CHATGPT_RATE_LIMIT_BACKOFF_BASE_MS = 15_000;
export const CHATGPT_RATE_LIMIT_BACKOFF_MAX_MS = 60_000;

export function chatGptRateLimitBackoffMs(streak: number): number {
  const normalized = Math.max(1, Math.floor(streak));
  return Math.min(
    CHATGPT_RATE_LIMIT_BACKOFF_BASE_MS * (2 ** (normalized - 1)),
    CHATGPT_RATE_LIMIT_BACKOFF_MAX_MS,
  );
}

export function isChatGptRateLimitError(error: unknown): error is ChatGptWebAdapterError {
  return error instanceof ChatGptWebAdapterError
    && error.status === 429
    && error.code === "rate_limit_exceeded";
}

function rateLimitAbortError(): DOMException {
  return new DOMException("ChatGPT web turn aborted", "AbortError");
}

async function abortableRateLimitDelay(milliseconds: number, signal?: AbortSignal): Promise<void> {
  if (milliseconds <= 0) return;
  if (signal?.aborted) throw rateLimitAbortError();
  await new Promise<void>((resolveDelay, rejectDelay) => {
    let settled = false;
    let timer: ReturnType<typeof setTimeout>;
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      if (error) rejectDelay(error);
      else resolveDelay();
    };
    const onAbort = () => finish(rateLimitAbortError());
    timer = setTimeout(() => finish(), milliseconds);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}
'''
if helper_text.count(import_anchor) != 1:
    raise SystemExit(f"helper import anchor count={helper_text.count(import_anchor)}")
helper_text = helper_text.replace(import_anchor, helper_functions, 1)

fields_anchor = '''  private readonly pending = new Map<string, PendingTurn>();

  constructor(private readonly config: ResolvedBrowserConfig) {}
'''
fields_block = '''  private readonly pending = new Map<string, PendingTurn>();
  private rateLimitUntil = 0;
  private rateLimitStreak = 0;
  private rateLimitGeneration = 0;

  constructor(private readonly config: ResolvedBrowserConfig) {}
'''
if helper_text.count(fields_anchor) != 1:
    raise SystemExit(f"helper fields anchor count={helper_text.count(fields_anchor)}")
helper_text = helper_text.replace(fields_anchor, fields_block, 1)

run_anchor = '''  async run(turn: BrowserTurn): Promise<string> {
    if (turn.abortSignal?.aborted) throw new DOMException("ChatGPT web turn aborted", "AbortError");
    const prepared = await turn.prepare();
    try {
'''
run_block = '''  async run(turn: BrowserTurn): Promise<string> {
    if (turn.abortSignal?.aborted) throw new DOMException("ChatGPT web turn aborted", "AbortError");
    await this.waitForRateLimitCooldown(turn);
    const generationAtStart = this.rateLimitGeneration;
    const prepared = await turn.prepare();
    try {
'''
if helper_text.count(run_anchor) != 1:
    raise SystemExit(f"helper run anchor count={helper_text.count(run_anchor)}")
helper_text = helper_text.replace(run_anchor, run_block, 1)

promise_anchor = '      return await new Promise<string>((resolveResult, rejectResult) => {\n'
if helper_text.count(promise_anchor) != 1:
    raise SystemExit(f"helper promise anchor count={helper_text.count(promise_anchor)}")
helper_text = helper_text.replace(
    promise_anchor,
    '      const result = await new Promise<string>((resolveResult, rejectResult) => {\n',
    1,
)

finish_anchor = '''        }).catch(error => this.finishWithError(turn.traceId, error instanceof Error ? error : new Error(String(error))));
      });
    } finally {
      prepared.release();
    }
  }

  async close(): Promise<void> {
'''
finish_block = '''        }).catch(error => this.finishWithError(turn.traceId, error instanceof Error ? error : new Error(String(error))));
      });
      if (this.rateLimitGeneration === generationAtStart && this.rateLimitStreak > 0) {
        console.info(`[chatgpt-web] rate-limit backoff cleared after successful browser turn trace=${turn.traceId}`);
        this.rateLimitStreak = 0;
        this.rateLimitUntil = 0;
      }
      return result;
    } catch (error) {
      if (isChatGptRateLimitError(error)) this.recordRateLimit(turn.traceId);
      throw error;
    } finally {
      prepared.release();
    }
  }

  private async waitForRateLimitCooldown(turn: BrowserTurn): Promise<void> {
    for (;;) {
      const remainingMs = this.rateLimitUntil - Date.now();
      if (remainingMs <= 0) return;
      console.warn(
        `[chatgpt-web] rate-limit backoff waiting trace=${turn.traceId}`
        + ` delayMs=${remainingMs} streak=${this.rateLimitStreak}`,
      );
      await abortableRateLimitDelay(remainingMs, turn.abortSignal);
    }
  }

  private recordRateLimit(traceId: string): void {
    this.rateLimitGeneration += 1;
    this.rateLimitStreak += 1;
    const delayMs = chatGptRateLimitBackoffMs(this.rateLimitStreak);
    this.rateLimitUntil = Math.max(this.rateLimitUntil, Date.now() + delayMs);
    console.warn(
      `[chatgpt-web] rate-limit backoff armed trace=${traceId}`
      + ` delayMs=${delayMs} streak=${this.rateLimitStreak}`,
    );
  }

  async close(): Promise<void> {
'''
if helper_text.count(finish_anchor) != 1:
    raise SystemExit(f"helper finish anchor count={helper_text.count(finish_anchor)}")
helper_path.write_text(helper_text.replace(finish_anchor, finish_block, 1), encoding="utf-8")
helper_base.unlink()
