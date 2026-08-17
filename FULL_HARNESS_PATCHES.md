# Full Harness patch stack

Baseline: `3baa1749aa52dab24fea1895d0c32af7b58c5bc0` (upstream `main`, `v2.1.11`).

Apply the maintained branches in this order. Every branch is the direct child of the
preceding boundary, so the combined stack has ordinary linear ancestry from upstream.

1. `Lyndon/patch-composer-atomic-fill` (`1028365886e2`) — generic, upstreamable atomic composer fill with exact verification. Connector pills are prepended only after the full prompt is proven intact; bounded edits remain a verified fallback.
2. `Lyndon/patch-tunnel-startup-race` (`298e5ad3fd05`) — generic launcher recovery for a tunnel control command that exits while its managed process is still becoming ready. Genuine no-process failures still fail immediately, and readiness remains bounded.
3. `Lyndon/patch-resume-tool-state` (`32b8c59`) — sparse-resume native tool continuity. Remove when upstream persists and merges authoritative tool registries.
4. `Lyndon/patch-compaction-continuity` (`a418cfd`) — semantic compaction, bounded in-flight tool continuity, post-compaction refresh, and trace correlation.
5. `Lyndon/patch-web-turn-resilience` (`d5f00ef`) — bounded 429 cooldown and stalled-progress detection. Upstream's three-retry browser-turn budget remains authoritative.
6. `Lyndon/patch-composer-fallbacks` (`dbdf795`) — shared textarea and contenteditable selector fallbacks only. Atomic fill and generic bounded recovery belong to patch 1.
7. `Lyndon/patch-connector-routing` (`2fa13cd`) — GitHub default, keyboard and multi-pill selection, and Native2-before-GitHub order. No textual Native2 authorization shim is present.
8. `Lyndon/patch-linux-ci` (`8ad14f9`) — Linux-only routine validation for this maintained deployment.

The combined maintained tip is published as `Lyndon/full-harness-stack`, matching the
deployment installer. Lowercase legacy branches remain available only as safety history
until the replacement stack and pull requests are confirmed.
