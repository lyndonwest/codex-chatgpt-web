from pathlib import Path
import re

p = Path("tests/server-compaction.test.ts")
text = p.read_text()
text, count = re.subn(
    r'^\s*expect\(sse\.match\(.*compaction.*$',
    '  expect((sse.match(/"type":"compaction"/g) ?? [])).toHaveLength(2);',
    text,
    count=1,
    flags=re.MULTILINE,
)
if count != 1:
    raise SystemExit(f"expected one streaming compaction assertion, found {count}")
p.write_text(text)

p = Path("tests/persistent-session.test.ts")
text = p.read_text()
old = '  expect(source).toContain("const persistentSessionId = browserSessionId(parsed)");'
new = '  expect(source).toContain("const persistentSessionId = chatGptBrowserSessionId(provider, parsed)");'
if text.count(old) != 1:
    raise SystemExit(f"expected one persistent session identity assertion, found {text.count(old)}")
p.write_text(text.replace(old, new, 1))

p = Path("tests/chatgpt-web-harness.test.ts")
text = p.read_text()
pattern = re.compile(
    r'  test\("replaces the active browser response after Codex compacts mid-tool-loop", async \(\) => \{.*?\n  \}\);\n\n(?=  test\("runs Pro as one context-complete read-only browser turn)',
    re.DOTALL,
)
replacement = '''  test("routes native Codex compaction above the browser adapter", async () => {
    const socketPath = brokerTestEndpoint(`cgw-h3-native-compact-${process.pid}-${Date.now()}`);
    const provider: CodexProviderConfig = {
      adapter: "chatgpt-web",
      baseUrl: "browser://chatgpt",
      chatgptWeb: { brokerSocketPath: socketPath, turnTimeoutMs: 30_000, localToolsEnabled: true, proAvailable: true },
    };
    const adapter = createChatGptWebAdapter(provider);
    const compactRequest = rawWireRequest(environmentXml);
    compactRequest._compactionRequest = true;
    const compactEvents: AdapterEvent[] = [];
    try {
      await expect(adapter.runTurn!(compactRequest, { headers: new Headers() }, event => compactEvents.push(event)))
        .rejects.toThrow("must be handled by the bridge without opening or retiring a browser turn");
      expect(compactEvents).toEqual([]);
    } finally {
      await TurnBroker.forSocket(socketPath).close();
    }
  });

'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"expected one legacy mid-tool compaction harness test, found {count}")
p.write_text(text)
