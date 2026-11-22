# Reliable Maryam radar scheduling

Primary: Supabase pg_cron dispatches `job-alert.yml` at :00/:15/:30/:45. An independent cron entry dispatches `radar-health.yml` five minutes later. Existing GitHub concurrency prevents overlapping collectors; delivery claims preserve notification deduplication.

GitHub's scheduler is retained as a backup at :07/:22/:37/:52. A backup skips collection when an actual scan finished in the previous 12 minutes. Manual and Supabase dispatches always run. Gate API errors let the backup run, and permanent delivery claims still prevent repeated job messages.

The watchdog checks the successful `Run job alert` step, not merely a green workflow. Skipped backups do not count as scans. If no actual scan completed for over 45 minutes, it sends a message to Maryam's existing bot, at most once per UTC hour. A Telegram timeout keeps its durable claim and is not retried automatically. The watchdog needs GitHub's runner/API to work; it cannot deliver during a complete GitHub outage. Source HTTP errors remain separately visible in trial metrics.

## Activation

The existing Arash scheduler token returned HTTP 403 for Maryam's repository. It is not modified or reused by this installer.

1. In Maryam's GitHub account create a fine-grained token, restricted to `munich-ai-job-alert`, with **Actions: read and write**. Metadata read is automatic. It does not need code write permission. Choose an expiry that covers the trial.
2. Store it directly in the existing scheduler project's Supabase Vault under **github_maryam_radar_token**. Never paste the token into chat, code, logs or an issue. Project: `pqkautrdrsbnuggxwjqz`.
3. The installer in `scripts/install_scheduler.sql` prepares both cron entries paused. After merging the workflows, test `select radar_scheduler.dispatch_maryam('job-alert.yml');`, and inspect only the corresponding `net._http_response` status. HTTP 204 is expected. Test `radar-health.yml` similarly and confirm both workflow runs exist and complete.
4. Enable the two existing jobs with `cron.alter_job(jobid, active := true)`. Confirm the next scheduled run and a successful scan. Do not treat a queued pg_net request as proof of successful dispatch.

The function uses invoker security in a non-exposed schema; only the cron owner has access. GitHub credentials are read from Vault inside the database and are never returned.

## Rollback

Pause only `maryam-job-radar` and `maryam-job-radar-watchdog`, then revert the scheduling PR. Leave Arash's jobs and Vault token intact. Never reset either radar's notification history or remove delivery claims. The pre-optimization baseline remains available.
