import re
import time

import anthropic


def score_job(
    job: dict,
    cv_text: str,
    assessor_prompt: str,
    preferences: dict,
    client: anthropic.Anthropic,
) -> tuple[float, str]:
    """
    Assess how well a job matches the candidate's CV using the assessor skill.
    Returns (score, assessment_markdown). On failure returns (0.0, error markdown).
    """
    salary_str = _format_salary(job)
    user_message = f"""\
## Candidate Preferences
- Location: {preferences["location"]}
- Salary expectation: {preferences["salary"]}
- Work type: {preferences["work_type"]}

---

## CV

{cv_text}

---

## Job Description

**Title:** {job.get("jobTitle", "N/A")}
**Company:** {job.get("employerName", "N/A")}
**Location:** {job.get("locationName", "N/A")}
**Salary:** {salary_str or "Not listed"}
**Job ID:** {job.get("jobId", "N/A")}
**URL:** {job.get("jobUrl", "N/A")}

{job.get("jobDescription") or "(No description provided.)"}
"""
    return _call_with_retry(client, assessor_prompt, user_message)


def _call_with_retry(
    client: anthropic.Anthropic, system: str, user_message: str
) -> tuple[float, str]:
    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user_message}],
            )
            text = response.content[0].text.strip()
            score = _parse_score(text)
            return (score, text)
        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            if attempt == 0:
                print(f"    Rate limit / overload — waiting 60s before retry...")
                time.sleep(60)
            else:
                return (0.0, f"## Assessment Failed\n\nError: {e}")
        except Exception as e:
            return (0.0, f"## Assessment Failed\n\nError: {e}")
    return (0.0, "## Assessment Failed\n\nUnknown error.")


def _parse_score(text: str) -> float:
    match = re.search(r"\*\*Skills Score:\s*(\d+(?:\.\d+)?)/10\*\*", text)
    if match:
        return float(match.group(1))
    match = re.search(r"Skills Score:\s*(\d+(?:\.\d+)?)/10", text)
    if match:
        return float(match.group(1))
    return 0.0


def parse_recommendation(text: str) -> str:
    match = re.search(r"\*\*Overall Recommendation:\s*([^\*\n]+)", text)
    if match:
        return match.group(1).strip().split("—")[0].strip()
    return "Unknown"


def _format_salary(job: dict) -> str:
    min_s = job.get("minimumSalary")
    max_s = job.get("maximumSalary")
    if min_s and max_s:
        return f"£{min_s:,.0f} – £{max_s:,.0f}"
    if min_s:
        return f"from £{min_s:,.0f}"
    if max_s:
        return f"up to £{max_s:,.0f}"
    return ""
