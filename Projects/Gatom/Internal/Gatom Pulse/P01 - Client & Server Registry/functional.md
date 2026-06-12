---
tags: [gatom, pulse, p01, client-registry, server-registry, functional]
---

# P01 — Client & Server Registry: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P01 — Client & Server Registry
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers, operations staff

---

## 1. Purpose & Scope

This domain is the **source of truth** for every managed client and every deployed server. Before monitoring, licensing, or billing can begin, a client must be registered in Pulse and their server must be enrolled. The registry tracks the relationship between business entities (clients) and technical entities (servers), including the API keys that authenticate agent-to-Pulse communication.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P01-001 | Each client organization must have a unique record with contact details, country, and subscription tier |
| P01-002 | Each client may have one or more servers (e.g., production + staging) |
| P01-003 | Each server must have a unique API key generated at registration time |
| P01-004 | API keys must be displayed exactly once (on creation) and stored as SHA-256 hashes (not plaintext) |
| P01-005 | Server status must reflect the latest heartbeat state: `Pending`, `Online`, `Degraded`, `Down`, `Decommissioned` |
| P01-006 | A server's `last_seen_at` timestamp must update on every heartbeat received |
| P01-007 | Decommissioned servers must be soft-deleted (data retained for audit, excluded from active monitoring) |
| P01-008 | Gatom admin must be able to regenerate an API key for a server (invalidates the old key immediately) |

---

## 3. DocTypes

### 3.1 Pulse Client

> A business entity — the organization that purchased a Gatom product.

| Field | Type | Required | Notes |
|---|---|---|---|
| `client_name` | Data | ✅ | Organization name |
| `client_id` | Data (auto) | ✅ | Auto-generated slug from `client_name` (e.g., `al-andalus-park`) |
| `contact_name` | Data | ✅ | Primary contact person |
| `contact_email` | Data | ✅ | Primary email for communications |
| `contact_phone` | Data | | Phone number |
| `country` | Link → Country | ✅ | Client's country (affects currency, timezone) |
| `tier` | Select | ✅ | `Starter` / `Professional` / `Enterprise` |
| `status` | Select | ✅ | `Active` / `Churned` / `Suspended` |
| `onboarded_at` | Date | ✅ | Date client was first set up |
| `contract_start_date` | Date | | When the contract began |
| `contract_end_date` | Date | | When the contract expires (for renewal tracking) |
| `contract_auto_renew` | Check | | Whether contract auto-renews |
| `linked_customer` | Link → Customer | | Auto-created ERPNext Customer for billing (P08) |
| `notes` | Text Editor | | Internal notes (not visible to client) |

**Acceptance Criteria**:
- [ ] `client_id` auto-generated as lowercase slug from `client_name`
- [ ] `client_id` is unique and immutable after creation
- [ ] Status defaults to `Active` on creation
- [ ] Changing status to `Churned` triggers license revocation check (P07)
- [ ] On `before_insert`: auto-create ERPNext `Customer` with `customer_group = "Pulse Clients"` and set `linked_customer`
- [ ] Auto-created Customer gets `custom_pulse_client` custom field linking back to this Pulse Client
- [ ] If `linked_customer` is manually cleared, do NOT delete the ERPNext Customer (data safety)

---

### 3.2 Pulse Server

> A technical entity — a specific Frappe site deployed for a client.

| Field | Type | Required | Notes |
|---|---|---|---|
| `server_name` | Data | ✅ | Human-readable label (e.g., "Al-Andalus Production") |
| `client` | Link → Pulse Client | ✅ | Owning client |
| `site_url` | Data | ✅ | Full URL (e.g., `https://rental.alandalus.com`) |
| `environment` | Select | ✅ | `Production` / `Staging` / `Development` |
| `frappe_version` | Data | | Reported by agent on registration |
| `python_version` | Data | | Python runtime version (reported by agent) |
| `os_version` | Data | | Operating system version (reported by agent) |
| `timezone` | Data | | IANA timezone of client server (reported by agent) |
| `installed_apps` | Small Text | | JSON array of installed apps (reported by agent) |
| `agent_version` | Data | | `gatom_agent` version (reported by agent) |
| `api_key_hash` | Data | ✅ | SHA-256 hash of the API key (never stored in plaintext) |
| `api_key_hash_previous` | Data | | SHA-256 hash of the previous API key (for rotation grace period) |
| `api_key_rotation_at` | Datetime | | Timestamp of last API key rotation |
| `status` | Select | ✅ | `Pending` → `Online` → `Degraded` / `Down` / `Down (Auth Failure)` / `Decommissioned` |
| `last_seen_at` | Datetime | | Updated on every heartbeat |
| `registered_at` | Datetime | | Set when agent first calls `/register` |
| `decommissioned_at` | Datetime | | Set when status → `Decommissioned` |
| `active_incident_ticket` | Link → HD Ticket | | Currently open incident ticket for this server (set by P06, cleared on auto-resolution) |

**Acceptance Criteria**:
- [ ] `site_url` is unique across all servers
- [ ] `api_key_hash` stores SHA-256 hash, not plaintext
- [ ] Status defaults to `Pending` (before agent registers)
- [ ] Status transitions to `Online` after first successful heartbeat
- [ ] `Decommissioned` status is terminal — cannot transition back
- [ ] `installed_apps` parsed as JSON for display in dashboard
- [ ] `active_incident_ticket` set when P06 auto-creates an incident, cleared on resolution
- [ ] During API key rotation, old hash moved to `api_key_hash_previous` (see P00 §5 for dual-key grace)

---

## 4. API Endpoints

### 4.1 Agent Registration (`allow_guest=True`)

> Called by `gatom_agent` on first install.
> ⚠️ **Canonical payload**: [[../API Contract#2.1 Register Server|API Contract §2.1]]

```
POST /api/method/gatom_pulse.api.agent.register
Authorization: Bearer {api_key}
Body: { see API Contract §2.1 }
```

**Logic**:
1. Hash the Bearer token with SHA-256
2. Find `Pulse Server` where `api_key_hash` matches (or `api_key_hash_previous` during rotation grace)
3. If not found → return 401
4. Update: `frappe_version`, `python_version`, `os_version`, `installed_apps`, `agent_version`, `timezone`, `status = Online`
5. Set `registered_at = now()` only on first registration
6. Write to Pulse Audit Log: `SERVER_REGISTERED`
7. Return `{"status": "registered", "server_id": "...", "server_name": "..."}`

**Acceptance Criteria**:
- [ ] Invalid API key → 401 Unauthorized
- [ ] Valid API key → server status updated to `Online`
- [ ] `registered_at` set only on first registration (not overwritten on re-registration)
- [ ] Re-registration (same key) updates version fields without error
- [ ] Registration logged in Pulse Audit Log

---

### 4.2 Generate API Key (Internal, Desk Action)

> Called by Gatom admin from the `Pulse Server` form.

**Logic**:
1. Generate UUID v4
2. Move current `api_key_hash` → `api_key_hash_previous`
3. Set `api_key_rotation_at` = `now()`
4. Hash new UUID with SHA-256 → store in `api_key_hash`
5. Display raw UUID to admin **once** (modal dialog with copy-to-clipboard)
6. Both old and new keys are valid for `Pulse Configuration.api_key_rotation_grace_hours` (default: 1 hour)

**Acceptance Criteria**:
- [ ] API key displayed exactly once in a copy-to-clipboard modal
- [ ] Old API key remains valid during grace period (not immediately invalidated)
- [ ] After grace period expires, only the new key is accepted
- [ ] API key is UUID v4 format (36 characters with hyphens)
- [ ] Key generation logged in Pulse Audit Log: `API_KEY_GENERATED` with details: `{"generated_by": "...", "grace_period_hours": 24, "old_key_expires_at": "..."}`
- [ ] Key rotation completion logged in Pulse Audit Log: `API_KEY_ROTATED`
- [ ] Grace expiry logged in Pulse Audit Log: `API_KEY_GRACE_EXPIRED`
- [ ] `api_key_hash_previous` cleared by a scheduler job after grace period expires
- [ ] New key piggybacked to agent via heartbeat response `commands.rotate_key` (see [[../API Contract#7.7 Automated Re-Keying via Heartbeat|API Contract §7.7]])

---

## 5. Dashboard Views (React)

### 5.1 Fleet Overview

A grid of server cards showing:
- Server name + client name
- Environment badge (`Production` / `Staging`)
- Status indicator (green dot / yellow dot / red dot / grey dot)
- Last seen time (relative: "2 minutes ago")
- Frappe version
- Installed apps as pill badges

### 5.2 Client Detail

When clicking a client:
- Client info card (name, contact, tier, status)
- List of servers for this client
- Quick links: Licenses (P07), Subscription (P08), Tickets (P06)

---

## 6. ERPNext Customer Sync (P01 → P08)

When a `Pulse Client` is created, an ERPNext `Customer` is auto-created via a `before_insert` hook:

```python
def before_insert(self):
    if not self.linked_customer:
        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": self.client_name,
            "customer_group": "Pulse Clients",
            "territory": self.country or "All Territories",
            "customer_type": "Company",
            "custom_pulse_client": self.name
        }).insert(ignore_permissions=True)
        self.linked_customer = customer.name
```

> [!NOTE]
> The `custom_pulse_client` field on `Customer` is a custom field created during `gatom_pulse` installation via `custom_fields` in `hooks.py`.

---

## 7. Integration Points

| System | Direction | Purpose |
|---|---|---|
| P00 (Configuration) | Reads from | Global thresholds, rate limits, timezone |
| P02 (Monitoring) | Reads from | Uses `Pulse Server.status` and `last_seen_at` |
| P06 (Tickets) | Reads/Writes | Sets `active_incident_ticket` on server |
| P07 (Licensing) | Reads from | License links to `Pulse Server` and `Pulse Client` |
| P08 (Billing) | Reads from | Subscription links to `Pulse Client` via `linked_customer` → ERPNext Customer |
| ERPNext Customer | Auto-sync | `Pulse Client` auto-creates and links to `Customer` DocType |

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A01 — Server Registration (Agent side)]]

