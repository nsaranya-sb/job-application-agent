"""
Job application pipeline.

Usage:
    REED_API_KEY=<key> ANTHROPIC_API_KEY=<key> python pipeline.py
"""

import html as html_module
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

from config import CANDIDATE_PREFERENCES
from cover_letter import generate_cover_letter
from fetcher import fetch_job_detail, fetch_jobs
from scorer import score_job


# ── Title pre-filter ─────────────────────────────────────────────────────────

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


# ── I/O helpers ──────────────────────────────────────────────────────────────

def load_text(path: Path) -> str:
    if not path.exists():
        sys.exit(f"Error: required file '{path}' not found.")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        sys.exit(f"Error: '{path}' is empty — please fill it in before running.")
    return text


def _strip_html(html: str) -> str:
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


def slugify(title: str, employer: str) -> str:
    raw = f"{title}-{employer}"
    slug = re.sub(r"[^\w\s-]", "", raw.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:80]


# ── Markdown builder ──────────────────────────────────────────────────────────

def build_markdown(job: dict, detail: dict, assessment_md: str, cover_letter: str | None) -> str:
    salary = format_salary(detail or job)
    url = job.get("jobUrl") or detail.get("jobUrl") or "N/A"
    posted = job.get("date") or detail.get("date") or "N/A"

    header = f"""\
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
        header += f"""
---

## Cover Letter

{cover_letter}
"""

    return header


def save_output(filename: str, content: str) -> None:
    Path("output", filename).write_text(content, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    reed_api_key = os.environ.get("REED_API_KEY")
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    missing = [k for k, v in {"REED_API_KEY": reed_api_key, "ANTHROPIC_API_KEY": anthropic_api_key}.items() if not v]
    if missing:
        sys.exit(f"Error: missing environment variable(s): {', '.join(missing)}")

    root = Path(__file__).parent
    cv_text = load_text(root / "cv.md")
    assessor_prompt = load_text(root / "prompts" / "assessor_system_prompt.md")

    client = anthropic.Anthropic(api_key=anthropic_api_key)
    Path("output").mkdir(exist_ok=True)

    print("Fetching product manager jobs in London (last 24h)...\n")
    jobs = fetch_jobs(reed_api_key)

    if not jobs:
        print("No jobs found.")
        return

    total = len(jobs)
    relevant = [j for j in jobs if is_relevant_title(j.get("jobTitle", ""))]
    skipped = total - len(relevant)
    print(f"Found {total} job(s). {skipped} filtered by title, {len(relevant)} to process.\n")
    jobs = relevant
    total = len(jobs)

    scored = 0
    letters = 0

    for i, job in enumerate(jobs, 1):
        title = job.get("jobTitle", "Unknown")
        employer = job.get("employerName", "Unknown")
        job_id = job.get("jobId")

        print(f"[{i}/{total}] {title} at {employer}")

        if i > 1:
            time.sleep(0.5)

        try:
            detail = fetch_job_detail(reed_api_key, job_id)
        except Exception as e:
            print(f"    Warning: could not fetch detail — {e}. Skipping.\n")
            continue

        raw_desc = detail.get("jobDescription") or detail.get("description") or ""
        stripped_desc = _strip_html(raw_desc) if raw_desc else "(No description provided.)"
        enriched = {**detail, "jobDescription": stripped_desc}

        print(f"    Scoring...")
        score, assessment_md = score_job(enriched, cv_text, assessor_prompt, CANDIDATE_PREFERENCES, client)
        scored += 1
        print(f"    Score: {score}/10")

        cover_letter = None
        if score > 6:
            print(f"    Score > 6 — generating cover letter...")
            cover_letter = generate_cover_letter(enriched, cv_text, assessment_md, client)
            letters += 1

        md = build_markdown(job, detail, assessment_md, cover_letter)
        filename = f"{job_id}-{slugify(title, employer)}.md"
        save_output(filename, md)

        status = "cover letter written" if cover_letter else "no cover letter"
        print(f"    Saved: output/{filename} ({status})\n")

    print(f"Done. {scored}/{total} jobs scored, {letters} cover letter(s) generated.")
    print(f"Outputs written to output/")


if __name__ == "__main__":
    main()
