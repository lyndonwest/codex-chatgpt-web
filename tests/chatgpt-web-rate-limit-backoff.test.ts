import { describe, expect, test } from "bun:test";
import { ChatGptWebAdapterError } from "../src/adapters/chatgpt-web/adapter-error";
import {
  CHATGPT_RATE_LIMIT_BACKOFF_BASE_MS,
  CHATGPT_RATE_LIMIT_BACKOFF_MAX_MS,
  chatGptRateLimitBackoffMs,
  isChatGptRateLimitError,
} from "../src/adapters/chatgpt-web/launcher-helper-client";

describe("ChatGPT Web rate-limit backoff", () => {
  test("backs off exponentially with a bounded ceiling", () => {
    expect(chatGptRateLimitBackoffMs(1)).toBe(CHATGPT_RATE_LIMIT_BACKOFF_BASE_MS);
    expect(chatGptRateLimitBackoffMs(2)).toBe(30_000);
    expect(chatGptRateLimitBackoffMs(3)).toBe(CHATGPT_RATE_LIMIT_BACKOFF_MAX_MS);
    expect(chatGptRateLimitBackoffMs(8)).toBe(CHATGPT_RATE_LIMIT_BACKOFF_MAX_MS);
  });

  test("recognizes only the structured ChatGPT account throttle", () => {
    expect(isChatGptRateLimitError(new ChatGptWebAdapterError("rate limited", {
      status: 429,
      errorType: "rate_limit_error",
      code: "rate_limit_exceeded",
      retryable: true,
    }))).toBe(true);
    expect(isChatGptRateLimitError(new ChatGptWebAdapterError("busy", {
      status: 503,
      errorType: "server_error",
      code: "upstream_server_error",
      retryable: true,
    }))).toBe(false);
    expect(isChatGptRateLimitError(new Error("Too many requests"))).toBe(false);
  });
});
