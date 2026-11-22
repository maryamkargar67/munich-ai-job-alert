"""Fallback scan gating and a watchdog that counts actual completed scans."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import sys

import requests

WORKFLOW = 'job-alert.yml'
STALE_MINUTES = 45


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def latest_completed_scan(repo, token, get=requests.get):
    headers = {'Accept': 'application/vnd.github+json', 'Authorization': f'Bearer {token}', 'X-GitHub-Api-Version': '2022-11-28'}
    response = get(f'https://api.github.com/repos/{repo}/actions/workflows/{WORKFLOW}/runs',
                   headers=headers, params={'branch': 'main', 'status': 'success', 'per_page': 20}, timeout=20)
    response.raise_for_status()
    completed = []
    for run in response.json().get('workflow_runs', []):
        response = get(f'https://api.github.com/repos/{repo}/actions/runs/{run["id"]}/jobs', headers=headers, timeout=20)
        response.raise_for_status()
        for job in response.json().get('jobs', []):
            for step in job.get('steps', []):
                # A gated/skipped workflow must never reset the scan heartbeat.
                if step.get('name') == 'Run job alert' and step.get('conclusion') == 'success' and step.get('completed_at'):
                    completed.append(instant(step['completed_at']))
        if completed:
            return max(completed)
    return None


def stale(last, now):
    return last is None or (now - last).total_seconds() > STALE_MINUTES * 60


def should_scan(event, last, now):
    # Supabase dispatches and manual checks always run. GitHub cron is backup.
    return event != 'schedule' or last is None or (now - last).total_seconds() >= 12 * 60


def alert_stale(repo, last, now):
    # Import configuration only when an alert is needed. Reuse durable claims.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import main as backend
    from delivery import History
    if not backend.use_supabase() or not backend.TELEGRAM_TOKEN or not backend.TELEGRAM_CHAT_ID:
        raise RuntimeError('Persistent history and Telegram configuration are required for the watchdog')
    history = History(backend)
    bucket = now.strftime('%Y%m%d%H')
    job = {'id': 'radar-health:' + bucket, 'company': 'Radar monitoring', 'title': 'Maryam radar missed scans',
           'location': '', 'url': f'https://github.com/{repo}/actions?radar_health_period={bucket}'}
    if not history.claim(job):
        print('Watchdog alert already claimed this hour; no repeated Telegram message')
        return False
    backend.save_job(job)
    last_text = last.astimezone(timezone.utc).isoformat() if last else 'not found'
    message = f'⚠️ Maryam Job Radar: no successful scan completed in the last {STALE_MINUTES} minutes.\nLast completion (UTC): {last_text}\nhttps://github.com/{repo}/actions/workflows/{WORKFLOW}'
    try:
        response = requests.post(f'https://api.telegram.org/bot{backend.TELEGRAM_TOKEN}/sendMessage',
                                 json={'chat_id': backend.TELEGRAM_CHAT_ID, 'text': message}, timeout=20)
        response.raise_for_status()
    except requests.RequestException:
        # Do not expose the token in requests' exception URL or retry an uncertain send.
        raise RuntimeError('Watchdog Telegram delivery failed or uncertain; claim retained') from None
    history.delivered(job)
    print('Watchdog alert delivered')
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('gate', 'health'))
    args = parser.parse_args()
    repo = os.environ['GITHUB_REPOSITORY']
    token = os.environ['GITHUB_TOKEN']
    now = datetime.now(timezone.utc)
    if args.mode == 'gate':
        event = os.getenv('GITHUB_EVENT_NAME', '')
        run = True
        if event == 'schedule':
            try:
                run = should_scan(event, latest_completed_scan(repo, token), now)
            except requests.RequestException:
                print('::warning::Could not inspect recent runs; letting the backup scan proceed')
        with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
            output.write(f'run_scan={str(run).lower()}\n')
        print('Scan enabled' if run else 'Backup skipped: a real scan recently completed')
    else:
        last = latest_completed_scan(repo, token)
        if stale(last, now):
            alert_stale(repo, last, now)
        else:
            print(f'Watchdog healthy; last actual scan completed at {last.isoformat()}')


if __name__ == '__main__':
    main()
