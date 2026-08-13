# Full Harness patch stack

Baseline: `9f744869a5383961ddb9f3b249d1387b258231cd` (upstream `main`, 2.1.9 plus post-release cleanup #113).
Release tag: `7d4e08cf147021d0cf34ea2f3dd5e109ddeb698f` (`v2.1.9`).
Previous validated deployment: `7546963d852cb4f7e54722d0d8db15f74e1901d7` (2.1.8 stack).

Apply in this order:

1. `lyndon/patch-resume-tool-state` (`ee48b162ee83`) — sparse-resume native tools. Uses raw Responses `tools` vs additive `additional_tools` wire evidence so it does not depend on upstream's removed tool-origin marker. Remove when upstream persists/merges authoritative tool registries.
2. `lyndon/patch-compaction-continuity` (`2ee829882bf4`) — semantic compaction, bounded in-flight tool continuity, post-compaction refresh, trace correlation. This remains distinct from 2.1.9's browser insertion/automatic-compaction transport fixes; remove or shrink as upstream absorbs these continuity contracts.
3. `lyndon/patch-web-turn-resilience` (`4aad45a5e56f`) — bounded 429 cooldown and stalled-progress detection. Remove per behavior as upstream gains equivalents.
4. `lyndon/patch-composer-fallbacks` (`89dc7b5d4214`) — only shared composer selector fallbacks still absent upstream. Remove when upstream includes equivalent textarea/contenteditable fallbacks.
5. `lyndon/patch-connector-routing` (`5f0f46e8a899`) — GitHub default, fail-closed Native2 opt-in, keyboard/multi-pill selection, Native2-before-GitHub dual-app order. Upstream 2.1.9 owns stale connector-catalog refresh/reverification; this patch layers routing policy and selection behavior on that path.
6. `lyndon/patch-linux-ci` (`74b3cf7cabd6`) — Linux-only routine validation for this maintained deployment. Keep only while this fork intentionally validates Linux as its routine target.

Removed on 2.1.9:

- `lyndon/patch-direct-native-tools` — upstream 2.1.9 now preserves Responses Lite native `exec` in the default `functions` namespace and keeps the native Full Harness tool mode.
- `lyndon/patch-auth-session-proof` — upstream 2.1.9 now requires server-backed ChatGPT session proof and keeps sign-in/model turns in the launcher-owned Electron partition.
