import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from location_filter import location_allowed
from language_filter import requires_advanced_german


API_URL = "https://api.ashbyhq.com/posting-api/job-board/DeepL"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

AI_TITLE_TERMS = [
    "artificial intelligence",
    "machine learning",
    "ml engineer",
    "ai engineer",
    "research scientist",
    "applied scientist",
    "data scientist",
    "deep learning",
    "nlp",
    "natural language",
    "language model",
    "llm",
    "inference",
    "computer vision",
]

AI_DESCRIPTION_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "natural language processing",
    "large language model",
    "language model",
    "llm",
    "transformer",
    "pytorch",
    "tensorflow",
    "inference",
    "research",
]

EARLY_TERMS = [
    "working student",
    "werkstudent",
    "intern",
    "internship",
    "junior",
    "graduate",
    "entry level",
    "entry-level",
    "student",
    "part-time",
    "part time",
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
    return " ".join((value or "").split())


def has_ai_relevance(title, description):
    title_low = f" {title.lower()} "
    description_low = f" {description.lower()} "

    if any(term in title_low for term in AI_TITLE_TERMS):
        return True

    matches = sum(
        1
        for term in AI_DESCRIPTION_TERMS
        if term in description_low
    )

    return matches >= 2


def classify_type(title, description):
    text = f"{title} {description}".lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if "intern" in text:
        return "Internship"

    if (
        "part-time" in text
        or "part time" in text
        or "teilzeit" in text
    ):
        return "Part-Time"

    return "Full-Time"


def is_early_career(title, description, job_type):
    text = f" {title} {description} ".lower()
    title_low = title.lower()

    if any(term in text for term in BLOCKED_STUDENT_TERMS):
        return False

    if any(term in title_low for term in BLOCKED_SENIOR_TERMS):
        return False

    if job_type in [
        "Working Student",
        "Internship",
        "Part-Time"
    ]:
        return True

    if any(term in text for term in EARLY_TERMS):
        return True

    return job_type == "Full-Time"


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


def fetch_deepl_jobs(max_age_minutes=180):
    print("Checking DeepL Direct Careers...")

    r = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    raw_jobs = r.json().get("jobs", [])

    print("DeepL discovery jobs:", len(raw_jobs))

    jobs = []

    for job in raw_jobs:
        title = clean_text(job.get("title", ""))
        location = clean_text(job.get("location", ""))

        description = clean_text(
            BeautifulSoup(
                job.get("descriptionHtml", "") or "",
                "html.parser"
            ).get_text(" ", strip=True)
        )

        published_at = clean_text(
            job.get("publishedAt", "")
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

        if not is_early_career(
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
            "id": f"deepl-{job.get('id')}",
            "company": "DeepL",
            "title": title,
            "location": location,
            "type": job_type,
            "description": description,
            "url": job.get("jobUrl", ""),
            "posted_at": published_at,
            "source": "DeepL",
        })

    print(
        "Fresh relevant DeepL jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_deepl_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
