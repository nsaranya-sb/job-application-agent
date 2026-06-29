"""
Notion integration — posts scored job results to the Job Application Tracker database.
"""

import re
import requests


NOTION_API_VERSION = "2022-06-28"
NOTION_API_BASE = "https://api.notion.com/v1"


def parse_ir35_status(assessment_md: str) -> str:
    text = assessment_md.lower()
    if "outside ir35" in text:
        return "Outside IR35"
    if "inside ir35" in text:
        return "Inside IR35"
    return "Not Specified"


def post_to_notion(
    api_key: str,
    database_id: str,
    title: str,
    company: str,
    job_id: str,
    salary: str,
    skills_score: float,
    recommendation: str,
    url: str,
    date_posted: str,
    date_processed: str,
    assessment_md: str,
) -> bool:
    ir35_status = parse_ir35_status(assessment_md)

    # Normalise recommendation to one of the three valid select values
    rec_lower = recommendation.lower()
    if "skip" in rec_lower:
        rec_value = "Skip"
    elif "caveat" in rec_lower:
        rec_value = "Apply with caveats"
    else:
        rec_value = "Apply"

    properties = {
        "Role": {"title": [{"text": {"content": title}}]},
        "Company": {"rich_text": [{"text": {"content": company}}]},
        "Job ID": {"rich_text": [{"text": {"content": str(job_id)}}]},
        "Source": {"select": {"name": "Reed"}},
        "Salary": {"rich_text": [{"text": {"content": salary or "Not specified"}}]},
        "IR35 Status": {"select": {"name": ir35_status}},
        "Skills Score": {"number": skills_score},
        "Recommendation": {"select": {"name": rec_value}},
        "URL": {"url": url or None},
        "Application Status": {"select": {"name": "Not Started"}},
    }

    if date_posted:
        properties["Date Posted"] = {"date": {"start": _parse_date(date_posted)}}

    if date_processed:
        properties["Date Processed"] = {"date": {"start": date_processed}}

    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }

    resp = requests.post(
        f"{NOTION_API_BASE}/pages",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Notion-Version": NOTION_API_VERSION,
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )

    if not resp.ok:
        print(f"    Notion API error {resp.status_code}: {resp.text[:200]}")
        return False
    return True


def _parse_date(date_str: str) -> str:
    """Convert Reed date formats (DD/MM/YYYY or ISO) to YYYY-MM-DD."""
    match = re.match(r"(\d{2})/(\d{2})/(\d{4})", date_str)
    if match:
        d, m, y = match.groups()
        return f"{y}-{m}-{d}"
    # Already ISO or partial ISO — take first 10 chars
    return date_str[:10]
