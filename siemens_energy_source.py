import requests
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta

from location_filter import location_allowed
from language_filter import requires_advanced_german


SEARCH_URL = "https://jobs.siemens-energy.com/en_US/CareersMarketplace/Jobs"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

QUERIES = [
    "artificial intelligence",
    "machine learning",
    "data science",
    "generative AI",
    "computer vision",
    "LLM",
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
    "llm",
    "large language model",
    "computer vision",
    "ai engineer",
    "applied scientist",
    "agentic",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "staff",
    "lead",
    "head of",
    "director",
    "manager",
]


def has_ai_term(text):
    text = (text or "").lower()
    return any(term in text for term in AI_TERMS)


def is_senior_title(title):
    title = (title or "").lower()
    return any(term in title for term in BLOCKED_SENIOR_TERMS)


def get_role_type(title, detail_text):
    text = f"{title} {detail_text}".lower()

    if "werkstudent" in text or "working student" in text:
        return "Working Student"

    if "internship" in text or "intern " in text or "internship" in title.lower():
        return "Internship"

    if "junior" in text or "graduate" in text:
        return "Junior"

    return "Full-Time"


def get_job_detail(job_url):
    try:
        r = requests.get(
            job_url,
            headers=HEADERS,
            timeout=30
        )
        r.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    title = ""

    og_title = soup.find(
        "meta",
        attrs={"property": "og:title"}
    )

    if og_title:
        title = og_title.get("content", "").strip()

    date_posted = None

    for tag in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        try:
            data = json.loads(tag.string or "{}")

            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                date_posted = data.get("datePosted")

                if not title:
                    title = data.get("title", "")

                break
        except Exception:
            continue

    detail_text = " ".join(
        soup.get_text(" ", strip=True).split()
    )

    return {
        "title": title,
        "date_posted": date_posted,
        "detail_text": detail_text,
    }


def is_recent(date_posted, days=1):
    if not date_posted:
        return False

    try:
        posted = datetime.strptime(
            date_posted,
            "%Y-%m-%d"
        ).date()
    except ValueError:
        return False

    today = datetime.now().date()

    return posted >= today - timedelta(days=days)


def search_query(query, max_pages=3):
    jobs = []

    for page in range(max_pages):
        offset = page * 20

        data = {
            "search": query,
            "listFilterMode": "true",
            "folderOffset": offset,
            "folderRecordsPerPage": 20,
            "folderSort": "schemaField_3_146_3",
            "folderSortDirection": "DESC",
        }

        try:
            r = requests.post(
                SEARCH_URL,
                data=data,
                headers=HEADERS,
                timeout=30
            )
            r.raise_for_status()
        except Exception as e:
            print(
                f"Siemens Energy search error "
                f"for '{query}' page {page}: {e}"
            )
            break

        soup = BeautifulSoup(r.text, "html.parser")

        page_jobs = []
        seen = set()

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")

            if "/FolderDetail/" not in href:
                continue

            job_url = urljoin(r.url, href)

            if job_url in seen:
                continue

            seen.add(job_url)

            title = " ".join(
                a.get_text(" ", strip=True).split()
            )

            if not title:
                continue

            page_jobs.append({
                "title": title,
                "url": job_url
            })

        if not page_jobs:
            break

        jobs.extend(page_jobs)

    return jobs


def fetch_siemens_energy_jobs():
    print("Checking Siemens Energy Direct Careers...")

    discovered = {}

    for query in QUERIES:
        jobs = search_query(
            query,
            max_pages=3
        )

        print(
            f"Siemens Energy '{query}': "
            f"{len(jobs)} discovery jobs"
        )

        for job in jobs:
            discovered[job["url"]] = job

    print(
        f"Unique Siemens Energy discovery jobs: "
        f"{len(discovered)}"
    )

    relevant = []

    for job in discovered.values():
        title = job["title"]

        if not has_ai_term(title):
            continue

        if is_senior_title(title):
            continue

        detail = get_job_detail(
            job["url"]
        )

        if not detail:
            continue

        detail_text = detail["detail_text"]

        if not has_ai_term(
            f"{title} {detail_text}"
        ):
            continue

        if not is_recent(
            detail["date_posted"],
            days=1
        ):
            continue

        if requires_advanced_german(
            detail_text
        ):
            continue

        location_text = detail_text

        if not location_allowed(
            location_text,
            detail_text
        ):
            continue

        role_type = get_role_type(
            title,
            detail_text
        )

        relevant.append({
            "id": (
                "siemens_energy_"
                + job["url"].rstrip("/").split("/")[-1]
            ),
            "company": "Siemens Energy",
            "title": title,
            "location": location_text[:300],
            "type": role_type,
            "description": detail_text,
            "url": job["url"],
            "source": "Siemens Energy",
            "posted_at": detail["date_posted"],
        })

    print(
        f"Fresh relevant Siemens Energy jobs: "
        f"{len(relevant)}"
    )

    return relevant


if __name__ == "__main__":
    jobs = fetch_siemens_energy_jobs()

    print()
    print("=" * 70)

    for job in jobs:
        print(
            job["posted_at"],
            "|",
            job["type"],
            "|",
            job["title"]
        )
        print(job["url"])
        print()
