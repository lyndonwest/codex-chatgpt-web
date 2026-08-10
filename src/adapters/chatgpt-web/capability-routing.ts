import type { CodexContentPart, CodexParsedRequest } from "../../types";

function userMessageText(content: string | CodexContentPart[]): string {
  if (typeof content === "string") return content;
  return content
    .filter(part => part.type === "text")
    .map(part => part.type === "text" ? part.text : "")
    .join("\n");
}

/**
 * Native2 is fail-closed per Web phase. The most recent explicit directive in user-role
 * task packets wins; developer/system text cannot accidentally authorize local access.
 */
export function chatGptNative2Allowed(parsed: CodexParsedRequest): boolean {
  if (parsed._compactionRequest) return false;
  for (let messageIndex = parsed.context.messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
    const message = parsed.context.messages[messageIndex]!;
    if (message.role !== "user") continue;
    const lines = userMessageText(message.content).split(/\r?\n/);
    for (let lineIndex = lines.length - 1; lineIndex >= 0; lineIndex -= 1) {
      const match = lines[lineIndex]!.match(/^\s*native2_allowed:\s*(true|false)\s*$/i);
      if (match) return match[1]!.toLowerCase() === "true";
    }
  }
  return false;
}
