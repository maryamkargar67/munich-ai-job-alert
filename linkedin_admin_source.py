import re

from linkedin_source import (
    search_linkedin,
    fetch_job_description,
    extract_job_id,
)

from location_filter import location_allowed
from language_filter import requires_advanced_german


QUERIES = [
    "Working Student Operations",
    "Working Student Administration",
    "Working Student Office",
    "Working Student Business Operations",
    "Working Student HR Administration",
    "Working Student People Operations",
    "Working Student Project Assistant",
    "Working Student Team Assistant",
    "Working Student Document Management",
    "Working Student Data Entry",
    "Part Time Office Assistant",
    "Student Assistant Operations",
    "Working Student Program Management",
    "Working Student Project Management",
    "Working Student PMO",
    "Working Student Project Coordination",
    "Working Student Research",
    "Working Student Business Research",
    "Working Student Data Management",
    "Working Student Reporting",
    "Working Student Jira",
    "Working Student Confluence",
]


ADMIN_TERMS = [
    "administration",
    "administrative",
    "office assistant",
    "office support",
    "office management",
    "operations assistant",
    "business operations",
    "people operations",
    "hr administration",
    "human resources",
    "team assistant",
    "project assistant",
    "student assistant",
    "document management",
    "document processing",
    "documentation",
    "data entry",
    "data maintenance",
    "database maintenance",
    "crm",
    "back office",
    "filing",
    "archive",
    "archiving",
    "onboarding",
    "invoice processing",
    "invoicing",
    "email correspondence",
    "calendar management",
    "program management",
    "project management",
    "project coordination",
    "project support",
    "pmo",
    "ticketing",
    "ticket system",
    "jira",
    "confluence",
    "research",
    "desk research",
    "market research",
    "business research",
    "data management",
    "data handling",
    "data cleaning",
    "data maintenance",
    "reporting",
    "excel",
    "spreadsheet",
    "microsoft excel",
    "büro",
    "verwaltung",
    "dokumentenmanagement",
    "datenpflege",
    "sachbearbeitung",
]


STUDENT_PARTTIME_TERMS = [
    "working student",
    "werkstudent",
    "student assistant",
    "studentische aushilfe",
    "studentische hilfskraft",
    "student",
    "part-time",
    "part time",
    "teilzeit",
    "minijob",
    "intern",
    "internship",
    "praktikum",
]


BLOCKED_TITLE_TERMS = [
    "senior",
    "manager",
    "head of",
    "director",
    "lead ",
    "principal",
    "engineer",
    "developer",
    "scientist",
    "researcher",
    "consultant",
    "analyst",
    "architect",
    "data scientist",
    "software",
    "machine learning",
    "artificial intelligence",
    "sales ",
    "account executive",
    "product manager",
]


DRIVING_LICENCE_PATTERNS = [
    r"führerschein\s+(?:der\s+)?klasse\s+b",
    r"fuehrerschein\s+(?:der\s+)?klasse\s+b",
    r"fahrerlaubnis\s+(?:der\s+)?klasse\s+b",
    r"führerschein\s+b\b",
    r"fuehrerschein\s+b\b",
    r"driving\s+licen[cs]e\s+(?:class\s+)?b",
    r"class\s+b\s+driving\s+licen[cs]e",
]


def looks_english_friendly(text):
    low = text.lower()

    # Explicit English acceptance
    english_indicators = [
        "english",
        "englisch",
        "business english",
        "working language is english",
        "company language is english",
        "english-speaking",
        "international team",
    ]

    if any(term in low for term in english_indicators):
        return True

    # Basic heuristic for an English-language posting
    english_words = [
        "the",
        "and",
        "your",
        "you",
        "with",
        "our",
        "team",
        "work",
        "support",
        "responsibilities",
        "requirements",
        "skills",
        "we are",
        "what you",
    ]

    hits = sum(
        1 for word in english_words
        if re.search(r"\b" + re.escape(word) + r"\b", low)
    )

    return hits >= 5


def fetch_linkedin_admin_jobs():

    print("\nChecking LinkedIn Admin / Office jobs...")

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
                "LinkedIn Admin search error:",
                query,
                error
            )

    results = []

    for job in discovered.values():

        title = job.get("title", "")
        title_lower = title.lower()

        if any(
            term in title_lower
            for term in BLOCKED_TITLE_TERMS
        ):
            continue

        job_id = extract_job_id(
            job.get("url", "")
        )

        description = fetch_job_description(
            job_id
        )

        if not description:
            continue

        full_text = (
            f"{title} {description}"
        )

        full_lower = full_text.lower()

        # Munich <=100 km or Germany remote
        if not location_allowed(
            job.get("location", ""),
            description
        ):
            continue

        # Hard German requirement
        if requires_advanced_german(
            full_text
        ):
            continue

        # Driving licence required
        if any(
            re.search(
                pattern,
                full_lower
            )
            for pattern in DRIVING_LICENCE_PATTERNS
        ):
            continue

        # The JOB TITLE itself must clearly be admin / office / operations related.
        admin_title_terms = [
            "administration",
            "administrative",
            "office",
            "operations",
            "assistant",
            "coordinator",
            "people operations",
            "hr ",
            "human resources",
            "project support",
            "team support",
            "document",
            "data entry",
            "back office",
            "procurement",
            "governance",
            "program management",
            "project management",
            "project coordination",
            "project support",
            "pmo",
            "research",
            "data management",
            "reporting",
            "jira",
            "confluence",
            "student assistant",
            "werkstudent",
        ]

        if not any(
            term in title_lower
            for term in admin_title_terms
        ):
            continue

        # Must be student / part-time / minijob / internship friendly
        if not any(
            term in full_lower
            for term in STUDENT_PARTTIME_TERMS
        ):
            continue

        # English must be explicitly accepted or posting appears English
        if not looks_english_friendly(
            full_text
        ):
            continue

        job_type = "Part-Time / Student"

        if (
            "working student" in full_lower
            or "werkstudent" in full_lower
        ):
            job_type = "Working Student"

        elif (
            "internship" in full_lower
            or "intern " in full_lower
            or "praktikum" in full_lower
        ):
            job_type = "Internship"

        elif "minijob" in full_lower:
            job_type = "Minijob"

        elif (
            "part-time" in full_lower
            or "part time" in full_lower
            or "teilzeit" in full_lower
        ):
            job_type = "Part-Time"

        results.append({
            "id": f"linkedin-admin-{job_id}",
            "company": job.get("company", ""),
            "title": title,
            "location": job.get("location", ""),
            "type": job_type,
            "url": job.get("url", ""),
            "description": description,
            "posted_at": job.get("posted_at", ""),
            "source": "LinkedIn Admin Side Jobs",
        })

    print(
        "Fresh English LinkedIn Admin jobs:",
        len(results)
    )

    return results


if __name__ == "__main__":
    jobs = fetch_linkedin_admin_jobs()

    for job in jobs:
        print()
        print("COMPANY:", job["company"])
        print("TITLE:", job["title"])
        print("LOCATION:", job["location"])
        print("TYPE:", job["type"])
        print("URL:", job["url"])
