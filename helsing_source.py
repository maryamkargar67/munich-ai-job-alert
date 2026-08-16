import re
import html
import requests
from datetime import datetime, timezone

from location_filter import location_allowed
from language_filter import requires_advanced_german


URL = "https://helsing.ai/jobs"
HEADERS = {"User-Agent": "Mozilla/5.0"}

AI_TITLE_TERMS = [
    "ai research",
    "ai engineer",
    "machine learning",
    "ml engineering",
    "computer vision",
    "foundation model",
    "reinforcement learning",
    "robotics",
    "signal processing",
    "applied scientist",
    "research scientist",
    "data scientist",
    "deep learning",
    "llm",
    "language model",
]

EARLY_TERMS = [
    "intern",
    "internship",
    "working student",
    "werkstudent",
    "junior",
    "graduate",
    "entry level",
    "entry-level",
    "student",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "staff",
    "principal",
    "lead ",
    "manager",
    "director",
    "head of",
    "vp ",
    "vice president",
]

BLOCKED_STUDENT_TERMS = [
    "duales studium",
    "ausbildung",
    "abschlussarbeit",
    "masterarbeit",
    "bachelorarbeit",
    "thesis",
]


def clean_text(value):
    value = html.unescape(value or "")
    value = value.replace("\\u0026", "&")
    return " ".join(value.split())


def is_fresh(first_published, max_age_minutes=180):
    try:
        dt = datetime.fromisoformat(
            first_published.replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)
        age = (
            now - dt.astimezone(timezone.utc)
        ).total_seconds() / 60

        return 0 <= age <= max_age_minutes
    except Exception:
        return False


def has_ai_relevance(title):
    low = title.lower()
    return any(term in low for term in AI_TITLE_TERMS)


def classify_type(title):
    low = title.lower()

    if "working student" in low or "werkstudent" in low:
        return "Working Student"

    if "intern" in low:
        return "Internship"

    return "Full-Time"


def is_early_career(title, job_type):
    low = title.lower()

    if any(term in low for term in BLOCKED_STUDENT_TERMS):
        return False

    if any(term in low for term in BLOCKED_SENIOR_TERMS):
        return False

    if job_type in ["Working Student", "Internship"]:
        return True

    if any(term in low for term in EARLY_TERMS):
        return True

    return job_type == "Full-Time"


def fetch_helsing_jobs(max_age_minutes=180):
    print("Checking Helsing Direct Careers...")

    r = requests.get(
        URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    text = r.text

    pattern = re.compile(
        r'\\"id\\":(\d+),'
        r'\\"updated_at\\":\\"([^"]+)\\",'
        r'\\"requisition_id\\":\\"?([^",}]*)\\"?,'
        r'\\"title\\":\\"([^"]+)\\",'
        r'\\"company_name\\":\\"Helsing\\",'
        r'\\"first_published\\":\\"([^"]+)\\",'
        r'\\"language\\":\\"([^"]+)\\"'
    )

    matches = pattern.findall(text)

    print("Helsing discovery jobs:", len(matches))

    jobs = []

    for job_id, updated, req, title, first_published, language in matches:
        title = clean_text(title)

        marker = f'\\"id\\":{job_id},'
        pos = text.find(marker)

        location = ""

        if pos != -1:
            nearby = text[max(0, pos - 700):pos + 1800]

            m = re.search(
                r'\\"location\\":\{\\"name\\":\\"([^"]+)\\"\}',
                nearby
            )

            if m:
                location = clean_text(m.group(1))

        if not is_fresh(
            first_published,
            max_age_minutes=max_age_minutes
        ):
            continue

        if not has_ai_relevance(title):
            continue

        job_type = classify_type(title)

        if not is_early_career(
            title,
            job_type
        ):
            continue

        if requires_advanced_german(title):
            continue

        if not location_allowed(
            location,
            ""
        ):
            continue

        jobs.append({
            "id": f"helsing-{job_id}",
            "company": "Helsing",
            "title": title,
            "location": location,
            "type": job_type,
            "description": title,
            "url": f"https://helsing.ai/jobs/{job_id}",
            "posted_at": first_published,
            "source": "Helsing",
        })

    print(
        "Fresh relevant Helsing jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_helsing_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
