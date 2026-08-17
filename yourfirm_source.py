import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://www.yourfirm.de"

SEARCH_URLS = [
    "https://www.yourfirm.de/suche/all/?fulltext=artificial+intelligence&locationIds=M-DE-3302&onlyAdsOnlineForDays=1&perimeterRadius=100",
    "https://www.yourfirm.de/suche/all/?fulltext=machine+learning&locationIds=M-DE-3302&onlyAdsOnlineForDays=1&perimeterRadius=100",
    "https://www.yourfirm.de/suche/all/?fulltext=data+science&locationIds=M-DE-3302&onlyAdsOnlineForDays=1&perimeterRadius=100",
    "https://www.yourfirm.de/suche/all/?fulltext=computer+vision&locationIds=M-DE-3302&onlyAdsOnlineForDays=1&perimeterRadius=100",
    "https://www.yourfirm.de/suche/all/?fulltext=deep+learning&locationIds=M-DE-3302&onlyAdsOnlineForDays=1&perimeterRadius=100",
    "https://www.yourfirm.de/suche/all/?fulltext=llm&locationIds=M-DE-3302&onlyAdsOnlineForDays=1&perimeterRadius=100",
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
    "bildverarbeitung",
    "künstliche intelligenz",
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
    "lead",
    "principal",
    "staff",
    "head of",
    "director",
]


def clean_text(value):
    return " ".join((value or "").split())


def extract_date(text):
    match = re.search(r"\b(\d{2}\.\d{2}\.\d{4})\b", text)
    return match.group(1) if match else ""


def extract_ref(text, url):
    match = re.search(r"Ref-Nr:\s*([A-Z0-9-]+)", text, re.I)
    if match:
        return match.group(1)

    match = re.search(r"/([^/]+)/?$", url)
    return match.group(1) if match else url


def fetch_yourfirm_jobs():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    today = datetime.now().strftime("%d.%m.%Y")

    seen_urls = set()
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
            print("Yourfirm search error:", error)
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")

            if "/job/" not in href:
                continue

            url = urljoin(BASE_URL, href)

            if url in seen_urls:
                continue

            seen_urls.add(url)

            parent = a.parent
            if parent is None:
                continue

            card_text = clean_text(
                " ".join(parent.stripped_strings)
            )

            if not card_text:
                continue

            posted_date = extract_date(card_text)

            # Yourfirm search may still include yesterday.
            # Only accept jobs explicitly dated today.
            if posted_date != today:
                continue

            try:
                detail = requests.get(
                    url,
                    headers=headers,
                    timeout=30,
                )
                detail.raise_for_status()
            except Exception as error:
                print("Yourfirm detail error:", error)
                continue

            detail_soup = BeautifulSoup(
                detail.text,
                "html.parser",
            )

            detail_text = clean_text(
                detail_soup.get_text(" ", strip=True)
            )

            title = ""

            if detail_soup.title:
                title = clean_text(
                    detail_soup.title.get_text(
                        " ",
                        strip=True,
                    )
                )
                title = re.sub(
                    r"\s*-\s*Jobangebot.*$",
                    "",
                    title,
                    flags=re.I,
                )

            if not title:
                continue

            title_lower = title.lower()
            full_lower = detail_text.lower()

            if any(
                term in title_lower
                for term in BLOCKED_SENIOR_TERMS
            ):
                continue

            ai_match = any(
                term in title_lower
                or term in full_lower
                for term in AI_TERMS
            )

            if not ai_match:
                continue

            student_match = any(
                term in title_lower
                for term in STUDENT_TERMS
            )

            # Full-time is only accepted if clearly junior/graduate/student.
            if (
                "vollzeit" in card_text.lower()
                and not student_match
            ):
                continue

            if requires_advanced_german(detail_text):
                continue

            location = ""

            # Card usually has location directly after the title.
            card_without_title = card_text

            if title in card_without_title:
                card_without_title = card_without_title.replace(
                    title,
                    "",
                    1,
                ).strip()

            stop_words = [
                "Vollzeit",
                "Teilzeit",
                "Werkstudent",
                "Praktikum",
                "Homeoffice",
            ]

            earliest = len(card_without_title)

            for stop in stop_words:
                pos = card_without_title.find(stop)
                if pos != -1:
                    earliest = min(earliest, pos)

            location = clean_text(
                card_without_title[:earliest]
            )

            if not location_allowed(location):
                continue

            ref = extract_ref(card_text, url)

            results.append({
                "id": f"yourfirm-{ref}",
                "company": "Yourfirm",
                "title": title,
                "location": location,
                "type": (
                    "Working Student"
                    if "werkstudent" in title_lower
                    or "working student" in title_lower
                    else "Internship"
                    if "intern" in title_lower
                    or "praktik" in title_lower
                    else "Junior / Early Career"
                ),
                "url": url,
                "description": detail_text,
                "posted_at": posted_date,
                "source": "Yourfirm",
            })

    print(
        "Fresh relevant Yourfirm jobs:",
        len(results),
    )

    return results


if __name__ == "__main__":
    jobs = fetch_yourfirm_jobs()

    for job in jobs:
        print()
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("POSTED:", job["posted_at"])
        print("URL:", job["url"])
