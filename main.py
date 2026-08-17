from datetime import datetime, timezone
import os
import sqlite3
import requests
from dotenv import load_dotenv
from check24_source import fetch_check24_jobs
from hawk_source import fetch_hawk_jobs
from ashby_source import fetch_ashby_jobs
from location_filter import location_allowed
from language_filter import requires_advanced_german
from linkedin_source import fetch_linkedin_jobs
from allianz_source import fetch_allianz_jobs
from sap_source import fetch_sap_jobs
from infineon_source import fetch_infineon_jobs
from bmw_source import fetch_bmw_jobs
from bosch_source import fetch_bosch_jobs
from munichre_source import fetch_munichre_jobs
from mercedes_source import fetch_mercedes_jobs
from techladies_source import fetch_techladies_jobs
from deepl_source import fetch_deepl_jobs
from helsing_source import fetch_helsing_jobs
from mistral_source import fetch_mistral_jobs
from tacto_source import fetch_tacto_jobs
from appliedai_source import fetch_appliedai_jobs
from celonis_source import fetch_celonis_jobs
from siemens_source import fetch_siemens_jobs
from siemens_energy_source import fetch_siemens_energy_jobs
from jobmensa_source import fetch_jobmensa_jobs
from studentjob_source import fetch_studentjob_jobs
from nvidia_source import fetch_nvidia_jobs

load_dotenv(".env")

DB_NAME = "jobs.db"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "").strip()

def use_supabase():
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)

def supabase_headers():
    return {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
    }

COMPANIES = {
    "FINN": "finn",
    "QuantCo": "quantco-"
}

AI_TITLE_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "data science",
    "data scientist",
    "generative ai",
    "genai",
    "llm",
    "nlp",
    "computer vision",
    "deep learning",
    "ai applied scientist",
    "ai engineering",
    "ai engineer",
    "ml engineer"
]

STUDENT_TITLE_KEYWORDS = [
    "working student",
    "werkstudent",
    "intern",
    "internship",
    "praktikum",
    "student assistant"
]

MUNICH_LOCATIONS = [
    "munich",
    "münchen",
    "garching",
    "ottobrunn",
    "unterhaching",
    "unterschleißheim",
    "ismaning",
    "taufkirchen"
]



def minimum_score_for_job(title, job_type):
    text = f"{title} {job_type}".lower()

    if any(
        term in text
        for term in [
            "working student",
            "werkstudent",
            "intern",
            "internship",
            "junior",
            "graduate",
            "early career",
            "entry level",
            "entry-level"
        ]
    ):
        return 50

    return 65


def calculate_cv_score(title, description, commitment, location):
    text = f"{title} {description}".lower()
    title_lower = title.lower()
    commitment_lower = commitment.lower()
    location_lower = location.lower()

    # -----------------------------
    # 1. AI relevance: max 30
    # -----------------------------
    ai_terms = [
        "artificial intelligence",
        "machine learning",
        "deep learning",
        "computer vision",
        "generative ai",
        "genai",
        "llm",
        "large language model",
        "nlp",
        "data science",
        "ai engineering",
        "ai applied scientist",
        "ai engineer",
        "ml engineer",
        "agentic ai",
        "agent-based ai",
        "ki-agent",
        "ki agent",
        "chatbot"
    ]

    ai_hits = sum(1 for term in ai_terms if term in text)
    ai_score = min(30, ai_hits * 6)

    title_ai_terms = [
        "artificial intelligence",
        "machine learning",
        "data science",
        "computer vision",
        "generative ai",
        "agentic ai",
        "llm",
        "ki-agent",
        "ki agent",
        "chatbot"
    ]

    if any(term in title_lower for term in title_ai_terms):
        ai_score = min(30, ai_score + 6)

    # -----------------------------
    # 2. CV skills: max 35
    # -----------------------------
    cv_skills = {
        "python": 5,
        "pytorch": 5,
        "tensorflow": 4,
        "machine learning": 4,
        "deep learning": 4,
        "computer vision": 5,
        "opencv": 4,
        "llm": 4,
        "nlp": 3,
        "data science": 4,
        "sql": 3,
        "scikit-learn": 3,
        "keras": 2,
        "aws": 2,
        "git": 2,
        "github": 1,
        "matlab": 1,
        "pandas": 2,
        "numpy": 2
    }

    skill_score = 0
    matched_skills = []

    for skill, points in cv_skills.items():
        if skill in text:
            skill_score += points
            matched_skills.append(skill)

    skill_score = min(35, skill_score)

    # -----------------------------
    # 3. Student suitability: max 15
    # -----------------------------
    student_score = 0

    student_terms = [
        "working student",
        "werkstudent",
        "intern",
        "internship",
        "praktikum",
        "praktikant",
        "praktikantin",
        "student assistant",
        "student"
    ]

    if any(term in title_lower for term in student_terms):
        student_score = 15
    elif "part-time" in commitment_lower or "part time" in commitment_lower:
        student_score = 12
    elif any(term in title_lower for term in ["junior", "graduate", "entry level", "entry-level"]):
        student_score = 10
    else:
        student_score = 5

    # -----------------------------
    # 4. Location / Remote: max 10
    # -----------------------------
    location_score = 0

    munich_terms = [
        "munich",
        "münchen",
        "garching",
        "freising",
        "dachau",
        "erding",
        "ottobrunn",
        "unterhaching",
        "taufkirchen",
        "ismaning",
        "unterschleißheim",
        "fürstenfeldbruck",
        "starnberg",
        "rosenheim",
        "augsburg",
        "ingolstadt"
    ]

    if any(place in location_lower for place in munich_terms):
        location_score = 10
    elif "europe" in location_lower:
        location_score = 7
    elif "germany" in location_lower or "deutschland" in location_lower:
        location_score = 8

    if any(term in text for term in [
        "remote",
        "home office",
        "homeoffice",
        "mobile work",
        "work from home"
    ]):
        location_score = max(location_score, 9)

    # -----------------------------
    # 5. Education/background: max 10
    # -----------------------------
    education_score = 0

    if any(term in text for term in [
        "master",
        "master's",
        "msc",
        "m.sc",
        "meng",
        "m.eng"
    ]):
        education_score += 5

    if any(term in text for term in [
        "electrical engineering",
        "engineering",
        "computer science",
        "data science",
        "artificial intelligence"
    ]):
        education_score += 5

    education_score = min(10, education_score)

    total = (
        ai_score
        + skill_score
        + student_score
        + location_score
        + education_score
    )

    total = min(100, total)

    breakdown = {
        "ai": ai_score,
        "skills": skill_score,
        "student": student_score,
        "location": location_score,
        "education": education_score
    }

    return total, matched_skills, breakdown

def init_database():
    connection = sqlite3.connect(DB_NAME)

    connection.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            company TEXT,
            title TEXT,
            location TEXT,
            url TEXT
        )
    """)

    connection.commit()
    connection.close()


def job_exists(job_id):
    if use_supabase():
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/jobs",
                headers=supabase_headers(),
                params={
                    "job_id": f"eq.{job_id}",
                    "select": "job_id",
                    "limit": "1",
                },
                timeout=30,
            )
            r.raise_for_status()
            return len(r.json()) > 0

        except Exception as error:
            print("Supabase job_exists error:", error)
            return True

    connection = sqlite3.connect(DB_NAME)

    result = connection.execute(
        "SELECT job_id FROM jobs WHERE job_id = ?",
        (job_id,)
    ).fetchone()

    connection.close()

    return result is not None


def save_job(job, alerted=False):
    if use_supabase():
        payload = {
            "job_id": job["id"],
            "company": job["company"],
            "title": job["title"],
            "location": job["location"],
            "url": job["url"],
        }

        if alerted:
            payload["alerted_at"] = datetime.now(timezone.utc).isoformat()

        headers = supabase_headers().copy()
        headers["Prefer"] = "resolution=ignore-duplicates"

        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/jobs",
                headers=headers,
                json=payload,
                timeout=30,
            )
            r.raise_for_status()
            return

        except Exception as error:
            print("Supabase save_job error:", error)
            return

    connection = sqlite3.connect(DB_NAME)

    if alerted:
        connection.execute("""
            INSERT OR IGNORE INTO jobs
            (
                job_id,
                company,
                title,
                location,
                url,
                first_seen_at,
                alerted_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                datetime('now'),
                datetime('now')
            )
        """, (
            job["id"],
            job["company"],
            job["title"],
            job["location"],
            job["url"]
        ))
    else:
        connection.execute("""
            INSERT OR IGNORE INTO jobs
            (
                job_id,
                company,
                title,
                location,
                url,
                first_seen_at,
                alerted_at
            )
            VALUES (
                ?, ?, ?, ?, ?,
                datetime('now'),
                NULL
            )
        """, (
            job["id"],
            job["company"],
            job["title"],
            job["location"],
            job["url"]
        ))

    connection.commit()
    connection.close()


def send_telegram(job):
    score = job.get("score", 0)
    skills = job.get("matched_skills", [])
    breakdown = job.get("breakdown", {})

    if score >= 80:
        match_label = "🔥 Strong Match"
    elif score >= 65:
        match_label = "✅ Good Match"
    else:
        match_label = "🟡 Possible Match"

    skills_text = (
        ", ".join(skills)
        if skills
        else "No major CV skills detected"
    )

    message = (
        "🚨 NEW AI JOB MATCH\n\n"
        f"{match_label}\n"
        f"🎯 CV Match: {score}%\n\n"
        f"🏢 Company: {job['company']}\n"
        f"💼 Title: {job['title']}\n"
        f"📍 Location: {job['location']}\n"
        f"⏱ Type: {job['type']}\n\n"
        f"✅ Matching Skills:\n{skills_text}\n\n"
        f"📊 Score Breakdown:\n"
        f"🤖 AI: {breakdown.get('ai', 0)}/30\n"
        f"🧠 Skills: {breakdown.get('skills', 0)}/35\n"
        f"🎓 Student Fit: {breakdown.get('student', 0)}/15\n"
        f"📍 Location: {breakdown.get('location', 0)}/10\n"
        f"🎓 Education: {breakdown.get('education', 0)}/10\n\n"
        f"🔗 Apply:\n{job['url']}"
    )

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=20
    )

    if response.status_code == 200:
        print("📨 Telegram notification sent.")
        return True

    print("❌ Telegram error:", response.text)
    return False


def send_side_job_telegram(job):
    message = (
        "🟢 NEW ENGLISH SIDE JOB\n\n"
        f"🏢 Company: {job['company']}\n"
        f"💼 Title: {job['title']}\n"
        f"📍 Location: {job['location']}\n"
        f"⏱ Type: {job['type']}\n"
        f"🗣 Language: English accepted\n\n"
        f"🔗 Apply:\n{job['url']}"
    )

    response = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message
        },
        timeout=20
    )

    if response.status_code == 200:
        print("📨 Side-job Telegram notification sent.")
        return True

    print("❌ Side-job Telegram error:", response.text)
    return False


init_database()

all_matches = []

for company_name, lever_id in COMPANIES.items():

    print(f"\nChecking {company_name}...")

    url = f"https://api.lever.co/v0/postings/{lever_id}?mode=json"

    try:
        response = requests.get(url, timeout=20)
        response.raise_for_status()

        jobs = response.json()

        print(f"Total jobs: {len(jobs)}")

        for job in jobs:

            created_at = job.get("createdAt")

            if created_at:
                try:
                    created_dt = datetime.fromtimestamp(
                        created_at / 1000,
                        tz=timezone.utc
                    )

                    age = datetime.now(timezone.utc) - created_dt

                    if age.total_seconds() > 3 * 3600:
                        continue

                except Exception:
                    continue

            title = job.get("text", "")
            title_lower = title.lower()

            categories = job.get("categories", {})
            location = categories.get("location", "")
            commitment = categories.get("commitment", "")

            if "working student" in title_lower or "werkstudent" in title_lower:
                commitment = "Working Student"
            elif "internship" in title_lower or " intern" in title_lower:
                commitment = "Internship"
            elif "junior" in title_lower or "graduate" in title_lower:
                commitment = "Junior"

            description = job.get("descriptionPlain", "")

            extra_parts = []

            for section in job.get("lists", []):
                label = section.get("text", "")
                content = section.get("content", "")
                extra_parts.append(f"{label} {content}")

            additional = job.get("additionalPlain", "")

            full_description = (
                description
                + " "
                + " ".join(extra_parts)
                + " "
                + additional
            )

            location_lower = location.lower()

            ai_match = any(
                keyword in title_lower
                for keyword in AI_TITLE_KEYWORDS
            )

            student_match = any(
                keyword in title_lower
                for keyword in STUDENT_TITLE_KEYWORDS
            )

            munich_match = any(
                place in location_lower
                for place in MUNICH_LOCATIONS
            )

            location_match = location_allowed(location)

            if ai_match and student_match and location_match:

                score_text = f"{title} {full_description}"
                score, matched_skills, breakdown = calculate_cv_score(title, full_description, commitment, location)

                all_matches.append({
                    "id": job.get("id"),
                    "company": company_name,
                    "title": title,
                    "location": location,
                    "type": commitment,
                    "url": job.get("hostedUrl"),
                    "score": score,
                    "matched_skills": matched_skills,
                    "breakdown": breakdown,
                    "source": company_name
                })

    except Exception as error:
        print("Error:", error)


# Sort jobs by CV score
all_matches.sort(
    key=lambda job: job.get("score", 0),
    reverse=True
)


# -----------------------------------
# CHECK24
# -----------------------------------

try:
    check24_jobs = fetch_check24_jobs()

    for job in check24_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "CHECK24"
            })

except Exception as error:
    print("CHECK24 error:", error)



# -----------------------------------
# HAWK
# -----------------------------------

try:
    hawk_jobs = fetch_hawk_jobs()

    for job in hawk_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Hawk"
            })

except Exception as error:
    print("Hawk error:", error)



# -----------------------------------
# ASHBY AI COMPANIES
# -----------------------------------

try:
    ashby_jobs = fetch_ashby_jobs()

    for job in ashby_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Ashby"
            })

except Exception as error:
    print("Ashby error:", error)



# -----------------------------------
# NVIDIA DIRECT
# -----------------------------------

try:
    nvidia_jobs = fetch_nvidia_jobs()

    for job in nvidia_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "NVIDIA Direct Careers",
                "posted_at": job.get("date_posted", "")
            })

except Exception as error:
    print("NVIDIA error:", error)



# -----------------------------------
# BMW DIRECT
# -----------------------------------

try:
    bmw_jobs = fetch_bmw_jobs()

    for job in bmw_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "BMW",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("BMW error:", error)




# -----------------------------------
# BOSCH DIRECT
# -----------------------------------

try:
    bosch_jobs = fetch_bosch_jobs()

    for job in bosch_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Bosch",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Bosch error:", error)


# -----------------------------------
# MUNICH RE DIRECT
# -----------------------------------

try:
    munichre_jobs = fetch_munichre_jobs()

    for job in munichre_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Munich Re",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Munich Re error:", error)


# -----------------------------------
# MERCEDES-BENZ DIRECT
# -----------------------------------

try:
    mercedes_jobs = fetch_mercedes_jobs()

    for job in mercedes_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Mercedes-Benz",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Mercedes-Benz error:", error)


# -----------------------------------
# TECH LADIES
# -----------------------------------

try:
    techladies_jobs = fetch_techladies_jobs()

    for job in techladies_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Tech Ladies",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Tech Ladies error:", error)


# -----------------------------------
# DEEPL DIRECT
# -----------------------------------

try:
    deepl_jobs = fetch_deepl_jobs()

    for job in deepl_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "DeepL",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("DeepL error:", error)


# -----------------------------------
# HELSING DIRECT
# -----------------------------------

try:
    helsing_jobs = fetch_helsing_jobs()

    for job in helsing_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Helsing",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Helsing error:", error)


# -----------------------------------
# MISTRAL AI DIRECT
# -----------------------------------

try:
    mistral_jobs = fetch_mistral_jobs()

    for job in mistral_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Mistral AI",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Mistral AI error:", error)


# -----------------------------------
# TACTO DIRECT
# -----------------------------------

try:
    tacto_jobs = fetch_tacto_jobs()

    for job in tacto_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Tacto",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Tacto error:", error)


# -----------------------------------
# APPLIEDAI DIRECT
# -----------------------------------

try:
    appliedai_jobs = fetch_appliedai_jobs()

    for job in appliedai_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "appliedAI",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("appliedAI error:", error)


# -----------------------------------
# CELONIS DIRECT
# -----------------------------------

try:
    celonis_jobs = fetch_celonis_jobs()

    for job in celonis_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Celonis",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Celonis error:", error)


# -----------------------------------
# INFINEON DIRECT
# -----------------------------------

try:
    infineon_jobs = fetch_infineon_jobs()

    for job in infineon_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Infineon",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Infineon error:", error)




# -----------------------------------
# SAP DIRECT
# -----------------------------------

try:
    sap_jobs = fetch_sap_jobs()

    for job in sap_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "SAP",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("SAP error:", error)




# -----------------------------------
# SIEMENS DIRECT
# -----------------------------------

try:
    siemens_jobs = fetch_siemens_jobs()

    for job in siemens_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Siemens",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Siemens error:", error)



# -----------------------------------
# SIEMENS ENERGY DIRECT
# -----------------------------------

try:
    siemens_energy_jobs = fetch_siemens_energy_jobs()

    for job in siemens_energy_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Siemens Energy",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Siemens Energy error:", error)




# -----------------------------------
# ALLIANZ DIRECT
# -----------------------------------

try:
    allianz_jobs = fetch_allianz_jobs()

    for job in allianz_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "Allianz",
                "posted_at": job.get("posted_at", "")
            })

except Exception as error:
    print("Allianz error:", error)



# -----------------------------------
# LINKEDIN DISCOVERY
# -----------------------------------

try:
    linkedin_jobs = fetch_linkedin_jobs()

    for job in linkedin_jobs:

        score, matched_skills, breakdown = calculate_cv_score(
            job["title"],
            job["description"],
            job["type"],
            job["location"]
        )

        if score >= minimum_score_for_job(
            job["title"],
            job["type"]
        ):
            all_matches.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "type": job["type"],
                "url": job["url"],
                "score": score,
                "matched_skills": matched_skills,
                "breakdown": breakdown,
                "source": "LinkedIn"
            })

except Exception as error:
    print("LinkedIn error:", error)


side_jobs = []

try:
    side_jobs.extend(fetch_jobmensa_jobs())
except Exception as error:
    print("Jobmensa error:", error)

try:
    side_jobs.extend(fetch_studentjob_jobs())
except Exception as error:
    print("StudentJob error:", error)


print("\n===================================")
print("🎯 CV-MATCHED JOBS")
print("===================================\n")

for job in all_matches:
    print("-" * 60)
    print("🎯 CV Match:", str(job.get("score", 0)) + "%")
    print("🏢 Company:", job["company"])
    print("💼 Title:", job["title"])
    print("📍 Location:", job["location"])
    print("⏱ Type:", job["type"])
    print("✅ Skills:", ", ".join(job.get("matched_skills", [])))

    breakdown = job.get("breakdown", {})

    print(
        "📊 Breakdown:",
        "AI", str(breakdown.get("ai", 0)) + "/30 |",
        "Skills", str(breakdown.get("skills", 0)) + "/35 |",
        "Student", str(breakdown.get("student", 0)) + "/15 |",
        "Location", str(breakdown.get("location", 0)) + "/10 |",
        "Education", str(breakdown.get("education", 0)) + "/10"
    )

    print("🔗 URL:", job["url"])

print("\n===================================")
print("🔎 CHECKING FOR NEW JOBS")
print("===================================\n")

new_jobs = []

def source_is_initialized(source_name):
    if use_supabase():
        try:
            r = requests.get(
                f"{SUPABASE_URL}/rest/v1/source_state",
                headers=supabase_headers(),
                params={
                    "source_name": f"eq.{source_name}",
                    "select": "source_name",
                    "limit": "1",
                },
                timeout=30,
            )
            r.raise_for_status()

            return len(r.json()) > 0

        except Exception as error:
            print("Supabase source_is_initialized error:", error)
            return False

    connection = sqlite3.connect(DB_NAME)

    result = connection.execute(
        "SELECT source_name FROM source_state WHERE source_name = ?",
        (source_name,)
    ).fetchone()

    connection.close()

    return result is not None


def mark_source_initialized(source_name):
    if use_supabase():
        headers = supabase_headers().copy()
        headers["Prefer"] = "resolution=ignore-duplicates"

        try:
            r = requests.post(
                f"{SUPABASE_URL}/rest/v1/source_state",
                headers=headers,
                json={
                    "source_name": source_name
                },
                timeout=30,
            )
            r.raise_for_status()
            return

        except Exception as error:
            print("Supabase mark_source_initialized error:", error)
            return

    connection = sqlite3.connect(DB_NAME)

    connection.execute(
        """
        INSERT OR IGNORE INTO source_state
        (source_name, initialized_at)
        VALUES (?, datetime('now'))
        """,
        (source_name,)
    )

    connection.commit()
    connection.close()


for job in all_matches:

    if not job_exists(job["id"]):

        source_name = job.get("source", "Unknown")

        if not source_is_initialized(source_name):

            print(
                "🗃️ Initial sync:",
                source_name,
                "|",
                job["company"],
                "-",
                job["title"]
            )

            save_job(job)
            mark_source_initialized(source_name)

            continue

        print("🚨 NEW JOB FOUND!")
        print(job["company"], "-", job["title"])

        telegram_sent = send_telegram(job)

        if telegram_sent:
            save_job(job, alerted=True)
            new_jobs.append(job)
        else:
            print(
                "⚠️ Job not saved; Telegram will retry next run."
            )


if not new_jobs:
    print("✅ No new matching AI jobs.")


new_side_jobs = []

for job in side_jobs:

    if job_exists(job["id"]):
        continue

    source_name = job.get(
        "source",
        "Jobmensa Side Jobs"
    )

    if not source_is_initialized(source_name):
        print(
            "🗃️ Initial side-job sync:",
            source_name
        )
        save_job(job)
        mark_source_initialized(source_name)
        continue

    print("🟢 NEW ENGLISH SIDE JOB!")
    print(job["company"], "-", job["title"])

    telegram_sent = send_side_job_telegram(job)

    if telegram_sent:
        save_job(job, alerted=True)
        new_side_jobs.append(job)
    else:
        print(
            "⚠️ Side job not saved; Telegram will retry next run."
        )


if not new_side_jobs:
    print("✅ No new English side jobs.")


print("-----------------------------------")
print("Matching AI jobs:", len(all_matches))
print("New AI jobs:", len(new_jobs))
print("Fresh English side jobs:", len(side_jobs))
print("New English side jobs:", len(new_side_jobs))
