"""
Fetches product manager jobs in London posted in the last 24 hours from the Reed API.

Usage:
    REED_API_KEY=<your_key> python fetcher.py

Reed API docs: https://www.reed.co.uk/developers/jobseeker
"""

import os
import sys
from datetime import datetime, timedelta

import requests
from dotenv import load_dotenv

load_dotenv()


REED_API_BASE = "https://www.reed.co.uk/api/1.0"


def fetch_jobs(api_key: str, since: datetime | None = None) -> list[dict]:
    """Return product manager jobs in London posted since `since` (default: last 24h)."""
    if since is None:
        since = datetime.utcnow() - timedelta(hours=24)

    params = {
        "keywords": "product manager",
        "locationName": "London",
        "distancefromLocation": 10,
        "minimumSalary": 90000,
        "resultsToTake": 5,
    }

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
