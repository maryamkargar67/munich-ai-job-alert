import json
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urljoin

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://www.studentjob.de"
SEARCH_URL = "https://www.studentjob.de/nebenjob/munchen"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def clean_text(value):
    return " ".join((value or "").split())


def parse_jobposting_jsonld(html):
    soup = BeautifulSoup(html, "html.parser")

    for script in soup.find_all(
        "script",
        attrs={"type": "application/ld+json"}
    ):
        raw = script.string or ""

        try:
            data = json.loads(raw)
        except Exception:
            continue

        items = data if isinstance(data, list) else [data]

        for item in items:
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


def extract_location(data):
    job_locations = data.get("jobLocation", [])

    if isinstance(job_locations, dict):
        job_locations = [job_locations]

    for item in job_locations:
        if not isinstance(item, dict):
            continue

        address = item.get("address", {})

        if not isinstance(address, dict):
            continue

        location = clean_text(
            address.get("addressLocality", "")
        )

        if location:
            return location

    return ""


def get_language_section(page_text):
    match = re.search(
        r"Sprachkenntnisse\s+(.+?)(?:\s+[A-ZÄÖÜ][A-Za-zÄÖÜäöüß /()-]+ Stellenangebote|\s+Bewirb dich jetzt|\s+Auf einen Blick)",
        page_text,
        flags=re.IGNORECASE
    )

    if match:
        return clean_text(match.group(1))

    return ""


def english_is_accepted(page_text, description):
    page_low = page_text.lower()
    desc_low = description.lower()

    full_text = f"{page_text} {description}"

    # Shared hard German requirement filter
    if requires_advanced_german(full_text):
        return False

    # Additional StudentJob wording
    hard_german_patterns = [
        r"fließend(?:e|er|es)?\s+deutsch",
        r"fliessend(?:e|er|es)?\s+deutsch",
        r"deutsch\s+fließend",
        r"deutsch\s+fliessend",
        r"sehr\s+gut(?:e|er|es)?\s+deutsch",
        r"gute\s+deutschkenntnisse",
    ]

    if any(
        re.search(pattern, full_text.lower())
        for pattern in hard_german_patterns
    ):
        return False

    # Driving licence / Führerschein hard filter
    driving_licence_patterns = [
        r"führerschein\s+(?:der\s+)?klasse\s+b",
        r"fuehrerschein\s+(?:der\s+)?klasse\s+b",
        r"fahrerlaubnis\s+(?:der\s+)?klasse\s+b",
        r"führerschein\s+b\b",
        r"fuehrerschein\s+b\b",
        r"driving\s+licen[cs]e\s+(?:class\s+)?b",
        r"class\s+b\s+driving\s+licen[cs]e",
    ]

    if any(
        re.search(pattern, full_text.lower())
        for pattern in driving_licence_patterns
    ):
        return False

    language_section = get_language_section(page_text)
    lang_low = language_section.lower()

    if not language_section:
        return False

    has_english = (
        "englisch" in lang_low
        or "english" in lang_low
    )

    has_german = (
        "deutsch" in lang_low
        or "german" in lang_low
    )

    # German only
    if has_german and not has_english:
        return False

    # English listed and no hard German requirement in description
    if has_english:
        return True

    return False


def fetch_studentjob_jobs(max_age_minutes=180):
    print("Checking StudentJob English Side Jobs...")

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

        if "/stellenangebote/" not in href:
            continue

        title = clean_text(
            a.get_text(" ", strip=True)
        )

        if not title:
            continue

        full_url = urljoin(
            BASE_URL,
            href
        )

        links[full_url] = title

    print(
        "StudentJob discovery jobs:",
        len(links)
    )

    jobs = []

    for url, card_title in links.items():

        try:
            detail = requests.get(
                url,
                headers=HEADERS,
                timeout=30
            )
        except Exception:
            continue

        if detail.status_code != 200:
            continue

        html = detail.text

        data = parse_jobposting_jsonld(html)

        if not data:
            continue

        published_at = clean_text(
            data.get("datePosted", "")
        )

        if not is_fresh(
            published_at,
            max_age_minutes=max_age_minutes
        ):
            continue

        location = extract_location(data)

        if not location:
            continue

        detail_soup = BeautifulSoup(
            html,
            "html.parser"
        )

        page_text = clean_text(
            detail_soup.get_text(
                " ",
                strip=True
            )
        )

        description = clean_text(
            BeautifulSoup(
                data.get("description", ""),
                "html.parser"
            ).get_text(
                " ",
                strip=True
            )
        )

        if not english_is_accepted(
            page_text,
            description
        ):
            continue

        if not location_allowed(
            location,
            description
        ):
            continue

        title = clean_text(
            data.get("title", "")
        ) or card_title

        job_id_match = re.search(
            r"/stellenangebote/(\d+)-",
            url
        )

        if job_id_match:
            job_id = job_id_match.group(1)
        else:
            job_id = re.sub(
                r"\W+",
                "-",
                url.lower()
            )

        jobs.append({
            "id": f"studentjob-{job_id}",
            "company": "StudentJob",
            "title": title,
            "location": location,
            "type": "Side Job",
            "description": description,
            "url": url,
            "posted_at": published_at,
            "source": "StudentJob Side Jobs",
        })

    print(
        "Fresh English StudentJob jobs:",
        len(jobs)
    )

    return jobs


if __name__ == "__main__":
    jobs = fetch_studentjob_jobs()

    print()

    for job in jobs:
        print("=" * 80)
        print("PUBLISHED:", job["posted_at"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
