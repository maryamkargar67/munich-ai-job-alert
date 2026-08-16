import time
from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://api.smartrecruiters.com/v1/companies/BoschGroup/postings"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

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

STUDENT_TERMS = [
    "working student",
    "werkstudent",
    "intern",
    "internship",
    "praktikant",
    "praktikum",
    "student",
    "graduate",
    "junior",
    "trainee",
]


def get_with_retry(url, params=None):
    for attempt in range(3):
        try:
            r = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()
            return r.json()
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


def is_blocked_senior(title):
    title = (title or "").lower()
    return any(term in title for term in BLOCKED_SENIOR_TERMS)


def classify_role(title, employment_label, experience_label):
    text = f"{title} {employment_label} {experience_label}".lower()

    if "working student" in text or "werkstudent" in text:
        return "Working Student"

    if (
        "internship" in text
        or "intern" in text
        or "praktikant" in text
        or "praktikum" in text
    ):
        return "Internship"

    if any(term in text for term in [
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


def is_early_career(title, role_type, experience_label):
    if role_type in {
        "Working Student",
        "Internship",
        "Junior",
        "Part-Time",
    }:
        return True

    text = f"{title} {experience_label}".lower()

    return any(term in text for term in [
        "entry level",
        "entry-level",
        "graduate",
        "junior",
        "student",
    ])


def extract_description(detail):
    sections = (
        detail.get("jobAd", {})
        .get("sections", {})
    )

    parts = []

    for key in [
        "jobDescription",
        "qualifications",
        "additionalInformation",
    ]:
        section = sections.get(key, {})
        parts.append(
            html_to_text(section.get("text", ""))
        )

    return " ".join(parts).strip()


def fetch_bosch_jobs(max_age_minutes=180):
    print("Checking Bosch Direct Careers...")

    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=max_age_minutes
    )

    discovered = {}

    for term in SEARCH_TERMS:
        try:
            data = get_with_retry(
                BASE_URL,
                {
                    "limit": 100,
                    "offset": 0,
                    "country": "de",
                    "q": term,
                },
            )
        except Exception as error:
            print(f"Bosch '{term}' error:", error)
            continue

        jobs = data.get("content", [])

        print(
            f"Bosch '{term}': {len(jobs)} discovery jobs"
        )

        for job in jobs:
            job_id = job.get("id")
            released = job.get("releasedDate")

            if not job_id or not released:
                continue

            try:
                posted = datetime.fromisoformat(
                    released.replace("Z", "+00:00")
                )
            except Exception:
                continue

            if posted < cutoff:
                continue

            discovered[job_id] = job

    print(
        "Fresh Bosch discovery jobs:",
        len(discovered)
    )

    relevant = []

    for job_id, job in discovered.items():
        title = (job.get("name") or "").strip()

        if is_blocked_senior(title):
            continue

        try:
            detail = get_with_retry(
                f"{BASE_URL}/{job_id}"
            )
        except Exception as error:
            print(
                f"Bosch detail error {job_id}:",
                error,
            )
            continue

        description = extract_description(detail)
        combined_text = f"{title} {description}"

        if not has_ai_relevance(combined_text):
            continue

        employment = (
            detail.get("typeOfEmployment", {})
            .get("label", "")
        )

        experience = (
            detail.get("experienceLevel", {})
            .get("label", "")
        )

        role_type = classify_role(
            title,
            employment,
            experience,
        )

        if not is_early_career(
            title,
            role_type,
            experience,
        ):
            continue

        if requires_advanced_german(
            combined_text
        ):
            continue

        location = detail.get("location", {})
        city = location.get("city", "")
        full_location = location.get(
            "fullLocation",
            city
        )

        remote_hint = ""

        if location.get("remote"):
            remote_hint = " Remote Germany"

        if not location_allowed(
            full_location,
            description + remote_hint,
        ):
            continue

        relevant.append({
            "id": f"bosch-{job_id}",
            "company": "Bosch Group",
            "title": title,
            "location": full_location,
            "type": role_type,
            "url": detail.get(
                "postingUrl",
                job.get("ref", "")
            ),
            "description": description,
            "source": "Bosch",
            "posted_at": detail.get(
                "releasedDate",
                job.get("releasedDate", "")
            ),
        })

    relevant.sort(
        key=lambda x: x["posted_at"],
        reverse=True,
    )

    print(
        "Fresh relevant Bosch jobs:",
        len(relevant)
    )

    return relevant


if __name__ == "__main__":
    jobs = fetch_bosch_jobs()

    print()
    print("=" * 70)

    for job in jobs:
        print(job["posted_at"])
        print(job["type"])
        print(job["title"])
        print(job["location"])
        print(job["url"])
        print()
