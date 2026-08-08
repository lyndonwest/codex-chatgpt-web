import { expect, test } from "bun:test";
import type { ProviderAdapter } from "../src/adapters/base";
import { defaultConfig } from "../src/config";
import { SUMMARY_PREFIX, decodeCompactionSummary } from "../src/responses/compaction";
import { compactRequest, responseRequest } from "../src/server";

const model = "chatgpt-web/high";

function forbiddenBrowserFactory(counter: { calls: number }) {
  return (): ProviderAdapter => {
    counter.calls += 1;
    return {
      name: "forbidden-browser-compactor",
      async runTurn() {
        throw new Error("browser adapter must not run for ChatGPT Web compaction");
      },
    };
  };
}

test("v1 compaction is answered locally without opening a browser turn", async () => {
  const counter = { calls: 0 };
  const response = await compactRequest(new Request("http://127.0.0.1:17841/v1/responses/compact", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      input: [
        { type: "message", role: "user", content: [{ type: "input_text", text: "First request" }] },
        { type: "message", role: "assistant", content: [{ type: "output_text", text: "Implementation is halfway complete" }] },
        { type: "message", role: "user", content: [{ type: "input_text", text: "Latest request" }] },
      ],
    }),
  }), defaultConfig("full"), forbiddenBrowserFactory(counter));

  expect(response.status).toBe(200);
  expect(counter.calls).toBe(0);
  const body = await response.json() as { output: Array<{ role: string; content: Array<{ text: string }> }> };
  expect(body.output.slice(0, 2).map(item => item.content[0]!.text)).toEqual(["First request", "Latest request"]);
  const summary = body.output.at(-1)!.content[0]!.text;
  expect(summary.startsWith(`${SUMMARY_PREFIX}\n`)).toBe(true);
  expect(summary).toContain("Codex-only context checkpoint");
  expect(summary).toContain("Implementation is halfway complete");
});

test("v2 compaction returns exactly one local compaction item without browser inference", async () => {
  const counter = { calls: 0 };
  const response = await responseRequest(new Request("http://127.0.0.1:17841/v1/responses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      stream: false,
      tools: [{ type: "function", name: "codex_exec", description: "Run", parameters: { type: "object" } }],
      input: [
        { type: "message", role: "user", content: [{ type: "input_text", text: "Inspect the project" }] },
        { type: "message", role: "assistant", content: [{ type: "output_text", text: "Found the relevant implementation" }] },
        { type: "function_call", call_id: "call_1", name: "codex_exec", arguments: "{\"cmd\":\"true\"}" },
        { type: "function_call_output", call_id: "call_1", output: "{\"exit_code\":0}" },
        { type: "compaction_trigger" },
      ],
    }),
  }), defaultConfig("full"), forbiddenBrowserFactory(counter));

  expect(response.status).toBe(200);
  expect(counter.calls).toBe(0);
  const body = await response.json() as {
    status: string;
    output: Array<{ type: string; encrypted_content?: string }>;
  };
  expect(body.status).toBe("completed");
  expect(body.output).toHaveLength(1);
  expect(body.output[0]!.type).toBe("compaction");
  const summary = decodeCompactionSummary(body.output[0]!.encrypted_content ?? "");
  expect(summary).toContain("Found the relevant implementation");
  expect(summary).toContain("function_call_output");
});

test("streaming v2 compaction emits one compaction item and no assistant message", async () => {
  const counter = { calls: 0 };
  const response = await responseRequest(new Request("http://127.0.0.1:17841/v1/responses", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      model,
      stream: true,
      input: [
        { type: "message", role: "assistant", content: [{ type: "output_text", text: "Keep this recovery state" }] },
        { type: "compaction_trigger" },
      ],
    }),
  }), defaultConfig("full"), forbiddenBrowserFactory(counter));

  expect(response.status).toBe(200);
  expect(counter.calls).toBe(0);
  const sse = await response.text();
  expect(sse).toContain('"type":"compaction"');
  expect(sse).toContain("response.completed");
  expect(sse).not.toContain("response.output_text.delta");
  expect((sse.match(/"type":"compaction"/g) ?? [])).toHaveLength(2);
});

test("rejects an unknown routed compact model instead of treating it as ChatGPT Web", async () => {
  const response = await compactRequest(new Request("http://127.0.0.1:17841/v1/responses/compact", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ model: "chatgpt-web/not-enabled", input: [] }),
  }), defaultConfig("browser-only"));

  expect(response.status).toBe(400);
  const body = await response.json() as { error: { message: string } };
  expect(body.error.message).toContain("model is not enabled");
});

test("rejects Pro-only routed models before compaction handling when the account has no Pro access", async () => {
  for (const [routedModel, label] of [
    ["chatgpt-web/extra-high", "Extra High"],
    ["chatgpt-web/pro", "Pro"],
  ] as const) {
    const response = await responseRequest(new Request("http://127.0.0.1:17841/v1/responses", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ model: routedModel, input: [{ type: "compaction_trigger" }], stream: false }),
    }), defaultConfig("browser-only"));

    expect(response.status).toBe(400);
    const body = await response.json() as { error: { message: string } };
    expect(body.error.message).toContain(`${label} is not available for this account`);
  }
});
