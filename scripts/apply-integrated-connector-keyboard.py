#!/usr/bin/env python3
from pathlib import Path


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 match, found {count}")
    path.write_text(text.replace(old, new, 1))
    print(f"updated: {label}")


worker = Path("src/adapters/chatgpt-web/browser-worker.ts")
test = Path("tests/browser-worker-contract.test.ts")

replace_once(
    worker,
    '    await appResult.click({ force: true, timeout: 10_000 });\n',
    '''    // ChatGPT commits mention-menu selection from the composer/menu keyboard state. Launcher\n    // verification can keep the embedded browser surface hidden, so pointer activation can fail\n    // even though the exact app row is rendered. Prove the row is keyboard-highlighted, then\n    // submit Enter through the composer. This works for both GitHub and Codex Native2 without\n    // relying on viewport geometry or an untrusted synthetic click.\n    let highlighted = await appResult.getAttribute("data-highlighted");\n    if (highlighted === null) {\n      await composer.fill("");\n      await composer.focus();\n      await composer.pressSequentially(`@${connectorName.replace(/\\s+/g, "")}`, { delay: 25 });\n      await appResult.waitFor({ state: "visible", timeout: 2_500 });\n      highlighted = await appResult.getAttribute("data-highlighted");\n    }\n    if (highlighted === null) {\n      throw new Error(\n        `ChatGPT connector row ${JSON.stringify(connectorName)} is visible but not keyboard-highlighted`,\n      );\n    }\n    await composer.press("Enter");\n''',
    "browser connector activation",
)

replace_once(
    test,
    '''  expect(workerSource).toContain("await appResult.click({ force: true, timeout: 10_000 })");\n  expect(workerSource).not.toContain("highlightConnectorMenuRow");\n  expect(workerSource).not.toContain('await appResult.dispatchEvent("click")');\n  expect(workerSource).not.toContain('appResult.press("Enter")');\n''',
    '''  expect(workerSource).toContain('await appResult.getAttribute("data-highlighted")');\n  expect(workerSource).toContain('connectorName.replace(/\\\\s+/g, "")');\n  expect(workerSource).toContain('await composer.press("Enter")');\n  expect(workerSource).not.toContain("highlightConnectorMenuRow");\n  expect(workerSource).not.toContain('await appResult.dispatchEvent("click")');\n  expect(workerSource).not.toContain('appResult.press("Enter")');\n  expect(workerSource).not.toContain("appResult.click({ force: true");\n''',
    "source contract",
)

replace_once(
    test,
    '''    click: async (options: { force: boolean; timeout: number }) => {\n      expect(options).toEqual({ force: true, timeout: 10_000 });\n      connectorSelected = true;\n      calls.push(["click"]);\n    },\n''',
    '''    getAttribute: async (name: string) => {\n      expect(name).toBe("data-highlighted");\n      return "";\n    },\n''',
    "re-resolution app result",
)

replace_once(
    test,
    '''    pressSequentially: async (value: string, options: { delay: number }) => {\n      expect(options).toEqual({ delay: 25 });\n      calls.push(["pressSequentially", value]);\n    },\n  };\n''',
    '''    pressSequentially: async (value: string, options: { delay: number }) => {\n      expect(options).toEqual({ delay: 25 });\n      calls.push(["pressSequentially", value]);\n    },\n    press: async (key: string) => {\n      expect(key).toBe("Enter");\n      connectorSelected = true;\n      calls.push(["press", key]);\n    },\n  };\n''',
    "re-resolution composer Enter",
)

replace_once(
    test,
    '''    ["waitForResult"],\n    ["click"],\n    ["waitForSelectedConnector"],\n''',
    '''    ["waitForResult"],\n    ["press", "Enter"],\n    ["waitForSelectedConnector"],\n''',
    "re-resolution call sequence",
)

replace_once(
    test,
    '''    click: async (options: { force: boolean; timeout: number }) => {\n      expect(options).toEqual({ force: true, timeout: 10_000 });\n      selected = true;\n      calls.push("activate");\n    },\n''',
    '''    getAttribute: async (name: string) => {\n      expect(name).toBe("data-highlighted");\n      return "";\n    },\n''',
    "hydration app result",
)

replace_once(
    test,
    '''    pressSequentially: async (value: string) => {\n      expect(value).toBe("@c");\n      calls.push("type");\n    },\n  };\n''',
    '''    pressSequentially: async (value: string) => {\n      expect(value).toBe("@c");\n      calls.push("type");\n    },\n    press: async (key: string) => {\n      expect(key).toBe("Enter");\n      selected = true;\n      calls.push("activate");\n    },\n  };\n''',
    "hydration composer Enter",
)

replace_once(
    test,
    '''    click: async (options: { force: boolean; timeout: number }) => {\n      expect(options).toEqual({ force: true, timeout: 10_000 });\n      selected = true;\n      calls.push(["selectConnector"]);\n    },\n''',
    '''    getAttribute: async (name: string) => {\n      expect(name).toBe("data-highlighted");\n      return "";\n    },\n''',
    "tool prompt app result",
)

replace_once(
    test,
    '''    fill: async (value: string) => { calls.push(["fill", value]); },\n    focus: async () => { calls.push(["focus"]); },\n    pressSequentially: async (value: string) => { calls.push(["type", value]); },\n  };\n''',
    '''    fill: async (value: string) => { calls.push(["fill", value]); },\n    focus: async () => { calls.push(["focus"]); },\n    pressSequentially: async (value: string) => { calls.push(["type", value]); },\n    press: async (key: string) => {\n      expect(key).toBe("Enter");\n      selected = true;\n      calls.push(["selectConnector"]);\n    },\n  };\n''',
    "tool prompt composer Enter",
)
