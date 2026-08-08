from pathlib import Path

path = Path("src/adapters/chatgpt-web/browser-worker.ts")
text = path.read_text()
old = '''    // Keep @ mention as a compatibility fallback for ChatGPT surfaces that do not expose\n    // the documented + -> More app picker.\n    composer = await this.activeComposer(page);\n    await composer.fill("");\n    const menuRows = page.locator('.__menu-item[tabindex="0"]');\n'''
new = '''    // Keep @ mention as a compatibility fallback for ChatGPT surfaces that do not expose\n    // the documented + -> More app picker. The existing mention loop re-resolves and clears\n    // the composer on every attempt.\n    const menuRows = page.locator('.__menu-item[tabindex="0"]');\n'''
if old not in text:
    raise SystemExit("redundant fallback reset block not found")
path.write_text(text.replace(old, new, 1))
