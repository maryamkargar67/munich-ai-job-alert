import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlencode

from location_filter import location_allowed
from language_filter import requires_advanced_german


SEARCH_URL = (
    "https://www.linkedin.com/jobs-guest/"
    "jobs/api/seeMoreJobPostings/search"
)

JOB_DETAIL_URL = (
    "https://www.linkedin.com/jobs-guest/"
    "jobs/api/jobPosting/{}"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


QUERIES = [
    "AI Working Student",
    "Machine Learning Working Student",
    "Data Science Working Student",
    "AI Intern",
    "Machine Learning Intern",
    "AI Engineer",
    "Junior AI Engineer",
    "Computer Vision Working Student",
    "LLM Working Student"
]


AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "computer vision",
    "generative ai",
    "genai",
    "llm",
    "large language model",
    "large language models",
    "nlp",
    "agentic ai",
    "agentic",
    "ai engineer",
    "ai engineering",
    "data science",
    "data scientist"
]


def extract_job_id(url):
    match = re.search(
        r"-(\d+)(?:\?|$)",
        url
    )

    if match:
        return match.group(1)

    return None


def fetch_job_description(job_id):
    if not job_id:
        return ""

    url = JOB_DETAIL_URL.format(job_id)

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        if response.status_code != 200:
            return ""

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        description = soup.select_one(
            ".show-more-less-html__markup"
        )

        if description:
            return " ".join(
                description.get_text(
                    " ",
                    strip=True
                ).split()
            )

        return " ".join(
            soup.get_text(
                " ",
                strip=True
            ).split()
        )

    except Exception:
        return ""


def search_linkedin(
    keyword,
    location="Munich, Bavaria, Germany"
):
    params = {
        "keywords": keyword,
        "location": location,
        "sortBy": "DD",

        # Only jobs published in roughly the last hour.
        # The bot will run every 5 minutes, so SQLite
        # prevents the same job from being sent repeatedly.
        "f_TPR": "r3600",

        "start": 0
    }

    response = requests.get(
        SEARCH_URL,
        params=params,
        headers=HEADERS,
        timeout=20
    )

    if response.status_code != 200:
        return []

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    jobs = []

    for card in soup.select("li"):

        link = card.select_one(
            "a.base-card__full-link"
        )

        title_el = card.select_one(
            ".base-search-card__title"
        )

        company_el = card.select_one(
            ".base-search-card__subtitle"
        )

        location_el = card.select_one(
            ".job-search-card__location"
        )

        time_el = card.select_one("time")

        posted_at = ""
        posted_text = ""

        if time_el:
            posted_at = time_el.get("datetime", "")
            posted_text = time_el.get_text(
                " ",
                strip=True
            )

        if not link or not title_el:
            continue

        url = link.get(
            "href",
            ""
        ).split("?")[0]

        title = " ".join(
            title_el.get_text(
                " ",
                strip=True
            ).split()
        )

        company = (
            " ".join(
                company_el.get_text(
                    " ",
                    strip=True
                ).split()
            )
            if company_el
            else ""
        )

        job_location = (
            " ".join(
                location_el.get_text(
                    " ",
                    strip=True
                ).split()
            )
            if location_el
            else ""
        )

        jobs.append({
            "title": title,
            "company": company,
            "location": job_location,
            "url": url,
            "posted_at": posted_at,
            "posted_text": posted_text
        })

    return jobs


def fetch_linkedin_jobs():

    print("\nChecking LinkedIn discovery...")

    discovered = {}

    for query in QUERIES:

        try:
            jobs = search_linkedin(query)

            print(
                query + ":",
                len(jobs),
                "results"
            )

            for job in jobs:
                discovered[job["url"]] = job

        except Exception as error:
            print(
                "LinkedIn search error:",
                query,
                error
            )

    print(
        "Unique LinkedIn jobs:",
        len(discovered)
    )

    results = []

    for job in discovered.values():

        title = job["title"]
        title_lower = title.lower()

        job_id = extract_job_id(
            job["url"]
        )

        description = fetch_job_description(
            job_id
        )

        full_text = (
            f"{title} {description}"
        ).lower()

        # Location:
        # <=100 km Munich OR Germany remote
        if not location_allowed(
            job["location"],
            description
        ):
            continue

        # Hard German filter
        if requires_advanced_german(
            full_text
        ):
            continue

        # -----------------------------------
        # TRUE AI ROLE RELEVANCE
        # -----------------------------------

        ai_hits = [
            term
            for term in AI_TERMS
            if term in full_text
        ]

        strong_ai_title_terms = [
            "artificial intelligence",
            " ai ",
            "ai engineer",
            "ai engineering",
            "ai developer",
            "ai systems",
            "ai solutions",
            "ai research",
            "ai/ml",
            "agentic ai",
            "machine learning",
            "ml engineer",
            "data scientist",
            "data science",
            "computer vision",
            "deep learning",
            "generative ai",
            "gen ai",
            "genai",
            "llm",
            "nlp",
            "sim2real",
            " ki ",
            "ki tool",
            "ki im ",
            "ki-"
        ]

        strong_ai_title = any(
            term in f" {title_lower} "
            for term in strong_ai_title_terms
        )

        student_role = any(
            term in title_lower
            for term in [
                "working student",
                "werkstudent",
                "werkstudium",
                "work and study",
                "intern",
                "internship",
                "praktikant",
                "praktikum"
            ]
        )

        # Remove clearly unsuitable roles
        unsuitable_title_terms = [
            "senior",
            "principal",
            "staff ",
            "lead ",
            "head of",
            "director",
            "customer support",
            "customer success",
            "sales",
            "account executive",
            "marketing",
            "legal",
            "recruiter",
            "talent acquisition",
            "business intelligence",
            "analytics & bi",
            "data engineering"
        ]

        if any(
            term in title_lower
            for term in unsuitable_title_terms
        ):
            continue

        # Full-time / junior roles:
        # AI/ML must be explicit in the title
        if not student_role and not strong_ai_title:
            continue

        # Student / intern roles:
        # Prefer explicit AI in title.
        # If title is broader, require multiple AI signals
        # in the actual job description.
        if student_role and not strong_ai_title:
            if len(ai_hits) < 3:
                continue

        # Determine role type
        if (
            "working student" in title_lower
            or "werkstudent" in title_lower
            or "work and study" in title_lower
            or "werkstudium" in title_lower
        ):
            job_type = "Working Student"

        elif (
            "intern" in title_lower
            or "internship" in title_lower
            or "praktikant" in title_lower
            or "praktikum" in title_lower
        ):
            job_type = "Internship"

        elif "junior" in title_lower or "(jr.)" in title_lower:
            job_type = "Junior"

        else:
            job_type = "Full-Time"

        results.append({
            "id": "linkedin-" + str(job_id),
            "company": job["company"],
            "title": title,
            "location": job["location"],
            "type": job_type,
            "description": description,
            "url": job["url"]
        })

    print(
        "Relevant LinkedIn jobs:",
        len(results)
    )

    return results
