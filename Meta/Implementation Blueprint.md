
This document outlines the phased setup, configuration, and integration strategy for building a local-first, server-parsable Obsidian vault. The vault is designed to act as a structured database for project management, collaborative tracking, automated journaling, and seamless cross-device synchronization.

## Architecture Overview

```
+---------------------+      Syncthing (TLS, peer mesh)     +---------------------+
| Obsidian – Laptop   | <----------------------------------> | Obsidian – Mobile   |
| [Daily Notes]       |                                     | [Daily Notes]       |
| [Projects]          |                                     | [Projects]          |
+---------------------+                                     +---------------------+
         ^  \                                                       /  ^
         |   \  Syncthing (server is a third peer)                /   |
         |    \                                                  /    |
         |     v                                                v     |
         |  +-------------------------------------------------------+  |
         |  | Custom Server                                         |  |
         |  | • Syncthing peer (watches vault/ in real time)        |  |
         |  | • Parses YAML frontmatter & checklist ASTs            |  |
         |  | • Writes .sync/errors.json back to shared folder      |  |
         |  | • Optional: pushes audit snapshots to private GitHub  |  |
         |  +-------------------------------------------------------+  |
         |                                                             |
         +---------------------- Git (optional, audit/history) --------+
```

---

## Phase 1: Directory Foundation & Version Control

In this phase, you will lay down a rigid, standardized folder hierarchy and configure your local Git repository.

### Step 1.1: File Structure

Initialize an empty folder on your laptop and create the following directory tree:

```
vault/
├── .gitignore
├── README.md                  # Schema conventions for collaborators & the server
├── 00_Inbox/                  # Quick captures, untagged thoughts, incoming syncs
├── 10_Projects/               # Project-specific markdown notes
│   └── Project Board.md       # Kanban board (visual display only — see Phase 3)
├── 20_People/                 # Team member contact and association files
├── 30_Journal/
│   ├── Daily/                 # YYYY-MM-DD.md
│   ├── Weekly/                # YYYY-[W]ww.md
│   ├── Monthly/               # YYYY-MM.md
│   └── Yearly/                # YYYY.md
├── 40_Resources/              # Static guides, documentation, excalidraw assets
└── 99_Templates/              # Raw templates parsed by Templater
    ├── Template_Project.md
    ├── Template_Daily.md
    ├── Template_Weekly.md
    ├── Template_Monthly.md
    ├── Template_Yearly.md
    └── Template_Person.md
```

Create a `README.md` at the vault root explaining the YAML schema conventions, the sync protocol, and the `block_id` naming standard. This is essential for the server integration and any future collaborators.

### Step 1.2: Strict `.gitignore` & Syncthing Ignore Setup

Obsidian stores local UI states inside the hidden `.obsidian` folder. These are device-specific and should **not** be synced, to avoid constant conflicts. Plugin *configuration* files (`data.json`) are valuable to keep in sync so settings stay consistent across devices.

**`.gitignore`** (for the optional Git audit trail):

```gitignore
# --- Obsidian Workspace State (device-specific) ---
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/graph.json
.obsidian/backups/

# --- Syncthing conflict files (auto-generated on true conflicts) ---
*.sync-conflict-*

# --- System Files ---
.DS_Store
Thumbs.db

# NOTE: .obsidian/plugins/*/data.json files are intentionally
# NOT ignored so that plugin settings (Dataview, Templater, etc.)
# stay consistent across devices. Review each before the first
# sync to ensure no secrets are embedded.
```

**`.stignore`** (Syncthing's own ignore file — place in vault root):

Syncthing reads `.stignore` from the root of each shared folder. Use it to exclude the same device-specific files:

```
// .stignore  (Syncthing ignore patterns — glob syntax)
.obsidian/workspace.json
.obsidian/workspace-mobile.json
.obsidian/graph.json
.obsidian/backups/
.DS_Store
Thumbs.db
// Keep *.sync-conflict-* files visible so you can resolve them in Obsidian
```

> **Why keep conflict files visible?** Unlike Git, Syncthing does not merge files — when two devices edit the same file simultaneously it renames one copy to `filename.sync-conflict-<date>-<deviceid>.md`. Keeping these visible in Obsidian allows you to inspect and resolve them using a diff plugin before deleting the stale copy.

### Step 1.3: Initialize the Local Repo (Optional — Audit Trail Only)

Git is **no longer the primary sync mechanism** — that role is taken over by Syncthing (Phase 4). However, maintaining a Git history gives you a searchable audit trail and a clean rollback path.

Open your terminal in the vault folder and run:

```bash
git init
git add .
git commit -m "chore: initial vault skeleton"
git branch -M main
# Add your private GitHub repository (optional but recommended)
git remote add origin git@github.com:yourusername/your-private-vault.git
git push -u origin main
```

You can run periodic `git add . && git commit && git push` manually, via a cron job on your laptop, or via the **Obsidian Git** plugin set to a long interval (e.g., 6-hour backup) — not continuous real-time sync.

### Step 1.4: Enable GitHub Branch Protection (Optional)

If you use the GitHub remote, go to **GitHub → Repository → Settings → Branches → Add rule** for `main`:

- ✅ **Require linear history** (prevents divergent history from periodic snapshots)
- ✅ **Do not allow force pushes**
- ✅ Do not allow branch deletions

---

## Phase 2: Metadata Schema Validation (The YAML Standards)

To ensure your future server can cleanly parse your notes without exceptions, every file type must adhere to a strict YAML schema. Enter these templates into your `99_Templates` directory.

### Step 2.1: Project Note Schema (`99_Templates/Template_Project.md`)

> **ID Uniqueness**: The `id` field appends a 4-character random hex suffix to the timestamp to prevent collisions if multiple projects are created in the same second (e.g. bulk imports).

```markdown
---
type: "project"
id: "proj_20260611181043_9b16"
title: "Implementation Blueprint"
status: "backlog"  # [backlog, planning, active, paused, completed, abandoned]
priority: "medium"  # [high, medium, low]
created_at: 2026-06-11T18:10:43+03:00
updated_at: 2026-06-11T18:10:43+03:00
owner: "[[John Doe]]"
team_members:
  - "[[Jane Smith]]"
tags:
  - "project"
---

# Implementation Blueprint

## Description
<!-- Provide a brief high-level objective here -->

## Milestones
- [ ] Define requirements ^ms-1
- [ ] Implement backend services ^ms-2
- [ ] QA & deployment ^ms-3

## Tasks
- [ ] Identify external dependencies #assignee/jdoe #status/todo ^task-1

## Notes & Documentation

## Attachments
<!-- Link to related files in 40_Resources/ -->
- [[40_Resources/]]
```

> **`updated_at` Maintenance**: This field is set at creation but does not auto-update. Create a Templater hotkey snippet (`tp.hooks.on_all_templates_executed`) that rewrites `updated_at` to the current timestamp whenever you run a "Update note metadata" command on an existing project file.

### Step 2.2: Person Schema (`99_Templates/Template_Person.md`)

This schema is required because `owner` and `team_members` fields in project notes use wikilinks (`[[Name]]`) that resolve to files in `20_People/`. Without a parseable schema, the server cannot resolve these references.

```markdown
---
type: "person"
id: "person_implementation_blueprint"
name: "Implementation Blueprint"
email: ""
role: ""           # e.g. "engineer", "designer", "pm"
team: ""
tags:
  - "person"
---

# Implementation Blueprint

## Contact
- **Email**: 
- **Role**: 
- **Team**: 

## Active Projects
```dataview
TABLE status, priority
FROM "10_Projects"
WHERE contains(team_members, this.file.link) OR owner = this.file.link
SORT status ASC
```

## Notes
```

### Step 2.3: Daily Journal Schema (`99_Templates/Template_Daily.md`)

```markdown
---
type: "journal/daily"
date: 2026-06-11
week: 2026-W24
summary: ""  # 1-2 sentence high-level summary for weekly rolling
wellbeing: 5       # Scale 1-5
energy: 5          # Scale 1-5
focus: 5           # Scale 1-5
top_priorities:
  - ""
  - ""
  - ""
tags:
  - "journal/daily"
---

# Daily Journal: Thursday, June 11, 2026

## Top 3 Priorities
- [ ] 
- [ ] 
- [ ] 

## Daily Log
- 

## Meetings
- 

## Notes & Discoveries

## Tomorrow / Intentions
- 

---
*Parent week: [[30_Journal/Weekly/2026-W24]]*
```

### Step 2.4: Weekly Journal Schema (`99_Templates/Template_Weekly.md`)

```markdown
---
type: "journal/weekly"
date: 2026-W24
summary: ""
tags:
  - "journal/weekly"
---

# Weekly Summary: 2026-W24

## Automated Daily Roll-ups
```dataview
TABLE summary as "Daily Recap", wellbeing as "Wellbeing", energy as "Energy", focus as "Focus"
FROM "30_Journal/Daily"
WHERE week = this.date
SORT file.day ASC
```

## Active Projects Progress
```dataview
TABLE status, priority, owner
FROM "10_Projects"
WHERE status = "active"
SORT priority DESC
```

## Weekly Reflection

## Key Decisions Made

## Next Week Focus
```

> **Dataview Fix**: The previous version used `this.file.day` to compute date ranges on a weekly note — `file.day` is undefined on non-daily notes and would silently return no results. The corrected version matches on the `week` frontmatter field that each daily note carries, which is reliable and server-parseable.

### Step 2.5: Monthly Journal Schema (`99_Templates/Template_Monthly.md`)

```markdown
---
type: "journal/monthly"
date: 2026-06
summary: ""
tags:
  - "journal/monthly"
---

# Monthly Review: June 2026

## Weekly Summaries
```dataview
TABLE summary
FROM "30_Journal/Weekly"
WHERE startswith(date, this.date)
SORT date ASC
```

## Completed Projects
```dataview
TABLE title, owner, priority
FROM "10_Projects"
WHERE status = "completed"
SORT file.mtime DESC
LIMIT 10
```

## Retrospective

## Goals for Next Month
```

### Step 2.6: Yearly Journal Schema (`99_Templates/Template_Yearly.md`)

```markdown
---
type: "journal/yearly"
date: 2026
summary: ""
tags:
  - "journal/yearly"
---

# Yearly Review: 2026

## Monthly Summaries
```dataview
TABLE summary
FROM "30_Journal/Monthly"
WHERE startswith(date, this.date)
SORT date ASC
```

## Projects Completed This Year
```dataview
TABLE title, owner, priority
FROM "10_Projects"
WHERE status = "completed" AND startswith(created_at, this.date)
SORT priority DESC
```

## Annual Retrospective

## Goals for Next Year


---

## Phase 3: Community Plugins & UI Layer

With folder directories and templates established, open Obsidian, navigate to **Settings > Community Plugins**, disable Safe Mode, and install the following toolchain.

### Step 3.1: Plugin Configuration Checklist

| Plugin Name | Critical Settings & Mappings |
| :--- | :--- |
| **Templater** | 1. Enable **Trigger Templater on new file creation**.<br>2. Map `99_Templates/` as your default template folder.<br>3. Add a custom hotkey command ("Update note metadata") that runs a snippet rewriting `updated_at` in the frontmatter of the current file. |
| **Periodic Notes** | 1. Enable **Daily**, **Weekly**, **Monthly**, and **Yearly** notes.<br>2. Point formats and locations to their respective paths in `30_Journal/`.<br>3. Bind daily/weekly/monthly/yearly templates to their respective schemas. |
| **Dataview** | 1. Enable **Enable JavaScript Queries** (DataviewJS).<br>2. Keep auto-refresh enabled at a conservative interval (e.g., 10 seconds). |
| **Kanban** | 1. Configure default lane paths to point to your `10_Projects` folder.<br>2. **Important**: The Kanban plugin does **not** natively write back to YAML frontmatter `status` fields — it maintains its own board state. Treat the Kanban board as a **read-only visual display** only. The authoritative `status` value lives in each project note's frontmatter. Update it there manually or via the Templater "Update metadata" command. |

### Step 3.2: Setting Up the Kanban Board

Create a note at `10_Projects/Project Board.md` and convert it to a Kanban view (via the Command Palette). Map your lanes to the frontmatter values as a **visual aid only**:

- **Backlog** (reflects YAML: `status: backlog`)
- **Active Development** (reflects YAML: `status: active`)
- **Completed** (reflects YAML: `status: completed`)

> **Source of Truth Clarification**: Do not rely on drag-and-drop in the Kanban board to update a project's status. Always edit the `status` field in the project note's frontmatter directly. The Kanban board will re-render to reflect changes on the next Dataview refresh.

---

## Phase 4: Sync & Device Orchestration (Syncthing)

Syncthing is a free, open-source, end-to-end encrypted peer-to-peer file sync tool. It requires **no cloud account**, no paid subscription, and syncs over your LAN when devices are on the same network — falling back to a relay server (or your own relay) for remote sync. All data is encrypted in transit with TLS.

### Step 4.1: Install Syncthing on Each Device

| Device | Installation Method |
| :--- | :--- |
| **Linux (laptop)** | `sudo apt install syncthing` or via [syncthing.net/downloads](https://syncthing.net/downloads/) |
| **macOS (laptop)** | `brew install syncthing` then `brew services start syncthing` |
| **Windows** | Download the `.exe` installer from [syncthing.net](https://syncthing.net/downloads/) and enable **Start on Login** |
| **Android** | Install **Syncthing-Fork** from F-Droid or Google Play |
| **iOS** | Install **Möbius Sync** or **Syncthing for iOS** from the App Store |
| **Server** | `sudo apt install syncthing` + run as a `systemd` service (see Step 4.4) |

Once installed, Syncthing's Web UI is available at `http://127.0.0.1:8384` on desktop.

### Step 4.2: Configure the Shared Vault Folder

1. Open the Syncthing Web UI on your **laptop** (`http://127.0.0.1:8384`).
2. Click **Add Folder**.
   - **Folder Label**: `Obsidian Vault`
   - **Folder Path**: `/path/to/your/vault` (the same path Obsidian uses)
   - **Folder ID**: Use the auto-generated ID or set a memorable one (e.g., `obsidian-vault`). This ID must match on all devices.
3. Under **Ignore Patterns**, confirm your `.stignore` file (created in Step 1.2) is in the vault root. Syncthing reads it automatically.
4. **Watch for Changes**: Enable **Watch for Changes** (real-time inotify/FSEvents watch) so edits propagate within seconds without polling.
5. Under **Advanced → Versioning**, set:
   - **Type**: Simple File Versioning
   - **Keep Versions**: `10`
   - **Clean Interval**: `3600` seconds
   This keeps the last 10 versions of any overwritten file in a hidden `.stversions/` folder inside your vault — a built-in safety net before you even look at Git.

### Step 4.3: Pair Devices (Laptop ↔ Mobile ↔ Server)

1. On **each additional device**, open Syncthing's UI and note its **Device ID** (shown under `Actions → Show ID`).
2. On your laptop's Syncthing UI, click **Add Remote Device** and paste the target device's ID.
3. Once both sides accept the pairing, go to the shared folder on the laptop and tick the new device under **Share With**.
4. The remote device will be prompted to **accept** the shared folder and select a local path (e.g., on Android: `/storage/emulated/0/ObsidianVault/`).
5. Point Obsidian on the mobile device to that same path.

> **Tip**: For LAN-first performance, enable **Local Discovery** and **Global Discovery** in Syncthing settings. When both devices are on the same Wi-Fi, sync is near-instant over the local network. Global Discovery relays kicks in when one device is remote.

### Step 4.4: Server as a Third Peer (Always-On Node)

Running Syncthing on your server ensures changes propagate even when your laptop is offline — the server acts as a persistent relay node for the mobile device.

```bash
# On the server (Debian/Ubuntu)
sudo apt install syncthing

# Create a dedicated system service for the 'ubuntu' (or your) user
sudo systemctl enable syncthing@ubuntu
sudo systemctl start syncthing@ubuntu

# Tunnel the Web UI securely via SSH to configure it
ssh -L 9384:127.0.0.1:8384 user@your-server.com
# Then open http://127.0.0.1:9384 in your local browser
```

In the server's Syncthing UI:
- Add the same **Folder ID** (`obsidian-vault`) and set the **Folder Path** to where you want the vault clone to live (e.g., `/srv/vault`).
- Pair the server with your laptop and mobile using the same Add Remote Device flow.
- Set the server folder to **Receive Only** if you only want the server to consume vault data (safer — prevents accidental server-side edits from propagating). Set to **Send & Receive** if the server needs to write `.sync/errors.json` back (see Phase 5).

### Step 4.5: Conflict Resolution Protocol

Syncthing does **not** merge files. If two devices edit the same file before a sync cycle completes, Syncthing keeps both versions:

- The **winning** version keeps the original filename.
- The **losing** version is renamed to `filename.sync-conflict-<YYYYMMDD>-<HHMMSS>-<deviceid>.md`.

**Prevention:**
- Enable **Watch for Changes** (Step 4.2) to minimize the sync window to seconds.
- Keep Syncthing running continuously on all devices. Use Android's battery exemption settings to prevent the app from being killed.

**Resolution (if a conflict file appears):**

1. Open Obsidian — the conflict file will appear as a note in your vault.
2. Use the **Better File Link** or **Linter** plugin (or any diff viewer) to compare the two versions.
3. Manually merge the content you want to keep into the canonical filename.
4. Delete the `.sync-conflict-*.md` file.

**Rollback Procedure (using Syncthing versioning):**

If a note is corrupted or accidentally deleted:
1. Navigate to the hidden `.stversions/` folder inside your vault.
2. Locate the timestamped version of the file (e.g., `.stversions/10_Projects/MyProject~20260611-174000.md`).
3. Copy or rename it back to the original path.

For a full rollback using Git snapshots:
```bash
# View recent commits
git log --oneline -10

# Restore a specific file from a known-good commit
git checkout <commit-hash> -- 10_Projects/MyProject.md

git commit -m "fix: restore MyProject.md to last known good state"
```

> The server validator (Phase 5) writes a `.sync/errors.json` file back to the vault. Because the server folder is set to **Send & Receive**, this file syncs back to all devices within seconds, giving you an in-Obsidian parse error report.

---

## Phase 5: Server Integration Validation Script

Before hosting a production backend, validate that your YAML structures are fully compliant and easily extractable. Below is a production-ready Python validation/extraction parser you can run locally or deploy on a cron job.

```python
# parse_vault.py
import os
import re
import json
import yaml

VAULT_PATH = "./"  # Set to absolute path of your local vault
PROJECTS_DIR = os.path.join(VAULT_PATH, "10_Projects")
ERRORS_OUTPUT = os.path.join(VAULT_PATH, ".sync", "errors.json")


def parse_md_file(file_path):
    """
    Parses frontmatter and inline tasks with Block IDs.
    Handles both Unix (LF) and Windows (CRLF) line endings.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalize line endings to LF before processing
    content = content.replace('\r\n', '\n').replace('\r', '\n')

    # Split YAML frontmatter from body text
    match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL)
    if not match:
        return None, f"No valid YAML frontmatter found in {file_path}"

    yaml_payload = match.group(1)
    body_payload = match.group(2)

    try:
        metadata = yaml.safe_load(yaml_payload)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error in {file_path}: {exc}"

    # Parse Checklist Tasks with ID tokens: e.g. - [ ] Task name #assignee ^id
    tasks = []
    task_regex = (
        r'^\s*-\s*\[(?P<completed>[ x\/])\]\s+'
        r'(?P<desc>.*?)\s+\^(?P<block_id>[a-zA-Z0-9\-]+)\s*$'
    )

    for line in body_payload.split('\n'):
        task_match = re.match(task_regex, line)
        if task_match:
            status_char = task_match.group('completed')
            status = 'todo'
            if status_char == 'x':
                status = 'completed'
            elif status_char == '/':
                status = 'in-progress'

            desc_text = task_match.group('desc')
            assignee_match = re.search(r'#assignee/(\S+)', desc_text)
            assignee = assignee_match.group(1) if assignee_match else None
            clean_desc = re.sub(r'#\S+', '', desc_text).strip()

            tasks.append({
                "block_id": task_match.group('block_id'),
                "description": clean_desc,
                "status": status,
                "assignee": assignee
            })

    metadata["tasks"] = tasks
    metadata["_source_file"] = os.path.relpath(file_path, VAULT_PATH)
    return metadata, None


def run_sync_validation():
    extracted_data = []
    errors = []

    for root, _, files in os.walk(PROJECTS_DIR):
        for file in files:
            if file.endswith(".md") and not file.startswith("Project Board"):
                file_path = os.path.join(root, file)
                result, error = parse_md_file(file_path)
                if result:
                    extracted_data.append(result)
                if error:
                    errors.append({"file": file_path, "error": error})

    # Write errors back to vault for visibility in Obsidian
    if errors:
        os.makedirs(os.path.dirname(ERRORS_OUTPUT), exist_ok=True)
        with open(ERRORS_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(errors, f, indent=2)
        print(f"⚠️  {len(errors)} parse error(s) written to {ERRORS_OUTPUT}")
    else:
        # Clean up stale error file if all is well
        if os.path.exists(ERRORS_OUTPUT):
            os.remove(ERRORS_OUTPUT)

    print(json.dumps(extracted_data, indent=2))
    return extracted_data, errors


if __name__ == "__main__":
    run_sync_validation()
```

---

## Phase 6: Server Event Processing

With Syncthing, the server already has the vault mounted as a live shared folder (Phase 4.4). There is no longer a need to pull from GitHub on every change — the server watches its local Syncthing folder directly.

### Step 6.1: Trigger Processing via Syncthing Event API

Syncthing exposes a REST event stream at `http://127.0.0.1:8384/rest/events`. Subscribe to `FolderScanProgress` or `LocalChangeDetected` events to trigger the parser whenever vault files change:

```python
# server/syncthing_watcher.py
import requests
import time
import os
from parse_vault import run_sync_validation

SYNCTHING_API = "http://127.0.0.1:8384"
SYNCTHING_KEY = os.environ["SYNCTHING_API_KEY"]  # From Syncthing Web UI → Actions → Settings → API Key
FOLDER_ID = "obsidian-vault"  # Must match the Folder ID set in Step 4.2


def watch_events():
    last_seen = 0
    print("Watching Syncthing events...")
    while True:
        try:
            resp = requests.get(
                f"{SYNCTHING_API}/rest/events",
                headers={"X-API-Key": SYNCTHING_KEY},
                params={"since": last_seen, "events": "FolderScanProgress,LocalChangeDetected", "timeout": 60},
                timeout=65
            )
            events = resp.json()
            for event in events:
                last_seen = event["id"]
                if event.get("data", {}).get("folder") == FOLDER_ID:
                    print(f"[{event['time']}] Change detected — running validator...")
                    data, errors = run_sync_validation()
                    print(f"  Parsed: {len(data)} files | Errors: {len(errors)}")
        except requests.exceptions.Timeout:
            pass  # Long-poll timeout is normal; loop continues
        except Exception as exc:
            print(f"Watcher error: {exc}")
            time.sleep(5)


if __name__ == "__main__":
    watch_events()
```

Run this as a `systemd` service alongside Syncthing on your server.

### Step 6.2: (Optional) GitHub Webhook for Audit Snapshots

If you retain the optional Git audit trail (Step 1.3), you can still configure a GitHub webhook to trigger additional downstream actions (CI checks, changelog generation, etc.) on each periodic Git snapshot push:

1. Go to **GitHub → Repository → Settings → Webhooks → Add webhook**.
2. Set **Payload URL** to `https://your-server.com/webhook/vault-snapshot`.
3. Set **Content type** to `application/json`.
4. Generate a **Webhook Secret** and store it as `GITHUB_WEBHOOK_SECRET`.
5. Select **Just the push event**.

The webhook handler does **not** need to `git pull` (the vault is already live via Syncthing); it only triggers secondary actions like changelog generation or external notifications.

### Step 6.3: Write-Back Protocol (Server → Vault)

Because the server's Syncthing folder is set to **Send & Receive** (Step 4.4), writing directly to the server's vault path is enough — Syncthing propagates the change to all other devices within seconds:

```python
# Writing an error report back to the vault (propagated via Syncthing)
import json, os

ERRORS_OUTPUT = "/srv/vault/.sync/errors.json"  # Server's local Syncthing vault path

def write_errors(errors: list):
    if errors:
        os.makedirs(os.path.dirname(ERRORS_OUTPUT), exist_ok=True)
        with open(ERRORS_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(errors, f, indent=2)
    elif os.path.exists(ERRORS_OUTPUT):
        os.remove(ERRORS_OUTPUT)  # Clear stale error file
```

> **No branch + merge flow required**: Direct writes from the server propagate instantly via Syncthing. The server does not need a Git branch-protection workaround for write-backs.

---

## Phase 7: Monitoring & Alerting

### Step 7.1: Sync Health Dashboard

Create a note at `00_Inbox/Sync Status.md` with:

```markdown
---
type: "system/sync-status"
---

# Sync Health Dashboard

## Parse Errors
![[.sync/errors.json]]

## Recent Commits
<!-- Updated by server after each webhook -->
```

### Step 7.2: Alerting

Configure your server to send a notification (email, Slack webhook, or Pushover) if:
- `errors.json` is non-empty after a parse run.
- The `git pull` on the server fails (network error or merge conflict).
- No push has been received from either device in over 48 hours (stale sync).

---

## Phase 8: Backup Strategy

Syncthing is a **sync tool, not a backup tool** — it propagates deletes and overwrites to all peers immediately. Use the following layered backup strategy:

| Layer | Tool | What it covers | Frequency |
| :--- | :--- | :--- | :--- |
| **1 — Syncthing Versioning** | Built-in `.stversions/` | Per-file overwrites & deletes | Continuous (last 10 versions) |
| **2 — Git Snapshots** | Git + GitHub | Full text history, rollback by commit | Every 6 hours (cron or Obsidian Git) |
| **3 — Offsite Object Storage** | `rclone` + Backblaze B2 | Binary attachments + full vault clone | Daily at 03:00 |
| **4 — Local rsync** | `rsync` | Laptop hot-backup to external drive | Weekly |

### Step 8.1: Encrypted Offsite Backup

Use `rclone` to sync your vault to an encrypted Backblaze B2 or S3-compatible bucket on a daily cron:

```bash
# Install rclone, configure a B2 remote named "b2-vault"
rclone sync /path/to/your/vault b2-vault:your-bucket-name/vault \
  --exclude ".obsidian/backups/**" \
  --exclude ".git/**" \
  --exclude ".stversions/**" \
  --log-file /var/log/vault-backup.log
```

Schedule via cron (`crontab -e`):
```
0 3 * * * /usr/bin/rclone sync /path/to/vault b2-vault:your-bucket/vault --exclude ".git/**" --exclude ".stversions/**"
```

### Step 8.2: Retention Policy

- **Syncthing `.stversions/`**: 10 versions per file, pruned automatically.
- **Git history**: Unlimited (GitHub free tier). Periodic snapshots only.
- **Backblaze B2**: Keep 30-day file versioning enabled on the bucket.
- **Local `rsync` / Time Machine**: Recommended for the laptop as a tertiary backup tier.