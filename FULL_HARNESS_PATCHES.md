# Full Harness patch stack

Baseline: `bda266b45c0e9d73c7a6e932a7c556954f9cea9c` (upstream `main`, 2.1.8).
Previous validated deployment: `1daa876ec4307d631ef0e30ea7034129989d713f`.

Apply in this order:

1. `lyndon/patch-resume-tool-state` (`c665e809923f`) — sparse-resume native tools. Remove when upstream persists/merges authoritative tool registries.
2. `lyndon/patch-direct-native-tools` (`f427b02af8c4`) — Direct-mode/`functions` native-tool compatibility. Remove when upstream/current Codex preserves the native command surface without it.
3. `lyndon/patch-compaction-continuity` (`b97fddde3910`) — semantic compaction, bounded in-flight tool continuity, post-compaction refresh, trace correlation. This remains distinct from 2.1.8's long-prompt writer fix; remove/shrink as upstream absorbs these continuity contracts.
4. `lyndon/patch-web-turn-resilience` (`50f8f503f824`) — bounded 429 cooldown and stalled-progress detection. Remove per behavior as upstream gains equivalents.
5. `lyndon/patch-composer-fallbacks` (`fa3ac32e52b3`) — only selector fallbacks still absent upstream. Remove when upstream's shared composer selector includes equivalent fallbacks.
6. `lyndon/patch-connector-routing` (`a2723a8706da`) — GitHub default, fail-closed Native2 opt-in, keyboard/multi-pill selection, Native2-before-GitHub dual-app order. As of 2.1.8, prompt insertion/re-anchor/cancellation is intentionally upstream-owned and excluded from this patch.
7. `lyndon/patch-linux-ci` (`aaa849bb7227`) — Linux-only routine validation for this maintained deployment. Keep only while this fork intentionally validates Linux as its routine target.
8. `lyndon/patch-auth-session-proof` (`2654b4617555`) — require server-owned `/api/auth/session` proof before system-browser login capture/import, preventing anonymous Temporary Chat UI from being mistaken for authentication. Temporary; remove when upstream lands equivalent server-session verification.
