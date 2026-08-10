from pathlib import Path

path = Path("src/adapters/chatgpt-web/browser-worker.ts")
text = path.read_text()

def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected exactly one match, found {count}: {old[:100]!r}")
    text = text.replace(old, new, 1)

replace_once(
    'export const CHATGPT_COMPLETION_SETTLE_MS = 2_000;\nexport const CHATGPT_TOOL_CONFIRMATION_TIMEOUT_MS = 60_000;\n',
    'export const CHATGPT_COMPLETION_SETTLE_MS = 2_000;\n'
    'export const CHATGPT_TOOL_CONFIRMATION_TIMEOUT_MS = 60_000;\n'
    'export const CHATGPT_STALLED_PROGRESS_TIMEOUT_MS = 5 * 60_000;\n'
    'export const CHATGPT_EFFORT_READY_TIMEOUT_MS = 30_000;\n',
)

replace_once(
    '  effortSelection: 120_000,\n',
    '  effortSelection: 45_000,\n',
)

count = text.count('timeout: 70_000')
if count != 4:
    raise SystemExit(f"expected four 70s effort readiness waits, found {count}")
text = text.replace('timeout: 70_000', 'timeout: CHATGPT_EFFORT_READY_TIMEOUT_MS')

replace_once(
    'export class ChatGptTurnDomHealthTracker {\n',
    '''export interface ChatGptTurnProgressState {\n  responsePresent: boolean;\n  currentText: string;\n  traceBlocks: ReadonlyArray<{ kind: string; text: string }>;\n}\n\n/**\n * Fails only after ChatGPT stops making observable semantic progress. Long turns remain valid as\n * long as answer text or visible reasoning/tool status changes. Animated DOM churn is intentionally\n * excluded so a frozen \"Thinking\" surface cannot keep a turn alive forever.\n */\nexport class ChatGptTurnProgressTracker {\n  private signature?: string;\n  private lastProgressAt?: number;\n\n  constructor(private readonly stalledMs = CHATGPT_STALLED_PROGRESS_TIMEOUT_MS) {}\n\n  update(state: ChatGptTurnProgressState, now = Date.now()): boolean {\n    const signature = JSON.stringify([\n      state.responsePresent,\n      state.currentText,\n      state.traceBlocks.map(block => [block.kind, block.text]),\n    ]);\n    if (signature !== this.signature || this.lastProgressAt === undefined) {\n      this.signature = signature;\n      this.lastProgressAt = now;\n      return false;\n    }\n    return now - this.lastProgressAt >= this.stalledMs;\n  }\n}\n\nexport class ChatGptTurnDomHealthTracker {\n''',
)

replace_once(
    '  return captureAll || checkpoint === "response-stalled-30s" || checkpoint === "turn-failed";\n',
    '  return captureAll\n    || checkpoint === "response-stalled-30s"\n    || checkpoint === "response-stalled-progress"\n    || checkpoint === "turn-failed";\n',
)

replace_once(
    '      const completionTracker = new ChatGptCompletionTracker();\n      const domHealthTracker = new ChatGptTurnDomHealthTracker();\n',
    '      const completionTracker = new ChatGptCompletionTracker();\n      const domHealthTracker = new ChatGptTurnDomHealthTracker();\n      const progressTracker = new ChatGptTurnProgressTracker();\n',
)

replace_once(
    '''        } else {\n          const domError = domHealthTracker.update({\n            responsePresent: false,\n            running,\n            currentText: "",\n            completionActionVisible: false,\n          });\n          if (domError) throw new Error(domError);\n        }\n        await new Promise(resolveSleep => setTimeout(resolveSleep, 250));\n''',
    '''        } else {\n          const domError = domHealthTracker.update({\n            responsePresent: false,\n            running,\n            currentText: "",\n            completionActionVisible: false,\n          });\n          if (domError) throw new Error(domError);\n        }\n        if (progressTracker.update({\n          responsePresent: snapshot.responsePresent,\n          currentText: snapshot.visibleText,\n          traceBlocks: snapshot.traceBlocks,\n        })) {\n          await diagnostics.capture(page, "response-stalled-progress");\n          const diagnostic = await this.stalledTurnDiagnostic(page, responseTurn).catch(error => JSON.stringify({\n            diagnosticError: error instanceof Error ? error.message : String(error),\n          }));\n          console.warn(\n            `[chatgpt-web] response stalled without observable progress for ${CHATGPT_STALLED_PROGRESS_TIMEOUT_MS}ms`\n            + ` trace=${turn.traceId} ui=${diagnostic}`,\n          );\n          throw new ChatGptWebAdapterError(\n            `ChatGPT response made no observable progress for ${CHATGPT_STALLED_PROGRESS_TIMEOUT_MS / 1000} seconds`,\n            { status: 504, errorType: "server_error", code: "chatgpt_response_stalled", retryable: true },\n          );\n        }\n        await new Promise(resolveSleep => setTimeout(resolveSleep, 250));\n''',
)

path.write_text(text)

test_path = Path("tests/chatgpt-web-stall-detection.test.ts")
if test_path.exists():
    raise SystemExit(f"test already exists: {test_path}")
test_path.write_text('''import { describe, expect, test } from "bun:test";\nimport {\n  browserDiagnosticIncludesScreenshot,\n  ChatGptTurnProgressTracker,\n} from "../src/adapters/chatgpt-web/browser-worker";\n\ndescribe("ChatGPT Web stalled response detection", () => {\n  test("times out a semantically frozen response", () => {\n    const tracker = new ChatGptTurnProgressTracker(1_000);\n    const state = { responsePresent: true, currentText: "", traceBlocks: [{ kind: "status", text: "Thinking" }] };\n    expect(tracker.update(state, 0)).toBe(false);\n    expect(tracker.update(state, 999)).toBe(false);\n    expect(tracker.update(state, 1_000)).toBe(true);\n  });\n\n  test("answer or visible status progress resets the deadline", () => {\n    const tracker = new ChatGptTurnProgressTracker(1_000);\n    const thinking = { responsePresent: true, currentText: "", traceBlocks: [{ kind: "status", text: "Thinking" }] };\n    const searching = { responsePresent: true, currentText: "", traceBlocks: [{ kind: "status", text: "Searching websites" }] };\n    const answering = { responsePresent: true, currentText: "Done", traceBlocks: searching.traceBlocks };\n    expect(tracker.update(thinking, 0)).toBe(false);\n    expect(tracker.update(searching, 900)).toBe(false);\n    expect(tracker.update(searching, 1_899)).toBe(false);\n    expect(tracker.update(answering, 1_900)).toBe(false);\n    expect(tracker.update(answering, 2_899)).toBe(false);\n    expect(tracker.update(answering, 2_900)).toBe(true);\n  });\n\n  test("captures the terminal stalled-progress checkpoint", () => {\n    expect(browserDiagnosticIncludesScreenshot("response-stalled-progress")).toBe(true);\n  });\n});\n''')
