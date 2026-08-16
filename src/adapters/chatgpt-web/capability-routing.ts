import type { CodexContentPart, CodexParsedRequest } from "../../types";

function userMessageText(content: string | CodexContentPart[]): string {
  if (typeof content === "string") return content;
  return content
    .filter(part => part.type === "text")
    .map(part => part.type === "text" ? part.text : "")
    .join("\n");
}

interface Native2AuthorizationSignal {
  allowed: boolean;
  source: "explicit-directive" | "explicit-negative" | "user-mention";
}

const NATIVE2_NAME = /\b(?:codex\s+)?native\s*2\b/i;
const NATIVE2_DIRECTIVE = /native2_allowed\s*[:=]\s*(true|false)/gi;
const NATIVE2_NEGATIVE = /(?:\bdo\s+not\b|\bdon['’]?t\b|\bnever\b)\s+(?:use|invoke|call|attach|enable|allow|authorize|expose|connect)\s+(?:codex\s+)?native\s*2\b|\b(?:disable|forbid|deny)\s+(?:codex\s+)?native\s*2\b|\b(?:without|no)\s+(?:codex\s+)?native\s*2\b|\b(?:codex\s+)?native\s*2\b[^\n.]{0,48}\b(?:not\s+allowed|disallowed|disabled|forbidden|denied|(?:should|must)\s+not\s+(?:be\s+)?(?:used|invoked|called|attached|enabled|allowed))\b/i;

function native2AuthorizationSignal(text: string): Native2AuthorizationSignal | undefined {
  // Keep the explicit machine-readable switch authoritative when it is present, while accepting
  // Markdown wrappers/bullets because the match is no longer anchored to the whole line.
  const directives = [...text.matchAll(NATIVE2_DIRECTIVE)];
  const latestDirective = directives.at(-1);
  if (latestDirective) {
    return {
      allowed: latestDirective[1]!.toLowerCase() === "true",
      source: "explicit-directive",
    };
  }

  if (NATIVE2_NEGATIVE.test(text)) {
    return { allowed: false, source: "explicit-negative" };
  }

  // Native2 is a low-consequence opt-in for this deployment. Prefer an occasional false positive
  // over silently withholding the connector when the user's prose clearly refers to it.
  if (NATIVE2_NAME.test(text)) {
    return { allowed: true, source: "user-mention" };
  }
  return undefined;
}

/**
 * Native2 authorization is user-controlled and sticky across the accumulated Web task context.
 * Developer/system text cannot authorize local access. The newest user message carrying a Native2
 * signal wins; compaction always disables local tools.
 */
export function chatGptNative2Allowed(parsed: CodexParsedRequest): boolean {
  if (parsed._compactionRequest) {
    console.info("[chatgpt-web] native2 authorization allowed=false source=compaction");
    return false;
  }
  for (let messageIndex = parsed.context.messages.length - 1; messageIndex >= 0; messageIndex -= 1) {
    const message = parsed.context.messages[messageIndex]!;
    if (message.role !== "user") continue;
    const signal = native2AuthorizationSignal(userMessageText(message.content));
    if (!signal) continue;
    console.info(
      `[chatgpt-web] native2 authorization allowed=${signal.allowed}`
      + ` source=${signal.source}`
      + ` user_message_from_end=${parsed.context.messages.length - 1 - messageIndex}`,
    );
    return signal.allowed;
  }
  console.info("[chatgpt-web] native2 authorization allowed=false source=no-user-signal");
  return false;
}
