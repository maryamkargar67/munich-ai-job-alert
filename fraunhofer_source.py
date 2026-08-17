import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import urljoin

from location_filter import location_allowed
from language_filter import requires_advanced_german


BASE_URL = "https://jobs.fraunhofer.de"

SEARCH_URLS = [
    "https://jobs.fraunhofer.de/search/?q=artificial+intelligence&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=machine+learning&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=data+science&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=computer+vision&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=deep+learning&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=LLM&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=generative+AI&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=working+student+AI&locationsearch=M%C3%BCnchen",
    "https://jobs.fraunhofer.de/search/?q=internship+AI&locationsearch=M%C3%BCnchen",
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
    "multimodal",
    "knowledge representation",
    "reasoning",
    "künstliche intelligenz",
    "bildverarbeitung",
]


STUDENT_TERMS = [
    "working student",
    "werkstudent",
    "student assistant",
    "studentische hilfskraft",
    "research assistant",
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
    "principal",
    "staff",
    "lead",
    "head of",
    "director",
]


def clean_text(value):
    return " ".join((value or "").split())


def extract_job_id(url):
    match = re.search(r"/(\d+)/?$", url)
    return match.group(1) if match else url


def parse_city(text):
    match = re.search(
        r"\bCity:\s*(.+?)\s+Date:",
        text,
        re.I,
    )
    return clean_text(match.group(1)) if match else ""


def parse_date(text):
    match = re.search(
        r"\bDate:\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})",
        text,
    )

    if not match:
        return ""

    try:
        return datetime.strptime(
            match.group(1),
            "%b %d, %Y",
        ).date()
    except Exception:
        return ""


def infer_job_type(title):
    title_lower = title.lower()

    if (
        "working student" in title_lower
        or "werkstudent" in title_lower
        or "student assistant" in title_lower
        or "studentische hilfskraft" in title_lower
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

    if "thesis" in title_lower:
        return "Thesis"

    return "Other"


def fetch_fraunhofer_jobs():
    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    today = datetime.now().date()

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
            print("Fraunhofer search error:", error)
            continue

        soup = BeautifulSoup(
            r.text,
            "html.parser",
        )

        links = []

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")

            if "/job/" not in href:
                continue

            url = urljoin(BASE_URL, href)

            if url in seen_urls:
                continue

            seen_urls.add(url)
            links.append(url)

        print(
            "Fraunhofer discovery jobs:",
            len(links),
        )

        for url in links:
            try:
                detail = requests.get(
                    url,
                    headers=headers,
                    timeout=30,
                )
                detail.raise_for_status()
            except Exception as error:
                print("Fraunhofer detail error:", error)
                continue

            detail_soup = BeautifulSoup(
                detail.text,
                "html.parser",
            )

            text = clean_text(
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
                    r"\s+Job Details.*$",
                    "",
                    title,
                    flags=re.I,
                )

            if not title:
                continue

            posted_date = parse_date(text)

            # Only jobs explicitly dated today.
            if posted_date != today:
                continue

            location = parse_city(text)

            if not location:
                continue

            if not location_allowed(location):
                continue

            title_lower = title.lower()

            if any(
                term in title_lower
                for term in BLOCKED_SENIOR_TERMS
            ):
                continue

            full_lower = (
                title + " " + text
            ).lower()

            if not any(
                term in full_lower
                for term in AI_TERMS
            ):
                continue

            job_type = infer_job_type(title)

            # Thesis positions are currently not alerted.
            if job_type == "Thesis":
                continue

            student_match = any(
                term in title_lower
                for term in STUDENT_TERMS
            )

            if (
                job_type == "Other"
                and not student_match
            ):
                continue

            if requires_advanced_german(text):
                continue

            job_id = extract_job_id(url)

            results.append({
                "id": f"fraunhofer-{job_id}",
                "company": "Fraunhofer-Gesellschaft",
                "title": title,
                "location": location,
                "type": job_type,
                "url": url,
                "description": text,
                "posted_at": posted_date.isoformat(),
                "source": "Fraunhofer Direct Careers",
            })

    print(
        "Fresh relevant Fraunhofer jobs:",
        len(results),
    )

    return results


if __name__ == "__main__":
    jobs = fetch_fraunhofer_jobs()

    for job in jobs:
        print()
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("POSTED:", job["posted_at"])
        print("URL:", job["url"])
