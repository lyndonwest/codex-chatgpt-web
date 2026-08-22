import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const worker = readFileSync(new URL("../src/adapters/chatgpt-web/browser-worker.ts", import.meta.url), "utf8");

test("Full-mode turns add GitHub after the upstream connector without changing tool-free turns", () => {
  expect(worker).toContain('CHATGPT_GITHUB_CONNECTOR_NAME = "GitHub"');
  expect(worker).toContain("connectorName = this.config.appName");
  expect(worker).toContain("preserveExisting = false");
  expect(worker).toContain("if (!localTools) {");
  expect(worker).toContain("this.connectorIsSelected(selectedComposer, this.config.appName)");
  expect(worker).toContain("this.connectorIsSelected(selectedComposer, CHATGPT_GITHUB_CONNECTOR_NAME)");
  const attach = worker.indexOf("private async attachPrompt(");
  const native2 = worker.indexOf("this.config.appName,", attach);
  const github = worker.indexOf("CHATGPT_GITHUB_CONNECTOR_NAME,", native2);
  const preserve = worker.indexOf("true,", github);
  expect(attach).toBeGreaterThan(-1);
  expect(native2).toBeGreaterThan(attach);
  expect(github).toBeGreaterThan(native2);
  expect(preserve).toBeGreaterThan(github);
});
