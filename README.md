# Job Application Agent 🚀

An autonomous AI-powered pipeline that automatically searches for relevant job opportunities, evaluates role suitability against your CV using Claude LLMs, crafts tailored 3-paragraph cover letters, and synchronizes evaluation records directly into a Notion tracker database.

---

## 🌟 Key Features

- **Automated Job Search**: Fetches recent Product Manager roles in London via the [Reed API](https://www.reed.co.uk/developers/jobseeker).
- **Smart Pre-Filtering**: Filters out irrelevant role titles (e.g., product marketing, analyst, project manager) before API/LLM processing.
- **Incremental Runs & Deduplication**: Tracks `.pipeline_state.json` to only fetch jobs posted since the last execution run and skips previously processed job IDs.
- **AI Suitability Scoring**: Evaluates candidate fit using **Claude Haiku** against candidate CV (`cv.md`) and candidate preferences (location, salary, work type), outputting a **Skills Score (0–10)**, structured fit matrix, and recommendation.
- **Tailored Cover Letter Generation**: Automatically writes focused 3-paragraph cover letters using **Claude Sonnet** for top-matching roles (Skills Score $\ge$ 7 with non-Skip recommendations).
- **Notion Database Integration**: Automatically creates formatted records in your Notion Job Application Tracker database, including role info, salary, IR35 status, scores, and URLs.
- **Local Markdown Archiving**: Saves complete evaluation reports and cover letters as structured Markdown documents in `output/`.

---

## 🏗️ Architecture & Component Overview

```
job-application-agent/
├── main.py                     # Primary pipeline orchestrator & CLI entry point
├── fetcher.py                  # Reed API client (job search & job detail fetcher)
├── scorer.py                   # LLM evaluation engine (Claude Haiku candidate-JD matcher)
├── cover_letter.py             # Cover letter generator (Claude Sonnet 3-paragraph writer)
├── notion.py                   # Notion API integration for tracker database syncing
├── config.sample.py            # Sample candidate preferences schema
├── cv.md                       # Your CV content (Markdown format)
├── cv.sample.md                # Template CV
├── prompts/
│   └── assessor_system_prompt.md # System prompt for candidate-JD fit assessment
├── output/                     # Local archive for generated reports and cover letters
└── .pipeline_state.json        # Pipeline run timestamp & processed job ID state file
```

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- Python 3.10+
- Active API Keys for:
  - **Reed API** ([Get a free developer key](https://www.reed.co.uk/developers/jobseeker))
  - **Anthropic API** (for Claude Haiku & Claude Sonnet models)
  - **Notion API** & Integration Token ([Notion Developers](https://developers.notion.com/))

### 2. Environment Setup

Clone the repository and install required packages:

```bash
git clone https://github.com/your-username/job-application-agent.git
cd job-application-agent

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration (`.env`)

Create a `.env` file in the root directory (refer to `.env.example` or sample settings below):

```env
# API Keys
REED_API_KEY=your_reed_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
NOTION_API_KEY=your_notion_integration_token
NOTION_DATABASE_ID=your_notion_database_id

# Candidate Preferences
CANDIDATE_LOCATION="London (open to remote and hybrid)"
CANDIDATE_SALARY="£100,000+ for permanent roles; £600+ per day outside IR35 for contract roles"
CANDIDATE_WORK_TYPE="Open to permanent and contract roles"
```

### 4. Candidate CV Setup

Ensure `cv.md` exists in the repository root containing your experience, skills, metrics, and achievements. You can use `cv.sample.md` as a guide.

---

## 🚦 Usage

Run the main pipeline:

```bash
python main.py
```

### Workflow Execution Flow

1. **State Restoration**: Reads `.pipeline_state.json` to find the last run timestamp and seen job IDs.
2. **Fetch**: Queries Reed API for Product Manager roles in London.
3. **Filter**: Skips seen job IDs and filters out irrelevant job titles.
4. **Enrich & Score**: Retrieves full JD details and evaluates fit using Claude Haiku.
5. **Cover Letter**: For jobs with a **Skills Score $\ge$ 7** and **Recommendation != Skip**, generates a customized cover letter using Claude Sonnet.
6. **Notion Sync**: Pushes job metadata, score, recommendation, IR35 status, and application status to Notion.
7. **Local Output**: Saves a Markdown summary report to `output/<job_id>_<employer>.md`.
8. **State Save**: Updates `.pipeline_state.json` for subsequent incremental runs.

---

## 📊 Outputs & Notion Schema

### Local Archive Files (`output/`)
Each processed role generates a Markdown document formatted like:
```markdown
# [Job Title] — [Employer]

| Field | Value |
|-------|-------|
| Job ID | 1234567 |
| Location | London |
| Salary | £100,000 - £120,000 |
| Posted | DD/MM/YYYY |
| URL | View on Reed |

---
## Fit Assessment & Evaluation Matrix
...

---
## Cover Letter
...
```

### Notion Database Schema
The Notion integration (`notion.py`) expects a database with the following fields:
- **Role** (*Title*)
- **Company** (*Rich Text*)
- **Job ID** (*Rich Text*)
- **Source** (*Select*: `Reed`)
- **Salary** (*Rich Text*)
- **IR35 Status** (*Select*: `Outside IR35`, `Inside IR35`, `Not Specified`)
- **Skills Score** (*Number*)
- **Recommendation** (*Select*: `Apply`, `Apply with caveats`, `Skip`)
- **URL** (*URL*)
- **Application Status** (*Select*: `Not Started`)
- **Date Posted** (*Date*)
- **Date Processed** (*Date*)

---

## 📜 License

MIT License.
