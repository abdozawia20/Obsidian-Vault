# Obsidian Vault — Schema & Conventions

> This document is the source of truth for YAML frontmatter schemas, folder structure, sync protocol, and `block_id` naming. Required reading for the server integration and any collaborators.

---

## Folder Structure

```
vault/
├── .stignore                  # Syncthing ignore patterns (device-specific files)
├── README.md                  # This file
├── Home.md                    # Master vault dashboard
│
├── 00_Inbox/                  # Quick captures, unprocessed thoughts
│   └── Sync Status.md         # Live sync health dashboard (server writes errors.json)
│
├── 20_People/                 # Team member & contact files (Template_Person.md)
│
├── 40_Resources/              # Static guides, docs, shared assets
│
├── Projects/                  # All work projects
│   ├── Websers/               # Websers company workspace
│   │   └── Clients/           # Websers client projects
│   └── Gatom/                 # Gatom agency workspace
│       └── Clients/           # Gatom client projects
│
├── Project MLT/               # Personal life-tracker project
│
├── Journal/                   # Periodic journaling (excluded from server parsing)
│   ├── 01 Daily/
│   ├── 02 Weekly/
│   ├── 03 Monthly/
│   ├── 04 Quarterly/
│   ├── 05 Yearly/
│   └── 06 Templates/
│
├── Meta/                      # Vault management, blueprints, server scripts
│
├── Family/                    # Personal (not synced to server parser)
└── Excalidraw/                # Excalidraw diagram files
```

---

## YAML Frontmatter Schemas

### Project Note (`type: project`)
```yaml
---
type: "project"
id: "proj_YYYYMMDDHHMMSS_XXXX"   # Timestamp + 4-char hex suffix
title: ""
status: "backlog"                  # [backlog, planning, active, paused, completed, abandoned]
priority: "medium"                 # [high, medium, low]
created_at: YYYY-MM-DDTHH:MM:SS+03:00
updated_at: YYYY-MM-DDTHH:MM:SS+03:00
owner: "[[20_People/Name]]"
team_members:
  - "[[20_People/Name]]"
tags:
  - "project"
---
```

### Person Note (`type: person`)
```yaml
---
type: "person"
id: "person_YYYYMMDDHHMMSS"
name: ""
email: ""
role: ""        # e.g. "engineer", "designer", "pm"
team: ""
tags:
  - "person"
---
```

### Task Block IDs (`^block_id`)
Inline tasks in project notes must carry a block ID and optional assignee tag:
```markdown
- [ ] Task description #assignee/username #status/todo ^task-1
- [x] Completed task ^task-2
- [/] In-progress task ^task-3
```

The server parser (`Meta/parse_vault.py`) reads these `^block_id` tokens to extract tasks as structured JSON.

---

## Sync Protocol

- **Primary sync**: Syncthing (peer-to-peer, TLS encrypted, LAN-first)
- **Versioning**: `.stversions/` keeps last 10 file versions automatically
- **Audit trail**: Git snapshots (optional, periodic — not real-time)
- **Conflict files**: `*.sync-conflict-*` files appear when two devices edit simultaneously. Resolve in Obsidian, then delete the conflict copy.

---

## Server Integration

The server runs `Meta/parse_vault.py` on every vault change (triggered via Syncthing event API).
It writes parse errors to `.sync/errors.json` — visible in `00_Inbox/Sync Status.md`.
