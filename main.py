"""
Job application pipeline.

Usage:
    python main.py
    (API keys and candidate preferences are loaded from .env)
"""

import html as html_module
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

from cover_letter import generate_cover_letter
from fetcher import fetch_job_detail, fetch_jobs
from notion import post_to_notion
from scorer import parse_recommendation, score_job


_REQUIRED_WORD = "product"
_EXCLUDE_PHRASES = [
    "product marketing",
    "product analyst",
    "project manager",
    "programme manager",
    "program manager",
]


def is_relevant_title(title: str) -> bool:
    t = title.lower()
    if _REQUIRED_WORD not in t:
        return False
    return not any(phrase in t for phrase in _EXCLUDE_PHRASES)


def load_text(path: Path) -> str:
    if not path.exists():
        sys.exit(f"Error: required file '{path}' not found.")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        sys.exit(f"Error: '{path}' is empty — please fill it in before running.")
    return text


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html)
    text = html_module.unescape(text)
    return re.sub(r"\s{2,}", "\n", text).strip()


def format_salary(job: dict) -> str:
    min_s = job.get("minimumSalary")
    max_s = job.get("maximumSalary")
    if min_s and max_s:
        return f"£{min_s:,.0f} – £{max_s:,.0f}"
    if min_s:
        return f"from £{min_s:,.0f}"
    if max_s:
        return f"up to £{max_s:,.0f}"
    return "Not specified"


def slugify(employer: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", employer.lower())
    return re.sub(r"[\s_]+", "-", slug).strip("-")[:50]


def build_markdown(job: dict, detail: dict, assessment_md: str, cover_letter: str | None) -> str:
    salary = format_salary(detail or job)
    url = job.get("jobUrl") or detail.get("jobUrl") or "N/A"
    posted = job.get("date") or detail.get("date") or "N/A"

    doc = f"""\
# {job.get("jobTitle", "N/A")} — {job.get("employerName", "N/A")}

| Field | Value |
|-------|-------|
| **Job ID** | {job.get("jobId", "N/A")} |
| **Location** | {job.get("locationName", "N/A")} |
| **Salary** | {salary} |
| **Posted** | {posted} |
| **URL** | [View on Reed]({url}) |

---

{assessment_md}
"""
    if cover_letter:
        doc += f"""
---

## Cover Letter

{cover_letter}
"""
    return doc


_STATE_FILE = Path(__file__).parent / ".pipeline_state.json"


def load_state() -> tuple[datetime, set[int]]:
    """Return (last_run datetime, seen_job_ids). Defaults to 24h ago with empty set."""
    if _STATE_FILE.exists():
        try:
            data = json.loads(_STATE_FILE.read_text())
            last_run = datetime.fromisoformat(data["last_run"])
            seen = set(data.get("seen_job_ids", []))
            return last_run, seen
        except Exception:
            pass
    return datetime.now(timezone.utc) - timedelta(hours=24), set()


def save_state(last_run: datetime, seen_job_ids: set[int]) -> None:
    _STATE_FILE.write_text(
        json.dumps({"last_run": last_run.isoformat(), "seen_job_ids": sorted(seen_job_ids)},
                   indent=2)
    )


def print_summary(results: list[dict]) -> None:
    if not results:
        return

    col_title  = max(len(r["title"])  for r in results)
    col_co     = max(len(r["company"]) for r in results)
    col_score  = len("Skills Score")
    col_rec    = max(len(r["recommendation"]) for r in results)

    header = (
        f"{'Job Title':<{col_title}}  "
        f"{'Company':<{col_co}}  "
        f"{'Skills Score':^{col_score}}  "
        f"Recommendation"
    )
    print("\n" + "─" * len(header))
    print(header)
    print("─" * len(header))
    for r in results:
        score_str = f"{r['skills_score']}/10" if r["skills_score"] else "—"
        print(
            f"{r['title']:<{col_title}}  "
            f"{r['company']:<{col_co}}  "
            f"{score_str:^{col_score}}  "
            f"{r['recommendation']}"
        )
    print("─" * len(header))


def main() -> None:
    reed_api_key      = os.environ.get("REED_API_KEY")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    notion_api_key    = os.environ.get("NOTION_API_KEY")
    notion_db_id      = os.environ.get("NOTION_DATABASE_ID")
    required = {
        "REED_API_KEY":        reed_api_key,
        "ANTHROPIC_API_KEY":   anthropic_api_key,
        "NOTION_API_KEY":      notion_api_key,
        "NOTION_DATABASE_ID":  notion_db_id,
        "CANDIDATE_LOCATION":  os.environ.get("CANDIDATE_LOCATION"),
        "CANDIDATE_SALARY":    os.environ.get("CANDIDATE_SALARY"),
        "CANDIDATE_WORK_TYPE": os.environ.get("CANDIDATE_WORK_TYPE"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        sys.exit(f"Error: missing environment variable(s): {', '.join(missing)}")

    preferences = {
        "location":  os.environ["CANDIDATE_LOCATION"],
        "salary":    os.environ["CANDIDATE_SALARY"],
        "work_type": os.environ["CANDIDATE_WORK_TYPE"],
    }

    root = Path(__file__).parent
    cv_text        = load_text(root / "cv.md")
    assessor_prompt = load_text(root / "prompts" / "assessor_system_prompt.md")

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    Path("output").mkdir(exist_ok=True)

    last_run, seen_job_ids = load_state()
    run_start = datetime.now(timezone.utc)
    print(f"Fetching product manager jobs in London posted since {last_run.strftime('%Y-%m-%d %H:%M UTC')}...\n")
    jobs = fetch_jobs(reed_api_key, since=last_run)

    if not jobs:
        print("No jobs found.")
        save_state(run_start, seen_job_ids)
        return

    total    = len(jobs)
    relevant = [j for j in jobs if is_relevant_title(j.get("jobTitle", ""))]
    new_jobs = [j for j in relevant if j.get("jobId") not in seen_job_ids]
    skipped_seen = len(relevant) - len(new_jobs)
    print(
        f"Found {total} job(s). {total - len(relevant)} filtered by title, "
        f"{skipped_seen} already processed, {len(new_jobs)} new to process.\n"
    )
    jobs  = new_jobs
    total = len(jobs)

    if total == 0:
        print("No new jobs to process.")
        save_state(run_start, seen_job_ids)
        return

    results = []
    letters = 0

    for i, job in enumerate(jobs, 1):
        title    = job.get("jobTitle", "Unknown")
        employer = job.get("employerName", "Unknown")
        job_id   = job.get("jobId")

        print(f"[{i}/{total}] {title} at {employer}")

        if i > 1:
            time.sleep(0.5)

        try:
            detail = fetch_job_detail(reed_api_key, job_id)
        except Exception as e:
            print(f"    Warning: could not fetch detail — {e}. Skipping.\n")
            continue

        raw_desc = detail.get("jobDescription") or detail.get("description") or ""
        enriched = {**detail, "jobDescription": strip_html(raw_desc) if raw_desc else "(No description provided.)"}

        print("    Scoring...")
        skills_score, assessment_md = score_job(enriched, cv_text, assessor_prompt, preferences, client)
        recommendation = parse_recommendation(assessment_md)
        print(f"    Skills Score: {skills_score}/10  |  Recommendation: {recommendation}")

        cover_letter = None
        if skills_score >= 7 and recommendation.lower() != "skip":
            print("    Generating cover letter...")
            cover_letter = generate_cover_letter(enriched, cv_text, assessment_md, client)
            letters += 1

        filename = f"{job_id}_{slugify(employer)}.md"
        Path("output", filename).write_text(
            build_markdown(job, detail, assessment_md, cover_letter),
            encoding="utf-8",
        )
        status = "cover letter written" if cover_letter else "no cover letter"
        print(f"    Saved: output/{filename} ({status})")

        print("    Posting to Notion...")
        posted = post_to_notion(
            api_key=notion_api_key,
            database_id=notion_db_id,
            title=title,
            company=employer,
            job_id=str(job_id),
            salary=format_salary(detail or job),
            skills_score=skills_score,
            recommendation=recommendation,
            url=job.get("jobUrl") or detail.get("jobUrl") or "",
            date_posted=job.get("date") or detail.get("date") or "",
            date_processed=__import__("datetime").date.today().isoformat(),
            assessment_md=assessment_md,
        )
        print(f"    Notion: {'✓ posted' if posted else '✗ failed'}\n")

        seen_job_ids.add(job_id)
        results.append({
            "title":        title,
            "company":      employer,
            "skills_score": skills_score,
            "recommendation": recommendation,
        })

    save_state(run_start, seen_job_ids)
    print_summary(results)
    print(f"\n{len(results)}/{total} jobs scored, {letters} cover letter(s) generated.")
    print("Outputs written to output/")


if __name__ == "__main__":
    main()
