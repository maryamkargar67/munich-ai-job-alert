import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta

from location_filter import location_allowed
from language_filter import requires_advanced_german


SEARCH_URL = "https://jobs.siemens.com/en_US/externaljobs/SearchJobs"

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
    "data science working student"
]

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data science",
    "data scientist",
    "generative ai",
    "genai",
    "llm",
    "large language model",
    "computer vision",
    "ai engineer",
    "applied scientist",
    "agentic"
]

BLOCKED_SENIOR = [
    "senior",
    "principal",
    "staff ",
    "lead ",
    "head of",
    "director",
    "manager"
]


def clean(text):
    return " ".join((text or "").split())


def extract_card(a, base_url):
    card = a

    for _ in range(10):
        if card is None:
            break

        if "Job ID:" in card.get_text(" ", strip=True):
            break

        card = card.parent

    if card is None:
        return None

    url = urljoin(base_url, a.get("href", ""))
    title = clean(a.get_text(" ", strip=True))

    city_el = card.select_one(".list-item-jobCity")
    state_el = card.select_one(".list-item-jobState")
    country_el = card.select_one(".list-item-jobCountry")
    job_id_el = card.select_one(".list-item-jobId")

    city = clean(city_el.get_text(" ", strip=True) if city_el else "")
    state = clean(state_el.get_text(" ", strip=True) if state_el else "")
    country = clean(country_el.get_text(" ", strip=True) if country_el else "")

    job_id_text = clean(
        job_id_el.get_text(" ", strip=True)
        if job_id_el else ""
    )

    match = re.search(r"(\d+)", job_id_text)

    if not match:
        match = re.search(r"/JobDetail/(\d+)", url)

    if not match:
        return None

    return {
        "job_id": match.group(1),
        "title": title,
        "city": city,
        "state": state,
        "country": country,
        "url": url
    }


def search_query(query, max_pages=3):
    found = {}

    for page in range(max_pages):

        offset = page * 6

        response = requests.post(
            SEARCH_URL,
            data={
                "search": query,
                "listFilterMode": "true",
                "folderSort": "postedDate",
                "folderSortDirection": "DESC",
                "folderOffset": offset,
                "folderRecordsPerPage": 6
            },
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        page_jobs = 0

        for a in soup.find_all(
            "a",
            href=lambda x: (
                x and "/externaljobs/JobDetail/" in x
            )
        ):
            job = extract_card(
                a,
                response.url
            )

            if not job:
                continue

            found[job["job_id"]] = job
            page_jobs += 1

        if page_jobs < 6:
            break

    return list(found.values())


def parse_detail(job):
    response = requests.get(
        job["url"],
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    lines = [
        clean(line)
        for line in soup.get_text("\n").splitlines()
        if clean(line)
    ]

    def value_after(label):
        for i, line in enumerate(lines):
            if line.lower() == label.lower():
                if i + 1 < len(lines):
                    return lines[i + 1]

        return ""

    return {
        **job,
        "posted_since": value_after("Posted since"),
        "experience": value_after("Experience level"),
        "job_type": value_after("Job type"),
        "work_mode": value_after("Work mode"),
        "employment_type": value_after("Employment type"),
        "location": value_after("Location(s)"),
        "description": clean(
            soup.get_text(" ", strip=True)
        )
    }


def is_recent(date_text, days=1):
    if not date_text:
        return False

    try:
        posted = datetime.strptime(
            date_text,
            "%d-%b-%Y"
        ).date()

        today = datetime.now().date()

        return (
            today - timedelta(days=days)
            <= posted
            <= today
        )

    except Exception:
        return False


def fetch_siemens_jobs():

    print("\nChecking Siemens Direct Careers...")

    discovered = {}

    for query in QUERIES:

        try:
            jobs = search_query(
                query,
                max_pages=3
            )

            print(
                query + ":",
                len(jobs),
                "recent discovery jobs"
            )

            for job in jobs:
                discovered[
                    job["job_id"]
                ] = job

        except Exception as error:
            print(
                "Siemens search error:",
                query,
                error
            )

    print(
        "Unique Siemens discovery jobs:",
        len(discovered)
    )

    relevant = []

    for job in discovered.values():

        title_lower = job["title"].lower()

        if any(
            term in title_lower
            for term in BLOCKED_SENIOR
        ):
            continue

        if not any(
            term in title_lower
            for term in AI_TERMS
        ):
            continue

        try:
            detail = parse_detail(job)

        except Exception as error:
            print(
                "Siemens detail error:",
                job["job_id"],
                error
            )
            continue

        if not is_recent(
            detail["posted_since"],
            days=1
        ):
            continue

        location = detail["location"]

        if not location:
            location = ", ".join(
                x for x in [
                    detail["city"],
                    detail["state"],
                    detail["country"]
                ] if x
            )

        if not location_allowed(
            location + " " + detail["work_mode"],
            detail["description"]
        ):
            continue

        if requires_advanced_german(
            detail["description"]
        ):
            continue

        experience_lower = detail[
            "experience"
        ].lower()

        if any(
            term in title_lower
            for term in [
                "working student",
                "werkstudent"
            ]
        ):
            role_type = "Working Student"

        elif any(
            term in title_lower
            for term in [
                "intern",
                "internship",
                "praktikant",
                "praktikum"
            ]
        ):
            role_type = "Internship"

        elif (
            "junior" in title_lower
            or "student" in experience_lower
        ):
            role_type = "Junior"

        else:
            role_type = (
                detail["job_type"]
                or "Full-Time"
            )

        relevant.append({
            "id": "siemens-" + detail["job_id"],
            "company": "Siemens",
            "title": detail["title"],
            "location": location,
            "type": role_type,
            "description": detail["description"],
            "url": detail["url"],
            "posted_at": detail["posted_since"],
            "source": "Siemens"
        })

    print(
        "Fresh relevant Siemens jobs:",
        len(relevant)
    )

    return relevant
