---
tags: [gatom, pulse, p09, usage-analytics, metrics, functional]
---

# P09 — Usage Analytics: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P09 — Usage Analytics
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers, operations staff

---

## 1. Purpose & Scope

This domain provides visibility into how clients actually use the rental platform. It answers: "Are clients approaching their asset limits?", "Which features are adopted?", "Is engagement growing or declining?". Data is collected weekly by the agent (low priority, not real-time) and aggregated in Pulse for trending and tier compliance.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P09-001 | Agent must collect usage metrics daily at 2 AM and push to Pulse. Pulse groups pushes into weekly snapshots by upsert (one record per server per ISO week). |
| P09-002 | Metrics must include: asset count, agreement count, user count, portal visits, API calls, storage used |
| P09-003 | Pulse must detect clients approaching tier asset limits (> 80% of `max_assets`) |
| P09-004 | Pulse must calculate engagement scores: growing / stable / declining |
| P09-005 | Fleet-wide aggregates must be available: total assets, total agreements, total users |
| P09-006 | Feature adoption tracking: which modules and features are used per client |
| P09-007 | Historical trends must be stored for at least 12 months |

---

## 3. Agent Collection Payload

> ⚠️ **Canonical payload defined in**: [[../API Contract#2.4 Push Usage Stats|API Contract §2.4]]
> Domain docs must use the field names from the API Contract. Do not redefine payload fields here.

The agent collects the following metrics daily:

| Metric | Collection Method |
|---|---|
| `active_assets` | `frappe.db.count("Rental Asset", {"status": ["!=", "Retired"]})` |
| `active_agreements` | `frappe.db.count("Rental Agreement", {"status": "Active"})` |
| `total_users` | `frappe.db.count("User", {"enabled": 1})` |
| `active_users_7d` | Users with login in last 7 days |
| `portal_visits_7d` | `frappe.db.count("Access Log", {"creation": [">", 7_days_ago]})` |
| `api_calls_7d` | Count of `Access Log` entries with API paths |
| `storage_used_mb` | Sum of `File.file_size` for app-related files |
| `kyc_submissions_7d` | `frappe.db.count("KYC Submission", {"creation": [">", 7_days_ago]})` |

---

## 4. DocTypes

### 4.1 Usage Snapshot

One record per server per week:

| Field | Type | Notes |
|---|---|---|
| `server` | Link → Pulse Server | |
| `client` | Link → Pulse Client | Denormalized for easy querying |
| `collected_at` | Datetime | When agent collected this data |
| `active_assets` | Int | |
| `total_assets` | Int | |
| `active_agreements` | Int | |
| `total_agreements` | Int | |
| `total_users` | Int | |
| `active_users_7d` | Int | |
| `portal_visits_7d` | Int | |
| `api_calls_7d` | Int | |
| `storage_used_mb` | Int | |
| `kyc_submissions_7d` | Int | |
| `invoices_generated_7d` | Int | |
| `payments_received_7d` | Int | |
| `installed_modules` | Small Text | JSON array |
| `engagement_score` | Select | `Growing` / `Stable` / `Declining` (computed by Pulse) |
| `week_start` | Date | Monday of the snapshot week (upsert key) |
| `last_updated_at` | Datetime | When this snapshot was last updated by a daily push |
| `daily_push_count` | Int | How many daily pushes have updated this snapshot (1–7) |

> [!NOTE]
> Agent pushes daily. Pulse finds the existing snapshot for the same ISO week (by `server` + `week_start`) and upserts it. If no snapshot exists for the current week, a new one is created. The `daily_push_count` field tracks how many days of data contributed to this snapshot.

---

## 5. Engagement Score Calculation

Computed by comparing last 4 weeks of snapshots:

```python
def compute_engagement(snapshots_4w):
    """Compare active_users_7d + portal_visits_7d trend over 4 weeks."""
    if len(snapshots_4w) < 4:
        return "Stable"  # Not enough data
    
    recent = (snapshots_4w[0].active_users_7d + snapshots_4w[0].portal_visits_7d)
    oldest = (snapshots_4w[3].active_users_7d + snapshots_4w[3].portal_visits_7d)
    
    change_pct = ((recent - oldest) / max(oldest, 1)) * 100
    
    if change_pct > 10:
        return "Growing"
    elif change_pct < -10:
        return "Declining"
    return "Stable"
```

---

## 6. Tier Compliance Check

```python
def check_tier_compliance(snapshot, license):
    asset_pct = (snapshot.active_assets / license.max_assets) * 100
    
    if asset_pct > 100:
        create_alert(server, "Asset Limit", "High",
            f"Client exceeds asset limit: {snapshot.active_assets}/{license.max_assets}")
    elif asset_pct > 80:
        create_alert(server, "Asset Limit", "Warning",
            f"Client approaching asset limit: {snapshot.active_assets}/{license.max_assets} ({asset_pct:.0f}%)")
```

---

## 7. API Endpoint

### 7.1 Receive Usage Stats (`allow_guest=True`)

```
POST /api/method/gatom_pulse.api.agent.usage
Authorization: Bearer {api_key}
Body: { usage payload above }
```

**Logic**:
1. Authenticate API key
2. Create `Usage Snapshot` record
3. Compute engagement score (compare to previous 4 snapshots)
4. Check tier compliance against linked license
5. Return `{"status": "ok"}`

---

## 8. Dashboard Views (React)

### 8.1 Fleet Analytics

- **Total assets under management**: number card, all clients combined
- **Total active agreements**: number card
- **Total users**: number card
- **Fleet growth chart**: line chart of total assets over 12 months
- **Engagement breakdown**: pie chart (Growing / Stable / Declining clients)

### 8.2 Client Usage Detail

- Usage timeline: weekly charts of assets, agreements, users, portal visits
- Tier compliance gauge: assets used vs. max_assets (with danger zone)
- Feature adoption: which modules are installed + which features are used
- Engagement trend badge
- Week-over-week comparisons

### 8.3 Tier Compliance Table

- All clients sorted by asset usage % (most full first)
- Color-coded: green (< 80%), yellow (80-100%), red (> 100%)
- Quick action: "Suggest Upgrade" → draft email to client

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A06 — Usage Collection (Agent side)]]
