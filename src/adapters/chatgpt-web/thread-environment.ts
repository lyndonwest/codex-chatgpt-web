import { existsSync, readFileSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";
import { atomicWriteFile } from "../../config";
import { namespacedToolName, type CodexParsedRequest, type CodexTool } from "../../types";
import {
  extractChatGptTurnEnvironment,
  extractChatGptTurnIdentity,
  MissingTrustedCodexEnvironmentError,
  type ChatGptSandboxPolicy,
  type ChatGptTurnEnvironment,
} from "./environment";

interface StoredThreadEnvironment {
  cwd: string;
  roots: string[];
  writableRoots: string[];
  sandboxPolicy: ChatGptSandboxPolicy;
  tools?: CodexTool[];
  updatedAt: number;
}

interface StoredThreadEnvironmentFile {
  version: 1;
  threads: Record<string, StoredThreadEnvironment>;
}

const MAX_THREAD_ENVIRONMENTS = 256;
const THREAD_ENVIRONMENT_TTL_MS = 30 * 24 * 60 * 60_000;

function record(value: unknown): Record<string, unknown> | undefined {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function pathIdentity(value: string): string {
  const normalized = resolve(value);
  return process.platform === "win32" ? normalized.toLowerCase() : normalized;
}

function contains(root: string, path: string): boolean {
  const rel = relative(pathIdentity(root), pathIdentity(path));
  return rel === "" || (!rel.startsWith("..") && !isAbsolute(rel));
}

function absolutePaths(value: unknown, field: string): string[] {
  if (!Array.isArray(value) || value.length === 0 || value.some(path => typeof path !== "string" || !isAbsolute(path))) {
    throw new Error(`Invalid persisted ChatGPT thread ${field}`);
  }
  const unique = new Map<string, string>();
  for (const path of value.map(path => resolve(path as string))) {
    if (!unique.has(pathIdentity(path))) unique.set(pathIdentity(path), path);
  }
  return [...unique.values()];
}

function sandboxPolicy(value: unknown, roots: string[], writableRoots: string[]): ChatGptSandboxPolicy {
  const parsed = record(value);
  if (parsed?.type === "dangerFullAccess") {
    const rootIdentities = new Set(roots.map(pathIdentity));
    if (writableRoots.length !== roots.length || writableRoots.some(path => !rootIdentities.has(pathIdentity(path)))) {
      throw new Error("Invalid persisted ChatGPT danger-full-access roots");
    }
    return { type: "dangerFullAccess" };
  }
  if (parsed?.type === "workspaceWrite") {
    if (typeof parsed.networkAccess !== "boolean" || writableRoots.some(path => !roots.some(root => contains(root, path)))) {
      throw new Error("Invalid persisted ChatGPT workspace-write policy");
    }
    return { type: "workspaceWrite", writableRoots, networkAccess: parsed.networkAccess };
  }
  if (parsed?.type === "readOnly") {
    if (typeof parsed.networkAccess !== "boolean" || writableRoots.length !== 0) {
      throw new Error("Invalid persisted ChatGPT read-only policy");
    }
    return { type: "readOnly", networkAccess: parsed.networkAccess };
  }
  throw new Error("Invalid persisted ChatGPT sandbox policy");
}

function storedTool(value: unknown): CodexTool {
  const parsed = record(value);
  const parameters = record(parsed?.parameters);
  if (!parsed || typeof parsed.name !== "string" || typeof parsed.description !== "string" || !parameters) {
    throw new Error("Invalid persisted ChatGPT thread tool");
  }
  const tool: CodexTool = { name: parsed.name, description: parsed.description, parameters };
  for (const field of ["strict", "freeform", "toolSearch", "loadedFromToolSearch", "webSearch"] as const) {
    if (parsed[field] !== undefined) {
      if (typeof parsed[field] !== "boolean") throw new Error(`Invalid persisted ChatGPT tool ${field}`);
      tool[field] = parsed[field] as boolean;
    }
  }
  if (parsed.namespace !== undefined) {
    if (typeof parsed.namespace !== "string") throw new Error("Invalid persisted ChatGPT tool namespace");
    tool.namespace = parsed.namespace;
  }
  return tool;
}

function storedTools(value: unknown): CodexTool[] {
  if (value === undefined) return [];
  if (!Array.isArray(value)) throw new Error("Invalid persisted ChatGPT thread tools");
  return value.map(storedTool);
}

function mergeTools(previous: readonly CodexTool[], current: readonly CodexTool[]): CodexTool[] {
  const merged = new Map<string, CodexTool>();
  for (const tool of previous) merged.set(namespacedToolName(tool.namespace, tool.name), structuredClone(tool));
  for (const tool of current) merged.set(namespacedToolName(tool.namespace, tool.name), structuredClone(tool));
  return [...merged.values()];
}

function rawRequestDeclaresTools(parsed: CodexParsedRequest): boolean {
  const body = record(parsed._rawBody);
  if (!body) return false;
  if (Object.prototype.hasOwnProperty.call(body, "tools")) return true;
  const input = Array.isArray(body.input) ? body.input : [];
  return input.some(item => record(item)?.type === "additional_tools");
}

function currentToolsAreAuthoritative(parsed: CodexParsedRequest): boolean {
  if (rawRequestDeclaresTools(parsed)) return true;
  return (parsed.context.tools ?? []).some(tool => tool.loadedFromToolSearch !== true);
}

function resolveTools(parsed: CodexParsedRequest, stored?: StoredThreadEnvironment): CodexTool[] {
  const current = parsed.context.tools ?? [];
  if (currentToolsAreAuthoritative(parsed) || !stored) return structuredClone(current);
  return mergeTools(stored.tools ?? [], current);
}

function validateStoredEnvironment(value: unknown): StoredThreadEnvironment {
  const parsed = record(value);
  if (!parsed || typeof parsed.cwd !== "string" || !isAbsolute(parsed.cwd) || typeof parsed.updatedAt !== "number") {
    throw new Error("Invalid persisted ChatGPT thread environment");
  }
  const cwd = resolve(parsed.cwd);
  const roots = absolutePaths(parsed.roots, "roots");
  const writableRoots = Array.isArray(parsed.writableRoots) && parsed.writableRoots.length === 0
    ? []
    : absolutePaths(parsed.writableRoots, "writable roots");
  if (!roots.some(root => contains(root, cwd))) throw new Error("Persisted ChatGPT cwd is outside its roots");
  return {
    cwd,
    roots,
    writableRoots,
    sandboxPolicy: sandboxPolicy(parsed.sandboxPolicy, roots, writableRoots),
    tools: storedTools(parsed.tools),
    updatedAt: parsed.updatedAt,
  };
}

function authority(environment: ChatGptTurnEnvironment, updatedAt: number): StoredThreadEnvironment {
  return {
    cwd: environment.cwd,
    roots: environment.roots,
    writableRoots: environment.writableRoots,
    sandboxPolicy: environment.sandboxPolicy,
    tools: structuredClone(environment.tools),
    updatedAt,
  };
}

/**
 * Codex emits its trusted environment envelope and full native tool registry when a task starts or
 * those capabilities change, but follow-up/resume requests can omit either. Persist the last
 * authoritative per-thread values and merge only deferred tool_search additions when a later
 * request omits the base registry. An explicitly supplied registry (including an empty one)
 * replaces the stored tools instead of accumulating stale capabilities.
 */
export class ChatGptThreadEnvironmentStore {
  private loaded = false;
  private readonly threads = new Map<string, StoredThreadEnvironment>();

  constructor(
    private readonly path?: string,
    private readonly now: () => number = Date.now,
  ) {}

  resolve(parsed: CodexParsedRequest): ChatGptTurnEnvironment {
    const identity = extractChatGptTurnIdentity(parsed);
    const stored = identity.threadId ? this.get(identity.threadId) : undefined;
    try {
      const environment = extractChatGptTurnEnvironment(parsed);
      const resolved = { ...environment, tools: resolveTools(parsed, stored) };
      if (identity.threadId) this.set(identity.threadId, resolved);
      return resolved;
    } catch (error) {
      if (!(error instanceof MissingTrustedCodexEnvironmentError) || !identity.threadId) throw error;
      if (!stored) throw error;
      const resolved: ChatGptTurnEnvironment = {
        cwd: stored.cwd,
        roots: stored.roots,
        writableRoots: stored.writableRoots,
        sandboxPolicy: stored.sandboxPolicy,
        tools: resolveTools(parsed, stored),
      };
      this.set(identity.threadId, resolved);
      return resolved;
    }
  }

  private get(threadId: string): StoredThreadEnvironment | undefined {
    this.load();
    const stored = this.threads.get(threadId);
    if (!stored) return undefined;
    if (this.now() - stored.updatedAt > THREAD_ENVIRONMENT_TTL_MS) {
      this.threads.delete(threadId);
      this.persist();
      return undefined;
    }
    return stored;
  }

  private set(threadId: string, environment: ChatGptTurnEnvironment): void {
    this.load();
    this.threads.delete(threadId);
    this.threads.set(threadId, authority(environment, this.now()));
    while (this.threads.size > MAX_THREAD_ENVIRONMENTS) {
      const oldest = this.threads.keys().next().value as string | undefined;
      if (!oldest) break;
      this.threads.delete(oldest);
    }
    this.persist();
  }

  private load(): void {
    if (this.loaded) return;
    this.loaded = true;
    if (!this.path || !existsSync(this.path)) return;
    const parsed = JSON.parse(readFileSync(this.path, "utf8")) as Partial<StoredThreadEnvironmentFile>;
    const rawThreads = record(parsed.threads);
    if (parsed.version !== 1 || !rawThreads) {
      throw new Error(`Invalid ChatGPT thread environment store: ${this.path}`);
    }
    const cutoff = this.now() - THREAD_ENVIRONMENT_TTL_MS;
    const entries = Object.entries(rawThreads)
      .map(([threadId, value]) => [threadId, validateStoredEnvironment(value)] as const)
      .filter(([, environment]) => environment.updatedAt >= cutoff)
      .sort((left, right) => left[1].updatedAt - right[1].updatedAt)
      .slice(-MAX_THREAD_ENVIRONMENTS);
    for (const [threadId, environment] of entries) this.threads.set(threadId, environment);
  }

  private persist(): void {
    if (!this.path) return;
    const payload: StoredThreadEnvironmentFile = {
      version: 1,
      threads: Object.fromEntries(this.threads),
    };
    atomicWriteFile(this.path, `${JSON.stringify(payload, null, 2)}\n`);
  }
}
