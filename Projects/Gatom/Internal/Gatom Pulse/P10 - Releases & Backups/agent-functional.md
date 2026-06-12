---
tags: [gatom, pulse, agent, a07, backup, monitoring, functional]
---

# A07 — Backup Checking: Functional Analysis

> **Component**: `gatom_agent`
> **Domain**: A07 — Backup Checking
> **Pulse Counterpart**: [[functional|P10 — Releases & Backup Monitoring]]
> **File**: `collectors/backup_checker.py`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

Every day at 3 AM, the agent checks whether a recent backup exists on the client server's filesystem. It reports the backup's timestamp, size, and health status to Pulse. If no backup is found within 24 hours, Pulse triggers warnings and eventually auto-creates a ticket.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| A07-001 | Agent must check daily at 3 AM whether a backup file exists from the last 24 hours |
| A07-002 | Agent must report: last backup timestamp, file size, backup type (full/partial) |
| A07-003 | Agent must compute a health status: `Healthy` / `Warning` / `Critical` |
| A07-004 | Backup size < 1 MB → `Warning` (possible corruption or empty database) |
| A07-005 | No backup in 24h → `Warning` |
| A07-006 | No backup in 48h → `Critical` |

---

## 3. Backup Location

Frappe stores backups in the site's `private/backups/` directory:

```
/home/frappe/bench/sites/{site}/private/backups/
├── 20260612_010000-{site}_database.sql.gz    # Database backup
├── 20260612_010000-{site}_files.tar           # Public files backup
└── 20260612_010000-{site}_private_files.tar   # Private files backup
```

The agent checks for `.sql.gz` files (database backups) as the primary indicator.

---

## 4. Health Status Logic

```python
def determine_status(latest_backup_path: str | None, now: datetime) -> dict:
    if not latest_backup_path:
        return {"status": "Critical", "reason": "No backup files found"}
    
    mtime = datetime.fromtimestamp(os.path.getmtime(latest_backup_path))
    size_mb = os.path.getsize(latest_backup_path) / (1024 * 1024)
    hours_old = (now - mtime).total_seconds() / 3600
    
    if hours_old > 48:
        status = "Critical"
        reason = f"Last backup is {hours_old:.0f} hours old"
    elif hours_old > 24:
        status = "Warning"
        reason = f"Last backup is {hours_old:.0f} hours old"
    elif size_mb < 1:
        status = "Warning"
        reason = f"Backup is suspiciously small ({size_mb:.2f} MB)"
    else:
        status = "Healthy"
        reason = None
    
    return {
        "status": status,
        "reason": reason,
        "last_backup_at": mtime.isoformat() + "Z",
        "backup_size_mb": round(size_mb, 2),
        "backup_path": os.path.join("private", "backups", os.path.basename(latest_backup_path))
    }
```

---

## 5. Collection Logic

```python
def check_backup_status():
    """Daily at 3 AM — verify backups exist and report to Pulse."""
    backup_dir = os.path.join(frappe.get_site_path(), "private", "backups")
    
    if not os.path.exists(backup_dir):
        push_backup_status(has_backup=False, status="Critical",
                          reason="Backup directory does not exist")
        return
    
    # Find most recent .sql.gz file
    sql_backups = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith(".sql.gz")],
        key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
        reverse=True
    )
    
    if not sql_backups:
        push_backup_status(has_backup=False, status="Critical",
                          reason="No .sql.gz backup files found")
        return
    
    latest_path = os.path.join(backup_dir, sql_backups[0])
    result = determine_status(latest_path, datetime.now())
    push_backup_status(
        has_backup=True,
        backup_count=len(sql_backups),
        backup_type="Full",
        **result
    )
```

---

## 6. Push Payload

> ⚠️ **Canonical payload defined in**: [[../../API Contract#2.5 Push Backup Status|API Contract §2.5]]
> All field names use the canonical names from the API Contract.

> [!IMPORTANT]
> `backup_path` must be the full relative path from site root (e.g., `private/backups/20260612_010000-site_database.sql.gz`), **not** just the filename. This resolves audit finding **PM-06**.

---

## 7. Request

```
POST /api/method/gatom_pulse.api.agent.backup_status
Authorization: Bearer {pulse_api_key}
X-Agent-Version: 1.0.0
X-Request-Timestamp: 1749700800
X-Request-ID: {uuid4}
```

---

## 8. Acceptance Criteria

- [ ] Backup check runs daily at 3 AM local time
- [ ] Scans `private/backups/` for `.sql.gz` files
- [ ] Finds the most recent backup by file modification time
- [ ] `Healthy` if backup < 24h old and > 1 MB
- [ ] `Warning` if 24–48h old OR < 1 MB
- [ ] `Critical` if > 48h old OR no backup files found OR backup dir missing
- [ ] Payload pushed to Pulse's backup status endpoint
- [ ] `backup_path` is full relative path (e.g., `private/backups/...`), not just filename
- [ ] `backup_count` included in payload
- [ ] Pulse unreachable → payload queued locally (A08)

---

## 🔗 Related

- [[../Agent Overview|🤖 Agent Overview]]
- [[functional|P10 — Releases & Backup Monitoring (Pulse side)]]
- [[../P00 - Configuration/agent-functional|A08 — Transport & Resilience]]
