import requests
from bs4 import BeautifulSoup

API_URL = "https://api.ashbyhq.com/posting-api/job-board/hawk"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def requires_advanced_german(text):
    text = text.lower()

    blocked_terms = [
        "german speaking",
        "german-speaking",
        "fluent german",
        "advanced german",
        "native german",
        "german required",
        "german is required",
        "german mandatory",
        "at least c1",
        "c1 german",
        "german c1",
        "verhandlungssichere deutschkenntnisse",
        "sehr gute deutschkenntnisse",
        "fließende deutschkenntnisse",
        "fliessende deutschkenntnisse",
        "mind. c1",
        "mindestens c1"
    ]

    return any(term in text for term in blocked_terms)


AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "generative ai",
    "genai",
    "large language model",
    "llm",
    "agentic",
    "ai agent",
    "ai agents",
    "data science",
    "ml engineer",
    "ai engineer"
]

CV_SKILLS = [
    "python",
    "pytorch",
    "tensorflow",
    "machine learning",
    "deep learning",
    "computer vision",
    "opencv",
    "llm",
    "generative ai",
    "data science",
    "sql",
    "aws",
    "git",
    "jupyter",
    "pandas",
    "numpy"
]


def fetch_hawk_jobs():

    print("\nChecking Hawk...")

    response = requests.get(
        API_URL,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    jobs = response.json().get("jobs", [])

    results = []

    for job in jobs:

        title = job.get("title", "")
        location = job.get("location", "")
        employment = job.get("employmentType", "")
        url = job.get("jobUrl", "")

        title_lower = title.lower()

        # Skip irrelevant senior jobs
        if any(
            term in title_lower
            for term in [
                "senior",
                "principal",
                "head of",
                "director",
                "account executive",
                "account director",
                "legal",
                "talent acquisition",
                "accountant",
                "bdr"
            ]
        ):
            continue

        # Get actual job page text
        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=20
            )

            r.raise_for_status()

            soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            description = " ".join(
                soup.get_text(
                    " ",
                    strip=True
                ).split()
            )

        except Exception:
            description = ""

        full_text = f"{title} {description}".lower()

        # Ignore advanced German
        if requires_advanced_german(full_text):
            continue

        # Munich or Germany remote only
        location_lower = location.lower()

        location_ok = (
            "munich" in location_lower
            or (
                "remote" in location_lower
                and (
                    "germany" in location_lower
                    or "deutschland" in location_lower
                )
            )
        )

        if not location_ok:
            continue

        # Must genuinely relate to AI
        ai_hits = [
            term
            for term in AI_TERMS
            if term in full_text
        ]

        title_ai = any(
            term in title_lower
            for term in AI_TERMS
        )

        if not title_ai and len(ai_hits) < 2:
            continue

        matched_skills = [
            skill
            for skill in CV_SKILLS
            if skill in full_text
        ]

        # Need at least some overlap with CV
        if len(matched_skills) < 2:
            continue

        # Student / early-career / potentially suitable full-time
        if (
            "working student" in title_lower
            or "werkstudent" in title_lower
        ):
            job_type = "Working Student"

        elif (
            "intern" in title_lower
            or "internship" in title_lower
        ):
            job_type = "Internship"

        elif "junior" in title_lower:
            job_type = "Junior"

        else:
            job_type = employment or "Full-Time"

        job_id = "hawk-" + url.rstrip("/").split("/")[-1]

        results.append({
            "id": job_id,
            "company": "Hawk",
            "title": title,
            "location": location,
            "type": job_type,
            "description": description,
            "url": url,
            "matched_skills_raw": matched_skills
        })

    print("Relevant Hawk jobs:", len(results))

    return results
