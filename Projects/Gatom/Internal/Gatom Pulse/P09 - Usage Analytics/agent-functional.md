---
tags: [gatom, pulse, agent, a06, usage, analytics, functional]
---

# A06 — Usage Collection: Functional Analysis

> **Component**: `gatom_agent`
> **Domain**: A06 — Usage Collection
> **Pulse Counterpart**: [[functional|P09 — Usage Analytics]]
> **File**: `collectors/usage_collector.py`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

The agent collects usage metrics **daily at 2 AM** (local time) and pushes them to Pulse. Pulse groups daily pushes into **weekly snapshots** by upserting: it finds the existing snapshot for the current ISO week and updates it, or creates a new one if it's the first push of the week.

> [!NOTE]
> Daily collection ensures data is always fresh (max 24h old). Pulse-side weekly grouping keeps the `Usage Snapshot` table compact (52 records/year/server). See [[../../API Contract#2.4 Push Usage Stats|API Contract §2.4]] for the upsert logic.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| A06-001 | Agent must collect usage metrics daily at 2 AM local time |
| A06-002 | Metrics must include: asset counts, agreement counts, user counts, portal visits, API calls, storage used |
| A06-003 | Agent must report which modules are installed |
| A06-004 | All counts must be computed from the client server's own database (not from Pulse) |
| A06-005 | Collection must complete within 30 seconds (database queries on large datasets) |

---

## 3. Metrics Collected

| Metric | Query | Notes |
|---|---|---|
| `active_assets` | `frappe.db.count("Rental Asset", {"status": ["!=", "Retired"]})` | Non-retired assets |
| `total_assets` | `frappe.db.count("Rental Asset")` | All assets ever created |
| `active_agreements` | `frappe.db.count("Rental Agreement", {"status": "Active"})` | Currently active |
| `total_agreements` | `frappe.db.count("Rental Agreement")` | All agreements |
| `total_users` | `frappe.db.count("User", {"enabled": 1})` | Enabled users |
| `active_users_7d` | Users with `last_active` or `last_login` in last 7 days | Active users |
| `portal_visits_7d` | `frappe.db.count("Access Log", {"creation": [">", 7_days_ago]})` | Web portal access |
| `api_calls_7d` | Count of `Access Log` entries with API path patterns | REST API usage |
| `storage_used_mb` | `sum(File.file_size)` for site files | Disk usage |
| `kyc_submissions_7d` | Count of KYC-related submissions in last 7 days | If KYC module exists |
| `invoices_generated_7d` | Count of Sales Invoices created in last 7 days | If billing is active |
| `payments_received_7d` | Count of Payment Entries in last 7 days | If billing is active |
| `installed_modules` | `frappe.get_installed_apps()` | JSON array |
| `frappe_version` | `frappe.__version__` | Current Frappe version |
| `agent_version` | `gatom_agent.__version__` | Current agent version |

---

## 4. Graceful Handling of Missing DocTypes

Not all client servers have the same modules installed. The agent must handle missing DocTypes gracefully:

```python
def safe_count(doctype: str, filters: dict = None) -> int:
    """Count records, returning 0 if DocType doesn't exist."""
    try:
        return frappe.db.count(doctype, filters or {})
    except Exception:
        return 0
```

This ensures the agent doesn't crash on servers that don't have `rental_flats` or `rental_vehicles` installed.

---

## 5. Push Payload

> ⚠️ **Canonical payload defined in**: [[../../API Contract#2.4 Push Usage Stats|API Contract §2.4]]
> All field names use the canonical names from the API Contract. Payload is not duplicated here.

---

## 6. Request

```
POST /api/method/gatom_pulse.api.agent.usage
Authorization: Bearer {pulse_api_key}
X-Agent-Version: 1.0.0
X-Request-Timestamp: 1749945600
X-Request-ID: {uuid4}
```

---

## 7. Acceptance Criteria

- [ ] Usage collection runs daily at 2 AM local time
- [ ] All 15 metrics collected correctly
- [ ] Missing DocTypes → `0` returned (no crash)
- [ ] Collection completes within 30 seconds
- [ ] Payload pushed to Pulse's usage endpoint
- [ ] Pulse unreachable → payload queued locally (A08)

---

## 🔗 Related

- [[../Agent Overview|🤖 Agent Overview]]
- [[functional|P09 — Usage Analytics (Pulse side)]]
- [[../P00 - Configuration/agent-functional|A08 — Transport & Resilience]]
