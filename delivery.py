"""Durable claims in the existing jobs table. Never retry an uncertain send."""
import hashlib
import re
import sqlite3
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


def canonical_url(url):
    parts = urlsplit(str(url or ""))
    host = (parts.hostname or "").lower().removeprefix("www.")
    if host.endswith("linkedin.com"):
        match = re.search(r"/jobs/view/(?:[^/?]*-)?(\d+)", parts.path)
        if match:
            return "linkedin:" + match.group(1)
    # Keep job-identifying query parameters; discard tracking only.
    query = sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(("utm_", "trk", "tracking", "ref")))
    return urlunsplit(("https", host, parts.path.rstrip("/"), urlencode(query), ""))


class History:
    def __init__(self, backend):
        self.backend = backend
        self.ids, self.urls = set(), set()
        if backend.use_supabase():
            offset = 0
            while True:
                response = backend.requests.get(f"{backend.SUPABASE_URL}/rest/v1/jobs", headers=backend.supabase_headers(),
                    params={"select": "job_id,url", "order": "job_id.asc", "limit": 1000, "offset": offset}, timeout=30)
                response.raise_for_status()
                rows = response.json()
                self.add(rows)
                if len(rows) < 1000:
                    break
                offset += len(rows)
        else:
            with sqlite3.connect(backend.DB_NAME) as db:
                self.add([dict(zip(("job_id", "url"), row)) for row in db.execute("SELECT job_id,url FROM jobs")])

    def add(self, rows):
        for row in rows:
            self.ids.add(str(row["job_id"]))
            if row.get("url"):
                self.urls.add(canonical_url(row["url"]))

    def claim(self, job):
        b = self.backend
        key = canonical_url(job.get("url")) if job.get("url") else "id:" + str(job["id"])
        if str(job["id"]) in self.ids or key in self.urls:
            return False
        claim_id = "delivery:" + hashlib.sha256(key.encode()).hexdigest()
        payload = {"job_id": claim_id, **{k: job.get(k, "") for k in ("company", "title", "location", "url")}}
        if b.use_supabase():
            headers = {**b.supabase_headers(), "Prefer": "resolution=ignore-duplicates,return=representation"}
            response = b.requests.post(f"{b.SUPABASE_URL}/rest/v1/jobs", headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            claimed = bool(response.json())
        else:
            with sqlite3.connect(b.DB_NAME) as db:
                claimed = db.execute("INSERT OR IGNORE INTO jobs(job_id,company,title,location,url,first_seen_at) VALUES(?,?,?,?,?,?)",
                    tuple(payload[k] for k in ("job_id", "company", "title", "location", "url")) + (datetime.now(timezone.utc).isoformat(),)).rowcount == 1
        self.add([payload])
        return claimed

    def delivered(self, job):
        b = self.backend
        stamp = datetime.now(timezone.utc).isoformat()
        if b.use_supabase():
            response = b.requests.patch(f"{b.SUPABASE_URL}/rest/v1/jobs", headers=b.supabase_headers(),
                params={"job_id": "eq." + str(job["id"])}, json={"alerted_at": stamp}, timeout=30)
            response.raise_for_status()
        else:
            with sqlite3.connect(b.DB_NAME) as db:
                db.execute("UPDATE jobs SET alerted_at=? WHERE job_id=?", (stamp, job["id"]))


def deliver_batch(jobs, sender, initialized, backend, history):
    sent = []
    for job in sorted(jobs, key=lambda j: j.get("score", 0), reverse=True):
        source = job.get("source", "Unknown")
        if source not in initialized:
            initialized[source] = backend.source_is_initialized(source)
        if str(job["id"]) in history.ids or canonical_url(job.get("url")) in history.urls:
            continue
        if not initialized[source]:
            backend.save_job(job)
            history.add([{"job_id": job["id"], "url": job.get("url")}])
            continue
        if not history.claim(job):
            continue
        # Persist before attempting Telegram. A timeout is an uncertain delivery,
        # so the claim is intentionally retained rather than risking a duplicate.
        backend.save_job(job)
        history.ids.add(str(job["id"]))
        try:
            if sender(job):
                history.delivered(job)
                sent.append(job)
            else:
                print("::warning::Telegram delivery failed; claim retained for manual investigation")
        except Exception:
            print("::warning::Telegram delivery uncertain; claim retained for manual investigation")
    return sent
