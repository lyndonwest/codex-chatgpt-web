import { expect, test } from "bun:test";
import { buildNativeOnlyCompactionSummary } from "../src/responses/compaction";

test("native-only compaction summary keeps recent assistant/tool state bounded", () => {
  const huge = "x".repeat(50_000);
  const summary = buildNativeOnlyCompactionSummary([
    { type: "message", role: "user", content: [{ type: "input_text", text: "User request remains separately retained" }] },
    { type: "message", role: "assistant", content: [{ type: "output_text", text: "Implemented half of the task" }] },
    { type: "function_call", call_id: "call_1", name: "exec_command", arguments: "{\"cmd\":\"test\"}" },
    { type: "function_call_output", call_id: "call_1", output: huge },
    { type: "compaction_trigger" },
  ]);

  expect(summary).toContain("Codex-only context checkpoint");
  expect(summary).toContain("Implemented half of the task");
  expect(summary).toContain("function_call");
  expect(summary).toContain("function_call_output");
  expect(summary).not.toContain("User request remains separately retained");
  expect(summary.length).toBeLessThan(17_000);
});
