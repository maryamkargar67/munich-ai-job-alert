import json
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE = "https://careers.munichre.com"

SEARCH_TERMS = [
    "artificial intelligence",
    "machine learning",
    "data science",
    "generative ai",
    "llm",
    "computer vision",
    "ai engineer",
    "working student ai",
    "working student data science",
]

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data science",
    "data scientist",
    "generative ai",
    "gen ai",
    "llm",
    "large language model",
    "computer vision",
    "natural language processing",
    "nlp",
    "ai engineer",
    "ai developer",
    "applied scientist",
    "agentic ai",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "lead ",
    "director",
    "head of",
    "chief",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def get(url, params=None):
    r = requests.get(
        url,
        params=params,
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r


def has_ai_relevance(title, description):
    title_text = (title or "").lower()
    description_text = (description or "").lower()

    strong_title_terms = [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "data science",
        "data scientist",
        "generative ai",
        "gen ai",
        "llm",
        "large language model",
        "computer vision",
        "natural language processing",
        "nlp",
        "ai engineer",
        "ai developer",
        "applied scientist",
        "agentic ai",
    ]

    strong_description_terms = [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "generative ai",
        "gen ai",
        "llm",
        "large language model",
        "computer vision",
        "natural language processing",
        "nlp",
        "neural network",
        "transformer",
        "pytorch",
        "tensorflow",
        "scikit-learn",
    ]

    if any(term in title_text for term in strong_title_terms):
        return True

    return any(
        term in description_text
        for term in strong_description_terms
    )


def is_blocked_senior(title):
    title = (title or "").lower()
    return any(term in title for term in BLOCKED_SENIOR_TERMS)


def classify_role(title, employment_type=""):
    text = f"{title} {employment_type}".lower()

    if "werkstudent" in text or "working student" in text:
        return "Working Student"

    if any(x in text for x in [
        "intern",
        "internship",
        "praktikant",
        "praktikum",
    ]):
        return "Internship"

    if any(x in text for x in [
        "junior",
        "graduate",
        "trainee",
        "entry level",
        "entry-level",
    ]):
        return "Junior"

    if "part-time" in text or "part time" in text:
        return "Part-Time"

    return "Full-Time"


def is_early_career(title, role_type):
    if role_type in {
        "Working Student",
        "Internship",
        "Junior",
        "Part-Time",
    }:
        return True

    title_lower = (title or "").lower()

    return any(x in title_lower for x in [
        "junior",
        "graduate",
        "trainee",
        "entry level",
        "entry-level",
    ])


def extract_jobposting(url):
    r = get(url)
    soup = BeautifulSoup(r.text, "html.parser")

    for script in soup.find_all(
        "script",
        type="application/ld+json"
    ):
        try:
            data = json.loads(
                script.get_text(strip=True)
            )

            items = data if isinstance(data, list) else [data]

            for item in items:
                if (
                    isinstance(item, dict)
                    and item.get("@type") == "JobPosting"
                ):
                    return item

        except Exception:
            continue

    return None


def extract_location(data):
    loc = data.get("jobLocation")

    if isinstance(loc, list):
        loc = loc[0] if loc else {}

    if not isinstance(loc, dict):
        return ""

    address = loc.get("address", {})

    if not isinstance(address, dict):
        return ""

    city = address.get("addressLocality", "")
    region = address.get("addressRegion", "")
    country = address.get("addressCountry", "")

    parts = [
        x for x in [city, region, country]
        if x
    ]

    return ", ".join(parts)


def clean_description(html):
    return BeautifulSoup(
        html or "",
        "html.parser"
    ).get_text(" ", strip=True)


def parse_date(date_text):
    if not date_text:
        return None

    try:
        parts = date_text.split("-")

        return datetime(
            int(parts[0]),
            int(parts[1]),
            int(parts[2]),
            tzinfo=timezone.utc,
        )
    except Exception:
        return None


def fetch_munichre_jobs(max_age_days=3):
    print("Checking Munich Re Direct Careers...")

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=max_age_days)
    )

    discovered = {}

    for term in SEARCH_TERMS:
        try:
            r = get(
                BASE + "/en/search-jobs",
                {
                    "k": term,
                    "orgIds": "3167",
                }
            )
        except Exception as error:
            print(
                f"Munich Re '{term}' error:",
                error
            )
            continue

        soup = BeautifulSoup(
            r.text,
            "html.parser"
        )

        count = 0

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")

            if "/en/job/" not in href:
                continue

            url = urljoin(BASE, href)

            match = re.search(
                r"/(\d+)/?$",
                url
            )

            if not match:
                continue

            job_id = match.group(1)

            if job_id in discovered:
                continue

            title = " ".join(
                a.get_text(
                    " ",
                    strip=True
                ).split()
            )

            discovered[job_id] = {
                "id": job_id,
                "title_hint": title,
                "url": url,
            }

            count += 1

        print(
            f"Munich Re '{term}': "
            f"{count} discovery jobs"
        )

    print(
        "Unique Munich Re discovery jobs:",
        len(discovered)
    )

    relevant = []

    for job_id, candidate in discovered.items():
        try:
            data = extract_jobposting(
                candidate["url"]
            )
        except Exception as error:
            print(
                f"Munich Re detail error {job_id}:",
                error
            )
            continue

        if not data:
            continue

        date_posted = data.get("datePosted")
        posted = parse_date(date_posted)

        if not posted:
            continue

        if posted < cutoff:
            continue

        title = (
            data.get("title")
            or candidate["title_hint"]
            or ""
        ).strip()

        if is_blocked_senior(title):
            continue

        description = clean_description(
            data.get("description", "")
        )

        combined = f"{title} {description}"

        if not has_ai_relevance(
            title,
            description
        ):
            continue

        employment_type = data.get(
            "employmentType",
            ""
        )

        role_type = classify_role(
            title,
            employment_type,
        )

        if not is_early_career(
            title,
            role_type,
        ):
            continue

        if requires_advanced_german(
            combined
        ):
            continue

        location = extract_location(data)

        if not location_allowed(
            location,
            description
        ):
            continue

        relevant.append({
            "id": f"munichre-{job_id}",
            "company": "Munich Re",
            "title": title,
            "location": location,
            "type": role_type,
            "url": candidate["url"],
            "description": description,
            "source": "Munich Re",
            "posted_at": date_posted,
        })

    relevant.sort(
        key=lambda x: x["posted_at"],
        reverse=True
    )

    print(
        "Fresh relevant Munich Re jobs:",
        len(relevant)
    )

    return relevant


if __name__ == "__main__":
    jobs = fetch_munichre_jobs()

    print()
    print("=" * 70)

    for job in jobs:
        print(job["posted_at"])
        print(job["type"])
        print(job["title"])
        print(job["location"])
        print(job["url"])
        print()
