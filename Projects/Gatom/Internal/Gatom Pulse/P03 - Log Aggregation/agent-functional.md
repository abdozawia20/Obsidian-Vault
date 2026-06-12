---
tags: [gatom, pulse, agent, a03, logs, sanitization, functional]
---

# A03 — Log Collection & Sanitization: Functional Analysis

> **Component**: `gatom_agent`
> **Domain**: A03 — Log Collection & Sanitization
> **Pulse Counterpart**: [[functional|P03 — Log Aggregation]]
> **Files**: `collectors/log_collector.py`, `utils/sanitizer.py`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

This domain collects Frappe log entries from the client server, strips sensitive data (passwords, API keys, tokens), and pushes structured log batches to Pulse every 5 minutes. This gives Gatom developers the ability to read client logs without SSH access.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| A03-001 | Agent must parse Frappe log files and push new entries every 5 minutes |
| A03-002 | All log content must be sanitized — passwords, API keys, tokens, and secrets stripped |
| A03-003 | Each log entry must include: timestamp, level, source module, message, optional traceback |
| A03-004 | Entries with tracebacks must include a fingerprint (computed by A04) |
| A03-005 | Maximum 500 entries per push batch (overflow truncated with notification) |
| A03-006 | Maximum 2,000 chars per message, 10,000 chars per traceback |
| A03-007 | Agent must track its read position across pushes (no duplicate entries) |

---

## 3. Log Sources

| Source File | Content |
|---|---|
| `logs/frappe.log` | Application-level logs (INFO, WARNING, ERROR) |
| `logs/web.log` | Gunicorn/web request logs |
| `logs/worker.log` | Background job logs |
| `logs/scheduler.log` | Scheduler execution logs |

The agent reads from **`frappe.log`** as the primary source — it captures all application events. `worker.log` and `scheduler.log` are secondary sources read when available.

---

## 4. Log Parsing

### 4.1 Frappe Log Format

```
2026-06-12 07:00:15,123 ERROR frappe.utils.scheduler Traceback (most recent call last):
  File "/home/frappe/bench/apps/rental_core/rental_core/billing/payment_routing.py", line 42, in process_payment
    gateway.charge(amount)
PaymentGatewayError: Insufficient funds
```

### 4.2 Parsed Structure

```json
{
    "timestamp": "2026-06-12T07:00:15.123Z",
    "level": "ERROR",
    "source": "frappe.utils.scheduler",
    "message": "PaymentGatewayError: Insufficient funds",
    "traceback": "Traceback (most recent call last):\n  File \".../payment_routing.py\", line 42...",
    "fingerprint": "a3f8b2c1d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1"
}
```

### 4.3 Read Position Tracking

```python
# Redis key tracks the file offset for each log source
pulse:log_offset:frappe.log → 284716    # byte offset
pulse:log_offset:worker.log → 19200
```

On each push cycle:
1. Read current file offset from Redis
2. Seek to that offset in the log file
3. Parse all new lines
4. Update the offset in Redis after successful push

If log file is rotated (offset > file size), reset offset to 0.

---

## 5. Sensitive Data Sanitization

### 5.1 Regex Patterns (`utils/sanitizer.py`)

Applied to **every log message and traceback** before pushing:

| Pattern | Replacement |
|---|---|
| `password['\"]?\\s*[:=]\\s*['\"]?[^\\s,\"']+` | `password=***REDACTED***` |
| `api_key['\"]?\\s*[:=]\\s*['\"]?[^\\s,\"']+` | `api_key=***REDACTED***` |
| `secret['\"]?\\s*[:=]\\s*['\"]?[^\\s,\"']+` | `secret=***REDACTED***` |
| `token['\"]?\\s*[:=]\\s*['\"]?[^\\s,\"']+` | `token=***REDACTED***` |
| `Bearer [A-Za-z0-9._\\-]+` | `Bearer ***REDACTED***` |
| `pulse_api_key['\"]?\\s*[:=]\\s*['\"]?[^\\s,\"']+` | `pulse_api_key=***REDACTED***` |
| `custom_access_code['\"]?\\s*[:=]\\s*['\"]?[^\\s,\"']+` | `custom_access_code=***REDACTED***` |

> [!IMPORTANT]
> `custom_access_code` is explicitly included — this rental platform field must **never** appear in logs pushed to Pulse.

### 5.2 Sanitization Order

1. Sanitize the raw message text
2. Sanitize the traceback text
3. Truncate message to 2,000 chars
4. Truncate traceback to 10,000 chars
5. Compute fingerprint (A04) if traceback present

---

## 6. Volume Throttling

### 6.1 Per-Push Limits

| Limit | Value | Rationale |
|---|---|---|
| Max entries per push | 500 | Prevents payload bloat from error storms |
| Max message length | 2,000 chars | Prevents oversized log messages |
| Max traceback length | 10,000 chars | Full stack traces can be very long |

### 6.2 Overflow Handling

When a 5-minute window produces > 500 log entries:

```python
if len(entries) > MAX_ENTRIES_PER_PUSH:
    overflow_count = len(entries) - MAX_ENTRIES_PER_PUSH
    entries = entries[:MAX_ENTRIES_PER_PUSH]
    entries.append({
        "timestamp": now_utc(),
        "level": "WARNING",
        "source": "gatom_agent.log_collector",
        "message": f"Log volume throttled: {overflow_count} additional entries truncated",
        "fingerprint": None
    })
```

---

## 7. Push Payload

```json
{
    "server_id": "PULSE-SRV-00001",
    "entries": [
        {
            "timestamp": "2026-06-12T07:00:15.123Z",
            "level": "ERROR",
            "source": "frappe.utils.scheduler",
            "message": "PaymentGatewayError: Insufficient funds",
            "traceback": "Traceback (most recent call last):\n  ...",
            "fingerprint": "a3f8b2c1..."
        },
        {
            "timestamp": "2026-06-12T07:01:30.456Z",
            "level": "INFO",
            "source": "rental_core.billing",
            "message": "Invoice SI-00042 created for Agreement RA-00015",
            "traceback": null,
            "fingerprint": null
        }
    ],
    "log_sources": ["frappe.log", "worker.log"],
    "total_entries_in_window": 127,
    "truncated": false
}
```

---

## 8. Acceptance Criteria

- [ ] Log push fires every 5 minutes via Frappe scheduler
- [ ] New log entries parsed correctly from `frappe.log`
- [ ] Read position tracked in Redis — no duplicate entries across pushes
- [ ] Log rotation detected (file size < offset) → offset reset to 0
- [ ] All 7 sanitization patterns applied to messages and tracebacks
- [ ] Entries with tracebacks include a SHA-256 fingerprint (computed by A04)
- [ ] Batch capped at 500 entries — overflow logged with count
- [ ] Messages truncated to 2,000 chars, tracebacks to 10,000 chars
- [ ] Pulse unreachable → log batch queued locally (A08)

---

## 🔗 Related

- [[../Agent Overview|🤖 Agent Overview]]
- [[../P04 - Error Tracking/agent-functional|A04 — Error Fingerprinting]]
- [[functional|P03 — Log Aggregation (Pulse side)]]
- [[../P04 - Error Tracking/functional|P04 — Error Tracking (Pulse side)]]
- [[../P00 - Configuration/agent-functional|A08 — Transport & Resilience]]
