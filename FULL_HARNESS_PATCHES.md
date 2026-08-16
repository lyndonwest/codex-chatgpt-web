# Full Harness patch stack

Baseline: `809557a421b472682e6613c9070f564eaa2608ec` (upstream `main`, `v2.1.10`).
Release tag: `809557a421b472682e6613c9070f564eaa2608ec` (`v2.1.10`).
Previous validated deployment: `91e8615ab8aa1055298d0c8c2c1ab22967f3c607` (2.1.9 stack).

Apply in this order:

1. `lyndon/patch-resume-tool-state` (`7dc98c95f582`) — sparse-resume native tools. Uses raw Responses `tools` vs additive `additional_tools` wire evidence so it does not depend on upstream's removed tool-origin marker. Remove when upstream persists/merges authoritative tool registries.
2. `lyndon/patch-compaction-continuity` (`4d864ba3df03`) — semantic compaction, bounded in-flight tool continuity, post-compaction refresh, trace correlation. This remains distinct from upstream's browser insertion/automatic-compaction transport fixes; remove or shrink as upstream absorbs these continuity contracts.
3. `lyndon/patch-web-turn-resilience` (`ce6bb33439a0`) — bounded 429 cooldown and stalled-progress detection. The 2.1.10 rebase preserves upstream's current tool-approval-card support. Remove per behavior as upstream gains equivalents.
4. `lyndon/patch-composer-fallbacks` (`800c44d6e9ba`) — only shared composer selector fallbacks still absent upstream. Remove when upstream includes equivalent textarea/contenteditable fallbacks.
5. `lyndon/patch-connector-routing` (`b31ab0121d61`) — GitHub default, permissive user-controlled Native2 opt-in, keyboard/multi-pill selection, Native2-before-GitHub dual-app order, and authorization diagnostics. Upstream owns stale connector-catalog refresh/reverification and 2.1.10 approval-card handling; this patch layers routing policy and selection behavior on that path.
6. `lyndon/patch-linux-ci` (`692c7b7f4851`) — Linux-only routine validation for this maintained deployment. Keep only while this fork intentionally validates Linux as its routine target.

Superseded upstream:

- `lyndon/patch-direct-native-tools` — 2.1.9 absorbed the default-`functions` Responses Lite native-tool parsing, and 2.1.10 now preserves the authoritative outer Full Harness tool registry with `tool_mode: null`. Do not restore this patch.
- `lyndon/patch-auth-session-proof` — upstream 2.1.9 requires server-backed ChatGPT session proof and keeps sign-in/model turns in the launcher-owned Electron partition.
