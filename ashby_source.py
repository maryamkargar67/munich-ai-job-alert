import requests
from bs4 import BeautifulSoup
from location_filter import location_allowed


ASHBY_COMPANIES = {
    "Manex AI": "manex",
    "Dataleap": "Dataleap",
    "Tools for Humanity": "Tools%20for%20Humanity",
    "Mercura": "mercura",
    "Proxima Fusion": "proxima-fusion",
    "Knowlix": "knowlix",
    "RobCo": "robco",
    "Hawk": "hawk"
}

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
        "native-level german",
        "german required",
        "german is required",
        "german mandatory",
        "german is mandatory",
        "at least c1",
        "german c1",
        "c1 german",
        "verhandlungssichere deutschkenntnisse",
        "verhandlungssicher deutsch",
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
    "computer vision",
    "generative ai",
    "genai",
    "large language model",
    "large language models",
    "llm",
    "llms",
    "nlp",
    "natural language processing",
    "data science",
    "ai engineer",
    "ai engineering",
    "ai software",
    "applied ai",
    "applied scientist",
    "ai agent",
    "ai agents",
    "agentic ai",
    "agentic",
    "ai workflow",
    "ai platform"
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
    "nlp",
    "data science",
    "sql",
    "aws",
    "git",
    "github",
    "jupyter",
    "scikit-learn",
    "pandas",
    "numpy",
    "raspberry pi",
    "automation"
]


BLOCKED_ROLES = [
    "senior",
    "principal",
    "staff ",
    "head of",
    "director",
    "account executive",
    "account manager",
    "sales",
    "legal",
    "talent acquisition",
    "recruiter",
    "accountant",
    "marketing",
    "content manager",
    "business development representative",
    "bdr "
]


def get_job_description(job):
    description = job.get("descriptionPlain", "")

    if description:
        return description

    url = job.get("jobUrl", "")

    if not url:
        return ""

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

        return " ".join(
            soup.get_text(
                " ",
                strip=True
            ).split()
        )

    except Exception:
        return ""


def fetch_ashby_jobs():

    print("\nChecking Ashby AI companies...")

    results = []

    for company, board in ASHBY_COMPANIES.items():

        url = (
            "https://api.ashbyhq.com/"
            f"posting-api/job-board/{board}"
        )

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=20
            )

            if response.status_code != 200:
                print(
                    "⚠️",
                    company,
                    "board error:",
                    response.status_code
                )
                continue

            jobs = response.json().get("jobs", [])

            print(
                company + ":",
                len(jobs),
                "open jobs"
            )

            for job in jobs:

                title = job.get("title", "")
                title_lower = title.lower()

                location = job.get("location", "")
                employment = job.get(
                    "employmentType",
                    ""
                )

                job_url = job.get("jobUrl", "")

                if any(
                    blocked in title_lower
                    for blocked in BLOCKED_ROLES
                ):
                    continue

                description = get_job_description(job)

                full_text = (
                    f"{title} {description}"
                ).lower()

                # German hard filter
                if requires_advanced_german(full_text):
                    continue

                # Munich area OR remote Germany
                if not location_allowed(
                    location,
                    description
                ):
                    continue

                ai_hits = [
                    term
                    for term in AI_TERMS
                    if term in full_text
                ]

                title_ai = any(
                    term in title_lower
                    for term in AI_TERMS
                )

                # -----------------------------------
                # ROLE RELEVANCE
                # -----------------------------------

                student_role = any(
                    term in title_lower
                    for term in [
                        "working student",
                        "werkstudent",
                        "intern",
                        "internship",
                        "praktik"
                    ]
                )

                strong_ai_title_terms = [
                    "artificial intelligence",
                    "ai engineer",
                    "ai engineering",
                    "ai agent",
                    "ai agents",
                    "ai solutions",
                    "machine learning",
                    "ml engineer",
                    "data scientist",
                    "data science",
                    "computer vision",
                    "deep learning",
                    "generative ai",
                    "genai",
                    "llm",
                    "nlp",
                    "applied scientist"
                ]

                strong_ai_title = any(
                    term in title_lower
                    for term in strong_ai_title_terms
                )

                # Hard-ignore clearly unsuitable role families
                unsuitable_title_terms = [
                    "customer support",
                    "customer success",
                    "sales",
                    "account ",
                    "business development",
                    "legal",
                    "talent acquisition",
                    "recruiter",
                    "marketing",
                    "content",
                    "physicist",
                    "quality & reliability",
                    "quality and reliability",
                    "engineering lead",
                    "team lead"
                ]

                if any(
                    term in title_lower
                    for term in unsuitable_title_terms
                ):
                    continue

                # Full-time roles must clearly be AI-related in the title.
                if not student_role and not strong_ai_title:
                    continue

                # Student/intern roles may have broader titles,
                # but must contain meaningful AI content.
                if student_role and not strong_ai_title:
                    if len(ai_hits) < 2:
                        continue

                matched_skills = [
                    skill
                    for skill in CV_SKILLS
                    if skill in full_text
                ]

                if len(matched_skills) < 2:
                    continue

                # Determine employment category
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

                elif (
                    "parttime" in employment.lower()
                    or "part time" in employment.lower()
                ):
                    job_type = "Part-Time"

                else:
                    job_type = employment or "Full-Time"

                # Stable ID
                job_id = (
                    "ashby-"
                    + company.lower()
                    .replace(" ", "-")
                    + "-"
                    + job_url.rstrip("/").split("/")[-1]
                )

                results.append({
                    "id": job_id,
                    "company": company,
                    "title": title,
                    "location": location,
                    "type": job_type,
                    "description": description,
                    "url": job_url,
                    "matched_skills_raw": matched_skills
                })

        except Exception as error:
            print(
                "⚠️",
                company,
                "error:",
                error
            )

    print(
        "Relevant Ashby jobs:",
        len(results)
    )

    return results
