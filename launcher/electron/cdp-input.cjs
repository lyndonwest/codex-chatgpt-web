async function withWebContentsDebugger(debuggerClient, action) {
  if (!debuggerClient || typeof debuggerClient.sendCommand !== "function") {
    throw new Error("Electron WebContents debugger is unavailable");
  }
  const ownedAttachment = !debuggerClient.isAttached();
  if (ownedAttachment) debuggerClient.attach("1.3");
  try {
    return await action((method, params = {}) => debuggerClient.sendCommand(method, params));
  } finally {
    if (ownedAttachment && debuggerClient.isAttached()) debuggerClient.detach();
  }
}

async function dispatchTrustedKey({ debuggerClient, key }) {
  const virtualKeyCode = key === "Enter" ? 13
    : key === "ArrowLeft" ? 37
      : key === "ArrowRight" ? 39
        : undefined;
  if (virtualKeyCode === undefined) throw new Error(`Unsupported CDP key: ${String(key)}`);
  const event = {
    key,
    code: key,
    windowsVirtualKeyCode: virtualKeyCode,
    nativeVirtualKeyCode: virtualKeyCode,
  };
  await withWebContentsDebugger(debuggerClient, async (sendCommand) => {
    await sendCommand("Input.dispatchKeyEvent", {
      ...event,
      type: "keyDown",
      ...(key === "Enter" ? { text: "\r", unmodifiedText: "\r" } : {}),
    });
    await sendCommand("Input.dispatchKeyEvent", {
      ...event,
      type: "keyUp",
    });
  });
}

async function dispatchTrustedClick({ debuggerClient, point }) {
  if (!Number.isFinite(point?.x) || !Number.isFinite(point?.y)) {
    throw new Error("CDP click point is invalid");
  }
  const position = { x: point.x, y: point.y };
  await withWebContentsDebugger(debuggerClient, async (sendCommand) => {
    await sendCommand("Input.dispatchMouseEvent", {
      ...position,
      type: "mouseMoved",
      button: "none",
    });
    await sendCommand("Input.dispatchMouseEvent", {
      ...position,
      type: "mousePressed",
      button: "left",
      clickCount: 1,
    });
    await sendCommand("Input.dispatchMouseEvent", {
      ...position,
      type: "mouseReleased",
      button: "left",
      clickCount: 1,
    });
  });
}

async function evaluatePage({ debuggerClient, expression }) {
  if (typeof expression !== "string" || !expression.trim()) {
    throw new Error("CDP evaluation expression is required");
  }
  return await withWebContentsDebugger(debuggerClient, async (sendCommand) => {
    const response = await sendCommand("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (response?.exceptionDetails) {
      const detail = response.exceptionDetails.exception?.description
        || response.exceptionDetails.text
        || "unknown page exception";
      throw new Error(`CDP page evaluation failed: ${detail}`);
    }
    return response?.result?.value;
  });
}

module.exports = {
  dispatchTrustedClick,
  dispatchTrustedKey,
  evaluatePage,
  withWebContentsDebugger,
};
