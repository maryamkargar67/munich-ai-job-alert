import json
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

from location_filter import location_allowed
from language_filter import requires_advanced_german


SEARCH_URLS = [
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-artificial+intelligence?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-machine+learning?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-data+science?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-computer+vision?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-deep+learning?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-llm?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-generative+ai?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-Werkstudent+AI?orderBy=date&distance=100",
    "https://www.heyjobs.co/de-de/jobs-in-M%C3%BCnchen-als-Werkstudent+Data+Science?orderBy=date&distance=100",
]


AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "computer vision",
    "data science",
    "data scientist",
    "ai engineer",
    "ml engineer",
    "llm",
    "large language model",
    "generative ai",
    "genai",
    "nlp",
    "natural language processing",
    "künstliche intelligenz",
    "bildverarbeitung",
]


STUDENT_TERMS = [
    "working student",
    "werkstudent",
    "intern",
    "internship",
    "praktik",
    "junior",
    "graduate",
    "entry level",
    "entry-level",
    "trainee",
]


BLOCKED_SENIOR_TERMS = [
    "senior",
    "staff",
    "principal",
    "lead",
    "head of",
    "director",
]


def clean_text(value):
    return " ".join((value or "").split())


def extract_job_id(job):
    uris = (job.get("application_info") or {}).get("uris") or []

    if not uris:
        return ""

    url = uris[0]

    match = re.search(
        r"/jobs/([0-9a-fA-F-]{36})",
        url,
    )

    if match:
        return match.group(1)

    return urlparse(url).path.rstrip("/").split("/")[-1]


def extract_initial_jobs(html):
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all("script"):
        content = script.string or script.get_text()

        if (
            "publicationData" not in content
            or '"search"' not in content
            or '"jobs"' not in content
        ):
            continue

        try:
            data = json.loads(content)

            jobs = (
                data["props"]
                ["pageProps"]
                ["initialState"]
                ["search"]
                ["jobs"]
            )

            return jobs

        except Exception:
            continue

    return []


def get_detail_text(url, headers):
    try:
        r = requests.get(
            url,
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
    except Exception as error:
        print("HeyJobs detail error:", error)
        return ""

    soup = BeautifulSoup(
        r.text,
        "html.parser",
    )

    return clean_text(
        soup.get_text(" ", strip=True)
    )


def infer_job_type(title, raw_job):
    title_lower = title.lower()

    if (
        "werkstudent" in title_lower
        or "working student" in title_lower
    ):
        return "Working Student"

    if (
        "intern" in title_lower
        or "praktik" in title_lower
    ):
        return "Internship"

    if any(
        term in title_lower
        for term in [
            "junior",
            "graduate",
            "entry level",
            "entry-level",
            "trainee",
        ]
    ):
        return "Junior / Early Career"

    employment_types = (
        ((raw_job.get("custom_attributes") or {})
         .get("employment_types") or {})
        .get("string_values")
        or []
    )

    if "working_student" in employment_types:
        return "Working Student"

    if "internship" in employment_types:
        return "Internship"

    return "Other"


def fetch_heyjobs_jobs():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    seen_ids = set()
    results = []

    for search_url in SEARCH_URLS:
        try:
            r = requests.get(
                search_url,
                headers=headers,
                timeout=30,
            )
            r.raise_for_status()
        except Exception as error:
            print("HeyJobs search error:", error)
            continue

        items = extract_initial_jobs(r.text)

        print(
            "HeyJobs discovery jobs:",
            len(items),
        )

        for item in items:
            raw_job = item.get("job", {})

            publication = (
                raw_job.get("publicationData")
                or {}
            )

            days = publication.get("days")

            # Only jobs published today.
            if days != 0:
                continue

            job_id = extract_job_id(raw_job)

            if not job_id:
                continue

            if job_id in seen_ids:
                continue

            seen_ids.add(job_id)

            title = clean_text(
                raw_job.get("title", "")
            )

            company = clean_text(
                raw_job.get(
                    "company_display_name",
                    ""
                )
            )

            addresses = (
                raw_job.get("addresses")
                or []
            )

            location = clean_text(
                addresses[0]
                if addresses
                else ""
            )

            uris = (
                (raw_job.get("application_info") or {})
                .get("uris")
                or []
            )

            if not uris:
                continue

            url = uris[0]

            if not title:
                continue

            title_lower = title.lower()

            if any(
                term in title_lower
                for term in BLOCKED_SENIOR_TERMS
            ):
                continue

            if not location_allowed(location):
                continue

            job_type = infer_job_type(
                title,
                raw_job,
            )

            student_match = any(
                term in title_lower
                for term in STUDENT_TERMS
            )

            # Reject ordinary full-time roles unless clearly early-career.
            if (
                job_type == "Other"
                and not student_match
            ):
                continue

            detail_text = get_detail_text(
                url,
                headers,
            )

            if not detail_text:
                continue

            full_lower = (
                title
                + " "
                + detail_text
            ).lower()

            ai_match = any(
                term in full_lower
                for term in AI_TERMS
            )

            if not ai_match:
                continue

            if requires_advanced_german(
                detail_text
            ):
                continue

            results.append({
                "id": f"heyjobs-{job_id}",
                "company": company or "HeyJobs",
                "title": title,
                "location": location,
                "type": job_type,
                "url": url,
                "description": detail_text,
                "posted_at": "today",
                "source": "HeyJobs",
            })

    print(
        "Fresh relevant HeyJobs jobs:",
        len(results),
    )

    return results


if __name__ == "__main__":
    jobs = fetch_heyjobs_jobs()

    for job in jobs:
        print()
        print("TITLE:", job["title"])
        print("COMPANY:", job["company"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
