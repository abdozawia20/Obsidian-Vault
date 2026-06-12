---
tags: [gatom, pulse, p05, alerting, notifications, functional]
---

# P05 — Alerting & Notifications: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P05 — Alerting & Notifications
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers, operations staff

---

## 1. Purpose & Scope

This domain ensures the Gatom team is notified **before clients notice problems**. It provides multi-channel alerting (email, WhatsApp, in-dashboard), configurable per-client rules, and digest mode to prevent alert fatigue.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P05-001 | Critical alerts must be delivered within 60 seconds of detection |
| P05-002 | Email alerts must be sent via Frappe's built-in email infrastructure |
| P05-003 | WhatsApp alerts (critical only) must be sent via Twilio API |
| P05-004 | In-dashboard notifications must appear in real-time (Socketio) |
| P05-005 | Alert rules must be configurable per client (some clients may CC their own team) |
| P05-006 | Digest mode: non-critical alerts (WARNING, Medium) bundled into hourly email digest |
| P05-007 | Alert deduplication: same alert type for same server within 15 minutes → suppress |
| P05-008 | All alerts must be logged in `Pulse Alert` DocType for audit |

---

## 3. Alert Types

| Trigger | Severity | Default Channel | Source Domain |
|---|---|---|---|
| Server `DOWN` > 5 min | 🔴 Critical | Email + WhatsApp + Dashboard | P02 |
| Server `DEGRADED` > 15 min | 🟠 High | Email + Dashboard | P02 |
| CPU/RAM threshold exceeded | 🟡 Warning | Email digest | P02 |
| Disk threshold exceeded (> 90%) | 🟠 High | Email + Dashboard | P02 |
| Redis/MariaDB unreachable | 🔴 Critical | Email + WhatsApp + Dashboard | P02 |
| New unresolved ERROR | 🟡 Warning | Email digest | P04 |
| Error regression detected | 🟠 High | Email + Dashboard | P04 |
| License expiring (30/14/7 days) | 🟠 High | Email + Dashboard | P07 |
| License validation failure | 🔴 Critical | Email + WhatsApp + Dashboard | P07 |
| Backup not run in 24h | 🟡 Warning | Email | P10 |
| Backup not run in 48h | 🟠 High | Email + Dashboard | P10 |
| Payment overdue > 7 days | 🟠 High | Email + Dashboard | P08 |

---

## 4. DocTypes

### 4.1 Pulse Alert

| Field | Type | Notes |
|---|---|---|
| `server` | Link → Pulse Server | Source server (if server-specific) |
| `client` | Link → Pulse Client | Source client |
| `alert_type` | Select | `Server Down`, `Degraded`, `Threshold`, `Error`, `License`, `Backup`, `Payment` |
| `severity` | Select | `Critical` / `High` / `Warning` / `Info` |
| `title` | Data | Alert headline |
| `message` | Text | Alert body text |
| `channel_sent` | Small Text | JSON array: which channels were used |
| `sent_at` | Datetime | When alert was dispatched |
| `acknowledged` | Check | Gatom team acknowledged this alert |
| `acknowledged_by` | Link → User | Who acknowledged |
| `acknowledged_at` | Datetime | When acknowledged |
| `resolved` | Check | Whether the alert condition has been resolved |
| `resolved_at` | Datetime | When resolved |
| `resolved_by` | Link → User | Who resolved it |
| `suppressed` | Check | Was this a duplicate (suppressed by dedup rule) |
| `dispatch_log` | Table → Alert Dispatch Log | Per-channel delivery tracking |

### 4.2 Alert Dispatch Log (Child Table of Pulse Alert)

Tracks delivery result for each channel:

| Field | Type | Notes |
|---|---|---|
| `channel` | Select | `Email` / `WhatsApp` / `Dashboard` / `Digest` |
| `status` | Select | `Sent` / `Failed` / `Queued` |
| `sent_at` | Datetime | When dispatch was attempted |
| `error_message` | Small Text | Error details if failed |
| `recipient` | Data | Email address or phone number |

### 4.3 Alert Rule (Child Table of Pulse Client)

Per-client alert customization:

| Field | Type | Notes |
|---|---|---|
| `alert_type` | Select | Which alert type this rule applies to |
| `enabled` | Check | Whether this alert type is active for this client |
| `cc_client_email` | Check | Whether to CC the client's contact email |
| `custom_recipients` | Small Text | Additional email addresses (comma-separated) |

---

## 5. Alert Processing Pipeline

```python
def process_alert(server, alert_type, severity, title, message):
    # 1. Deduplication check
    recent = get_recent_alert(server, alert_type, within_minutes=15)
    if recent:
        mark_suppressed(recent)
        return

    # 2. Create alert record
    alert = create_pulse_alert(server, alert_type, severity, title, message)

    # 3. Route by severity
    channels = []
    if severity == "Critical":
        send_email(alert)
        send_whatsapp(alert)
        send_dashboard_notification(alert)
        channels = ["email", "whatsapp", "dashboard"]
    elif severity == "High":
        send_email(alert)
        send_dashboard_notification(alert)
        channels = ["email", "dashboard"]
    elif severity == "Warning":
        queue_for_digest(alert)
        channels = ["digest"]

    # 4. Apply per-client rules
    client_rules = get_alert_rules(server.client)
    if client_rules.get(alert_type, {}).get("cc_client_email"):
        send_email_to_client(alert, server.client.contact_email)

    alert.channel_sent = json.dumps(channels)
    alert.save()
```

---

## 6. Scheduler Jobs

| Frequency | Job | Purpose |
|---|---|---|
| Hourly | `send_alert_digest` | Bundle WARNING-level alerts into one hourly email |
| Weekly (Monday 9 AM) | `send_weekly_digest` | Summary: total alerts, top issues, server health overview |

---

## 7. Dashboard Views (React)

### 7.1 Notification Center

- Bell icon in dashboard header with unread count badge
- Dropdown: latest 20 alerts with severity icons
- Click → navigate to server detail or issue detail
- "Mark all as read" action

### 7.2 Alert History

- Full chronological alert log
- Filter by server, client, severity, type, time range
- Acknowledge toggle per alert
- Suppressed alerts shown in grey (for transparency)
