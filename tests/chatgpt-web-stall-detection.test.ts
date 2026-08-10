import { describe, expect, test } from "bun:test";
import {
  browserDiagnosticIncludesScreenshot,
  ChatGptTurnProgressTracker,
} from "../src/adapters/chatgpt-web/browser-worker";

describe("ChatGPT Web stalled response detection", () => {
  test("times out a semantically frozen response", () => {
    const tracker = new ChatGptTurnProgressTracker(1_000);
    const state = { responsePresent: true, currentText: "", traceBlocks: [{ kind: "status", text: "Thinking" }] };
    expect(tracker.update(state, 0)).toBe(false);
    expect(tracker.update(state, 999)).toBe(false);
    expect(tracker.update(state, 1_000)).toBe(true);
  });

  test("answer or visible status progress resets the deadline", () => {
    const tracker = new ChatGptTurnProgressTracker(1_000);
    const thinking = { responsePresent: true, currentText: "", traceBlocks: [{ kind: "status", text: "Thinking" }] };
    const searching = { responsePresent: true, currentText: "", traceBlocks: [{ kind: "status", text: "Searching websites" }] };
    const answering = { responsePresent: true, currentText: "Done", traceBlocks: searching.traceBlocks };
    expect(tracker.update(thinking, 0)).toBe(false);
    expect(tracker.update(searching, 900)).toBe(false);
    expect(tracker.update(searching, 1_899)).toBe(false);
    expect(tracker.update(answering, 1_900)).toBe(false);
    expect(tracker.update(answering, 2_899)).toBe(false);
    expect(tracker.update(answering, 2_900)).toBe(true);
  });

  test("captures the terminal stalled-progress checkpoint", () => {
    expect(browserDiagnosticIncludesScreenshot("response-stalled-progress")).toBe(true);
  });
});
