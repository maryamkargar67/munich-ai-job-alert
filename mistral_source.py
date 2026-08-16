import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone

from location_filter import location_allowed
from language_filter import requires_advanced_german


API_URL = "https://api.ashbyhq.com/posting-api/job-board/mistral.ai"
HEADERS = {"User-Agent": "Mozilla/5.0"}

AI_TITLE_TERMS = [
    "applied ai",
    "ai engineer",
    "machine learning",
    "ml engineer",
    "applied scientist",
    "research scientist",
    "research engineer",
    "data scientist",
    "computer vision",
    "deep learning",
    "llm",
    "language model",
    "foundation model",
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


def has_ai_relevance(title):
    low = title.lower()

    return any(
        term in low
        for term in AI_TITLE_TERMS
    )


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


def requires_too_much_experience(description, job_type):
    if job_type in ["Working Student", "Internship"]:
        return False

    text = " ".join(description.lower().split())

    # AI-specific professional experience:
    # 2+ years or more is too experienced for our target profile.
    ai_specific_patterns = [
        r"(\d+)\+?\s*years?.{0,100}(?:ai|machine learning|ml|data scientist)",
        r"(?:ai|machine learning|ml).{0,100}(\d+)\+?\s*years?",
    ]

    for pattern in ai_specific_patterns:
        match = re.search(pattern, text)

        if match:
            try:
                if int(match.group(1)) >= 2:
                    return True
            except Exception:
                pass

    # General explicit experience requirements:
    # 3+ years or more are outside our early-career target.
    general_patterns = [
        r"(\d+)\+?\s*years?\s+(?:of\s+)?experience",
        r"minimum\s+(?:of\s+)?(\d+)\s+years?",
        r"at\s+least\s+(\d+)\s+years?",
    ]

    for pattern in general_patterns:
        match = re.search(pattern, text)

        if match:
            try:
                if int(match.group(1)) >= 3:
                    return True
            except Exception:
                pass

    return False


def is_suitable_level(title, description, job_type):
    title_low = title.lower()

    if any(
        term in title_low
        for term in BLOCKED_SENIOR_TERMS
    ):
        return False

    combined = f"{title} {description}".lower()

    if any(
        term in combined
        for term in BLOCKED_STUDENT_TERMS
    ):
        return False

    if requires_too_much_experience(
        description,
        job_type
    ):
        return False

    return True


def fetch_mistral_jobs(max_age_minutes=180):
    print("Checking Mistral AI Direct Careers...")

    r = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    raw_jobs = r.json().get("jobs", [])

    print("Mistral discovery jobs:", len(raw_jobs))

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

        if not has_ai_relevance(title):
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
            "id": f"mistral-{job.get('id')}",
            "company": "Mistral AI",
            "title": title,
            "location": location,
            "type": job_type,
            "description": description,
            "url": job.get("jobUrl", ""),
            "posted_at": published_at,
            "source": "Mistral AI",
        })

    print(
        "Fresh relevant Mistral jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_mistral_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
