import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://appliedai.jobs.personio.de/"
LIST_URL = "https://appliedai.jobs.personio.de/?language=en"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

AI_TERMS = [
    "artificial intelligence",
    " ai ",
    "ai engineering",
    "ai engineer",
    "machine learning",
    "ml engineer",
    "data science",
    "data scientist",
    "llm",
    "large language model",
    "generative ai",
    "agent",
    "agents",
    "agentic",
    "computer vision",
    "deep learning",
    "nlp",
    "mlops",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "staff",
    "lead",
    "director",
    "head of",
    "manager",
    "vp ",
    "vice president",
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
    "entry level",
    "entry-level",
]


def clean_text(value):
    return " ".join((value or "").split())


def parse_published(html):
    patterns = [
        r'published[^0-9]*(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)',
        r'datePosted[^0-9]*(\d{4}-\d{2}-\d{2})',
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            html,
            flags=re.IGNORECASE
        )

        if match:
            value = match.group(1)

            if "T" not in value:
                value += "T00:00:00Z"

            return value

    return ""


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
    text = f" {title} {description} ".lower()
    title_low = f" {title.lower()} "

    if any(term in title_low for term in AI_TERMS):
        return True

    matches = sum(
        1 for term in AI_TERMS
        if term in text
    )

    return matches >= 2


def classify_type(title, description):
    text = f"{title} {description}".lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if "intern" in text or "intern / student" in text:
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

    if any(term in text for term in EARLY_TERMS):
        return True

    return True


def fetch_appliedai_jobs(max_age_minutes=180):
    print("Checking appliedAI Direct Careers...")

    r = requests.get(
        LIST_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    job_links = {}

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")

        if not href.startswith("/job/"):
            continue

        title = clean_text(
            a.get_text(" ", strip=True)
        )

        if not title:
            continue

        full_url = urljoin(
            BASE_URL,
            href
        )

        job_id_match = re.search(
            r"/job/(\d+)",
            href
        )

        if not job_id_match:
            continue

        job_id = job_id_match.group(1)

        job_links[job_id] = {
            "title_card": title,
            "url": full_url,
        }

    print(
        "appliedAI discovery jobs:",
        len(job_links)
    )

    jobs = []

    for job_id, item in job_links.items():

        detail = requests.get(
            item["url"],
            headers=HEADERS,
            timeout=30
        )

        if detail.status_code != 200:
            continue

        html = detail.text

        published_at = parse_published(
            html
        )

        if not is_fresh(
            published_at,
            max_age_minutes=max_age_minutes
        ):
            continue

        detail_soup = BeautifulSoup(
            html,
            "html.parser"
        )

        text = clean_text(
            detail_soup.get_text(
                " ",
                strip=True
            )
        )

        title = item["title_card"]

        if "|" in text:
            page_title = text.split("|", 1)[0].strip()

            if page_title:
                title = page_title

        location = ""

        location_match = re.search(
            r"(München|Munich|Heilbronn)",
            text,
            flags=re.IGNORECASE
        )

        if location_match:
            location = location_match.group(1)

        if not has_ai_relevance(
            title,
            text
        ):
            continue

        job_type = classify_type(
            title,
            text
        )

        if not is_suitable_level(
            title,
            text,
            job_type
        ):
            continue

        if requires_advanced_german(
            f"{title} {text}"
        ):
            continue

        if not location_allowed(
            location,
            text
        ):
            continue

        jobs.append({
            "id": f"appliedai-{job_id}",
            "company": "appliedAI",
            "title": title,
            "location": location or "Germany",
            "type": job_type,
            "description": text,
            "url": item["url"],
            "posted_at": published_at,
            "source": "appliedAI",
        })

    print(
        "Fresh relevant appliedAI jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_appliedai_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
