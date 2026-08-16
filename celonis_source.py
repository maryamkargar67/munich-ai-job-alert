import html
import re
import requests
from bs4 import BeautifulSoup

from location_filter import location_allowed
from language_filter import requires_advanced_german


API_URL = "https://dxp-api-stage.celonis.com/v1/jobs"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

AI_TERMS = [
    "artificial intelligence",
    "applied ai",
    " ai ",
    "(ai)",
    "machine learning",
    "ml engineer",
    "data science",
    "data scientist",
    "generative ai",
    "llm",
    "large language model",
    "computer vision",
    "deep learning",
    "nlp",
    "automation",
]

EARLY_TERMS = [
    "working student",
    "werkstudent",
    "intern",
    "student",
    "junior",
    "associate",
    "graduate",
    "new grad",
    "early professional",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "staff",
    "lead",
    "director",
    "head of",
    "manager",
    "vice president",
]


def clean_text(value):
    return " ".join((value or "").split())


def description_to_text(value):
    decoded = html.unescape(value or "")

    return clean_text(
        BeautifulSoup(
            decoded,
            "html.parser"
        ).get_text(" ", strip=True)
    )


def has_ai_relevance(title, description):
    title_low = f" {title.lower()} "

    # Celonis job descriptions contain generic company text about AI,
    # so the title itself must indicate an AI/Data-related role.
    title_terms = [
        "ai",
        "artificial intelligence",
        "machine learning",
        "ml ",
        "data science",
        "data scientist",
        "data engineer",
        "analytics",
        "automation",
    ]

    return any(
        term in title_low
        for term in title_terms
    )


def classify_type(title, seniority, job_type):
    text = f"{title} {seniority} {job_type}".lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if "intern" in text:
        return "Internship"

    if (
        "associate" in text
        or "graduate" in text
        or "junior" in text
        or "early professional" in text
    ):
        return "Junior"

    return "Full-Time"


def suitable_level(title, seniority, job_type):
    title_low = title.lower()

    if any(
        term in title_low
        for term in BLOCKED_SENIOR_TERMS
    ):
        return False

    text = f"{title} {seniority} {job_type}".lower()

    if any(term in text for term in EARLY_TERMS):
        return True

    return False


def has_wrong_real_location(description):
    low = description.lower()

    madrid_patterns = [
        r"location:\s*madrid\s+for\s+an\s+onboarding\s+period",
        r"madrid[-\s]*based",
        r"based\s+in\s+madrid",
    ]

    return any(
        re.search(pattern, low)
        for pattern in madrid_patterns
    )


def fetch_celonis_jobs():
    print("Checking Celonis Direct Careers...")

    params = [
        ("groupedLocation", "Munich, Germany"),
        ("groupedLocation", "Remote, Germany"),
    ]

    r = requests.get(
        API_URL,
        params=params,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    discovery = r.json().get("jobs", [])

    print(
        "Celonis discovery jobs:",
        len(discovery)
    )

    jobs = []

    for item in discovery:
        title = clean_text(
            item.get("title", "")
        )

        seniority = clean_text(
            item.get("seniority", "")
        )

        raw_type = clean_text(
            item.get("type", "")
        )

        if not suitable_level(
            title,
            seniority,
            raw_type
        ):
            continue

        job_id = str(
            item.get("jobId", "")
        )

        if not job_id:
            continue

        detail_url = f"{API_URL}/{job_id}"

        detail = requests.get(
            detail_url,
            headers=HEADERS,
            timeout=30
        )

        if detail.status_code != 200:
            continue

        data = detail.json()

        description = description_to_text(
            data.get("description", "")
        )

        if not has_ai_relevance(
            title,
            description
        ):
            continue

        if has_wrong_real_location(
            description
        ):
            continue

        location = clean_text(
            data.get(
                "groupedLocation",
                item.get("groupedLocation", "")
            )
        )

        if requires_advanced_german(
            f"{title} {description}"
        ):
            continue

        if not location_allowed(
            location,
            description
        ):
            continue

        job_type = classify_type(
            title,
            seniority,
            raw_type
        )

        jobs.append({
            "id": f"celonis-{job_id}",
            "company": "Celonis",
            "title": title,
            "location": location,
            "type": job_type,
            "description": description,
            "url": data.get(
                "applyURL",
                f"https://careers.celonis.com/join-us/open-positions/job-detail?jobId={job_id}"
            ),
            "posted_at": clean_text(
                data.get("updatedAt", "")
            ),
            "source": "Celonis",
        })

    print(
        "Relevant Celonis jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_celonis_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("ID:", job["id"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("UPDATED:", job["posted_at"])
        print("URL:", job["url"])
