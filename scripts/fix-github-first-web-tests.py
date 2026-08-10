#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{path}: expected one match, found {count}: {old[:120]!r}")
    p.write_text(text.replace(old, new, 1))

# Keep existing diagnostic checkpoint names stable while allowing any exact connector.
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''    connectorName: string,\n  ): Promise<string> {\n''',
    '''    connectorName = this.config.appName,\n  ): Promise<string> {\n''',
)
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''    connectorName: string,\n    captureDiagnostic?: (checkpoint: string) => Promise<void>,\n  ): Promise<Locator> {\n''',
    '''    connectorName = this.config.appName,\n    captureDiagnostic?: (checkpoint: string) => Promise<void>,\n  ): Promise<Locator> {\n''',
)
for old, new in [
    ('`connector-already-selected-${connectorName}`', '"connector-already-selected"'),
    ('`connector-mention-triggered-${connectorName}`', '"connector-mention-triggered"'),
    ('`connector-menu-visible-${connectorName}`', '"connector-menu-visible"'),
    ('`connector-menu-missing-${connectorName}`', '"connector-menu-missing"'),
    ('`connector-selected-${connectorName}`', '"connector-selected"'),
]:
    replace_once("src/adapters/chatgpt-web/browser-worker.ts", old, new)
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''      await composer.focus();\n      await page.keyboard.press(CHATGPT_COMPOSER_DOCUMENT_END_KEY);\n      await settleChatGptUi();\n      await composer.pressSequentially(mentionTrigger, { delay: 25 });\n''',
    '''      await composer.focus();\n      await settleChatGptUi();\n      await composer.pressSequentially(mentionTrigger, { delay: 25 });\n''',
)
replace_once(
    "src/adapters/chatgpt-web/browser-worker.ts",
    '''    const selectedComposer = await this.selectConnectors(page, connectorNames, captureDiagnostic);\n    await selectedComposer.focus();\n''',
    '''    let selectedComposer = await this.activeComposer(page);\n    await selectedComposer.fill("");\n    for (const connectorName of connectorNames) {\n      selectedComposer = await this.selectConnector(page, connectorName, captureDiagnostic);\n    }\n    await selectedComposer.focus();\n''',
)

# Existing Full Harness fixtures explicitly opt in under the new fail-closed contract.
replace_once(
    "tests/native-compaction-continuity.test.ts",
    '''      messages: [{ role: "user", content: "Continue the running command", timestamp: 1 }],\n''',
    '''      messages: [{ role: "user", content: "native2_allowed: true\\nContinue the running command", timestamp: 1 }],\n''',
)
replace_once(
    "tests/chatgpt-web-harness.test.ts",
    '''        { role: "user", content: "Inspect the project", timestamp: 2 },\n''',
    '''        { role: "user", content: "native2_allowed: true\\nInspect the project", timestamp: 2 },\n''',
)

# Update browser-worker contract assertions for generalized app selection.
p = Path("tests/browser-worker-contract.test.ts")
text = p.read_text()
old_block = '''test("connector verification and real tool turns share one Playwright selector", () => {\n  const workerSource = readFileSync(new URL("../src/adapters/chatgpt-web/browser-worker.ts", import.meta.url), "utf8");\n  expect(workerSource.match(/this\\.selectConnector\\(page(?:, captureDiagnostic)?\\)/g)?.length).toBe(2);\n  expect(workerSource.match(/this\\.prepareTemporaryChatSurface\\(\\s*page/g)?.length).toBe(4);\n  expect(workerSource).toContain('\"temporary_chat_preparation\"');\n  expect(workerSource).toContain('if (page.url() !== CHATGPT_TEMPORARY_CHAT_URL)');\n  expect(workerSource).toContain('composer.pressSequentially("@c", { delay: 25 })');\n  expect(workerSource).toContain('page.locator(\\'.__menu-item[tabindex="0"]\\')');\n  expect(workerSource).toContain("await appResult.click({ force: true, timeout: 10_000 })");\n  expect(workerSource).not.toContain("highlightConnectorMenuRow");\n  expect(workerSource).not.toContain('await appResult.dispatchEvent("click")');\n  expect(workerSource).not.toContain('appResult.press("Enter")');\n  expect(workerSource).toContain("this.selectedConnectorControl(selectedComposer)");\n  expect(workerSource).toContain("'[data-id^=\\\"plugin:\\\"][data-keyword]'");\n  expect(workerSource).toContain("const selectedComposer = await this.activeComposer(page)");\n});\n'''
new_block = '''test("GitHub and Native2 turns share one exact Playwright app selector", () => {\n  const workerSource = readFileSync(new URL("../src/adapters/chatgpt-web/browser-worker.ts", import.meta.url), "utf8");\n  expect(workerSource.match(/this\\.prepareTemporaryChatSurface\\(\\s*page/g)?.length).toBe(4);\n  expect(workerSource).toContain('\"temporary_chat_preparation\"');\n  expect(workerSource).toContain('if (page.url() !== CHATGPT_TEMPORARY_CHAT_URL)');\n  expect(workerSource).toContain('CHATGPT_GITHUB_CONNECTOR_NAME = "GitHub"');\n  expect(workerSource).toContain('const mentionTrigger = `@${connectorName.slice(0, 1).toLowerCase()}`');\n  expect(workerSource).toContain('...(useGitHubApp ? [CHATGPT_GITHUB_CONNECTOR_NAME] : [])');\n  expect(workerSource).toContain('...(localTools ? [this.config.appName] : [])');\n  expect(workerSource).toContain('page.locator(\\'.__menu-item[tabindex="0"]\\')');\n  expect(workerSource).toContain("await appResult.click({ force: true, timeout: 10_000 })");\n  expect(workerSource).not.toContain("highlightConnectorMenuRow");\n  expect(workerSource).not.toContain('await appResult.dispatchEvent("click")');\n  expect(workerSource).not.toContain('appResult.press("Enter")');\n  expect(workerSource).toContain("this.selectedConnectorControl(selectedComposer, connectorName)");\n  expect(workerSource).toContain("'[data-id^=\\\"plugin:\\\"][data-keyword]'");\n  expect(workerSource).toContain("const selectedComposer = await this.activeComposer(page)");\n});\n'''
if text.count(old_block) != 1:
    raise SystemExit("browser-worker contract selector block did not match")
text = text.replace(old_block, new_block, 1)

# Direct selector test no longer clears the composer itself; the multi-app caller clears once.
text = text.replace(
    '''  expect(calls).toEqual([\n    ["fill", ""],\n    ["fill", ""],\n    ["focus"],\n''',
    '''  expect(calls).toEqual([\n    ["focus"],\n''',
    1,
)
# Hydration retry uses keyboard cleanup so an already-selected GitHub pill is preserved.
replace_target = '''  const page = {\n    getByText: () => ({ exactConnectorLabel: true }),\n    locator: (selector: string) => selector.includes("__menu-item")\n      ? { filter: () => appResult, evaluateAll: async () => [] }\n      : (() => { throw new Error(`Unexpected locator: ${selector}`); })(),\n  };\n'''
replace_value = '''  const page = {\n    getByText: () => ({ exactConnectorLabel: true }),\n    locator: (selector: string) => selector.includes("__menu-item")\n      ? { filter: () => appResult, evaluateAll: async () => [] }\n      : (() => { throw new Error(`Unexpected locator: ${selector}`); })(),\n    keyboard: {\n      press: async (value: string) => { calls.push(`key:${value}`); },\n    },\n  };\n'''
if text.count(replace_target) < 1:
    raise SystemExit("hydration page mock did not match")
# Only the first occurrence after the hydration test marker.
marker = 'test("connector selection retriggers the complete mention after a fresh-page hydration miss"'
idx = text.find(marker)
if idx < 0:
    raise SystemExit("hydration test marker missing")
pre, post = text[:idx], text[idx:]
if replace_target not in post:
    raise SystemExit("hydration page mock missing after marker")
post = post.replace(replace_target, replace_value, 1)
text = pre + post
old_expected = '''  expect(calls).toEqual([\n    "clear",\n    "clear", "focus", "type", "menu:1",\n    "clear", "focus", "type", "menu:2",\n    "activate", "selected",\n  ]);\n'''
new_expected = '''  expect(calls).toEqual([\n    "focus", "type", "menu:1",\n    "key:Escape", "key:Backspace", "key:Backspace",\n    "focus", "type", "menu:2",\n    "activate", "selected",\n  ]);\n'''
if old_expected not in text:
    raise SystemExit("hydration expected calls did not match")
text = text.replace(old_expected, new_expected, 1)
# Tool prompt caller clears exactly once before selecting Native2.
old_tool_expected = '''  expect(calls).toEqual([\n    ["fill", ""],\n    ["fill", ""],\n    ["focus"],\n'''
new_tool_expected = '''  expect(calls).toEqual([\n    ["fill", ""],\n    ["focus"],\n'''
if old_tool_expected not in text:
    raise SystemExit("tool prompt expected calls did not match")
text = text.replace(old_tool_expected, new_tool_expected, 1)
p.write_text(text)

print("Applied GitHub-first test compatibility fixes")
