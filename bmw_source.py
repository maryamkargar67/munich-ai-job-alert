import re
import time
import requests
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta

from location_filter import location_allowed
from language_filter import requires_advanced_german


RSS_URL = "https://jobs.bmwgroup.com/services/rss/job/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

SEARCH_TERMS = [
    "artificial intelligence",
    "machine learning",
    "data science",
    "generative AI",
    "agentic AI",
    "LLM",
    "computer vision",
    "AI engineer",
    "AI working student",
    "data science working student",
]

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data science",
    "data scientist",
    "generative ai",
    "gen ai",
    "agentic ai",
    "agent-based ai",
    "llm",
    "large language model",
    "computer vision",
    "natural language processing",
    "nlp",
    "synthetic data",
    "applied ai",
    "ai engineer",
    "ai developer",
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

BLOCKED_ROLE_TERMS = [
    "dual student",
    "dualer student",
    "azubi",
    "ausbildung",
    "phd",
]


def get_with_retry(params):
    for attempt in range(3):
        try:
            r = requests.get(
                RSS_URL,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            return r.text
        except Exception as error:
            if attempt == 2:
                raise error
            time.sleep(2)


def html_to_text(html):
    return BeautifulSoup(
        html or "",
        "html.parser"
    ).get_text(" ", strip=True)


def has_ai_relevance(text):
    text = (text or "").lower()
    return any(term in text for term in AI_TERMS)


def has_ai_title_relevance(title):
    title = (title or "").lower()

    title_terms = [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "data science",
        "data scientist",
        "generative ai",
        "agentic ai",
        "agent-based ai",
        "llm",
        "large language model",
        "computer vision",
        "nlp",
        "natural language processing",
        "ai engineer",
        "ai developer",
        "ki-agent",
        "ki agent",
        "chatbot",
    ]

    return any(term in title for term in title_terms)


def has_strong_description_ai(text):
    text = (text or "").lower()

    strong_terms = [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "generative ai",
        "agentic ai",
        "agent-based ai",
        "large language model",
        "llm",
        "computer vision",
        "natural language processing",
        "neural network",
        "ai agent",
        "ai-agent",
        "ki-agent",
        "ki agent",
        "chatbot",
    ]

    return any(term in text for term in strong_terms)


def is_blocked_title(title):
    text = (title or "").lower()

    if any(term in text for term in BLOCKED_SENIOR_TERMS):
        return True

    if any(term in text for term in BLOCKED_ROLE_TERMS):
        return True

    return False


def classify_role(title):
    text = (title or "").lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if (
        "intern " in text
        or text.startswith("intern")
        or "internship" in text
        or "praktikant" in text
        or "praktikum" in text
    ):
        return "Internship"

    if "junior" in text or "graduate" in text or "trainee" in text:
        return "Junior"

    if "part-time" in text or "part time" in text:
        return "Part-Time"

    return "Full-Time"


def is_early_career(title, role_type, description):
    if role_type in {
        "Working Student",
        "Internship",
        "Junior",
        "Part-Time",
    }:
        return True

    text = f"{title} {description}".lower()

    return any(term in text for term in [
        "entry level",
        "entry-level",
        "early career",
        "graduate",
        "recent graduate",
    ])


def extract_job_id(url):
    match = re.search(r"/(\d+)/?(?:\?|$)", url or "")
    return match.group(1) if match else url


def extract_location(feed_title):
    matches = re.findall(r"\(([^()]*)\)", feed_title or "")

    for value in reversed(matches):
        low = value.lower()

        if any(code in low for code in [
            ", de",
            "munich",
            "münchen",
            "germany",
        ]):
            return value.strip()

    return ""


def clean_title(feed_title, location):
    title = feed_title or ""

    if location:
        suffix = f"({location})"

        if title.endswith(suffix):
            title = title[:-len(suffix)].strip()

    return title


def fetch_bmw_jobs(max_age_hours=48):
    print("Checking BMW Direct Careers...")

    cutoff = datetime.now(timezone.utc) - timedelta(
        hours=max_age_hours
    )

    discovered = {}

    for term in SEARCH_TERMS:
        try:
            xml_text = get_with_retry({
                "locale": "en_US",
                "keywords": f"({term}) AND locationSearch:(Germany)",
            })
        except Exception as error:
            print(f"BMW '{term}' error:", error)
            continue

        root = ET.fromstring(xml_text)
        items = root.findall(".//item")

        print(
            f"BMW '{term}': {len(items)} discovery jobs"
        )

        for item in items:
            feed_title = item.findtext("title", "").strip()
            description_html = item.findtext(
                "description",
                ""
            )
            url = item.findtext("link", "").strip()
            pub_text = item.findtext(
                "pubDate",
                ""
            ).strip()

            if not url or not pub_text:
                continue

            try:
                posted = parsedate_to_datetime(pub_text)

                if posted.tzinfo is None:
                    posted = posted.replace(
                        tzinfo=timezone.utc
                    )
            except Exception:
                continue

            if posted < cutoff:
                continue

            job_id = extract_job_id(url)

            if job_id in discovered:
                continue

            description = html_to_text(
                description_html
            )

            location = extract_location(
                feed_title
            )

            title = clean_title(
                feed_title,
                location
            )

            discovered[job_id] = {
                "raw_id": job_id,
                "title": title,
                "location": location,
                "description": description,
                "url": url,
                "posted": posted,
            }

    print(
        "Fresh BMW discovery jobs:",
        len(discovered)
    )

    relevant = []

    for job in discovered.values():
        title = job["title"]
        description = job["description"]

        if is_blocked_title(title):
            continue

        combined_text = f"{title} {description}"

        if not (
            has_ai_title_relevance(title)
            or has_strong_description_ai(description)
        ):
            continue

        role_type = classify_role(title)

        if not is_early_career(
            title,
            role_type,
            description,
        ):
            continue

        if requires_advanced_german(
            combined_text
        ):
            continue

        location_text = job["location"]

        remote_hint = ""

        low = combined_text.lower()

        if any(term in low for term in [
            "remote work",
            "fully remote",
            "remote germany",
            "work remotely",
        ]):
            remote_hint = " Remote Germany"

        if not location_allowed(
            location_text,
            description + remote_hint,
        ):
            continue

        relevant.append({
            "id": f"bmw-{job['raw_id']}",
            "company": "BMW Group",
            "title": title,
            "location": location_text,
            "type": role_type,
            "url": job["url"],
            "description": description,
            "source": "BMW",
            "posted_at": job[
                "posted"
            ].isoformat(),
        })

    relevant.sort(
        key=lambda x: x["posted_at"],
        reverse=True,
    )

    print(
        "Fresh relevant BMW jobs:",
        len(relevant)
    )

    return relevant


if __name__ == "__main__":
    jobs = fetch_bmw_jobs()

    print()
    print("=" * 70)

    for job in jobs:
        print(job["posted_at"])
        print(job["type"])
        print(job["title"])
        print(job["location"])
        print(job["url"])
        print()
