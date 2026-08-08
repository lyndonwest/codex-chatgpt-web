from pathlib import Path


def replace_once(path: str, old: str, new: str, label: str) -> None:
    file = Path(path)
    text = file.read_text()
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match in {path}, got {count}")
    file.write_text(text.replace(old, new, 1))


replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    "  constructor(readonly runtime: ChatGptTurnRuntime) {\n",
    "  constructor(readonly runtime: ChatGptTurnRuntime, readonly browserSessionId?: string) {\n",
    "session browser identity",
)

replace_once(
    "src/adapters/chatgpt-web/turn-execution.ts",
    '''  getOrCreate(key: string, start: () => ChatGptTurnRuntime): ChatGptTurnSession {
    this.prune();
    const existing = this.entries.get(key);
    if (existing) {
      existing.touch();
      return existing;
    }
    const active = [...this.entries.values()].filter(session => session.isActive()).length;
    if (active >= MAX_CHATGPT_BROWSER_TABS) {
      throw new Error(
        `ChatGPT Web supports at most ${MAX_CHATGPT_BROWSER_TABS} simultaneous browser turns; close or finish a browser tab before starting another`,
      );
    }
    if (this.entries.size >= this.maxEntries) throw new Error(`ChatGPT web session registry is full (${this.maxEntries} entries)`);
    const session = new ChatGptTurnSession(start());
    this.entries.set(key, session);
    return session;
  }

  async waitForRetirement(key: string): Promise<void> {
''',
    '''  getOrCreate(
    key: string,
    start: () => ChatGptTurnRuntime,
    browserSessionId?: string,
  ): ChatGptTurnSession {
    this.prune();
    const existing = this.entries.get(key);
    if (existing) {
      existing.touch();
      return existing;
    }
    const active = [...this.entries.values()].filter(session => session.isActive()).length;
    if (active >= MAX_CHATGPT_BROWSER_TABS) {
      throw new Error(
        `ChatGPT Web supports at most ${MAX_CHATGPT_BROWSER_TABS} simultaneous browser turns; close or finish a browser tab before starting another`,
      );
    }
    if (this.entries.size >= this.maxEntries) throw new Error(`ChatGPT web session registry is full (${this.maxEntries} entries)`);
    const session = new ChatGptTurnSession(start(), browserSessionId);
    this.entries.set(key, session);
    return session;
  }

  activeForBrowserSession(browserSessionId: string): { key: string; session: ChatGptTurnSession } | undefined {
    this.prune();
    let active: { key: string; session: ChatGptTurnSession } | undefined;
    for (const [key, session] of this.entries) {
      if (session.browserSessionId !== browserSessionId || !session.isActive()) continue;
      if (active) {
        throw new Error(`ChatGPT browser session ${browserSessionId} has multiple active executions`);
      }
      active = { key, session };
    }
    return active;
  }

  async waitForRetirement(key: string): Promise<void> {
''',
    "registry browser-session ownership",
)

replace_once(
    "src/adapters/chatgpt-web/index.ts",
    '''      const executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;
      await chatGptTurnSessions.waitForRetirement(executionKey);
      const traceId = createHash("sha256").update(executionKey).digest("hex").slice(0, 12);
      const persistentSessionId = browserSessionId(parsed);
      const session = chatGptTurnSessions.getOrCreate(
        executionKey,
        () => startRuntime(parsed, environment, traceId, turnCapabilities, persistentSessionId),
      );
''',
    '''      let executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;
      const persistentSessionId = browserSessionId(parsed);
      if (!parsed._compactionRequest && persistentSessionId) {
        const activeBrowserExecution = chatGptTurnSessions.activeForBrowserSession(persistentSessionId);
        if (activeBrowserExecution && activeBrowserExecution.key !== executionKey) {
          const matchingToolResults = currentToolResults(parsed, activeBrowserExecution.session);
          if (activeBrowserExecution.session.outstanding().length > 0 && matchingToolResults.length > 0) {
            console.warn(
              `[chatgpt-web] rebound changed-key tool-result round to active browser execution `
              + `(browser_session=${persistentSessionId}, matching_results=${matchingToolResults.length})`,
            );
            executionKey = activeBrowserExecution.key;
          } else {
            await chatGptTurnSessions.retireAndWait(activeBrowserExecution.key);
          }
        }
      }
      await chatGptTurnSessions.waitForRetirement(executionKey);
      const traceId = createHash("sha256").update(executionKey).digest("hex").slice(0, 12);
      const session = chatGptTurnSessions.getOrCreate(
        executionKey,
        () => startRuntime(parsed, environment, traceId, turnCapabilities, persistentSessionId),
        persistentSessionId,
      );
''',
    "persistent browser execution rebind",
)
