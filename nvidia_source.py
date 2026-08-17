import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

from language_filter import requires_advanced_german
from location_filter import location_allowed

BASE_URL = "https://nvidia.wd5.myworkdayjobs.com"
API_URL = (
    BASE_URL
    + "/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
}

AI_TERMS = [
    "artificial intelligence",
    "machine learning",
    "deep learning",
    "computer vision",
    "data science",
    "generative ai",
    "genai",
    "llm",
    "large language model",
    "nlp",
    "natural language processing",
    "cuda",
    "gpu",
    "visual computing",
]

EARLY_CAREER_TERMS = [
    "intern",
    "internship",
    "working student",
    "werkstudent",
    "graduate",
    "new graduate",
    "newly graduating",
    "junior",
    "early career",
]

BLOCKED_SENIOR_TERMS = [
    "senior",
    "staff",
    "principal",
    "director",
    "manager",
    "lead",
]


def fetch_nvidia_jobs(max_age_days=0):
    print("Checking NVIDIA Direct Careers...")

    payload = {
        "appliedFacets": {},
        "limit": 20,
        "offset": 0,
        "searchText": "Munich",
    }

    try:
        r = requests.post(
            API_URL,
            json=payload,
            headers=HEADERS,
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as error:
        print("NVIDIA list error:", error)
        return []

    postings = data.get("jobPostings", [])
    print("NVIDIA discovery jobs:", len(postings))

    jobs = []
    cutoff = datetime.now().date() - timedelta(days=max_age_days)

    for posting in postings:
        try:
            title = posting.get("title", "")
            location_text = posting.get("locationsText", "")
            path = posting.get("externalPath", "")

            if not path:
                continue

            detail_url = (
                BASE_URL
                + "/wday/cxs/nvidia/NVIDIAExternalCareerSite"
                + path
            )

            detail = requests.get(
                detail_url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=30,
            )
            detail.raise_for_status()

            info = detail.json().get("jobPostingInfo", {})

            real_title = info.get("title") or title
            location = info.get("location") or location_text
            additional_locations = info.get("additionalLocations") or []
            start_date = info.get("startDate")
            job_req_id = info.get("jobReqId")
            external_url = info.get("externalUrl")

            description_html = info.get("jobDescription") or ""
            description = BeautifulSoup(
                description_html,
                "html.parser",
            ).get_text(" ", strip=True)

            full_text = (
                real_title
                + " "
                + description
            ).lower()

            title_lower = real_title.lower()

            # Freshness
            if start_date:
                try:
                    posted_date = datetime.strptime(
                        start_date,
                        "%Y-%m-%d",
                    ).date()

                    if posted_date < cutoff:
                        continue
                except Exception:
                    pass

            # Location
            combined_location = " | ".join(
                [location] + additional_locations
            )

            if not location_allowed(
                combined_location,
                description,
            ):
                continue

            # German hard requirement
            if requires_advanced_german(description):
                continue

            # AI relevance
            if not any(term in full_text for term in AI_TERMS):
                continue

            # Early-career suitability
            early_career = any(
                term in full_text
                for term in EARLY_CAREER_TERMS
            )

            senior_title = any(
                term in title_lower
                for term in BLOCKED_SENIOR_TERMS
            )

            # Always reject senior-level titles
            if senior_title:
                continue

            if not early_career:
                continue

            if not job_req_id:
                continue

            jobs.append({
                "id": "nvidia-" + job_req_id,
                "company": "NVIDIA",
                "title": real_title,
                "location": combined_location,
                "type": "Graduate / Early Career",
                "description": description,
                "url": external_url or (
                    BASE_URL
                    + "/NVIDIAExternalCareerSite"
                    + path
                ),
                "date_posted": start_date,
                "source": "NVIDIA Direct Careers",
            })

        except Exception as error:
            print("NVIDIA detail error:", error)

    print("Fresh relevant NVIDIA jobs:", len(jobs))

    return jobs
