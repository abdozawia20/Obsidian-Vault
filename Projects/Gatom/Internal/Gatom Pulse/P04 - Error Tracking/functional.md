---
tags: [gatom, pulse, p04, error-tracking, deduplication, functional]
---

# P04 — Error Tracking & Deduplication: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P04 — Error Tracking & Deduplication
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

This domain groups recurring errors into trackable issues instead of drowning the team in noise. Inspired by Sentry's model, each unique error signature (exception type + file + line number) maps to a single `Pulse Issue`. Issues have a lifecycle (`Unresolved` → `Resolved` → regression detection) and can be linked to support tickets (P06).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P04-001 | Each unique error signature must create exactly one `Pulse Issue` (deduplication by fingerprint) |
| P04-002 | Error fingerprint = SHA-256 of: `{exception_type}:{file_path}:{line_number}` |
| P04-003 | Issues must track: first seen, last seen, occurrence count, affected servers |
| P04-004 | Issues must have lifecycle: `Unresolved` → `Resolved` → `Ignored` |
| P04-005 | A resolved issue that reappears must auto-reopen as a `Regression` |
| P04-006 | Weekly error digest email must summarize new, trending, and regressed issues |
| P04-007 | Issues must be linkable to HD Tickets (P06) for tracking resolution |

---

## 3. DocTypes

### 3.1 Pulse Issue

| Field | Type | Notes |
|---|---|---|
| `title` | Data | Auto-generated: `{ExceptionType} in {module}` |
| `fingerprint` | Data (unique) | SHA-256 error signature |
| `exception_type` | Data | e.g., `ValueError`, `ValidationError` |
| `source_file` | Data | e.g., `rental_core/billing/invoice_builder.py` |
| `source_line` | Int | Line number of the exception |
| `status` | Select | `Unresolved` / `Resolved` / `Ignored` / `Regression` |
| `first_seen` | Datetime | Timestamp of first occurrence |
| `last_seen` | Datetime | Timestamp of most recent occurrence |
| `occurrence_count` | Int | Total occurrences across all servers |
| `affected_servers` | Small Text | JSON array of server names |
| `sample_traceback` | Long Text | Most recent full traceback |
| `sample_message` | Small Text | Most recent error message |
| `linked_ticket` | Link → HD Ticket | Optional link to support ticket |
| `resolved_at` | Datetime | When marked as resolved |
| `resolved_by` | Link → User | Who resolved it |
| `assigned_to` | Link → User | Developer assigned to investigate |
| `assigned_at` | Datetime | When assignment was made |
| `auto_ticket_threshold` | Int | Auto-create ticket after this many occurrences (default: 50) |
| `notes` | Text Editor | Internal developer notes |

---

## 4. Error Processing Pipeline

When P03 receives log entries with `level = ERROR` or `CRITICAL`:

```
1. Extract fingerprint from log entry
2. Search Pulse Issue by fingerprint
3. IF not found:
   → Create new Pulse Issue (status = Unresolved)
   → Set first_seen = last_seen = now()
   → occurrence_count = 1
4. IF found AND status = Unresolved or Ignored:
   → Increment occurrence_count
   → Update last_seen
   → Add server to affected_servers (if new)
   → Update sample_traceback
5. IF found AND status = Resolved:
   → REGRESSION: reopen issue (status = Regression)
   → Create alert (P05): "Regression detected: {title}"
   → Auto-create HD Ticket (type = Support Request, subject = "🔄 Regression: {title}")
   → Reset occurrence_count to 1 (new regression cycle)
6. IF occurrence_count >= auto_ticket_threshold (default 50)
   AND linked_ticket IS NULL AND status != "Ignored":
   → Auto-create HD Ticket (type = Support Request, subject = "⚠️ High-frequency error: {title}")
   → Set linked_ticket = new ticket
```

> ⚠️ **Full auto-ticket rules**: [[../API Contract#7.1 P04 → P06 Auto-Ticket for High-Frequency Errors|API Contract §7.1]]

---

## 5. Dashboard Views (React)

### 5.1 Issues Inbox

- Sortable table: by occurrence count (trending), last seen (recent), first seen (new)
- Filter by status: Unresolved, Resolved, Ignored, Regression
- Filter by server
- Batch actions: resolve multiple, ignore multiple
- Status badge colors: red (Unresolved), orange (Regression), green (Resolved), grey (Ignored)

### 5.2 Issue Detail

- Title, exception type, source file:line
- Occurrence sparkline (occurrences per day, last 30 days)
- Affected servers list
- Full traceback viewer with syntax highlighting
- Timeline: first seen, status changes, linked ticket
- Action buttons: Resolve, Ignore, Link to Ticket, Add Notes

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A04 — Error Fingerprinting (Agent side)]]
- [[../P03 - Log Aggregation/functional|P03 — Log Aggregation]]

> **Component**: `gatom_agent`
> **File**: `collectors/error_fingerprint.py`
