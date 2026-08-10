import { describe, expect, test } from "bun:test";
import { createChatGptWebAdapter } from "../src/adapters/chatgpt-web";

describe("ChatGPT Web adapter observability wrapper", () => {
  test("preserves the public adapter factory export", () => {
    expect(typeof createChatGptWebAdapter).toBe("function");
  });
});
