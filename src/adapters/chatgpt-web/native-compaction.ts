import { defaultBrokerEndpoint, resolveBrokerEndpoint } from "../../config";
import { parseDataUrl } from "../image";
import type { CodexContentPart, CodexParsedRequest, CodexProviderConfig, CodexToolResultMessage } from "../../types";
import { extractChatGptTurnIdentity } from "./environment";
import { chatGptCompactionSourceExecutionKey, chatGptTurnSessions, type ChatGptTurnSession } from "./turn-execution";
import { TurnBroker, type BrokerToolResult } from "./turn-broker";

export interface NativeCompactionContinuation {
  activeBrowserSession: boolean;
  deliveredToolResults: number;
  browserCompactionRequired: boolean;
}

/** One live browser execution may survive one native Codex compaction only to finish an in-flight tool handoff. */
const preservedNativeCompactions = new WeakSet<ChatGptTurnSession>();

function brokerSocketPath(provider: CodexProviderConfig): string {
  const configured = provider.chatgptWeb?.brokerSocketPath?.trim();
  return resolveBrokerEndpoint(configured || defaultBrokerEndpoint());
}

function structuredContent(text: string): unknown | undefined {
  try {
    const parsed: unknown = JSON.parse(text);
    return parsed !== null && typeof parsed === "object" ? parsed : undefined;
  } catch {
    return undefined;
  }
}

function brokerContent(content: string | CodexContentPart[]): unknown[] {
  if (typeof content === "string") return [{ type: "text", text: content }];
  return content.map(part => {
    if (part.type === "text") return { type: "text", text: part.text };
    const parsed = parseDataUrl(part.imageUrl);
    if (parsed) return { type: "image", data: parsed.base64, mimeType: parsed.mediaType };
    return { type: "resource_link", uri: part.imageUrl, name: "Codex tool image", mimeType: "image/*" };
  });
}

function brokerResult(message: CodexToolResultMessage): BrokerToolResult {
  const content = brokerContent(message.content);
  const text = typeof message.content === "string"
    ? message.content
    : message.content.filter(part => part.type === "text").map(part => part.text).join("\n");
  const structured = structuredContent(text);
  return {
    content,
    ...(structured !== undefined ? { structuredContent: structured } : {}),
    ...(message.isError ? { isError: true } : {}),
  };
}

function currentToolResults(parsed: CodexParsedRequest, session: ChatGptTurnSession): CodexToolResultMessage[] {
  const byId = new Map<string, CodexToolResultMessage>();
  for (const message of parsed.context.messages) {
    if (message.role !== "toolResult" || !session.hasOutstanding(message.toolCallId)) continue;
    if (byId.has(message.toolCallId)) throw new Error(`Codex returned duplicate results for tool call ${message.toolCallId}`);
    byId.set(message.toolCallId, message);
  }
  return [...byId.values()];
}

export async function continueChatGptWebAcrossNativeCompaction(
  parsed: CodexParsedRequest,
  provider: CodexProviderConfig,
): Promise<NativeCompactionContinuation> {
  const identity = extractChatGptTurnIdentity(parsed);
  if (!identity.threadId) {
    return { activeBrowserSession: false, deliveredToolResults: 0, browserCompactionRequired: false };
  }
  const threadId = identity.threadId;

  const sourceExecutionKey = chatGptCompactionSourceExecutionKey(parsed);
  const active = chatGptTurnSessions.markNativeCompactionContinuation(threadId, sourceExecutionKey);
  if (!active) {
    return { activeBrowserSession: false, deliveredToolResults: 0, browserCompactionRequired: false };
  }

  try {
    return await active.session.runExclusive(async () => {
      const outstanding = active.session.outstanding();

      // Preservation exists only to avoid dropping an already-issued native tool handoff. If the
      // browser has no unresolved tool call, Codex compaction is already a safe semantic boundary:
      // retire the near-full browser now and let the dedicated compaction LLM produce the checkpoint.
      if (outstanding.length === 0) {
        chatGptTurnSessions.rollbackNativeCompactionContinuation(threadId, sourceExecutionKey);
        preservedNativeCompactions.delete(active.session);
        chatGptTurnSessions.retire(active.key, active.session);
        console.warn(
          `[chatgpt-web] retired browser at native Codex compaction with no outstanding tools `
          + `(thread=${threadId})`,
        );
        return { activeBrowserSession: false, deliveredToolResults: 0, browserCompactionRequired: false };
      }

      // A browser may cross one compaction only to consume the result of the tool it already asked
      // for. If it reaches compaction again, stop extending that old model context; the canonical
      // history already carries the tool evidence for the semantic compaction/fresh-browser path.
      if (preservedNativeCompactions.has(active.session)) {
        chatGptTurnSessions.rollbackNativeCompactionContinuation(threadId, sourceExecutionKey);
        preservedNativeCompactions.delete(active.session);
        chatGptTurnSessions.retire(active.key, active.session);
        console.warn(
          `[chatgpt-web] retired browser at repeated native Codex compaction `
          + `(thread=${threadId}, outstanding_tools=${outstanding.length})`,
        );
        return { activeBrowserSession: false, deliveredToolResults: 0, browserCompactionRequired: true };
      }

      if (active.session.runtime.mode !== "tools") {
        throw new Error("Native Codex compaction found outstanding tools on a read-only ChatGPT Web runtime");
      }
      const results = currentToolResults(parsed, active.session);
      if (results.length !== outstanding.length) {
        throw new Error(
          `Native Codex compaction carried ${results.length} of ${outstanding.length} completed ChatGPT tool results`,
        );
      }
      const broker = TurnBroker.forSocket(brokerSocketPath(provider));
      const turnToken = await active.session.runtime.token;
      for (const message of results) {
        broker.completeTool(turnToken, message.toolCallId, brokerResult(message));
        active.session.markResultDelivered(message.toolCallId);
      }
      preservedNativeCompactions.add(active.session);
      console.warn(
        `[chatgpt-web] continued live browser execution across native Codex compaction `
        + `(thread=${threadId}, delivered_results=${results.length})`,
      );
      return { activeBrowserSession: true, deliveredToolResults: results.length, browserCompactionRequired: false };
    });
  } catch (error) {
    preservedNativeCompactions.delete(active.session);
    chatGptTurnSessions.rollbackNativeCompactionContinuation(threadId, sourceExecutionKey);
    throw error;
  }
}
