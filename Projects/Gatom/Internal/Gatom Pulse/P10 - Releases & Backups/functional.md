---
tags: [gatom, pulse, p10, releases, changelog, backups, functional]
---

# P10 — Releases & Backup Monitoring: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P10 — Releases & Backup Monitoring
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers, operations staff

---

## 1. Purpose & Scope

This domain covers two related capabilities:
1. **Release Management**: Track software versions, manage changelogs, and monitor fleet-wide adoption of updates.
2. **Backup Monitoring**: Verify that every client server has recent, valid backups.

Both are grouped here because they relate to the operational health of deployments.

---

## 2. Business Requirements — Releases

| # | Requirement |
|---|---|
| P10-001 | Releases must be versioned per app (e.g., `rental_core 1.3.0`) |
| P10-002 | Each release must have: version tag, affected apps, severity, markdown changelog |
| P10-003 | Releases must be targetable: all servers, specific clients, or by tier |
| P10-004 | Connected agents must be notified of new releases on next heartbeat |
| P10-005 | Agent must display changelog in Frappe Desk for the client's System Manager |
| P10-006 | Fleet adoption must be trackable: "4/6 servers updated to v1.3.0" |
| P10-007 | Updates are applied manually (bench commands) — Pulse only tracks status |

---

## 3. Business Requirements — Backup Monitoring

| # | Requirement |
|---|---|
| P10-008 | Agent must check daily whether a backup exists from the last 24 hours |
| P10-009 | Agent must report: last backup timestamp, backup file size, backup type (full/partial) |
| P10-010 | No backup in 24h → WARNING alert (P05) |
| P10-011 | No backup in 48h → CRITICAL alert + auto-create ticket (P06) |
| P10-012 | Backup size < 1 MB → WARNING (possible corruption or empty database) |
| P10-013 | Backup history must be retained for 90 days for trend analysis |

---

## 4. DocTypes — Releases

### 4.1 Pulse Release

| Field | Type | Notes |
|---|---|---|
| `version` | Data | ✅ e.g., `1.3.0` |
| `affected_apps` | Small Text | JSON array: `["rental_core", "rental_vehicles"]` |
| `severity` | Select | `Patch` / `Minor` / `Major` / `Security` |
| `status` | Select | `Draft` / `Published` / `Archived` |
| `changelog` | Markdown Editor | Release notes in markdown |
| `target_scope` | Select | `All Servers` / `Specific Clients` / `By Tier` |
| `target_clients` | Table MultiSelect → Pulse Client | If `Specific Clients` |
| `target_tier` | Select | If `By Tier`: `Starter` / `Professional` / `Enterprise` |
| `published_at` | Datetime | When published |
| `published_by` | Link → User | Who published it |

### 4.2 Server Release Status (Child Table of Pulse Release)

Tracks which servers have been updated:

| Field | Type |
|---|---|
| `server` | Link → Pulse Server |
| `notified` | Check (set when agent receives notification) |
| `updated` | Check (set manually by Gatom team after deploying) |
| `updated_at` | Datetime |
| `updated_by` | Link → User |
| `current_version` | Data (reported by agent) |

---

## 5. DocTypes — Backup Monitoring

### 5.1 Backup Status Report

One record per server per day:

| Field | Type | Notes |
|---|---|---|
| `server` | Link → Pulse Server | |
| `date` | Date | The day being reported |
| `has_backup` | Check | Whether a backup file was found |
| `last_backup_at` | Datetime | Timestamp of the most recent backup file |
| `backup_size_mb` | Float | Size of the backup file in MB |
| `backup_type` | Select | `Full` / `Partial` |
| `backup_path` | Data | Relative path to backup file on client server |
| `backup_count` | Int | Total `.sql.gz` files in backup directory |
| `status` | Select | `Healthy` / `Warning` / `Critical` |

---

## 6. Agent-Side Collection

### 6.1 Backup Checker

```python
def check_backup_status():
    """Daily at 3 AM — verify backups exist."""
    backup_dir = os.path.join(frappe.get_site_path(), "private", "backups")
    
    if not os.path.exists(backup_dir):
        return push_status(has_backup=False, status="Critical")
    
    # Find most recent .sql.gz file
    backups = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith(".sql.gz")],
        key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
        reverse=True
    )
    
    if not backups:
        return push_status(has_backup=False, status="Critical")
    
    latest = backups[0]
    path = os.path.join(backup_dir, latest)
    mtime = datetime.fromtimestamp(os.path.getmtime(path))
    size_mb = os.path.getsize(path) / (1024 * 1024)
    hours_old = (now() - mtime).total_seconds() / 3600
    
    status = "Healthy"
    if hours_old > 48:
        status = "Critical"
    elif hours_old > 24:
        status = "Warning"
    elif size_mb < 1:
        status = "Warning"
    
    push_status(
        has_backup=True,
        last_backup_at=mtime,
        backup_size_mb=round(size_mb, 2),
        backup_type="Full",
        backup_path=f"private/backups/{latest}",
        status=status
    )
```

### 6.2 Release Notification Receiver

On every heartbeat response, Pulse piggybacks pending release notifications:

```json
{
    "status": "ok",
    "releases": [
        {
            "version": "1.3.0",
            "severity": "Minor",
            "changelog": "## What's New\n- GPS tracking improvements\n- Bug fix: mileage overage calculation",
            "affected_apps": ["rental_core", "rental_vehicles"]
        }
    ]
}
```

Agent writes a Frappe System Notification for the site's System Manager:
```python
def notify_release(release):
    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": f"🆕 Update Available: rental_core v{release['version']}",
        "email_content": release["changelog"],
        "for_user": get_system_manager(),
        "type": "Alert",
    }).insert(ignore_permissions=True)
```

---

## 7. API Endpoints

### 7.1 Receive Backup Status (`allow_guest=True`)

> ⚠️ **Canonical payload**: [[../API Contract#2.5 Push Backup Status|API Contract §2.5]]

```
POST /api/method/gatom_pulse.api.agent.backup_status
Authorization: Bearer {api_key}
Body: { see API Contract §2.5 }
```

**Logic**:
1. Authenticate API key
2. Create `Backup Status Report` record
3. If `status = Warning` or `Critical` → trigger alert (P05)
4. If `Critical` and no backup in 48h → auto-create ticket (P06)

### 7.2 Acknowledge Release (`allow_guest=True`) *(NEW)*

> ⚠️ **Canonical payload**: [[../API Contract#2.7 Acknowledge Release|API Contract §2.7]]

```
POST /api/method/gatom_pulse.api.agent.release_ack
Authorization: Bearer {api_key}
Body: { see API Contract §2.7 }
```

**Logic**:
1. Authenticate API key
2. Find `Server Release Status` child row for this server + release
3. Set `notified = 1`, update `current_version`
4. Write to Pulse Audit Log: `RELEASE_ACKNOWLEDGED`

---

## 8. Dashboard Views (React)

### 8.1 Release Manager

- Release list: version, severity badge, status, published date, adoption ratio
- Adoption progress bar: "4/6 servers updated" (per release)
- Create/edit release form with markdown changelog editor
- Publish button with confirmation
- Drill-down: which specific servers are pending update

### 8.2 Backup Health Dashboard

- Server grid: each card shows backup status icon (green ✅ / yellow ⚠️ / red ❌)
- Last backup time (relative: "6 hours ago")
- Backup size trend (sparkline per server, last 30 days)
- Fleet summary: "12/14 servers have healthy backups"
- Click → backup history timeline for specific server

### 8.3 Backup Alert Panel

- Servers without backup in 24h → yellow warning cards
- Servers without backup in 48h → red critical cards with linked ticket
- Suspiciously small backups (< 1 MB) → yellow investigation cards

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A07 — Backup Checking (Agent side)]]

