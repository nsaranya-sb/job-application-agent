# Improvement Plan

## SQLite state tracking (replace `.pipeline_state.json`)

**Why**: Current state file is a flat JSON blob tracking last-run timestamp + processed job IDs. Doesn't scale for querying history, gets harder to inspect/debug as job count grows, and can't easily support future features (e.g. re-scoring, audit trail of past runs). Inspired by comparing against github.com/girshovich/job-hunter, which uses SQLite for this.

**Scope**:
- New `db.py` (or extend `fetcher.py`) with a SQLite schema, e.g.:
  - `jobs` table: `job_id` (PK), `title`, `employer`, `url`, `date_posted`, `first_seen_at`, `score`, `recommendation`, `cover_letter_generated` (bool), `notion_synced` (bool)
  - `runs` table: `run_id` (PK), `started_at`, `finished_at`, `jobs_fetched`, `jobs_scored`
- Migrate `main.py` / `fetcher.py` logic that currently reads/writes `.pipeline_state.json` (last-run timestamp, processed job ID set) to read/write from SQLite instead.
- One-time migration step: import existing `.pipeline_state.json` contents into the new DB on first run, then leave the old file in place (or delete) — decide when implementing.
- Keep the dedup logic itself unchanged (still ID-based, not semantic) — just swap storage backend.

**Out of scope for this pass**: semantic/LLM-based dedup, multi-source aggregation, scheduling — noted as possible future work but not part of this task.

**Files likely touched**: `main.py`, `fetcher.py`, new `db.py`, `.gitignore` (add `*.db`).
