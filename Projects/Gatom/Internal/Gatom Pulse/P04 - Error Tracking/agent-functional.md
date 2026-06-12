---
tags: [gatom, pulse, agent, a04, error-fingerprinting, functional]
---

# A04 — Error Fingerprinting: Functional Analysis

> **Component**: `gatom_agent`
> **Domain**: A04 — Error Fingerprinting
> **Pulse Counterpart**: [[functional|P04 — Error Tracking]]
> **File**: `collectors/error_fingerprint.py`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

When the agent collects log entries containing Python tracebacks (ERROR/CRITICAL level), it computes a **fingerprint** — a SHA-256 hash that uniquely identifies the error by its type and location. Pulse uses this fingerprint to deduplicate errors across time and across servers, grouping them into `Pulse Issue` records.

The fingerprint is computed **agent-side** (not by Pulse) to:
- Reduce Pulse's processing load
- Ensure consistent fingerprinting across all servers
- Include the fingerprint in the log push payload

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| A04-001 | Fingerprints must be computed for all log entries with `level = ERROR` or `CRITICAL` that contain a traceback |
| A04-002 | Fingerprint must be deterministic — same error at same location → same hash |
| A04-003 | Fingerprint must ignore the error message content (only type + location matter) |
| A04-004 | File paths must be normalized (remove bench-specific prefixes) |
| A04-005 | Fingerprint algorithm must be SHA-256 |

---

## 3. Fingerprint Algorithm

### 3.1 Signature Components

A fingerprint is a SHA-256 hash of three components:

```
{exception_type}:{normalized_file_path}:{line_number}
```

| Component | Source | Example |
|---|---|---|
| `exception_type` | Last line of traceback, before `:` | `PaymentGatewayError` |
| `normalized_file_path` | Last `File "..."` reference in traceback, with bench prefix removed | `rental_core/billing/payment_routing.py` |
| `line_number` | Line number from the same `File` reference | `42` |

### 3.2 Example

Given this traceback:
```
Traceback (most recent call last):
  File "/home/frappe/bench/apps/rental_core/rental_core/billing/payment_routing.py", line 42, in process_payment
    gateway.charge(amount)
PaymentGatewayError: Insufficient funds
```

Extracted:
- `exception_type` = `PaymentGatewayError`
- `normalized_file_path` = `rental_core/billing/payment_routing.py`
- `line_number` = `42`

Signature string: `PaymentGatewayError:rental_core/billing/payment_routing.py:42`
Fingerprint: `SHA-256("PaymentGatewayError:rental_core/billing/payment_routing.py:42")`

---

## 4. Implementation

```python
import hashlib
import re


def compute_fingerprint(traceback_text: str) -> str | None:
    """Extract error signature from traceback and compute SHA-256 hash.
    
    Returns None if traceback cannot be parsed (non-standard format).
    """
    if not traceback_text:
        return None
    
    lines = traceback_text.strip().split("\n")
    if not lines:
        return None
    
    # 1. Extract exception type from last line
    exception_line = lines[-1].strip()
    exception_type = exception_line.split(":")[0].strip()
    
    if not exception_type:
        return None
    
    # 2. Find the last "File" reference (the actual error location)
    file_path = ""
    line_number = ""
    for line in reversed(lines):
        match = re.match(r'\s*File "(.+?)", line (\d+)', line)
        if match:
            file_path = match.group(1)
            line_number = match.group(2)
            break
    
    if not file_path:
        # No file reference found — use exception type only
        signature = exception_type
    else:
        # 3. Normalize file path (remove bench-specific prefix)
        file_path = re.sub(r'.*/apps/', '', file_path)
        signature = f"{exception_type}:{file_path}:{line_number}"
    
    return hashlib.sha256(signature.encode("utf-8")).hexdigest()
```

---

## 5. Edge Cases

| Scenario | Behavior |
|---|---|
| No traceback in log entry | Skip fingerprinting — return `None` |
| Traceback with no `File "..."` line | Hash exception type only (e.g., `SHA-256("TimeoutError")`) |
| Multi-exception traceback (chained) | Use the **last** exception (the one Python actually raised) |
| Non-Python traceback (e.g., MariaDB error) | No `File` reference → hash the first line of the error message |
| Empty traceback string | Return `None` |

---

## 6. Integration with A03

The fingerprint is computed inside the log collection pipeline:

```python
# In A03 - log_collector.py
for entry in parsed_entries:
    if entry["level"] in ("ERROR", "CRITICAL") and entry.get("traceback"):
        entry["fingerprint"] = compute_fingerprint(entry["traceback"])
    else:
        entry["fingerprint"] = None
```

---

## 7. Acceptance Criteria

- [ ] Same error at same file:line always produces the same fingerprint
- [ ] Different errors at different locations produce different fingerprints
- [ ] File paths are normalized (no `/home/frappe/bench/apps/` prefix)
- [ ] Traceback without `File` reference → fingerprint based on exception type only
- [ ] Non-error log entries get `fingerprint = None`
- [ ] Empty or missing traceback → `None` (no crash)
- [ ] Fingerprint is 64-character hex string (SHA-256)

---

## 🔗 Related

- [[../Agent Overview|🤖 Agent Overview]]
- [[../P03 - Log Aggregation/agent-functional|A03 — Log Collection & Sanitization]]
- [[functional|P04 — Error Tracking (Pulse side)]]
