const test = require("node:test");
const assert = require("node:assert/strict");
const { BrowserHost } = require("../electron/browser-host.cjs");

function retainedFixture(tab) {
  const events = [];
  const fixture = Object.assign(Object.create(BrowserHost.prototype), {
    manualOperation: null,
    turnTabs: new Map([[tab.id, tab]]),
    closedTurnOwners: new Map(),
    selectedTabId: tab.id,
    visible: false,
    surfaceActive: true,
    boundsReady: true,
    window: { contentView: { removeChildView: () => events.push("remove") } },
    view: { setVisible() {} },
    syncViewVisibility() {},
    writeDescriptor: () => events.push("descriptor"),
    publishState: () => events.push("publish"),
    snapshot: () => ({ tabs: [] }),
    hide: () => events.push("hide"),
    logger: { info: (name) => events.push(name), warn() {} },
  });
  return { fixture, events };
}

test("completed persistent thread keeps its browser document and reuses it for a new trace", async () => {
  const throttling = [];
  const tab = {
    id: "tab-persistent",
    surfaceId: "surface-persistent",
    traceId: "trace_first",
    sessionId: "session_123456789012",
    helperPid: process.pid,
    status: "running",
    loading: true,
    lastUsedAt: 1,
    view: {
      setVisible() {},
      webContents: {
        isDestroyed: () => false,
        setBackgroundThrottling: enabled => throttling.push(enabled),
        close: () => assert.fail("persistent tab must not close"),
      },
    },
  };
  const { fixture } = retainedFixture(tab);

  await BrowserHost.prototype.endTurn.call(
    fixture,
    tab.traceId,
    tab.helperPid,
    "completed",
    false,
  );
  assert.equal(fixture.turnTabs.size, 1);
  assert.equal(tab.status, "ready");

  const lease = BrowserHost.prototype.beginTurn.call(
    fixture,
    "trace_second",
    false,
    process.pid,
    tab.sessionId,
  );
  assert.deepEqual(lease, {
    surfaceId: tab.surfaceId,
    tabId: tab.id,
    reused: true,
  });
  assert.equal(tab.traceId, "trace_second");
  assert.equal(tab.status, "running");
  assert.deepEqual(throttling, [true, false]);
});

test("aborted persistent turn is retained for native compaction but failed turn is discarded", async () => {
  for (const [status, retained] of [["aborted", true], ["failed", false]]) {
    let closed = false;
    const tab = {
      id: `tab-${status}`,
      surfaceId: `surface-${status}`,
      traceId: `trace_${status}`,
      sessionId: `session_${status}_123456`,
      helperPid: process.pid,
      status: "running",
      loading: true,
      lastUsedAt: 1,
      view: {
        setVisible() {},
        webContents: {
          isDestroyed: () => false,
          setBackgroundThrottling() {},
          close: () => { closed = true; },
        },
      },
    };
    const { fixture } = retainedFixture(tab);
    await BrowserHost.prototype.endTurn.call(
      fixture,
      tab.traceId,
      tab.helperPid,
      status,
      false,
      `turn ${status}`,
    );
    assert.equal(fixture.turnTabs.has(tab.id), retained);
    assert.equal(closed, !retained);
  }
});

test("new persistent thread evicts the oldest non-running retained session at the five-tab limit", () => {
  const removed = [];
  const turnTabs = new Map(Array.from({ length: 5 }, (_unused, index) => {
    const id = `tab-${index}`;
    return [id, {
      id,
      ordinal: index + 1,
      traceId: `trace_${index}`,
      sessionId: `session_${index}_123456789012`,
      status: "ready",
      lastUsedAt: index + 1,
      view: { webContents: { isDestroyed: () => false, close() {} } },
    }];
  }));
  const fixture = Object.assign(Object.create(BrowserHost.prototype), {
    turnTabs,
    closedTurnOwners: new Map(),
    selectedTabId: "home",
    window: {
      contentView: {
        removeChildView: view => removed.push(view),
        addChildView() {},
      },
    },
    syncViewVisibility() {},
    publishState() {},
    writeDescriptor() {},
    logger: { info() {} },
  });
  try {
    BrowserHost.prototype.createTurnTab.call(
      fixture, "trace_new", 123, "session_new_123456789",
    );
  } catch {
    // Node launcher tests do not construct a real Electron WebContentsView; eviction happens first.
  }
  assert.equal(turnTabs.has("tab-0"), false);
  assert.equal(turnTabs.size, 4);
  assert.equal(removed.length, 1);
});
