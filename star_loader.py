import csv
import io
import json
from pathlib import Path
from typing import Optional


def load_star_stories(file_path: Path) -> Optional[str]:
    """
    Loads STAR-formatted project stories from CSV, Markdown, or JSON.
    Returns a formatted Markdown string ready to be injected into LLM prompts.
    Returns None if file does not exist or is empty.
    """
    if not file_path.exists():
        return None

    ext = file_path.suffix.lower()

    if ext == ".md":
        content = file_path.read_text(encoding="utf-8").strip()
        return content if content else None

    if ext == ".json":
        return _parse_json_star_stories(file_path)

    if ext in (".csv", ".tsv"):
        return _parse_csv_star_stories(file_path)

    # Fallback to reading raw text
    content = file_path.read_text(encoding="utf-8").strip()
    return content if content else None


def _parse_csv_star_stories(file_path: Path) -> Optional[str]:
    content = file_path.read_text(encoding="utf-8").strip()
    if not content:
        return None

    # Sniff dialect / delimiter
    try:
        delimiter = "\t" if file_path.suffix.lower() == ".tsv" or "\t" in content.splitlines()[0] else ","
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    except Exception as e:
        print(f"Warning: Failed to parse CSV header from {file_path}: {e}")
        return content

    formatted_stories = []
    
    for i, row in enumerate(reader, 1):
        # Normalize column keys (case-insensitive lookup)
        keys = {k.strip().lower(): k for k in row.keys() if k}
        
        def get_val(names: list[str]) -> str:
            for name in names:
                if name in keys and row[keys[name]]:
                    val = str(row[keys[name]]).strip()
                    if val:
                        return val
            return ""

        title = get_val(["title", "project", "role", "project/role", "experience", "name"]) or f"Story #{i}"
        situation = get_val(["situation", "s", "context", "background"])
        task = get_val(["task", "t", "objective", "goal"])
        action = get_val(["action", "a", "actions", "implementation"])
        result = get_val(["result", "r", "results", "impact", "metric", "metrics", "outcome"])
        skills = get_val(["skills", "keywords", "tags", "competencies"])

        story_md = f"### {title}\n"
        if situation:
            story_md += f"- **Situation:** {situation}\n"
        if task:
            story_md += f"- **Task:** {task}\n"
        if action:
            story_md += f"- **Action:** {action}\n"
        if result:
            story_md += f"- **Result / Impact:** {result}\n"
        if skills:
            story_md += f"- **Key Skills / Tags:** {skills}\n"

        formatted_stories.append(story_md.strip())

    if not formatted_stories:
        return None

    return "\n\n".join(formatted_stories)


def _parse_json_star_stories(file_path: Path) -> Optional[str]:
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            formatted_stories = []
            for i, item in enumerate(data, 1):
                if isinstance(item, dict):
                    title = item.get("title") or item.get("project") or f"Story #{i}"
                    story_md = f"### {title}\n"
                    for key in ["situation", "task", "action", "result", "skills"]:
                        if key in item and item[key]:
                            story_md += f"- **{key.capitalize()}:** {item[key]}\n"
                    formatted_stories.append(story_md.strip())
            return "\n\n".join(formatted_stories) if formatted_stories else None
    except Exception as e:
        print(f"Warning: Failed to parse JSON STAR file {file_path}: {e}")

    return file_path.read_text(encoding="utf-8").strip() or None
