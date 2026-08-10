#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))


def replace_between(path: str, start_marker: str, end_marker: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text()
    start = text.find(start_marker)
    end = text.find(end_marker, start + 1)
    if start < 0 or end < 0:
        raise SystemExit(f"{path}: replacement markers not found")
    p.write_text(text[:start] + replacement + text[end:])


Path("src/adapters/chatgpt-web/capability-routing.ts").write_text(r'''import type { CodexContentPart, CodexParsedRequest } from "../../types";

function userMessageText(content: string | CodexContentPart[]): string {
  if (typeof content === "string") return content;
  return content
    .filter(part => part.type === "text")
    .map(part => part.type === "text" ? part.text : "")
    .join("\n");
}

/**
 * Native2 is fail-closed per Web phase. The most recent explicit directive in user-role
 * task packets wins; developer/system text cannot accidentally authorize local access.
 */
export function chatGptNative2Allowed(parsed: CodexParsedRequest): boolean {
  if (parsed._compactionRequest) return false;
  for (let messageIndex = parsed.context.messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
    const message = parsed.context.messages[messageIndex]!;
    if (message.role !== "user") continue;
    const lines = userMessageText(message.content).split(/\r?\n/);
    for (let lineIndex = lines.length - 1; lineIndex >= 0; lineIndex -= 1) {
      const match = lines[lineIndex]!.match(/^\s*native2_allowed:\s*(true|false)\s*$/i);
      if (match) return match[1]!.toLowerCase() === "true";
    }
  }
  return false;
}
''')

Path("tests/chatgpt-web-capability-routing.test.ts").write_text(r'''import { describe, expect, test } from "bun:test";
import type { CodexParsedRequest } from "../src/types";
import { chatGptNative2Allowed } from "../src/adapters/chatgpt-web/capability-routing";

function parsed(messages: unknown[], compaction = false): CodexParsedRequest {
  return {
    context: { messages },
    _compactionRequest: compaction,
  } as unknown as CodexParsedRequest;
}

describe("ChatGPT Web Native2 routing", () => {
  test("defaults closed and ignores developer instructions", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "developer", content: "native2_allowed: true" },
      { role: "user", content: "Review the PR through GitHub." },
    ]))).toBe(false);
  });

  test("honors the latest explicit user-packet directive", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: false" },
      { role: "user", content: "native2_allowed: true\nnative2_scope: inspect live container logs" },
    ]))).toBe(true);
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: true" },
      { role: "user", content: "native2_allowed: false" },
    ]))).toBe(false);
  });

  test("never enables Native2 for compaction turns", () => {
    expect(chatGptNative2Allowed(parsed([
      { role: "user", content: "native2_allowed: true" },
    ], true))).toBe(false);
  });
});
''')

# Adapter: gate local tools on the explicit packet directive, but attach GitHub on every normal turn.
replace_once(
    "src/adapters/chatgpt-web/index.ts",
    'import { ChatGptBrowserWorker } from "./browser-worker";\n',
    'import { ChatGptBrowserWorker } from "./browser-worker";\nimport { chatGptNative2Allowed } from "./capability-routing";\n',
)
replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''      const turnCapabilities = parsed._compactionRequest\n        ? { ...configuredCapabilities, localToolsEnabled: false }\n        : configuredCapabilities;\n''',
    '''      const native2Allowed = configuredCapabilities.localToolsEnabled && chatGptNative2Allowed(parsed);\n      const turnCapabilities: ChatGptWebCapabilities = {\n        ...configuredCapabilities,\n        localToolsEnabled: !parsed._compactionRequest && native2Allowed,\n      };\n''',
)
# Both browser-runtime construction paths need the serializable GitHub-app flag.
index_path = Path("src/adapters/chatgpt-web/index.ts")
index_text = index_path.read_text()
needle = '''        capabilities: turnCapabilities,\n        prepare: async () => ({\n'''
if index_text.count(needle) != 1:
    raise SystemExit(f"index.ts: expected one read-only BrowserTurn capability block, found {index_text.count(needle)}")
index_text = index_text.replace(
    needle,
    '''        capabilities: turnCapabilities,\n        useGitHubApp: !parsed._compactionRequest,\n        prepare: async () => ({\n''',
    1,
)
needle = '''      capabilities: turnCapabilities,\n      prepare: async () => {\n'''
if index_text.count(needle) != 1:
    raise SystemExit(f"index.ts: expected one tool BrowserTurn capability block, found {index_text.count(needle)}")
index_text = index_text.replace(
    needle,
    '''      capabilities: turnCapabilities,\n      useGitHubApp: !parsed._compactionRequest,\n      prepare: async () => {\n''',
    1,
)
# Policy-disabled Native2 is not the same as a Browser-only installation; use configured capability for warnings.
index_text = index_text.replace(
    'emitProContextWarning(parsed, turnCapabilities, emitCaptured);',
    'emitProContextWarning(parsed, configuredCapabilities, emitCaptured);',
)
index_text = index_text.replace(
    'emitProContextWarning(parsed, turnCapabilities, emitRound);',
    'emitProContextWarning(parsed, configuredCapabilities, emitRound);',
)
index_path.write_text(index_text)

# Browser worker: generalize exact connector selection and select GitHub by default.
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    'export const CHATGPT_EFFORT_READY_TIMEOUT_MS = 30_000;\n',
    'export const CHATGPT_EFFORT_READY_TIMEOUT_MS = 30_000;\nexport const CHATGPT_GITHUB_CONNECTOR_NAME = "GitHub";\n',
)
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''  capabilities: ChatGptWebCapabilities;\n  prepare: () => Promise<CompiledChatGptWebPrompt & { release: () => void }>;\n''',
    '''  capabilities: ChatGptWebCapabilities;\n  /** Attach the ChatGPT GitHub app to this normal repository turn. */\n  useGitHubApp?: boolean;\n  prepare: () => Promise<CompiledChatGptWebPrompt & { release: () => void }>;\n''',
)
connector_block = r'''  private selectedConnectorControl(composer: Locator, connectorName: string): Locator {
    return composer
      .locator('[data-id^="plugin:"][data-keyword]')
      .filter({ hasText: connectorName, visible: true });
  }

  private async connectorIsSelected(composer: Locator, connectorName: string): Promise<boolean> {
    const selected = this.selectedConnectorControl(composer, connectorName);
    const exactMatches = await selected.evaluateAll((elements, expected) => {
      const target = expected.toLowerCase();
      return elements.filter(element => {
        const keyword = (element.getAttribute("data-keyword") ?? "").trim().toLowerCase();
        const text = (element.textContent ?? "").replace(/\s+/g, " ").trim().toLowerCase();
        return keyword === target || text === target || text.startsWith(`${target} `);
      }).length;
    }, connectorName);
    if (exactMatches > 1) {
      throw new Error(`ChatGPT composer exposed duplicate ${JSON.stringify(connectorName)} connector selections`);
    }
    return exactMatches === 1;
  }

  private async connectorMentionRowTitles(menuRows: Locator): Promise<string[]> {
    const texts = await menuRows.filter({ visible: true }).allInnerTexts().catch(() => [] as string[]);
    return texts
      .map(text => (text.split("\n")[0] ?? "").replace(/\s+/g, " ").trim())
      .filter(title => title.length > 0);
  }

  private async connectorMentionFailure(
    menuRows: Locator,
    triggerAttempts: number,
    connectorName: string,
  ): Promise<string> {
    const titles = await this.connectorMentionRowTitles(menuRows);
    if (titles.length === 0) {
      return `ChatGPT connector menu did not open after ${triggerAttempts} complete mention trigger attempt(s)`;
    }
    if (connectorName === CHATGPT_CONNECTOR_NAME && this.config.appName === CHATGPT_CONNECTOR_NAME) {
      const legacyName = LEGACY_CHATGPT_CONNECTOR_NAMES.find(name => titles.includes(name));
      if (legacyName) return legacyChatGptConnectorMigrationMessage(legacyName);
    }
    return `ChatGPT connector menu opened but exposed no row named ${JSON.stringify(connectorName)}`
      + ` after ${triggerAttempts} complete mention trigger attempt(s)`
      + `; make that app available in ChatGPT before retrying`
      + `; visible rows: ${titles.map(title => JSON.stringify(title)).join(", ")}`;
  }

  private async selectConnector(
    page: Page,
    connectorName: string,
    captureDiagnostic?: (checkpoint: string) => Promise<void>,
  ): Promise<Locator> {
    let composer = await this.activeComposer(page);
    if (await this.connectorIsSelected(composer, connectorName)) {
      await captureDiagnostic?.(`connector-already-selected-${connectorName}`);
      return composer;
    }

    const menuRows = page.locator('.__menu-item[tabindex="0"]');
    const appResult = menuRows.filter({
      has: page.getByText(connectorName, { exact: true }),
    });
    const menuDeadline = Date.now() + 20_000;
    const mentionTrigger = `@${connectorName.slice(0, 1).toLowerCase()}`;
    let triggerAttempts = 0;
    let firstMenuCaptured = false;
    for (;;) {
      triggerAttempts += 1;
      composer = await this.activeComposer(page);
      await composer.focus();
      await page.keyboard.press(CHATGPT_COMPOSER_DOCUMENT_END_KEY);
      await settleChatGptUi();
      await composer.pressSequentially(mentionTrigger, { delay: 25 });
      if (!firstMenuCaptured) {
        firstMenuCaptured = true;
        await captureDiagnostic?.(`connector-mention-triggered-${connectorName}`);
      }
      try {
        await appResult.waitFor({
          state: "visible",
          timeout: Math.min(2_500, Math.max(1, menuDeadline - Date.now())),
        });
        await captureDiagnostic?.(`connector-menu-visible-${connectorName}`);
        break;
      } catch (error) {
        if (!(error instanceof Error) || error.name !== "TimeoutError") throw error;
        if (Date.now() >= menuDeadline) {
          await captureDiagnostic?.(`connector-menu-missing-${connectorName}`);
          throw new Error(await this.connectorMentionFailure(menuRows, triggerAttempts, connectorName));
        }
        await page.keyboard.press("Escape").catch(() => {});
        for (let index = 0; index < mentionTrigger.length; index += 1) {
          await page.keyboard.press("Backspace").catch(() => {});
        }
      }
    }
    if (await appResult.count() !== 1) {
      throw new Error(
        `ChatGPT connector menu did not expose one exact ${JSON.stringify(connectorName)} row`
        + `; visible rows: ${(await this.connectorMentionRowTitles(menuRows)).map(title => JSON.stringify(title)).join(", ")}`,
      );
    }
    await appResult.click({ force: true, timeout: 10_000 });
    const selectedComposer = await this.activeComposer(page);
    const selectedConnector = this.selectedConnectorControl(selectedComposer, connectorName);
    await selectedConnector.waitFor({ state: "visible", timeout: 10_000 });
    if (!await this.connectorIsSelected(selectedComposer, connectorName)) {
      throw new Error(`ChatGPT composer did not select ${JSON.stringify(connectorName)} connector`);
    }
    await captureDiagnostic?.(`connector-selected-${connectorName}`);
    return selectedComposer;
  }

  private async selectConnectors(
    page: Page,
    connectorNames: readonly string[],
    captureDiagnostic?: (checkpoint: string) => Promise<void>,
  ): Promise<Locator> {
    let composer = await this.activeComposer(page);
    await composer.fill("");
    for (const connectorName of connectorNames) {
      composer = await this.selectConnector(page, connectorName, captureDiagnostic);
    }
    return composer;
  }

  private async attachPrompt(
    page: Page,
    prompt: string,
    localTools: boolean,
    useGitHubApp: boolean,
    captureDiagnostic?: (checkpoint: string) => Promise<void>,
  ): Promise<void> {
    const connectorNames = [
      ...(useGitHubApp ? [CHATGPT_GITHUB_CONNECTOR_NAME] : []),
      ...(localTools ? [this.config.appName] : []),
    ];
    if (connectorNames.length === 0) {
      const composer = await this.activeComposer(page);
      await composer.fill("");
      await composer.focus();
      await this.insertPromptText(page, prompt);
      await this.assertPromptAttached(page, prompt);
      return;
    }
    const selectedComposer = await this.selectConnectors(page, connectorNames, captureDiagnostic);
    await selectedComposer.focus();
    await page.keyboard.press(CHATGPT_COMPOSER_DOCUMENT_END_KEY);
    await this.insertPromptText(page, ` ${prompt}`);
    await this.assertPromptAttached(page, prompt);
  }

'''
replace_between(
    "src/adapters/chatgpt-web/browser-worker.ts",
    "  private selectedConnectorControl(composer: Locator): Locator {",
    "  private async insertPromptText(page: Page, text: string): Promise<void> {",
    connector_block,
)
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''    await this.selectConnector(page);\n    return this.config.appName;\n''',
    '''    await this.selectConnectors(page, [this.config.appName]);\n    return this.config.appName;\n''',
)
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''        this.attachPrompt(page, prepared.text, mode.localTools, checkpoint => diagnostics.capture(page, checkpoint))\n''',
    '''        this.attachPrompt(\n          page,\n          prepared.text,\n          mode.localTools,\n          turn.useGitHubApp === true,\n          checkpoint => diagnostics.capture(page, checkpoint),\n        )\n''',
)

# The launcher browser-helper process carries the GitHub-app flag across IPC.
replace_once(
    "src/adapters/chatgpt-web/launcher-helper-client.ts",
    '''            capabilities: turn.capabilities,\n            prepared: { text: prepared.text, images: prepared.images } satisfies CompiledChatGptWebPrompt,\n''',
    '''            capabilities: turn.capabilities,\n            ...(turn.useGitHubApp ? { useGitHubApp: true } : {}),\n            prepared: { text: prepared.text, images: prepared.images } satisfies CompiledChatGptWebPrompt,\n''',
)
replace_once(
    "src/adapters/chatgpt-web/browser-helper-main.ts",
    '''    capabilities: ChatGptWebCapabilities;\n    prepared: CompiledChatGptWebPrompt;\n''',
    '''    capabilities: ChatGptWebCapabilities;\n    useGitHubApp?: boolean;\n    prepared: CompiledChatGptWebPrompt;\n''',
)
replace_once(
    "src/adapters/chatgpt-web/browser-helper-main.ts",
    '''  if (message.turn.captureLunaCheckpoint !== undefined && typeof message.turn.captureLunaCheckpoint !== "boolean") {\n    throw new Error("Browser helper Luna checkpoint flag is invalid");\n  }\n''',
    '''  if (message.turn.useGitHubApp !== undefined && typeof message.turn.useGitHubApp !== "boolean") {\n    throw new Error("Browser helper GitHub-app flag is invalid");\n  }\n  if (message.turn.captureLunaCheckpoint !== undefined && typeof message.turn.captureLunaCheckpoint !== "boolean") {\n    throw new Error("Browser helper Luna checkpoint flag is invalid");\n  }\n''',
)
replace_once(
    "src/adapters/chatgpt-web/browser-helper-main.ts",
    '''    capabilities: message.turn.capabilities,\n    prepare: async () => ({ ...message.turn.prepared, release: () => {} }),\n''',
    '''    capabilities: message.turn.capabilities,\n    ...(message.turn.useGitHubApp ? { useGitHubApp: true } : {}),\n    prepare: async () => ({ ...message.turn.prepared, release: () => {} }),\n''',
)

# Add a lightweight source contract test for deterministic app routing through the helper boundary.
Path("tests/chatgpt-web-app-routing-contract.test.ts").write_text(r'''import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";

const worker = readFileSync("src/adapters/chatgpt-web/browser-worker.ts", "utf8");
const adapter = readFileSync("src/adapters/chatgpt-web/index.ts", "utf8");
const helperClient = readFileSync("src/adapters/chatgpt-web/launcher-helper-client.ts", "utf8");
const helperMain = readFileSync("src/adapters/chatgpt-web/browser-helper-main.ts", "utf8");

describe("GitHub-first Web app routing contract", () => {
  test("normal turns attach GitHub and Native2 remains directive-gated", () => {
    expect(adapter).toContain("chatGptNative2Allowed(parsed)");
    expect(adapter).toContain("useGitHubApp: !parsed._compactionRequest");
    expect(worker).toContain('CHATGPT_GITHUB_CONNECTOR_NAME = "GitHub"');
    expect(worker).toContain("...(useGitHubApp ? [CHATGPT_GITHUB_CONNECTOR_NAME] : [])");
    expect(worker).toContain("...(localTools ? [this.config.appName] : [])");
  });

  test("launcher helper preserves the GitHub-app flag", () => {
    expect(helperClient).toContain("turn.useGitHubApp ? { useGitHubApp: true }");
    expect(helperMain).toContain("useGitHubApp?: boolean");
    expect(helperMain).toContain("message.turn.useGitHubApp ? { useGitHubApp: true }");
  });
});
''')

print("Applied GitHub-first Web app routing patch")
