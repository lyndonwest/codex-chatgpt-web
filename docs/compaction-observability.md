# Full Harness compaction observability

The bridge logs one trace/thread correlation record for each Codex Web response turn. Combined with existing browser-turn telemetry, diagnostics can correlate a physical native compaction with the browser prompt before compaction, the semantic-compaction prompt and summary, and the first resumed browser prompt.

Structured ChatGPT account throttles (`429`, `rate_limit_exceeded`) retain their retryable adapter status. The launcher helper adds a shared cooldown for its Web worker before a later browser attempt: 15 seconds after the first throttle, 30 seconds after the second consecutive throttle, and 60 seconds thereafter. A successful browser turn clears the streak. Codex remains responsible for deciding whether a role retry is permitted.

This change does not alter the Web context window, auto-compaction threshold, or semantic checkpoint policy.
