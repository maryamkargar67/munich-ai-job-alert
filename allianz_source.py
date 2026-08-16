import json
import requests
from datetime import datetime, timezone, timedelta

from location_filter import location_allowed
from language_filter import requires_advanced_german


URL = "https://careers.allianz.com/global/en/c/data-ai-jobs"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

MARKER = '"eagerLoadRefineSearch":'


def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%S.%f%z"
        )
    except Exception:
        return None


def is_fresh(posted_date, max_age_minutes=120):
    dt = parse_date(posted_date)

    if not dt:
        return False

    now = datetime.now(timezone.utc)
    age = now - dt.astimezone(timezone.utc)

    return (
        timedelta(0)
        <= age
        <= timedelta(minutes=max_age_minutes)
    )


def fetch_page(start):
    response = requests.get(
        URL,
        params={
            "from": start,
            "s": 1
        },
        headers=HEADERS,
        timeout=30
    )

    response.raise_for_status()

    html = response.text
    pos = html.find(MARKER)

    if pos == -1:
        return [], 0

    data, _ = json.JSONDecoder().raw_decode(
        html[pos + len(MARKER):]
    )

    jobs = (
        data
        .get("data", {})
        .get("jobs", [])
    )

    total = data.get("totalHits", 0)

    return jobs, total


def fetch_allianz_jobs():

    print("\nChecking Allianz Data & AI...")

    all_jobs = {}
    start = 0
    total = None

    while total is None or start < total:

        try:
            jobs, page_total = fetch_page(start)

            if total is None:
                total = page_total

            print(
                f"Allianz page from={start}:",
                len(jobs),
                "jobs"
            )

            for job in jobs:

                job_id = (
                    job.get("jobId")
                    or job.get("reqId")
                )

                if job_id:
                    all_jobs[str(job_id)] = job

            if not jobs:
                break

            start += 10

        except Exception as error:
            print(
                "Allianz page error:",
                start,
                error
            )
            break

    print(
        "Unique Allianz Data & AI jobs:",
        len(all_jobs)
    )

    results = []

    for job_id, job in all_jobs.items():

        posted_at = job.get(
            "postedDate",
            ""
        )

        # Freshness first
        if not is_fresh(
            posted_at,
            max_age_minutes=120
        ):
            continue

        title = job.get("title", "")
        title_lower = title.lower()

        description = job.get(
            "descriptionTeaser",
            ""
        )

        skills = job.get(
            "ml_skills",
            []
        )

        full_text = (
            title
            + " "
            + description
            + " "
            + " ".join(skills)
        )

        # Exclude senior roles
        if any(
            term in title_lower
            for term in [
                "senior",
                "principal",
                "staff ",
                "lead ",
                "head of",
                "director",
                "manager"
            ]
        ):
            continue

        locations = job.get(
            "multi_location",
            []
        )

        if locations:
            location = " | ".join(locations)
        else:
            location = (
                job.get("location")
                or job.get("cityStateCountry")
                or job.get("city")
                or ""
            )

        remote = job.get(
            "remote",
            ""
        )

        # Munich <=100 km OR Remote Germany
        if not location_allowed(
            f"{location} {remote}",
            description
        ):
            continue

        # Hard German-language exclusion
        if requires_advanced_german(
            full_text
        ):
            continue

        if any(
            term in title_lower
            for term in [
                "working student",
                "werkstudent"
            ]
        ):
            job_type = "Working Student"

        elif any(
            term in title_lower
            for term in [
                "intern",
                "internship",
                "praktikant",
                "praktikum"
            ]
        ):
            job_type = "Internship"

        elif "junior" in title_lower:
            job_type = "Junior"

        else:
            job_type = (
                job.get("type")
                or job.get("employmentType")
                or "Full-Time"
            )

        results.append({
            "id": "allianz-" + job_id,
            "company": job.get(
                "employingEntity",
                "Allianz"
            ),
            "title": title,
            "location": location,
            "type": job_type,
            "description": description,
            "url": (
                job.get("applyUrl")
                or job.get("imApplyUrl")
                or ""
            ),
            "posted_at": posted_at,
            "created_at": job.get(
                "dateCreated",
                ""
            ),
            "source": "Allianz"
        })

    results.sort(
        key=lambda x: parse_date(
            x["posted_at"]
        ) or datetime.min.replace(
            tzinfo=timezone.utc
        ),
        reverse=True
    )

    print(
        "Fresh relevant Allianz jobs:",
        len(results)
    )

    return results
