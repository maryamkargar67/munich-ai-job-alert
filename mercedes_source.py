from datetime import datetime, timezone, timedelta

import requests
from bs4 import BeautifulSoup

from location_filter import location_allowed
from language_filter import requires_advanced_german


API_URL = "https://jobs.api.mercedes-benz.com/search"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
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

STRONG_AI_TERMS = [
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
    "agentic ai",
    "ai agent",
    "ai agents",
    "ki-agent",
    "ki agent",
]

TITLE_AI_TERMS = STRONG_AI_TERMS + [
    "data science",
    "data scientist",
    "ai engineer",
    "ai developer",
    "applied scientist",
    "data & ai",
    "data and ai",
    "datenanalyse & ki",
    "datenanalyse und ki",
    "künstliche intelligenz",
    "kuenstliche intelligenz",
    " ki ",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "principal",
    "lead ",
    "director",
    "head of",
    "chief",
]


def clean_html(value):
    return BeautifulSoup(
        value or "",
        "html.parser"
    ).get_text(" ", strip=True)


def has_ai_relevance(title, description):
    title_text = (title or "").lower()
    desc_text = (description or "").lower()

    if any(term in title_text for term in TITLE_AI_TERMS):
        return True

    return any(
        term in desc_text
        for term in STRONG_AI_TERMS
    )


def is_blocked_senior(title):
    text = (title or "").lower()

    return any(
        term in text
        for term in BLOCKED_SENIOR_TERMS
    )


def classify_role(title, schedules, career_levels):
    text = " ".join([
        title or "",
        schedules or "",
        career_levels or "",
    ]).lower()

    if (
        "working student" in text
        or "werkstudent" in text
    ):
        return "Working Student"

    if any(x in text for x in [
        "internship",
        "intern ",
        "intern*",
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

    if (
        (
            "teilzeit" in text
            and "teilzeitgeeignet" not in text
        )
        or "part-time" in text
        or "part time" in text
    ):
        return "Part-Time"

    return "Full-Time"


def is_early_career(title, role_type, career_levels):
    if role_type in {
        "Working Student",
        "Internship",
        "Junior",
        "Part-Time",
    }:
        return True

    text = f"{title} {career_levels}".lower()

    return any(x in text for x in [
        "junior",
        "graduate",
        "trainee",
        "entry level",
        "entry-level",
        "student",
    ])


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).replace(tzinfo=timezone.utc)
    except Exception:
        return None


def extract_description(job):
    parts = []

    for section in job.get(
        "PositionFormattedDescription",
        []
    ):
        if not isinstance(section, dict):
            continue

        for value in section.values():
            if isinstance(value, str):
                parts.append(
                    clean_html(value)
                )

    return " ".join(parts).strip()


def extract_named_values(items):
    values = []

    for item in items or []:
        if isinstance(item, dict):
            name = item.get("Name")
            if name:
                values.append(name)

    return " ".join(values)


def extract_location(job):
    locations = job.get(
        "PositionLocation",
        []
    )

    if not locations:
        return ""

    loc = locations[0]

    city = loc.get("CityName", "")
    country = loc.get("CountryCode", "")
    display = loc.get("DisplayName", "")

    if city:
        return f"{city}, {country}"

    return display


def build_payload(term, first_item=1, count=50):
    return {
        "LanguageCode": "DE",
        "SearchParameters": {
            "FirstItem": first_item,
            "CountItem": count,
            "Sort": [
                {
                    "Criterion": "PublicationStartDate",
                    "Direction": "DESC"
                }
            ],
            "MatchedObjectDescriptor": [
                "ID",
                "PositionID",
                "PositionTitle",
                "PositionURI",
                "OrganizationName",
                "ParentOrganizationName",
                "PositionLocation.CityName",
                "PositionLocation.DisplayName",
                "PositionLocation.CountryCode",
                "PositionLocation.Country",
                "PositionLocation.Latitude",
                "PositionLocation.Longitude",
                "PositionFormattedDescription.Content",
                "PublicationStartDate",
                "PositionStartDate",
                "PositionSchedule.Name",
                "CareerLevel.Name",
                "JobCategory.Name",
                "PositionOfferingType.Name",
                "ApplyURI"
            ]
        },
        "SearchCriteria": [
            {
                "CriterionName":
                    "PositionFormattedDescription.Content",
                "CriterionValue": [term]
            },
            {
                "CriterionName":
                    "PositionLocation.Country",
                "CriterionValue": ["329"]
            }
        ]
    }


def fetch_mercedes_jobs(max_age_days=3):
    print("Checking Mercedes-Benz Direct Careers...")

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=max_age_days)
    )

    discovered = {}

    for term in SEARCH_TERMS:
        try:
            r = requests.post(
                API_URL,
                json=build_payload(term),
                headers=HEADERS,
                timeout=30,
            )
            r.raise_for_status()

            data = r.json()
            result = data.get(
                "SearchResult",
                {}
            )

            jobs = result.get(
                "SearchResultItems",
                []
            )

            print(
                f"Mercedes '{term}': "
                f"{len(jobs)} discovery jobs"
            )

            for item in jobs:
                job = item.get(
                    "MatchedObjectDescriptor",
                    {}
                )

                job_id = str(
                    job.get("ID", "")
                )

                if not job_id:
                    continue

                posted = parse_date(
                    job.get(
                        "PublicationStartDate"
                    )
                )

                if not posted:
                    continue

                if posted < cutoff:
                    continue

                discovered[job_id] = job

        except Exception as error:
            print(
                f"Mercedes '{term}' error:",
                error
            )

    print(
        "Fresh Mercedes discovery jobs:",
        len(discovered)
    )

    relevant = []

    for job_id, job in discovered.items():

        title = (
            job.get("PositionTitle")
            or ""
        ).strip()

        if is_blocked_senior(title):
            continue

        description = extract_description(job)

        if not has_ai_relevance(
            title,
            description
        ):
            continue

        schedules = extract_named_values(
            job.get("PositionSchedule")
        )

        career_levels = extract_named_values(
            job.get("CareerLevel")
        )

        role_type = classify_role(
            title,
            schedules,
            career_levels
        )

        if not is_early_career(
            title,
            role_type,
            career_levels
        ):
            continue

        combined = f"{title} {description}"

        if requires_advanced_german(
            combined
        ):
            continue

        location = extract_location(job)

        if not location_allowed(
            location,
            description
        ):
            continue

        url = (
            job.get("PositionURI")
            or ""
        )

        relevant.append({
            "id": f"mercedes-{job_id}",
            "company": (
                job.get("ParentOrganizationName")
                or "Mercedes-Benz"
            ),
            "title": title,
            "location": location,
            "type": role_type,
            "url": url,
            "description": description,
            "source": "Mercedes-Benz",
            "posted_at": job.get(
                "PublicationStartDate",
                ""
            ),
        })

    relevant.sort(
        key=lambda x: x["posted_at"],
        reverse=True
    )

    print(
        "Fresh relevant Mercedes jobs:",
        len(relevant)
    )

    return relevant


if __name__ == "__main__":
    jobs = fetch_mercedes_jobs()

    print()
    print("=" * 70)

    for job in jobs:
        print(job["posted_at"])
        print(job["type"])
        print(job["title"])
        print(job["location"])
        print(job["url"])
        print()
