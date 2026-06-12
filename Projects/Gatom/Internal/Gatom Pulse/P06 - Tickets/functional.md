---
tags: [gatom, pulse, p06, tickets, incidents, support, functional]
---

# P06 — Ticket System: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P06 — Ticket System
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers, operations staff

---

## 1. Purpose & Scope

This domain tracks all incidents, support requests, and change requests per client. It reuses ERPNext's built-in **HD Ticket** DocType (Help Desk) and extends it with custom fields for Pulse-specific context (server link, auto-creation flag, SLA tracking).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P06-001 | Incident tickets must be auto-created when a server transitions to `Down` (P02) |
| P06-002 | Incident tickets must auto-resolve when the server recovers |
| P06-003 | Support and Change Request tickets are created manually by Gatom team |
| P06-004 | Each ticket must link to a specific client and optionally a specific server |
| P06-005 | Ticket timeline must auto-log: status changes, linked alerts, linked errors, comments |
| P06-006 | SLA metrics must be tracked: time-to-first-response, time-to-resolution |
| P06-007 | Weekly summary: tickets opened/closed per client, avg resolution time |

---

## 3. Ticket Types

| Type | Created By | Typical Trigger |
|---|---|---|
| `Incident` | Auto (P02/P05) | Server down, critical threshold breach |
| `Support Request` | Gatom team (manual) | Client reports an issue |
| `Change Request` | Gatom team (manual) | Deployment, configuration change, update |
| `License Issue` | Auto (P07) | License validation failure, expiry |

---

## 4. Custom Fields on HD Ticket

ERPNext's `HD Ticket` already provides: `subject`, `description`, `status`, `priority`, `raised_by`, `resolution_details`, `opening_date`, `resolution_date`.

Pulse adds these custom fields:

| Field | Type | Section | Notes |
|---|---|---|---|
| `custom_pulse_client` | Link → Pulse Client | Pulse Context | Required for Pulse tickets |
| `custom_pulse_server` | Link → Pulse Server | Pulse Context | Optional (some tickets are client-level) |
| `custom_ticket_type` | Select | Pulse Context | `Incident` / `Support Request` / `Change Request` / `License Issue` |
| `custom_auto_created` | Check | Pulse Context | Whether created by monitoring (not manually) |
| `custom_related_issue` | Link → Pulse Issue | Pulse Context | Link to P04 error issue (if applicable) |
| `custom_related_alert` | Link → Pulse Alert | Pulse Context | Link to P05 alert that triggered this ticket |
| `custom_sla_first_response_minutes` | Int | SLA | Minutes from creation to first comment/status change |
| `custom_sla_resolution_minutes` | Int | SLA | Minutes from creation to resolution |
| `custom_downtime_minutes` | Int | SLA | Total server downtime (Incident type only) |
| `custom_auto_resolved` | Check | Pulse Context | Whether resolved by auto-recovery |

---

## 5. Auto-Creation Logic

### 5.1 Server Down → Incident

```python
def create_downtime_incident(server):
    ticket = frappe.get_doc({
        "doctype": "HD Ticket",
        "subject": f"🔴 Server DOWN: {server.server_name}",
        "description": f"Server {server.site_url} has not sent a heartbeat for > 5 minutes.",
        "priority": "Urgent",
        "custom_pulse_client": server.client,
        "custom_pulse_server": server.name,
        "custom_ticket_type": "Incident",
        "custom_auto_created": 1,
    })
    ticket.insert(ignore_permissions=True)
    # Store ticket reference on server for auto-resolution
    server.db_set("active_incident_ticket", ticket.name)
```

### 5.2 Server Recovery → Auto-Resolve

```python
def auto_resolve_incident(server):
    ticket_name = server.active_incident_ticket
    if not ticket_name:
        return
    ticket = frappe.get_doc("HD Ticket", ticket_name)
    downtime = (now() - ticket.creation).total_seconds() / 60
    ticket.status = "Resolved"
    ticket.resolution_details = f"Server auto-recovered. Total downtime: {downtime:.0f} minutes."
    ticket.custom_auto_resolved = 1
    ticket.custom_downtime_minutes = int(downtime)
    ticket.custom_sla_resolution_minutes = int(downtime)
    ticket.save(ignore_permissions=True)
    server.db_set("active_incident_ticket", None)
```

---

## 6. Dashboard Views (React)

### 6.1 Ticket Board

- Kanban-style view with columns: `Open` | `In Progress` | `Resolved` | `Closed`
- Card shows: subject, client, server, type badge, priority badge, age
- Drag-and-drop between columns
- Filter by: client, type, priority, auto-created

### 6.2 Client Ticket History

- Chronological list of all tickets for a client
- SLA summary: avg first-response time, avg resolution time
- Type breakdown: pie chart of Incident / Support / Change / License

### 6.3 Weekly Report Widget

- Tickets opened this week vs last week
- Avg resolution time this week
- Top clients by ticket count
