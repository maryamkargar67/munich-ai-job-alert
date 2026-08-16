import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from location_filter import location_allowed

BASE_URL = "https://jobs.check24.de"
SEARCH_URL = "https://jobs.check24.de/en/jobs/?locations=munich&query=ai"

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}


def requires_advanced_german(text):
    text = text.lower()

    blocked_terms = [
        "sehr gute deutschkenntnisse",
        "verhandlungssichere deutschkenntnisse",
        "verhandlungssicheres deutsch",
        "verhandlungssicher deutsch",
        "fließende deutschkenntnisse",
        "fliessende deutschkenntnisse",
        "fluent german",
        "advanced german",
        "native german",
        "at least b2",
        "mind. b2",
        "mindestens b2",
        "b2-niveau",
        "b2 niveau",
        "german b2",
        "deutsch b2",
        "at least c1",
        "mind. c1",
        "mindestens c1",
        "c1-niveau",
        "c1/c2",
        "c2-niveau",
        "german required",
        "german is required",
        "german mandatory",
        "deutsch zwingend erforderlich",
        "deutsch erforderlich"
    ]

    return any(term in text for term in blocked_terms)


STRONG_AI_TERMS = [
    "machine learning",
    "deep learning",
    "computer vision",
    "generative ai",
    "genai",
    "large language model",
    "llm",
    "natural language processing",
    "nlp",
    "data science",
    "artificial intelligence",
    "ai engineer",
    "ai engineering",
    "ai scientist",
    "applied scientist",
    "ml engineer"
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
    "jupyter",
    "scikit-learn",
    "pandas",
    "numpy"
]


def fetch_check24_jobs():

    print("\nChecking CHECK24...")

    response = requests.get(
        SEARCH_URL,
        headers=HEADERS,
        timeout=20
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    urls = set()

    for link in soup.find_all("a", href=True):

        href = link.get("href", "")

        if "/en/jobs/" not in href:
            continue

        if "ref" not in href.lower():
            continue

        url = urljoin(BASE_URL, href)
        url = url.split("?")[0]

        urls.add(url)

    jobs = []

    for url in urls:

        try:
            r = requests.get(
                url,
                headers=HEADERS,
                timeout=20
            )

            r.raise_for_status()

            job_soup = BeautifulSoup(
                r.text,
                "html.parser"
            )

            h1 = job_soup.find("h1")

            if not h1:
                continue

            title = " ".join(
                h1.get_text(
                    " ",
                    strip=True
                ).split()
            )

            # Extract only job-specific sections
            main_text_parts = []

            for heading in job_soup.find_all(["h2", "h3"]):
                heading_text = heading.get_text(
                    " ",
                    strip=True
                ).lower()

                if any(
                    key in heading_text
                    for key in [
                        "was du mitbringst",
                        "your profile",
                        "requirements",
                        "zu deinen aufgaben",
                        "your tasks",
                        "responsibilities",
                        "über diesen job",
                        "about this job"
                    ]
                ):
                    current = heading.find_next_sibling()

                    while current:
                        if current.name in ["h2", "h3"]:
                            break

                        main_text_parts.append(
                            current.get_text(
                                " ",
                                strip=True
                            )
                        )

                        current = current.find_next_sibling()

            job_text = " ".join(main_text_parts)

            # Fallback if sections were not found
            if not job_text:
                job_text = " ".join(
                    job_soup.get_text(
                        " ",
                        strip=True
                    ).split()
                )

            full_text = " ".join(
                job_soup.get_text(
                    " ",
                    strip=True
                ).split()
            )

            title_lower = title.lower()
            text_lower = job_text.lower()

            # Ignore advanced German requirements
            if requires_advanced_german(job_text):
                continue

            # Ignore senior positions
            if any(
                word in title_lower
                for word in [
                    "senior",
                    "principal",
                    "lead ",
                    "head of",
                    "director"
                ]
            ):
                continue

            ai_hits = [
                term
                for term in STRONG_AI_TERMS
                if term in text_lower
            ]

            title_ai = any(
                term in title_lower
                for term in STRONG_AI_TERMS
            )

            matched_skills = [
                skill
                for skill in CV_SKILLS
                if skill in text_lower
            ]

            # Must genuinely be AI-related
            if not title_ai and len(ai_hits) < 2:
                continue

            # Must overlap with the CV
            if len(matched_skills) < 2:
                continue

            # Infer job type
            if "working student" in title_lower or "werkstudent" in title_lower:
                job_type = "Working Student"
            elif "intern" in title_lower or "praktik" in title_lower:
                job_type = "Internship"
            elif "junior" in title_lower:
                job_type = "Junior"
            else:
                job_type = "Other"

            # Extract real location from the job page
            location = ""

            map_icon = job_soup.find(
                "svg",
                class_=lambda value: (
                    value
                    and "icon-map-marker" in value
                )
            )

            if map_icon and map_icon.parent:
                location_span = map_icon.parent.find("span")

                if location_span:
                    location = " ".join(
                        location_span.get_text(
                            " ",
                            strip=True
                        ).split()
                    )

            if not location:
                continue

            # Only keep jobs genuinely allowed by location filter
            if not location_allowed(
                location,
                job_text
            ):
                continue

            # Stable ID from URL
            job_id = "check24-" + url.rstrip("/").split("/")[-1]

            jobs.append({
                "id": job_id,
                "company": "CHECK24",
                "title": title,
                "location": location,
                "type": job_type,
                "description": job_text,
                "url": url
            })

        except Exception as error:
            print("CHECK24 error:", error)

    print("Relevant CHECK24 jobs:", len(jobs))

    return jobs
