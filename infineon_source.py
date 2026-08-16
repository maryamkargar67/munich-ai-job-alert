import time
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://jobs.infineon.com"
SEARCH_URL = BASE_URL + "/api/pcsx/search"
DETAIL_URL = BASE_URL + "/api/pcsx/position_details"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://jobs.infineon.com/careers",
}

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data science",
    "data scientist",
    "generative ai",
    "gen ai",
    "agentic",
    "llm",
    "large language model",
    "computer vision",
    "nlp",
    "natural language processing",
    "ai engineer",
    "ai developer",
    "applied scientist",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "lead ",
    "manager",
    "director",
    "head of",
    "chief",
]


def get_with_retry(url, params=None):
    for attempt in range(3):
        try:
            r = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
        except Exception as error:
            if attempt == 2:
                raise error
            time.sleep(2)


def html_to_text(html):
    return BeautifulSoup(html or "", "html.parser").get_text(" ", strip=True)


def has_ai_relevance(text):
    text = (text or "").lower()
    return any(term in text for term in AI_TERMS)


def is_blocked_senior(title):
    title = (title or "").lower()
    return any(term in title for term in BLOCKED_SENIOR_TERMS)


def classify_role(title, join_as):
    text = f"{title} {' '.join(join_as or [])}".lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if "internship" in text or "intern" in text:
        return "Internship"

    if "junior" in text or "graduate" in text or "trainee" in text:
        return "Junior"

    if "part-time" in text or "part time" in text:
        return "Part-Time"

    return "Full-Time"


def is_early_career(role_type, join_as):
    join_text = " ".join(join_as or []).lower()

    if role_type in {
        "Working Student",
        "Internship",
        "Junior",
        "Part-Time",
    }:
        return True

    if "graduate" in join_text:
        return True

    return False


def fetch_detail(position_id):
    data = get_with_retry(
        DETAIL_URL,
        {
            "position_id": position_id,
            "domain": "infineon.com",
        },
    )

    job = data.get("data", {})

    description = html_to_text(job.get("jobDescription", ""))

    return {
        "description": description,
        "join_as": job.get("efcustomTextJoinAs", []),
        "location": job.get("location", ""),
        "work_location": job.get("workLocationOption", ""),
        "public_url": job.get(
            "publicUrl",
            f"{BASE_URL}/careers/job/{position_id}",
        ),
    }


def fetch_infineon_jobs(max_age_minutes=180, max_pages=20):
    print("Checking Infineon Direct Careers...")

    cutoff = datetime.now() - timedelta(minutes=max_age_minutes)

    discovery = []
    seen_ids = set()

    for start in range(0, max_pages * 10, 10):
        data = get_with_retry(
            SEARCH_URL,
            {
                "domain": "infineon.com",
                "location": "Germany",
                "sort_by": "timestamp",
                "start": start,
                "filter_include_remote": 1,
            },
        ).get("data", {})

        positions = data.get("positions", [])

        if not positions:
            break

        print(
            f"Infineon Germany start={start}: "
            f"{len(positions)} discovery jobs"
        )

        page_has_recent = False

        for job in positions:
            job_id = job.get("id")

            if not job_id or job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            ts = job.get("postedTs")

            if not ts:
                continue

            posted = datetime.fromtimestamp(ts)

            if posted >= cutoff:
                page_has_recent = True
                discovery.append(job)

        if not page_has_recent:
            break

    print("Fresh Infineon discovery jobs:", len(discovery))

    relevant = []

    for job in discovery:
        title = (job.get("name") or "").strip()

        if is_blocked_senior(title):
            continue

        try:
            detail = fetch_detail(job["id"])
        except Exception as error:
            print(
                f"Infineon detail error {job['id']}:",
                error,
            )
            continue

        combined_text = f"{title} {detail['description']}"

        if not has_ai_relevance(combined_text):
            continue

        role_type = classify_role(
            title,
            detail["join_as"],
        )

        if not is_early_career(
            role_type,
            detail["join_as"],
        ):
            continue

        if requires_advanced_german(combined_text):
            continue

        locations = job.get("locations", [])
        location_text = ", ".join(locations)

        remote_hint = ""

        if (
            job.get("workLocationOption") == "remote_local"
            or detail.get("work_location") == "remote_local"
        ):
            remote_hint = " Remote Germany"

        if not location_allowed(
            location_text,
            detail["description"] + remote_hint,
        ):
            continue

        ts = job.get("postedTs")

        relevant.append({
            "id": f"infineon-{job['id']}",
            "company": "Infineon",
            "title": title,
            "location": location_text,
            "type": role_type,
            "url": detail["public_url"],
            "description": detail["description"],
            "source": "Infineon",
            "posted_at": (
                datetime.fromtimestamp(ts).isoformat()
                if ts else ""
            ),
        })

    print("Fresh relevant Infineon jobs:", len(relevant))

    return relevant


if __name__ == "__main__":
    jobs = fetch_infineon_jobs()

    print()
    print("=" * 70)

    for job in jobs:
        print(
            job["posted_at"],
            "|",
            job["type"],
            "|",
            job["title"],
        )
        print(job["location"])
        print(job["url"])
        print()
