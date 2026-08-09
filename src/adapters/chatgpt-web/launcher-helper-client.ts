import { ChatGptWebAdapterError } from "./adapter-error";
import type { BrowserTurn } from "./browser-worker";
import { LauncherBrowserHelperClient as BaseLauncherBrowserHelperClient } from "./launcher-helper-client-base";

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

function abortError(): DOMException {
  return new DOMException("ChatGPT web turn aborted", "AbortError");
}

async function abortableDelay(milliseconds: number, signal?: AbortSignal): Promise<void> {
  if (milliseconds <= 0) return;
  if (signal?.aborted) throw abortError();
  await new Promise<void>((resolveDelay, rejectDelay) => {
    let settled = false;
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      signal?.removeEventListener("abort", onAbort);
      if (error) rejectDelay(error);
      else resolveDelay();
    };
    const onAbort = () => finish(abortError());
    const timer = setTimeout(() => finish(), milliseconds);
    signal?.addEventListener("abort", onAbort, { once: true });
  });
}

/**
 * Persist ChatGPT account-level 429 cooldown across the fresh browser surfaces that Codex creates
 * for retries. Codex still owns retry count/policy; this only prevents a retryable upstream 429
 * from turning into a 3-6 second request loop against the same account.
 */
export class LauncherBrowserHelperClient extends BaseLauncherBrowserHelperClient {
  private rateLimitUntil = 0;
  private rateLimitStreak = 0;
  private rateLimitGeneration = 0;

  override async run(turn: BrowserTurn): Promise<string> {
    await this.waitForRateLimitCooldown(turn);
    const generationAtStart = this.rateLimitGeneration;
    try {
      const result = await super.run(turn);
      if (this.rateLimitGeneration === generationAtStart && this.rateLimitStreak > 0) {
        console.info(
          `[chatgpt-web] rate-limit backoff cleared after successful browser turn trace=${turn.traceId}`,
        );
        this.rateLimitStreak = 0;
        this.rateLimitUntil = 0;
      }
      return result;
    } catch (error) {
      if (isChatGptRateLimitError(error)) this.recordRateLimit(turn.traceId);
      throw error;
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
      await abortableDelay(remainingMs, turn.abortSignal);
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
}
