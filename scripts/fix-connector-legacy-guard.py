#!/usr/bin/env python3
from pathlib import Path
p = Path('src/adapters/chatgpt-web/browser-worker.ts')
text = p.read_text()
old = '    if (connectorName === CHATGPT_CONNECTOR_NAME && this.config.appName === CHATGPT_CONNECTOR_NAME) {\n'
new = '    if (connectorName === CHATGPT_CONNECTOR_NAME && this.config.appName === CHATGPT_CONNECTOR_NAME && !titles.includes(connectorName)) {\n'
if text.count(old) != 1:
    raise SystemExit(f'expected one legacy guard, found {text.count(old)}')
p.write_text(text.replace(old, new, 1))
print('Applied connector legacy guard fix')
