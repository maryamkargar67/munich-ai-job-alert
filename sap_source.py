import time
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from datetime import datetime, timedelta

from location_filter import location_allowed
from language_filter import requires_advanced_german


SEARCH_URL = "https://jobs.sap.com/search/"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "data science",
    "data scientist",
    "generative ai",
    "gen ai",
    "agentic ai",
    "llm",
    "large language model",
    "computer vision",
    "ai developer",
    "ai engineer",
    "ai architect",
    "ai consultant",
    "applied scientist",
    "nlp",
    "natural language processing",
]

STUDENT_TERMS = [
    "working student",
    "werkstudent",
    "intern",
    "internship",
    "student",
    "junior",
    "jr.",
    "graduate",
    "ixp",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "lead",
    "chief",
    "head of",
    "director",
    "manager",
]


def clean(text):
    return " ".join((text or "").split())


def is_candidate_title(title):
    text = title.lower()

    return (
        any(term in text for term in AI_TERMS)
        or any(term in text for term in STUDENT_TERMS)
    )


def is_blocked_title(title):
    text = title.lower()

    return any(
        term in text
        for term in BLOCKED_SENIOR_TERMS
    )


def has_ai_relevance(title, description):
    text = f"{title} {description}".lower()

    return any(
        term in text
        for term in AI_TERMS
    )


def get_role_type(title, career, employment):
    text = f"{title} {career} {employment}".lower()

    if (
        "working student" in text
        or "werkstudent" in text
        or "student" in career.lower()
    ):
        return "Working Student"

    if (
        "internship" in text
        or " intern" in text
        or "ixp" in text
    ):
        return "Internship"

    if (
        "junior" in text
        or "jr." in text
        or "graduate" in career.lower()
    ):
        return "Junior"

    if (
        "part time" in text
        or "part-time" in text
    ):
        return "Part-Time"

    return "Full-Time"


def is_early_career(title, career, role_type):
    if role_type in [
        "Working Student",
        "Internship",
        "Junior",
    ]:
        return True

    title_lower = title.lower()
    career_lower = career.lower()

    if "graduate" in career_lower:
        return True

    if (
        "junior" in title_lower
        or "jr." in title_lower
    ):
        return True

    return False


def parse_posted_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%b %d, %Y"
        ).date()
    except ValueError:
        return None


def is_recent(value, days=1):
    posted = parse_posted_date(value)

    if not posted:
        return False

    today = datetime.now().date()

    return posted >= today - timedelta(days=days)


def get_with_retry(url, params=None, attempts=3):
    for attempt in range(1, attempts + 1):
        try:
            r = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=60
            )

            r.raise_for_status()

            if "/errorpage/" in r.url:
                raise RuntimeError(
                    "SAP returned error page"
                )

            return r

        except Exception as error:
            if attempt == attempts:
                print(
                    "SAP request failed:",
                    type(error).__name__,
                    "|",
                    url
                )
                return None

            time.sleep(2)

    return None


def get_property(soup, property_id):
    tag = soup.find(
        attrs={
            "data-careersite-propertyid":
            property_id
        }
    )

    if not tag:
        return ""

    return clean(
        tag.get_text(" ", strip=True)
    )


def get_job_detail(url):
    r = get_with_retry(url)

    if not r:
        return None

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    posted_date = get_property(
        soup,
        "date"
    )

    career = get_property(
        soup,
        "customfield3"
    )

    employment = get_property(
        soup,
        "shifttype"
    )

    description = clean(
        soup.get_text(" ", strip=True)
    )

    return {
        "posted_date": posted_date,
        "career": career,
        "employment": employment,
        "description": description,
    }


def fetch_search_page(startrow):
    r = get_with_retry(
        SEARCH_URL,
        params={
            "q": "",
            "locationsearch": "Germany",
            "sortColumn": "referencedate",
            "sortDirection": "desc",
            "startrow": startrow,
        }
    )

    if not r:
        return []

    soup = BeautifulSoup(
        r.text,
        "html.parser"
    )

    jobs = []

    for row in soup.select("tr.data-row"):
        title_tag = row.select_one(
            "a.jobTitle-link"
        )

        location_tag = row.select_one(
            ".colLocation .jobLocation"
        )

        if not title_tag:
            continue

        title = clean(
            title_tag.get_text(
                " ",
                strip=True
            )
        )

        location = (
            clean(
                location_tag.get_text(
                    " ",
                    strip=True
                )
            )
            if location_tag
            else ""
        )

        url = urljoin(
            r.url,
            title_tag.get(
                "href",
                ""
            )
        )

        match = re.search(
            r"/(\d+)/?$",
            url
        )

        job_number = (
            match.group(1)
            if match
            else url
        )

        jobs.append({
            "id": job_number,
            "title": title,
            "location": location,
            "url": url,
        })

    return jobs


def fetch_sap_jobs(max_pages=5):
    print(
        "Checking SAP Direct Careers..."
    )

    discovered = {}

    for page in range(max_pages):
        startrow = page * 25

        jobs = fetch_search_page(
            startrow
        )

        print(
            f"SAP Germany page "
            f"{page + 1}: "
            f"{len(jobs)} jobs"
        )

        if not jobs:
            break

        for job in jobs:
            discovered[
                job["id"]
            ] = job

    print(
        "Unique SAP Germany jobs:",
        len(discovered)
    )

    relevant = []

    for job in discovered.values():
        title = job["title"]

        if not is_candidate_title(
            title
        ):
            continue

        if is_blocked_title(
            title
        ):
            continue

        detail = get_job_detail(
            job["url"]
        )

        if not detail:
            continue

        if not is_recent(
            detail["posted_date"],
            days=1
        ):
            continue

        if not has_ai_relevance(
            title,
            detail["description"]
        ):
            continue

        phd_text = f"{title} {detail['description']}".lower()

        if (
            "phd internship" in phd_text
            or "phd student" in phd_text
            or "postdoc" in phd_text
            or "postdocs" in phd_text
        ):
            continue

        role_type = get_role_type(
            title,
            detail["career"],
            detail["employment"]
        )

        if not is_early_career(
            title,
            detail["career"],
            role_type
        ):
            continue

        if requires_advanced_german(
            detail["description"]
        ):
            continue

        if not location_allowed(
            job["location"],
            detail["description"]
        ):
            continue

        relevant.append({
            "id": (
                "sap-"
                + str(job["id"])
            ),
            "company": "SAP",
            "title": title,
            "location": job["location"],
            "type": role_type,
            "description": detail[
                "description"
            ],
            "url": job["url"],
            "source": "SAP",
            "posted_at": detail[
                "posted_date"
            ],
        })

    print(
        "Fresh relevant SAP jobs:",
        len(relevant)
    )

    return relevant


if __name__ == "__main__":
    jobs = fetch_sap_jobs()

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
        print(
            job["location"]
        )
        print(
            job["url"]
        )
        print()
