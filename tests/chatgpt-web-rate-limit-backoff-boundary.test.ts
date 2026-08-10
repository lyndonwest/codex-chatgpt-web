import { describe, expect, test } from "bun:test";
import { chatGptRateLimitBackoffMs } from "../src/adapters/chatgpt-web/launcher-helper-client";

describe("ChatGPT Web rate-limit backoff boundaries", () => {
  test("normalizes non-positive streaks to the first cooldown", () => {
    expect(chatGptRateLimitBackoffMs(0)).toBe(15_000);
    expect(chatGptRateLimitBackoffMs(-2)).toBe(15_000);
  });
});
