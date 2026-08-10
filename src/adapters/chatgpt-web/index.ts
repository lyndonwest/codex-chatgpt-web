import { createHash } from "node:crypto";
import type { CodexProviderConfig } from "../../types";
import type { ProviderAdapter } from "../base";
import { extractChatGptTurnIdentity } from "./environment";
import { createChatGptWebAdapter as createBaseChatGptWebAdapter } from "./index-base";
import { chatGptTurnExecutionKey } from "./turn-execution";

/**
 * Keep one explicit trace/thread mapping in launcher logs. Browser-host lifecycle records already
 * carry traceId/surfaceId; adding the Codex thread here lets diagnostics correlate retirements,
 * fresh surfaces, prompt-token measurements and compaction boundaries without timestamp guessing.
 */
export function createChatGptWebAdapter(provider: CodexProviderConfig): ProviderAdapter {
  const adapter = createBaseChatGptWebAdapter(provider);
  const executionNamespace = createHash("sha256").update(JSON.stringify({
    baseUrl: provider.baseUrl,
    chatgptWeb: provider.chatgptWeb ?? {},
  })).digest("hex");

  return {
    ...adapter,
    async runTurn(parsed, incoming, emit) {
      // The base adapter owns the explicit opaque-V2 fail-closed error. Avoid deriving a normal
      // browser execution key first, because opaque V2 payloads intentionally lack that identity.
      if (!parsed._opaqueMultiAgentV2Payload) {
        const executionKey = `${executionNamespace}:${chatGptTurnExecutionKey(parsed)}`;
        const traceId = createHash("sha256").update(executionKey).digest("hex").slice(0, 12);
        const identity = extractChatGptTurnIdentity(parsed);
        console.info(
          `[chatgpt-web] trace correlation trace=${traceId}`
          + ` thread=${identity.threadId ?? "none"}`
          + ` turn=${identity.turnId ?? "none"}`
          + ` previous_response_id=${parsed.previousResponseId ?? "none"}`
          + ` compaction=${parsed._compactionRequest ? 1 : 0}`,
        );
      }
      return adapter.runTurn(parsed, incoming, emit);
    },
  };
}
