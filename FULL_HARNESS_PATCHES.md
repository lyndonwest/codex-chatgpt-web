# Full Harness patch stack

Baseline: `3baa1749aa52dab24fea1895d0c32af7b58c5bc0` (upstream `main`, `v2.1.11`).
Release tag: `3baa1749aa52dab24fea1895d0c32af7b58c5bc0` (`v2.1.11`).
Previous validated deployment: `4eb2d2c613259e3a7d08bedf1d1a65c0d2ba8d03` (2.1.10 stack).

Apply in this order:

1. `lyndon/patch-resume-tool-state` (`541cce13c257`) — sparse-resume native tools. Uses raw Responses `tools` vs additive `additional_tools` wire evidence so it does not depend on upstream's removed tool-origin marker. Remove when upstream persists/merges authoritative tool registries.
2. `lyndon/patch-compaction-continuity` (`550f97960007`) — semantic compaction, bounded in-flight tool continuity, post-compaction refresh, trace correlation. Upstream 2.1.11's stable per-native-turn retry key remains distinct from this execution-key/continuity layer. Remove or shrink as upstream absorbs these continuity contracts.
3. `lyndon/patch-web-turn-resilience` (`0718f63c67d0`) — bounded 429 cooldown and stalled-progress detection. Upstream 2.1.11 adds a separate three-retry browser-turn budget; keep this patch while its cooldown/stall behaviors remain absent upstream.
4. `lyndon/patch-composer-fallbacks` (`90d942e39da1`) — only shared composer selector fallbacks still absent upstream. Remove when upstream includes equivalent textarea/contenteditable fallbacks.
5. `lyndon/patch-connector-routing` (`79c2d425055c`) — GitHub default, keyboard/multi-pill selection, and Native2-before-GitHub dual-app order. Upstream owns normal-turn Native2 availability, compaction tool-free behavior, retry budgeting, stale connector-catalog refresh/reverification, and approval-card handling; this patch now layers only connector routing/selection behavior on that path.
6. `lyndon/patch-linux-ci` (`6cd7785ef04c`) — Linux-only routine validation for this maintained deployment. Keep only while this fork intentionally validates Linux as its routine target.

Superseded upstream:

- The local `capability-routing.ts` Native2 availability shim and its dedicated test were removed in the 2.1.11 rebase because upstream already enables configured local tools for normal turns and disables them for compaction.
- `lyndon/patch-direct-native-tools` — 2.1.9 absorbed the default-`functions` Responses Lite native-tool parsing, and 2.1.10 preserves the authoritative outer Full Harness tool registry with `tool_mode: null`. Do not restore this patch.
- `lyndon/patch-auth-session-proof` — upstream 2.1.9 requires server-backed ChatGPT session proof and keeps sign-in/model turns in the launcher-owned Electron partition.
