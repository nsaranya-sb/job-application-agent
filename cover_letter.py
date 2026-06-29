import time

import anthropic


SYSTEM_PROMPT = """\
You are an expert cover letter writer helping an experienced product manager craft targeted cover letters.

Write in first person, professional but direct. Be specific: name the company, reference the role's \
requirements, cite real numbers from the CV. Never use filler phrases like "I am passionate about", \
"I am a team player", or "I am excited to apply." Never use em-dashes (—) anywhere in the letter; \
use commas, colons, or rewrite the sentence instead.

Output exactly 3 paragraphs with no headers, no salutation, and no sign-off:
- Paragraph 1: Hook. What specifically draws this candidate to this role and company. \
Cite something concrete about the company or the role's scope.
- Paragraph 2: Evidence. 2-3 quantified achievements from the CV that directly address the \
key requirements of this role. Lead with the strongest match.
- Paragraph 3: Close. One confident sentence connecting the candidate's trajectory to what \
this role needs next. One sentence stating they welcome the conversation.\
"""


def generate_cover_letter(
    job: dict,
    cv_text: str,
    assessment_markdown: str,
    client: anthropic.Anthropic,
) -> str:
    """
    Generate a 3-paragraph cover letter grounded in the CV and assessor output.
    Returns plain text. On failure returns an error string.
    """
    salary_str = _format_salary(job)
    user_message = f"""\
## Role

**Title:** {job.get("jobTitle", "N/A")}
**Company:** {job.get("employerName", "N/A")}
**Location:** {job.get("locationName", "N/A")}
**Salary:** {salary_str or "Not listed"}

**Job Description:**
{job.get("jobDescription") or "(No description provided.)"}

---

## Candidate CV

{cv_text}

---

## Fit Assessment (use to decide what to emphasise)

{assessment_markdown}

---

Write the 3-paragraph cover letter now. No em-dashes.\
"""
    return _call_with_retry(client, user_message)


def _call_with_retry(client: anthropic.Anthropic, user_message: str) -> str:
    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            return response.content[0].text.strip()
        except (anthropic.RateLimitError, anthropic.InternalServerError) as e:
            if attempt == 0:
                print(f"    Rate limit / overload — waiting 60s before retry...")
                time.sleep(60)
            else:
                return f"(Cover letter generation failed: {e})"
        except Exception as e:
            return f"(Cover letter generation failed: {e})"
    return "(Cover letter generation failed: unknown error.)"


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
