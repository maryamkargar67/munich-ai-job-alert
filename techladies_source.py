import json
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://www.hiretechladies.com/jobs"
HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

AI_TITLE_TERMS = [
    "artificial intelligence",
    "machine learning",
    "data science",
    "data scientist",
    "computer vision",
    "generative ai",
    "genai",
    "llm",
    "large language model",
    "ai engineer",
    "ai developer",
    "ai scientist",
    "ml engineer",
    "ml scientist",
    "nlp",
    "deep learning",
]

AI_DESCRIPTION_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "computer vision",
    "generative ai",
    "genai",
    "large language model",
    " llm ",
    "natural language processing",
    " nlp ",
    "pytorch",
    "tensorflow",
    "scikit-learn",
    "transformer",
]

EARLY_CAREER_TERMS = [
    "working student",
    "werkstudent",
    "intern",
    "internship",
    "junior",
    "entry level",
    "entry-level",
    "graduate",
    "student",
    "part-time",
    "part time",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "staff",
    "principal",
    "lead ",
    "tech lead",
    "director",
    "head of",
    "manager",
    "vice president",
    "vp ",
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


def get_job_links(max_pages=10):
    links = []
    seen = set()

    for page in range(1, max_pages + 1):
        if page == 1:
            url = BASE_URL
        else:
            url = f"{BASE_URL}?690dd383_page={page}"

        r = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        page_links = []

        for a in soup.find_all("a", href=True):
            href = a["href"]

            if href.startswith("/jobs/"):
                href = "https://www.hiretechladies.com" + href

            if not href.startswith(
                "https://www.hiretechladies.com/jobs/"
            ):
                continue

            if href not in seen:
                seen.add(href)
                page_links.append(href)
                links.append(href)

        print(
            f"Tech Ladies page {page}: "
            f"{len(page_links)} new job links"
        )

        if page > 1 and not page_links:
            break

    return links


def extract_jobposting(soup):
    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        raw = script.string or script.get_text()

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        objects = data if isinstance(data, list) else [data]

        for obj in objects:
            if not isinstance(obj, dict):
                continue

            if obj.get("@type") == "JobPosting":
                return obj

            graph = obj.get("@graph")

            if isinstance(graph, list):
                for item in graph:
                    if (
                        isinstance(item, dict)
                        and item.get("@type") == "JobPosting"
                    ):
                        return item

    return None


def extract_location(data):
    job_location = data.get("jobLocation")

    if isinstance(job_location, list):
        locations = []

        for item in job_location:
            if not isinstance(item, dict):
                continue

            address = item.get("address", {})

            if isinstance(address, dict):
                loc = (
                    address.get("addressLocality")
                    or address.get("addressRegion")
                    or address.get("addressCountry")
                    or ""
                )

                if loc:
                    locations.append(clean_text(str(loc)))

        if locations:
            return ", ".join(dict.fromkeys(locations))

    if isinstance(job_location, dict):
        address = job_location.get("address", {})

        if isinstance(address, dict):
            parts = []

            for key in [
                "addressLocality",
                "addressRegion",
                "addressCountry"
            ]:
                value = address.get(key)

                if isinstance(value, dict):
                    value = value.get("name", "")

                if value:
                    parts.append(clean_text(str(value)))

            if parts:
                return ", ".join(dict.fromkeys(parts))

    return "Location Not Found"


def is_recent(date_posted, max_age_days=7):
    if not date_posted:
        return True

    try:
        posted = datetime.strptime(
            date_posted[:10],
            "%Y-%m-%d"
        ).date()

        cutoff = (
            datetime.now().date()
            - timedelta(days=max_age_days)
        )

        return posted >= cutoff

    except Exception:
        return True


def has_ai_relevance(title, description):
    title_low = f" {title.lower()} "
    description_low = f" {description.lower()} "

    title_match = any(
        term in title_low
        for term in AI_TITLE_TERMS
    )

    if title_match:
        return True

    strong_description_matches = sum(
        1
        for term in AI_DESCRIPTION_TERMS
        if term in description_low
    )

    return strong_description_matches >= 2


def classify_type(title, employment_type):
    text = f"{title} {employment_type}".lower()

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

    if any(term in text for term in BLOCKED_STUDENT_TERMS):
        return False

    if any(term in title.lower() for term in BLOCKED_SENIOR_TERMS):
        return False

    if job_type in [
        "Working Student",
        "Internship",
        "Part-Time"
    ]:
        return True

    if any(term in text for term in EARLY_CAREER_TERMS):
        return True

    # Full-time roles are allowed only when not obviously senior.
    return job_type == "Full-Time"


def fetch_techladies_jobs(
    max_age_days=7,
    max_pages=10
):
    print("Checking Tech Ladies Job Board...")

    links = get_job_links(max_pages=max_pages)

    print(
        "Unique Tech Ladies discovery jobs:",
        len(links)
    )

    jobs = []

    for index, url in enumerate(links, start=1):
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )
            r.raise_for_status()

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            data = extract_jobposting(soup)

            if not data:
                continue

            title = clean_text(
                str(data.get("title", ""))
            )

            description_html = str(
                data.get("description", "")
            )

            description = clean_text(
                BeautifulSoup(
                    description_html,
                    "html.parser"
                ).get_text(" ", strip=True)
            )

            company_data = data.get(
                "hiringOrganization",
                {}
            )

            if isinstance(company_data, dict):
                company = clean_text(
                    str(company_data.get("name", ""))
                )
            else:
                company = ""

            location = extract_location(data)

            date_posted = clean_text(
                str(data.get("datePosted", ""))
            )

            employment_type = data.get(
                "employmentType",
                ""
            )

            if isinstance(employment_type, list):
                employment_type = " ".join(
                    str(x)
                    for x in employment_type
                )

            employment_type = clean_text(
                str(employment_type)
            )

            if not is_recent(
                date_posted,
                max_age_days=max_age_days
            ):
                continue

            if not has_ai_relevance(
                title,
                description
            ):
                continue

            job_type = classify_type(
                title,
                employment_type
            )

            if not is_early_career(
                title,
                description,
                job_type
            ):
                continue

            combined_text = (
                f"{title} {description}"
            )

            if requires_advanced_german(
                combined_text
            ):
                continue

            if not location_allowed(
                location,
                description
            ):
                continue

            job_id = re.sub(
                r"^https?://www\.hiretechladies\.com/jobs/",
                "",
                url
            ).strip("/")

            jobs.append({
                "id": f"techladies-{job_id}",
                "company": company or "Unknown",
                "title": title,
                "location": location,
                "type": job_type,
                "description": description,
                "url": url,
                "posted_at": date_posted,
                "source": "Tech Ladies",
            })

        except Exception as e:
            print(
                f"Tech Ladies job error "
                f"{index}: {e}"
            )

    print(
        "Fresh relevant Tech Ladies jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_techladies_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("DATE:", job["posted_at"])
        print("COMPANY:", job["company"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
