"""
Fetches product manager jobs in London posted in the last 24 hours from the Reed API.

Usage:
    REED_API_KEY=<your_key> python fetcher.py

Reed API docs: https://www.reed.co.uk/developers/jobseeker
"""

import os
import re
import sys
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()


REED_API_BASE = "https://www.reed.co.uk/api/1.0"


def parse_minimum_salary(salary_text: str | None) -> int | None:
    """Extract a numeric annual minimum salary floor from a text string or env var."""
    if not salary_text:
        return None
    # Match annual salary figures like £100,000, 90,000, 100000
    match = re.search(r"£?\s*(\d{2,3})[,.]?(\d{3})", salary_text)
    if match:
        return int(match.group(1) + match.group(2))
    # Match patterns like 90k, 100k
    match_k = re.search(r"£?\s*(\d{2,3})\s*k", salary_text, re.IGNORECASE)
    if match_k:
        return int(match_k.group(1)) * 1000
    return None


def fetch_jobs(
    api_key: str,
    since: datetime | None = None,
    minimum_salary: int | None = None,
    results_to_take: int | None = None,
) -> list[dict]:
    """Return product manager jobs in London posted since `since` (default: last 24h)."""
    if since is None:
        since = datetime.utcnow() - timedelta(hours=24)

    if minimum_salary is None:
        raw_salary = os.environ.get("MINIMUM_SALARY") or os.environ.get("CANDIDATE_SALARY")
        minimum_salary = parse_minimum_salary(raw_salary)

    params: dict[str, int | str] = {
        "keywords": "product manager",
        "locationName": "London",
        "distancefromLocation": 10,
    }
    if minimum_salary is not None:
        params["minimumSalary"] = minimum_salary
    if results_to_take is not None:
        params["resultsToTake"] = results_to_take

    resp = requests.get(
        f"{REED_API_BASE}/search",
        params=params,
        auth=(api_key, ""),
        timeout=15,
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])

    # Reed's search API silently ignores date filter params (minimumDate,
    # fromDate, postedDate, datePosted all no-op), so filter locally using
    # the "date" field it returns (format: dd/mm/yyyy).
    since_date = since.date() if hasattr(since, "date") else since
    filtered = []
    for job in results:
        posted_str = job.get("date")
        if not posted_str:
            continue
        posted = datetime.strptime(posted_str, "%d/%m/%Y").date()
        if posted >= since_date:
            filtered.append(job)
    return filtered


def fetch_job_detail(api_key: str, job_id: int) -> dict:
    """Return full details for a single job."""
    resp = requests.get(
        f"{REED_API_BASE}/jobs/{job_id}",
        auth=(api_key, ""),
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def print_jobs(jobs: list[dict]) -> None:
    if not jobs:
        print("No jobs found in the last 24 hours.")
        return

    print(f"Found {len(jobs)} job(s):\n")
    for job in jobs:
        salary = ""
        min_s = job.get("minimumSalary")
        max_s = job.get("maximumSalary")
        if min_s and max_s:
            salary = f"£{min_s:,.0f} – £{max_s:,.0f}"
        elif min_s:
            salary = f"from £{min_s:,.0f}"
        elif max_s:
            salary = f"up to £{max_s:,.0f}"

        print(f"  [{job['jobId']}] {job['jobTitle']}")
        print(f"       Employer : {job.get('employerName', 'N/A')}")
        print(f"       Location : {job.get('locationName', 'N/A')}")
        print(f"       Salary   : {salary or 'Not specified'}")
        print(f"       Posted   : {job.get('date', 'N/A')}")
        print(f"       URL      : {job.get('jobUrl', 'N/A')}")
        print()


def main() -> None:
    api_key = os.environ.get("REED_API_KEY")
    if not api_key:
        sys.exit(
            "Error: REED_API_KEY environment variable not set.\n"
            "Get a free key at https://www.reed.co.uk/developers/jobseeker"
        )

    print("Fetching product manager jobs in London posted in the last 24 hours...\n")
    jobs = fetch_jobs(api_key)
    print_jobs(jobs)


if __name__ == "__main__":
    main()
