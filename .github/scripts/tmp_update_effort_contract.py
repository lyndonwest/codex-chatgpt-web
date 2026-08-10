from pathlib import Path

path = Path("tests/browser-worker-contract.test.ts")
text = path.read_text()
old = "  expect(workerSource).toContain('timeout: 70_000');\n"
new = "  expect(workerSource).toContain('timeout: CHATGPT_EFFORT_READY_TIMEOUT_MS');\n"
if text.count(old) != 1:
    raise SystemExit(f"expected one old effort-timeout contract, found {text.count(old)}")
path.write_text(text.replace(old, new, 1))
