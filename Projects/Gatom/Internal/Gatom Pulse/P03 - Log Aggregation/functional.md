---
tags: [gatom, pulse, p03, logs, aggregation, viewer, functional]
---

# P03 — Log Aggregation & Viewer: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P03 — Log Aggregation & Viewer
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

This domain enables Gatom developers to read client server logs without SSH access. The `gatom_agent` parses Frappe log files, structures them, strips sensitive data, and pushes log batches to Pulse every 5 minutes. Pulse stores, indexes, and presents logs with filtering, search, and live streaming capabilities.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P03-001 | Agent must push new log entries every 5 minutes (incremental — only lines since last push) |
| P03-002 | Logs must be structured with: timestamp, level, source (module), message, traceback (if error) |
| P03-003 | Agent must strip sensitive data (passwords, API keys, tokens) before pushing |
| P03-004 | Pulse must store logs with configurable retention: 30 days for INFO, 90 days for ERROR/WARNING |
| P03-005 | Dashboard must support real-time log streaming (tail-like view via Socketio) |
| P03-006 | Dashboard must support filtering by server, level, time range, and keyword search |
| P03-007 | Error logs with tracebacks must be parseable and linked to Error Tracking (P04) |

---

## 3. Agent-Side Collection

### 3.1 Log Sources

| Source | File/Method | Content |
|---|---|---|
| Frappe error log | `{bench}/logs/frappe.log` | Application errors, warnings, info messages |
| Worker logs | `{bench}/logs/worker.*.log` | Background job execution logs |
| Scheduler log | `{bench}/logs/scheduler.log` | Scheduled job success/failure |
| Custom rental_core log | `frappe.logger("rental_core")` output | Structured business logic logs (from cross-cutting concerns) |

### 3.2 Sensitive Data Stripping

Before pushing, the agent applies regex filters to remove:

| Pattern | Replacement |
|---|---|
| `password[\"']?\s*[:=]\s*[\"']?[^\s,\"']+` | `password=***REDACTED***` |
| `api_key[\"']?\s*[:=]\s*[\"']?[^\s,\"']+` | `api_key=***REDACTED***` |
| `secret[\"']?\s*[:=]\s*[\"']?[^\s,\"']+` | `secret=***REDACTED***` |
| `token[\"']?\s*[:=]\s*[\"']?[^\s,\"']+` | `token=***REDACTED***` |
| `Bearer [A-Za-z0-9._-]+` | `Bearer ***REDACTED***` |

> ⚠️ **Canonical payload defined in**: [[../API Contract#2.3 Push Logs|API Contract §2.3]]
> Domain docs must reference the API Contract for payload shape. Payload is not duplicated here.

The agent pushes a JSON object with `server_id`, an `entries` array (max 500), `log_sources`, `total_entries_in_window`, and `truncated` flag. See API Contract §2.3 for the full field specification.
```

---

## 4. DocTypes

### 4.1 Pulse Log Entry

| Field | Type | Notes |
|---|---|---|
| `server` | Link → Pulse Server | Source server |
| `timestamp` | Datetime | Original log timestamp |
| `level` | Select | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `source` | Data | Module path (e.g., `rental_core.billing`) |
| `message` | Small Text | Log message (truncated to 2000 chars) |
| `traceback` | Long Text | Full traceback for errors (if applicable) |
| `fingerprint` | Data | SHA-256 hash of error signature (for deduplication with P04) |

**Indexing**: Compound index on (`server`, `timestamp`) for efficient time-range queries. Index on `fingerprint` for P04 linking.

**Retention**: Scheduler job purges entries older than retention threshold (30 days INFO, 90 days ERROR).

---

## 5. API Endpoints

### 5.1 Receive Logs (`allow_guest=True`)

```
POST /api/method/gatom_pulse.api.agent.logs
Authorization: Bearer {api_key}
Body: { log batch payload above }
```

**Logic**:
1. Authenticate API key
2. Deduplicate via `X-Request-ID` header (see [[../API Contract#1.2 Authentication|API Contract §1.2]])
3. Bulk insert log entries
4. For ERROR/CRITICAL entries: check fingerprint against P04 error issues
5. Emit Socketio event for real-time dashboard updates
6. Return `{"status": "ok", "entries_received": N}`

---

## 6. Dashboard Views (React)

### 6.1 Log Stream View

- Per-server log viewer with auto-scroll (tail mode)
- Color-coded by level: grey (DEBUG), white (INFO), yellow (WARNING), red (ERROR), bright red (CRITICAL)
- Monospace font, terminal-like appearance
- Click on ERROR entry → expand to show full traceback with syntax highlighting
- Pause/resume streaming toggle
- Time range selector (last 1h, 6h, 24h, 7d, 30d)
- Keyword search with highlight

### 6.2 Cross-Fleet Error View

- Aggregated view: "Same error across multiple servers"
- Grouped by fingerprint → shows affected servers count
- Links to P04 error issues

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A03 — Log Collection & Sanitization (Agent side)]]
- [[../P04 - Error Tracking/functional|P04 — Error Tracking]]

> **Component**: `gatom_agent`
