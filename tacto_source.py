import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from location_filter import location_allowed
from language_filter import requires_advanced_german


API_URL = "https://api.ashbyhq.com/posting-api/job-board/tacto"
HEADERS = {"User-Agent": "Mozilla/5.0"}

AI_TERMS = [
    "artificial intelligence",
    "applied ai",
    "ai engineer",
    "ai automation",
    "machine learning",
    "ml engineer",
    "data science",
    "data scientist",
    "llm",
    "large language model",
    "agentic",
    "agents",
    "computer vision",
    "deep learning",
    "nlp",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "staff",
    "principal",
    "technical lead",
    "tech lead",
    "team lead",
    "director",
    "head of",
    "vp ",
    "vice president",
    "manager",
]

ALLOWED_EARLY_TERMS = [
    "intern",
    "working student",
    "werkstudent",
    "junior",
    "graduate",
    "new grad",
    "entry level",
    "entry-level",
]


def clean_text(value):
    return " ".join((value or "").split())


def is_fresh(published_at, max_age_minutes=180):
    if not published_at:
        return False

    try:
        published = datetime.fromisoformat(
            published_at.replace("Z", "+00:00")
        )
        now = datetime.now(timezone.utc)

        age_minutes = (
            now - published.astimezone(timezone.utc)
        ).total_seconds() / 60

        return 0 <= age_minutes <= max_age_minutes

    except Exception:
        return False


def has_ai_relevance(title, description):
    text = f"{title} {description}".lower()

    matches = sum(
        1 for term in AI_TERMS
        if term in text
    )

    title_low = title.lower()

    if any(term in title_low for term in AI_TERMS):
        return True

    return matches >= 2


def classify_type(title, description):
    text = f"{title} {description}".lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if "intern" in text:
        return "Internship"

    if "junior" in text or "new grad" in text or "graduate" in text:
        return "Junior"

    if (
        "part-time" in text
        or "part time" in text
        or "teilzeit" in text
    ):
        return "Part-Time"

    return "Full-Time"


def is_suitable_level(title, description, job_type):
    title_low = title.lower()

    if any(
        term in title_low
        for term in BLOCKED_SENIOR_TERMS
    ):
        return False

    if job_type in [
        "Working Student",
        "Internship",
        "Junior",
        "Part-Time",
    ]:
        return True

    text = f"{title} {description}".lower()

    if any(term in text for term in ALLOWED_EARLY_TERMS):
        return True

    # Full-time roles without obvious senior wording
    # can still pass; main.py applies the higher score threshold.
    return True


def fetch_tacto_jobs(max_age_minutes=180):
    print("Checking Tacto Direct Careers...")

    r = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    raw_jobs = r.json().get("jobs", [])

    print("Tacto discovery jobs:", len(raw_jobs))

    jobs = []

    for job in raw_jobs:
        title = clean_text(job.get("title", ""))
        location = clean_text(job.get("location", ""))
        published_at = clean_text(job.get("publishedAt", ""))

        description = clean_text(
            BeautifulSoup(
                job.get("descriptionHtml", "") or "",
                "html.parser"
            ).get_text(" ", strip=True)
        )

        if not is_fresh(
            published_at,
            max_age_minutes=max_age_minutes
        ):
            continue

        if not has_ai_relevance(
            title,
            description
        ):
            continue

        job_type = classify_type(
            title,
            description
        )

        if not is_suitable_level(
            title,
            description,
            job_type
        ):
            continue

        if requires_advanced_german(
            f"{title} {description}"
        ):
            continue

        if not location_allowed(
            location,
            description
        ):
            continue

        jobs.append({
            "id": f"tacto-{job.get('id')}",
            "company": "Tacto",
            "title": title,
            "location": location,
            "type": job_type,
            "description": description,
            "url": job.get("jobUrl", ""),
            "posted_at": published_at,
            "source": "Tacto",
        })

    print(
        "Fresh relevant Tacto jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_tacto_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
