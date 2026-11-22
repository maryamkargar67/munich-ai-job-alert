-- Run in the existing scheduler project. No secret values belong in this file.
-- A dedicated GitHub token is read from Vault at dispatch time.
begin;
create schema if not exists radar_scheduler;
revoke all on schema radar_scheduler from public, anon, authenticated, service_role;

create or replace function radar_scheduler.dispatch_maryam(workflow_file text default 'job-alert.yml')
returns bigint
language plpgsql
security invoker
set search_path = pg_catalog
as $function$
declare
    github_token text;
    request_id bigint;
begin
    if workflow_file not in ('job-alert.yml', 'radar-health.yml') or workflow_file is null then
        raise exception 'Unsupported Maryam workflow';
    end if;
    select decrypted_secret into github_token
    from vault.decrypted_secrets
    where name = 'github_maryam_radar_token'
    limit 1;
    if github_token is null or length(trim(github_token)) = 0 then
        raise exception 'github_maryam_radar_token is missing in Vault';
    end if;
    select net.http_post(
        url := 'https://api.github.com/repos/maryamkargar67/munich-ai-job-alert/actions/workflows/' || workflow_file || '/dispatches',
        headers := jsonb_build_object(
            'Accept', 'application/vnd.github+json',
            'Authorization', 'Bearer ' || github_token,
            'Content-Type', 'application/json',
            'User-Agent', 'Maryam-Supabase-Radar-Scheduler',
            'X-GitHub-Api-Version', '2022-11-28'),
        body := '{"ref":"main"}'::jsonb,
        timeout_milliseconds := 10000
    ) into request_id;
    return request_id;
end;
$function$;
revoke all on function radar_scheduler.dispatch_maryam(text) from public, anon, authenticated, service_role;

-- Prepare PAUSED. Enable only after a real dispatch has returned HTTP 204.
select cron.schedule('maryam-job-radar', '*/15 * * * *',
    $$select radar_scheduler.dispatch_maryam('job-alert.yml');$$);
select cron.alter_job((select jobid from cron.job where jobname='maryam-job-radar'), active := false);
select cron.schedule('maryam-job-radar-watchdog', '5-59/15 * * * *',
    $$select radar_scheduler.dispatch_maryam('radar-health.yml');$$);
select cron.alter_job((select jobid from cron.job where jobname='maryam-job-radar-watchdog'), active := false);
commit;
