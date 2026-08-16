import type { CodexParsedRequest } from "../../types";

/**
 * Native2 is available for every normal ChatGPT Web turn when local tools are
 * configured globally. Compaction is internal context maintenance and must remain
 * tool-free.
 */
export function chatGptNative2Allowed(parsed: CodexParsedRequest): boolean {
  const allowed = !parsed._compactionRequest;
  console.info(
    `[chatgpt-web] native2 availability allowed=${allowed}`
    + ` source=${allowed ? "default" : "compaction"}`,
  );
  return allowed;
}
