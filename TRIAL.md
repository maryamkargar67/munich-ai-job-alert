# Two-week optimization trial

Baseline: `baseline/pre-optimization-2026-11-22`, commit `818904228d8b90bd7dac019cae53af9a5a9d5376`.
Trial starts when this PR is merged into main; observe for 14 days. Existing source list, queries, 100-km Munich scope, student/part-time rules, match thresholds and Telegram bot are retained. Only main posts; PR tests use mocks and temporary databases.

Reliability: the existing jobs table stores canonical-URL delivery reservations before sending. Existing history is read once per run and preserved. Concurrent claims use the existing job_id unique constraint. An uncertain/failed Telegram attempt is held for manual investigation, never automatically retried. This favors avoiding duplicate messages over retrying uncertain deliveries. Claims have `delivery:` IDs and are not ordinary source results. No destructive migrations are required.

A new source's entire first matching batch is stored without sending; source_state is marked after both job lanes complete. Source-state/history failures abort instead of pretending the source is uninitialized. SQLite's missing columns and source_state are repaired locally; Actions requires the persistent Supabase configuration.

Discovery: short 2/3/6-hour lookbacks now overlap for 24 hours; existing BMW 48-hour lookback is unchanged. This covers recent observed schedule gaps, but cannot guarantee recovery after outages exceeding these windows or upstream pagination limits. Already-seen LinkedIn and Infineon jobs skip detail work; shared Infineon details are cached per run. Missing LinkedIn descriptions are deferred. German-level checks are shared across sources and English C1 is not a German requirement. Distant hybrid offices require explicit Germany-wide remote wording.

Monitor Actions summaries, per-source result/time/error counts and `radar-trial-*` artifacts retained 30 days. Compare suitable alerts, irrelevant jobs, publication-to-receipt delay, zero-result sources and HTTP errors. A successful process with blocked sources is explicitly marked with warnings; source outages are not called healthy empty results. Publication timestamps vary by source, so compare receipt time to the public posting for a sample of alerts.

Rollback: revert this optimization PR using a new revert PR; run quality gates and merge. Never reset jobs/source_state, delete delivery claims, or restore a database snapshot. Preserve job IDs and all history, including uncertain reservations. Old code lacks cross-source claiming, so investigate any uncertain delivery before changing its history or manually retrying it.
