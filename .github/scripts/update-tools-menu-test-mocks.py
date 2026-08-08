from pathlib import Path

path = Path("tests/browser-worker-contract.test.ts")
text = path.read_text()

old = '''    config: { appName: "Codex Native" },\n    connectorIsSelected: async () =>'''
new = '''    config: { appName: "Codex Native" },\n    selectConnectorFromToolsMenu: async () => undefined,\n    connectorIsSelected: async () =>'''
if text.count(old) < 2:
    raise SystemExit("expected connector mock blocks not found")
text = text.replace(old, new, 2)

old_attach = '''    config: { appName: "Codex Native" },\n    selectConnector,\n    insertPromptText,'''
new_attach = '''    config: { appName: "Codex Native" },\n    selectConnector,\n    selectConnectorFromToolsMenu: async () => undefined,\n    insertPromptText,'''
if old_attach not in text:
    raise SystemExit("attachPrompt connector mock not found")
text = text.replace(old_attach, new_attach, 1)
path.write_text(text)
