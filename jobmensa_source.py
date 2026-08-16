import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

from location_filter import location_allowed


BASE_URL = "https://www.jobmensa.de"

SEARCH_URL = (
    "https://www.jobmensa.de/jobs-suchen"
    "?latitude=48.1351"
    "&longitude=11.5820"
    "&location=M%C3%BCnchen"
    "&radius=100"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


SIDE_JOB_TERMS = [
    "minijob",
    "nebenjob",
    "studentenjob",
    "ferienjob",
    "aushilfe",
    "werkstudent",
    "working student",
    "part-time",
    "part time",
    "teilzeit",
    "courier",
    "delivery",
    "driver",
    "logistik",
    "warehouse",
    "kommissionierer",
    "event",
    "hostess",
    "promotion",
    "data entry",
    "datenerfassung",
    "office",
    "customer support",
    "service",
]


def clean_text(value):
    return " ".join((value or "").split())


def parse_jobposting_jsonld(html):
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        raw = script.string

        if not raw:
            continue

        try:
            data = json.loads(raw)
        except Exception:
            continue

        if isinstance(data, dict) and data.get("@type") == "JobPosting":
            return data

        if isinstance(data, list):
            for item in data:
                if (
                    isinstance(item, dict)
                    and item.get("@type") == "JobPosting"
                ):
                    return item

    return {}


def is_fresh(published_at, max_age_minutes=180):
    if not published_at:
        return False

    try:
        published = datetime.fromisoformat(
            published_at.replace("Z", "+00:00")
        )

        now = datetime.now(timezone.utc)

        age_minutes = (
            now - published.astimezone(timezone.utc)
        ).total_seconds() / 60

        return 0 <= age_minutes <= max_age_minutes

    except Exception:
        return False


def is_side_job(title, text):
    low = f"{title} {text}".lower()

    return any(
        term in low
        for term in SIDE_JOB_TERMS
    )


def english_is_accepted(text):
    low = text.lower()

    # Explicit alternatives: English alone is sufficient
    alternative_patterns = [
        r"fluent in either german or english",
        r"either german or english",
        r"english\s+or\s+german",
        r"german\s+or\s+english",
        r"eine der folgenden sprachen",
    ]

    if (
        ("english" in low or "englisch" in low)
        and any(
            re.search(pattern, low, flags=re.DOTALL)
            for pattern in alternative_patterns
        )
    ):
        return True

    # Hard German requirement
    hard_german_patterns = [
        r"deutsch\s*\(fließend\)",
        r"deutsch\s*\(fliessend\)",
        r"deutsch\s*\(fortgeschritten\)",
        r"german\s*\(fluent\)",
        r"fluent german",
        r"native german",
        r"native-level german",
        r"german required",
        r"german mandatory",
    ]

    if any(
        re.search(pattern, low)
        for pattern in hard_german_patterns
    ):
        return False

    # English mentioned and no hard German requirement
    return "english" in low or "englisch" in low


def extract_location(text):
    locations = [
        "München",
        "Munich",
        "Garching",
        "Ismaning",
        "Unterföhring",
        "Unterschleißheim",
        "Oberschleißheim",
        "Dachau",
        "Fürstenfeldbruck",
        "Germering",
        "Starnberg",
        "Gilching",
        "Freising",
        "Erding",
        "Ottobrunn",
        "Unterhaching",
        "Taufkirchen",
        "Neubiberg",
        "Rosenheim",
        "Augsburg",
        "Ingolstadt",
        "Landshut",
        "Mühldorf",
        "Weilheim",
        "Wolfratshausen",
        "Bad Tölz",
        "Holzkirchen",
        "Gersthofen",
        "Eichenau",
        "Hallbergmoos",
        "Oberpfaffenhofen",
    ]

    for loc in locations:
        if loc.lower() in text.lower():
            return loc

    return ""


def fetch_jobmensa_jobs(max_age_minutes=180):
    print("Checking Jobmensa English Side Jobs...")

    r = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        timeout=30
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    links = {}
    
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        title = clean_text(
            a.get_text(" ", strip=True)
        )

        if "/jobs/in/" not in href:
            continue

        if not title:
            continue

        full_url = urljoin(
            BASE_URL,
            href
        )

        links[full_url] = title

    print(
        "Jobmensa discovery jobs:",
        len(links)
    )

    jobs = []

    for url, card_title in links.items():

        detail = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        if detail.status_code != 200:
            continue

        html = detail.text

        data = parse_jobposting_jsonld(
            html
        )

        published_at = clean_text(
            data.get("datePosted", "")
        )

        if not is_fresh(
            published_at,
            max_age_minutes=max_age_minutes
        ):
            continue

        detail_soup = BeautifulSoup(
            html,
            "html.parser"
        )

        text = clean_text(
            detail_soup.get_text(
                " ",
                strip=True
            )
        )

        title = clean_text(
            data.get("title", "")
        ) or card_title

        if not is_side_job(
            title,
            text
        ):
            continue

        if not english_is_accepted(
            text
        ):
            continue

        location = ""

        job_locations = data.get("jobLocation", [])

        if isinstance(job_locations, dict):
            job_locations = [job_locations]

        for item in job_locations:
            if not isinstance(item, dict):
                continue

            address = item.get("address", {})

            if isinstance(address, dict):
                location = clean_text(
                    address.get("addressLocality", "")
                )

            if location:
                break

        if not location:
            continue

        if not location_allowed(
            location,
            text
        ):
            continue

        job_id_match = re.search(
            r"Job ID:\s*(\d+)",
            text,
            flags=re.IGNORECASE
        )

        job_id = (
            job_id_match.group(1)
            if job_id_match
            else re.sub(
                r"\W+",
                "-",
                url.lower()
            )
        )

        jobs.append({
            "id": f"jobmensa-{job_id}",
            "company": "Jobmensa / jobvalley",
            "title": title,
            "location": location,
            "type": "Side Job",
            "description": text,
            "url": url,
            "posted_at": published_at,
            "source": "Jobmensa Side Jobs",
        })

    print(
        "Fresh English Jobmensa jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_jobmensa_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
