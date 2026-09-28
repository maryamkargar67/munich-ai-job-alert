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
    "Computer Vision Working Student",
    "Generative AI Working Student",
    "LLM Working Student",
    "NLP Working Student",
    "Python Working Student",
    "PyTorch Working Student",
    "Data Analytics Working Student",
    "AI Automation Working Student",
    "Prompt Engineering Working Student",
    "AI Product Working Student",
    "Research Working Student AI",
    "Werkstudent KI",
    "Werkstudent Machine Learning",
    "Werkstudent Python",

    "AI Intern",
    "Machine Learning Intern",
    "Data Science Intern",
    "Computer Vision Intern",
    "Generative AI Intern",
    "LLM Intern",
    "NLP Intern",
    "Python Intern",
    "Data Analytics Intern",
    "AI Automation Intern",
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
    location="Munich, Bavaria, Germany",
    max_pages=4
):
    jobs = []

    for start in range(0, max_pages * 10, 10):

        params = {
            "keywords": keyword,
            "location": location,
            "sortBy": "DD",

            # Use a 6-hour overlap window so delayed GitHub runs
            # or delayed LinkedIn indexing do not cause missed jobs.
            # Database deduplication prevents duplicate alerts.
            "f_TPR": "r21600",

            "start": start
        }

        response = requests.get(
            SEARCH_URL,
            params=params,
            headers=HEADERS,
            timeout=20
        )

        if response.status_code != 200:
            break

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        cards = soup.select("li")

        if not cards:
            break

        page_jobs = 0

        for card in cards:

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
                posted_at = time_el.get(
                    "datetime",
                    ""
                )
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

            page_jobs += 1

        if page_jobs == 0:
            break

    # Deduplicate jobs that may appear on multiple pages
    unique = {}

    for job in jobs:
        unique[job["url"]] = job

    return list(unique.values())


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

        # Hard education filter:
        # reject PhD / doctoral-only positions
        phd_patterns = [
            r"\bph\.?d\.?\s+intern\b",
            r"\bph\.?d\.?\s+internship\b",
            r"\bph\.?d\.?\s+student\b",
            r"\bph\.?d\.?\s+candidate\b",
            r"\bdoctoral\s+student\b",
            r"\bdoctoral\s+researcher\b",
            r"\bdoctoral\s+candidate\b",
            r"\bcurrently\s+pursuing\s+(?:a\s+)?ph\.?d\.?\b",
            r"\bpursuing\s+(?:a\s+)?ph\.?d\.?\b",
            r"\benrolled\s+in\s+(?:a\s+)?ph\.?d\.?\b",
        ]

        if any(
            re.search(pattern, full_text)
            for pattern in phd_patterns
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
            re.search(pattern, title_lower)
            for pattern in [
                r"\bworking student\b",
                r"\bwerkstudent(?:in)?\b",
                r"\bwerkstudium\b",
                r"\bwork and study\b",
                r"\bintern\b",
                r"\binternship\b",
                r"\bpraktikant(?:in)?\b",
                r"\bpraktikum\b",
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
            "analytics & bi"
        ]

        if any(
            term in title_lower
            for term in unsuitable_title_terms
        ):
            continue

        # -----------------------------------
        # CV / DESCRIPTION BASED RELEVANCE
        # -----------------------------------
        # The job title is NOT the main criterion anymore.
        # A generic title is accepted when the actual
        # description matches Mary's AI/Data/CV profile.

        profile_terms = [
            "python",
            "pytorch",
            "tensorflow",
            "keras",
            "scikit-learn",
            "sklearn",
            "opencv",
            "computer vision",
            "image processing",
            "machine learning",
            "deep learning",
            "artificial intelligence",
            "generative ai",
            "genai",
            "large language model",
            "llm",
            "transformer",
            "transformers",
            "nlp",
            "natural language processing",
            "prompt engineering",
            "prompting",
            "chatbot",
            "data science",
            "data analysis",
            "data analytics",
            "pandas",
            "numpy",
            "sql",
            "aws",
        ]

        profile_hits = [
            term
            for term in profile_terms
            if term in full_text
        ]

        # We no longer prioritize the job title for relevance.
        # The title is mainly used to confirm that this is a
        # student / internship role. Suitability comes from
        # the actual description and Mary's CV skills.

        if not student_role:
            continue

        core_profile_terms = [
            "python",
            "pytorch",
            "tensorflow",
            "machine learning",
            "deep learning",
            "computer vision",
            "opencv",
            "data science",
            "data engineering",
            "data analysis",
            "data analytics",
            "sql",
            "nlp",
            "natural language processing",
            "llm",
            "large language model",
            "generative ai",
            "transformer",
            "aws",
        ]

        core_hits = [
            term for term in core_profile_terms
            if term in full_text
        ]

        # Generic titles are okay as long as the job description
        # genuinely overlaps with the CV.
        if len(set(profile_hits)) < 2:
            continue

        if not core_hits:
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
