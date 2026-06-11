#!/usr/bin/env python3
"""
parse_vault.py — Obsidian Vault YAML & Task Validator
======================================================
Scans all project notes under PROJECTS_DIR, extracts YAML frontmatter
and inline tasks (block IDs), and writes a .sync/errors.json report
back to the vault (propagated to all devices via Syncthing).

Run locally:   python3 Meta/parse_vault.py
Run on server: python3 /srv/vault/Meta/parse_vault.py

Adapted from the Implementation Blueprint to match the actual folder
structure: "Projects/" instead of "10_Projects/".
"""
import os
import re
import json
import yaml

# ── Configuration ────────────────────────────────────────────────────────────
VAULT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # vault root
PROJECTS_DIR = os.path.join(VAULT_PATH, "Projects")
ERRORS_OUTPUT = os.path.join(VAULT_PATH, ".sync", "errors.json")

# Files to skip (MOC files, Kanban boards, etc.)
SKIP_PATTERNS = ["MOC", "Project Board", "Sync Status"]

# Required YAML fields for project notes
REQUIRED_FIELDS = ["type", "id", "title", "status", "priority"]
VALID_STATUSES = {"backlog", "planning", "active", "paused", "completed", "abandoned"}
VALID_PRIORITIES = {"high", "medium", "low"}


def parse_md_file(file_path: str):
    """
    Parses frontmatter and inline tasks with Block IDs.
    Handles both Unix (LF) and Windows (CRLF) line endings.
    Returns (metadata_dict, error_string_or_None).
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    # Split YAML frontmatter from body
    match = re.match(r"^---\n(.*?)\n---\n(.*)", content, re.DOTALL)
    if not match:
        return None, f"No valid YAML frontmatter found in {file_path}"

    yaml_payload = match.group(1)
    body_payload = match.group(2)

    try:
        metadata = yaml.safe_load(yaml_payload)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error in {file_path}: {exc}"

    if not isinstance(metadata, dict):
        return None, f"Frontmatter is not a YAML mapping in {file_path}"

    # Skip non-project notes
    if metadata.get("type") != "project":
        return None, None  # Not an error, just not a project

    # Validate required fields
    for field in REQUIRED_FIELDS:
        if field not in metadata or not metadata[field]:
            return None, f"Missing required field '{field}' in {file_path}"

    if metadata.get("status") not in VALID_STATUSES:
        return None, (
            f"Invalid status '{metadata.get('status')}' in {file_path}. "
            f"Must be one of: {', '.join(sorted(VALID_STATUSES))}"
        )

    if metadata.get("priority") not in VALID_PRIORITIES:
        return None, (
            f"Invalid priority '{metadata.get('priority')}' in {file_path}. "
            f"Must be one of: {', '.join(sorted(VALID_PRIORITIES))}"
        )

    # Parse inline tasks with block IDs: - [ ] Description #assignee/x ^id
    tasks = []
    task_regex = (
        r"^\s*-\s*\[(?P<completed>[ x\/])\]\s+"
        r"(?P<desc>.*?)\s+\^(?P<block_id>[a-zA-Z0-9\-]+)\s*$"
    )
    for line in body_payload.split("\n"):
        task_match = re.match(task_regex, line)
        if task_match:
            status_char = task_match.group("completed")
            status = "todo"
            if status_char == "x":
                status = "completed"
            elif status_char == "/":
                status = "in-progress"

            desc_text = task_match.group("desc")
            assignee_match = re.search(r"#assignee/(\S+)", desc_text)
            assignee = assignee_match.group(1) if assignee_match else None
            clean_desc = re.sub(r"#\S+", "", desc_text).strip()

            tasks.append({
                "block_id": task_match.group("block_id"),
                "description": clean_desc,
                "status": status,
                "assignee": assignee,
            })

    metadata["tasks"] = tasks
    metadata["_source_file"] = os.path.relpath(file_path, VAULT_PATH)
    return metadata, None


def run_sync_validation():
    extracted_data = []
    errors = []

    for root, _, files in os.walk(PROJECTS_DIR):
        for file in sorted(files):
            if not file.endswith(".md"):
                continue
            if any(pattern in file for pattern in SKIP_PATTERNS):
                continue

            file_path = os.path.join(root, file)
            result, error = parse_md_file(file_path)

            if result:
                extracted_data.append(result)
            if error:
                errors.append({"file": os.path.relpath(file_path, VAULT_PATH), "error": error})

    # Write errors back to vault (Syncthing propagates to all devices)
    os.makedirs(os.path.dirname(ERRORS_OUTPUT), exist_ok=True)
    if errors:
        with open(ERRORS_OUTPUT, "w", encoding="utf-8") as f:
            json.dump(errors, f, indent=2, ensure_ascii=False)
        print(f"⚠️  {len(errors)} parse error(s) → {ERRORS_OUTPUT}")
    else:
        if os.path.exists(ERRORS_OUTPUT):
            os.remove(ERRORS_OUTPUT)
        print("✅  All project notes valid. No errors.")

    print(f"📄  Parsed {len(extracted_data)} project note(s).")
    return extracted_data, errors


if __name__ == "__main__":
    data, errors = run_sync_validation()
    if data:
        print("\n── Extracted Projects ──")
        print(json.dumps(data, indent=2, ensure_ascii=False, default=str))
