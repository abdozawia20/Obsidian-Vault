# Domain F04 — Insurance: Implementation Plan

> **Variant**: Flats (child app `rental_flats`)
> **Domain**: Insurance Validation
> **Sequence**: 4 of 5
> **Depends on**: F01 (app scaffold, custom fields on Rental Configuration), Base D05 (Rental Agreement — validate hook)
> **Functional Refs**: [[frappe-functional|Frappe]] (Desk-only — no web/Flutter customer-facing surfaces)

---

## 1. Overview

In many countries, landlords are legally required to hold specific insurance policies on rental properties (e.g., earthquake insurance in Turkey, flood insurance in the Netherlands). The **Insurance** domain enforces these requirements by **blocking agreement submission** when mandatory coverage is missing, alerting property managers when policies are about to expire, and providing an internal dashboard for insurance status.

This is an **entirely internal (Desk-only) domain** — customers never see insurance status on any web page or mobile screen. The insurance check is a server-side validation hook, not a step in the customer booking flow.

---

## 2. Frappe — `Flat Insurance Policy` DocType

### 2.1 Schema Definition

> **Requires**: F01-2.1 (app scaffold), Base D04-2.1 (Rental Asset for Link field)

A **Flat Insurance Policy** represents a single insurance contract covering a specific flat for a specific type of risk (e.g., fire, earthquake, flood). Each policy has a provider, policy number, coverage period, and status. Property managers create and manage these records in Frappe Desk. The system uses these records to determine whether mandatory coverage is in place when a rental agreement is submitted.

| Field | Type | Required | Notes |
|---|---|---|---|
| `flat` | Link → Rental Asset | ✅ | Filtered to `asset_type = Flat` |
| `provider` | Data | ✅ | Insurance company name |
| `policy_number` | Data | ✅ | |
| `coverage_type` | Select | ✅ | Options below |
| `start_date` | Date | ✅ | |
| `expiry_date` | Date | ✅ | |
| `premium_amount` | Currency | | |
| `coverage_amount` | Currency | | |
| `policy_document` | Attach | | Scanned policy PDF |
| `status` | Select | ✅ | `Active`, `Expired`, `Cancelled` |

**Coverage Type Options**:
`Earthquake`, `Flood`, `Fire`, `Structural`, `Liability`, `Theft`, `Water Damage`, `Storm`, `Subsidence`, `Personal Injury`, `Glass`, `Terrorism`

**Acceptance Criteria**:
- [ ] DocType exists in Frappe Desk under "Rental" module
- [ ] `flat`, `provider`, `policy_number`, `coverage_type`, `start_date`, `expiry_date`, `status` are mandatory
- [ ] `status` defaults to `Active`
- [ ] Only `Property Manager` and `System Manager` can create/edit
- [ ] Customer role CANNOT view or access this DocType (desk-only)
- [ ] `coverage_type` has all 12 listed options
- [ ] `policy_document` accepts PDF and image uploads

---

### 2.2 Status Auto-Update on Expiry

> **Requires**: 2.1

Insurance policies don't automatically become "Expired" in the database when their expiry date passes — someone needs to update them. This daily scheduler job scans for policies that are still marked "Active" but have a past expiry date, and automatically flips them to "Expired". This is important because the insurance validator (4.1) only counts "Active" policies, so stale data would create false positives.

Daily scheduler job to auto-expire stale policies:

```python
def update_expired_insurance_policies():
    expired = frappe.get_all("Flat Insurance Policy", filters={
        "status": "Active", "expiry_date": ["<", frappe.utils.today()]
    }, pluck="name")
    for name in expired:
        frappe.db.set_value("Flat Insurance Policy", name, "status", "Expired")
    if expired:
        frappe.db.commit()
```

**Acceptance Criteria**:
- [ ] Policy with `expiry_date < today` and `status = Active` → auto-updated to `Expired` by daily scheduler
- [ ] Cancelled policies are NOT affected by auto-update
- [ ] Already-expired policies are skipped (idempotent)

---

## 3. Frappe — `Country Insurance Requirement` Child Table

### 3.1 Schema Definition

> **Requires**: F01-2.3 (`country_insurance_requirements` Table injected on Rental Configuration)

Different countries have different mandatory insurance requirements. This child table on `Rental Configuration` lets the platform operator define which **coverage types are mandatory per country**. For example, Turkey might require Earthquake + Fire, while the Netherlands requires Flood + Water Damage. The `mandatory` flag controls whether missing coverage **blocks** agreement submission (mandatory = yes) or is just informational (mandatory = no).

| Field | Type | Required | Notes |
|---|---|---|---|
| `country` | Link → Country | ✅ | |
| `coverage_type` | Select | ✅ | Same options as `Flat Insurance Policy` |
| `mandatory` | Check | | Default 1 |

**Acceptance Criteria**:
- [ ] Child table rows addable on `Rental Configuration` form
- [ ] Each row specifies: which country requires which coverage type
- [ ] `mandatory = 1` means this coverage blocks agreement submission if missing
- [ ] Multiple rows per country allowed (e.g., Turkey: Earthquake + Fire)
- [ ] Non-mandatory rows are informational — they don't block agreements

---

## 4. Frappe — Insurance Validator

### 4.1 `validate_flat_insurance()` — Agreement Validate Hook

> **Requires**: 2.1 (Flat Insurance Policy), 3.1 (Country Insurance Requirement), F01-2.2 (hooks.py registers this)

This is the **core business logic** of the Insurance domain. It runs as a `validate` hook on `Rental Agreement` — meaning it fires every time someone tries to submit a new rental agreement. The function checks whether the flat has active insurance policies covering all mandatory types for the platform's country. If any mandatory coverage is missing, it **blocks the agreement submission** with a descriptive error message and creates a high-priority ToDo for the property manager.

Key design decisions:
- **Non-flat assets bypass**: Vehicle agreements pass through silently.
- **Gating, not suspension**: This check only blocks NEW agreement submissions — it does NOT retroactively suspend already-active agreements if insurance expires mid-lease.
- **Expiry alignment**: Only policies that expire on or after the agreement's start date count as active.

```python
def validate_flat_insurance(agreement, method=None):
    asset = frappe.get_doc("Rental Asset", agreement.asset)
    if asset.asset_type != "Flat":
        return  # Skip non-flat assets

    config = frappe.get_single("Rental Configuration")
    required = [r.coverage_type for r in config.get("country_insurance_requirements", [])
                if r.country == config.country and r.mandatory]
    if not required:
        return  # No mandatory insurance configured

    active_coverage = frappe.get_all("Flat Insurance Policy", filters={
        "flat": agreement.asset, "status": "Active",
        "expiry_date": [">=", agreement.start_date],
    }, pluck="coverage_type")

    missing = [c for c in required if c not in active_coverage]
    if missing:
        _create_insurance_todo(agreement, missing, config.country)
        frappe.throw(
            f"Agreement blocked. Mandatory insurance missing for {config.country}: "
            f"{', '.join(missing)}. An internal reminder has been created for the "
            "property manager."
        )
```

**Acceptance Criteria**:
- [ ] Non-Flat assets → validator returns silently (no check)
- [ ] No mandatory coverage configured for the country → passes silently
- [ ] All mandatory coverage types present and active → agreement validates successfully
- [ ] One or more mandatory types missing → `frappe.throw()` blocks submission
- [ ] Error message lists specific missing coverage types by name
- [ ] Error message mentions the country
- [ ] ToDo is created before the throw (see 4.2)
- [ ] Expired policies (expiry_date < agreement start_date) are NOT counted as active
- [ ] Cancelled policies are NOT counted as active

---

### 4.2 `_create_insurance_todo()` — Auto-ToDo

> **Requires**: 4.1

When an agreement is blocked due to missing insurance, the system creates a **high-priority ToDo** assigned to the flat's property manager. This ensures the gap doesn't just show as an error message — it becomes a tracked action item in the manager's task list. The ToDo includes all context needed to resolve it: which flat, which agreement, which country, and which specific coverage types are missing. The due date is set to 3 days from creation to encourage prompt action.

```python
def _create_insurance_todo(agreement, missing_types, country):
    asset = agreement.asset
    manager = frappe.db.get_value("Rental Asset", asset, "owner") or frappe.session.user
    frappe.get_doc({
        "doctype": "ToDo",
        "owner": manager,
        "assigned_by": frappe.session.user,
        "priority": "High",
        "date": frappe.utils.add_days(frappe.utils.today(), 3),
        "description": (
            f"⚠️ Insurance gap on flat {asset} is blocking agreement {agreement.name}.\n"
            f"Country: {country}\n"
            f"Missing coverage: {', '.join(missing_types)}\n"
            "Please obtain or renew the required policies before the agreement can proceed."
        ),
        "reference_type": "Rental Agreement",
        "reference_name": agreement.name,
    }).insert(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] ToDo created with `High` priority
- [ ] Assigned to the asset's `owner` (Property Manager)
- [ ] Falls back to `frappe.session.user` if owner not set
- [ ] Due date = today + 3 days
- [ ] Description includes: flat name, agreement name, country, list of missing coverage types
- [ ] `reference_type` and `reference_name` link to the blocked agreement
- [ ] ToDo is visible in the Property Manager's ToDo list in Desk
- [ ] Multiple blocked agreements for the same flat create separate ToDos

---

## 5. Frappe — Insurance Expiry Alert

### 5.1 `alert_insurance_expiry` Scheduler Job

> **Requires**: 2.1 (Flat Insurance Policy), F01-2.2 (hooks.py)

Insurance policies need to be renewed before they expire, but property managers managing many flats can easily miss renewal dates. This daily scheduler job sends proactive alerts at **two warning windows**: 30 days before expiry (early warning for procurement) and 7 days before expiry (urgent final reminder). Each alert emails the property manager with the policy details. The job is designed to be idempotent — running it multiple times on the same day won't send duplicate emails.

Fires at two alert windows — 30 days and 7 days before expiry:

```python
def alert_insurance_expiry():
    for days_before in [30, 7]:
        target_date = frappe.utils.add_days(frappe.utils.today(), days_before)
        expiring = frappe.get_all("Flat Insurance Policy", filters={
            "status": "Active", "expiry_date": target_date,
        }, fields=["name", "flat", "coverage_type", "expiry_date", "provider"])
        for policy in expiring:
            manager = frappe.db.get_value("Rental Asset", policy.flat, "owner")
            frappe.sendmail(recipients=[manager],
                subject=f"Insurance expiring in {days_before} days: {policy.coverage_type}",
                message=f"{policy.coverage_type} policy from {policy.provider} "
                        f"for flat {policy.flat} expires on {policy.expiry_date}.")
```

**Acceptance Criteria**:
- [ ] Policy expiring in 30 days → email sent to Property Manager
- [ ] Policy expiring in 7 days → email sent to Property Manager
- [ ] Policy expiring in 15 days → NO alert (not in configured windows)
- [ ] Already-expired policies → NO alert
- [ ] Alert includes: flat name, coverage type, expiry date, provider
- [ ] Alerts are idempotent — running twice on the same day doesn't send duplicate emails

---

## 6. Frappe — Insurance API (Internal Only)

### 6.1 `get_flat_insurance_status`

> **Requires**: 2.1

An internal API endpoint that returns the list of active insurance policies for a given flat. This is used by internal dashboards and reports — it is **not** customer-facing. Only users with `Property Manager`, `Rental Manager`, or `System Manager` roles can access it. The response intentionally excludes the `policy_document` URL (the actual PDF) since scanned insurance documents should only be viewable directly in Desk.

```python
@frappe.whitelist()
def get_flat_insurance_status(asset_name):
    """Returns active insurance policies list — internal role only."""
```

**Acceptance Criteria**:
- [ ] Returns list of active policies for the flat
- [ ] Only accessible by `Property Manager`, `Rental Manager`, `System Manager`
- [ ] Customer role → HTTP 403
- [ ] Returns: coverage type, provider, start date, expiry date, status
- [ ] Does NOT return policy document URL (sensitive — viewable only in Desk)

---

## 7. Business Rules Summary

### 7.1 Key Rules

These are architectural constraints that apply across all insurance-related code:

1. **Gating vs. Suspension**: Insurance gaps block new agreement submission — they do NOT retroactively suspend an already-active agreement.
2. **Desk-Only**: Insurance is entirely internal. No customer-facing web page, app screen, or API exposes insurance status.
3. **Not a Booking Step**: Insurance is validated server-side on agreement submit. It is NOT a step in the customer booking form.
4. **Asset-Type Scoped**: Insurance validation only fires for `asset_type == Flat`. Vehicle agreements pass silently.
5. **Country-Configurable**: Mandatory coverage types are set per country via `Country Insurance Requirement` child table on `Rental Configuration`.

**Acceptance Criteria**:
- [ ] Insurance gap blocks agreement submission — does NOT auto-suspend an already-active agreement
- [ ] Insurance is Desk-only — customers NEVER see insurance status on any web page or app screen
- [ ] Insurance is NOT a step in the booking form
- [ ] Insurance validation only fires for Flat-type assets
- [ ] Mandatory coverage types are configurable per country (e.g., Earthquake in Turkey, Flood in Netherlands)

---

## 8. Cross-Cutting Concerns

### 8.1 Logging

| Location | Log Level | What to Log |
|---|---|---|
| `validate_flat_insurance()` — passed | `INFO` | Agreement name, asset, country: "All mandatory coverage present" |
| `validate_flat_insurance()` — blocked | `WARNING` | Agreement name, asset, country, missing coverage types |
| `validate_flat_insurance()` — non-flat bypass | `DEBUG` | Agreement name, asset type: "Skipped — not a Flat" |
| `validate_flat_insurance()` — no config | `DEBUG` | Country: "No mandatory insurance requirements configured" |
| `_create_insurance_todo()` | `INFO` | ToDo created, assigned to, agreement, missing types |
| `update_expired_insurance_policies()` | `INFO` | Count of policies auto-expired |
| `alert_insurance_expiry` — alert sent | `INFO` | Policy name, flat, coverage type, expiry date, days before |
| `get_flat_insurance_status` API | `INFO` | User, asset queried, result count |
| `get_flat_insurance_status` — access denied | `WARNING` | User, role: "Unauthorized access attempt to insurance data" |

**Acceptance Criteria**:
- [ ] Every insurance validation decision is logged with outcome (passed/blocked/skipped)
- [ ] Blocked agreements log the specific missing coverage types
- [ ] Structured logging uses `frappe.logger("rental_flats.insurance")`
- [ ] Policy document URLs are never logged

---

### 8.2 Caching

| Data | Cache Key Pattern | TTL | Invalidation Trigger |
|---|---|---|---|
| Country insurance requirements | `insurance_requirements:{country}` | 60 min | `Rental Configuration` save |
| Active policies per flat | `insurance_policies:{asset_name}` | 10 min | `Flat Insurance Policy` save/submit |

> [!NOTE]
> Country insurance requirements rarely change but are queried on every agreement submission. Caching avoids loading the full `Rental Configuration` singleton for each validation.

**Acceptance Criteria**:
- [ ] Country requirements cached per country code
- [ ] Active policies cached per flat and invalidated on policy save
- [ ] Cache invalidated when `Rental Configuration` insurance requirements are changed

---

### 8.3 Rate Limiting

| Endpoint | Limit | Scope | Response on Limit |
|---|---|---|---|
| `get_flat_insurance_status` | 30 req/min | Per user session | HTTP 429 with `Retry-After` |

> [!NOTE]
> This is an internal-only API. Rate limiting protects against automated tooling querying insurance status for all flats in bulk.

**Acceptance Criteria**:
- [ ] Internal insurance API rate-limited to 30 req/min per user session
- [ ] Exceeding limit returns HTTP 429

---

### 8.4 Security Validation

| Check | Location | Rule |
|---|---|---|
| Role enforcement | `get_flat_insurance_status` | Only `Property Manager` / `Rental Manager` / `System Manager`; Customer → HTTP 403 |
| Customer invisibility | All layers | Insurance data never appears in any customer-facing API, web page, or Flutter screen |
| Policy document exclusion | `get_flat_insurance_status` | `policy_document` URL excluded from API response (Desk-only) |
| Agreement integrity | `validate_flat_insurance()` | Validator only checks at submission time — does NOT retroactively suspend active agreements |
| ToDo deduplication | `_create_insurance_todo()` | Check for existing open ToDo with same agreement + coverage before creating new |

**Acceptance Criteria**:
- [ ] Customer role can never access insurance DocType or API
- [ ] Policy document (scanned PDF) never returned in any API response
- [ ] Insurance validator does not modify existing active agreements
- [ ] ToDo creation is idempotent — no duplicates for same agreement + missing coverage

---

## 9. Domain-Level Acceptance Criteria

- [ ] Agreement submit for flat with all mandatory insurance → succeeds
- [ ] Agreement submit for flat with missing mandatory insurance → blocked with descriptive error
- [ ] ToDo created for Property Manager when insurance blocks agreement
- [ ] Insurance expiry alerts at 30 and 7 days before expiry
- [ ] Expired policies auto-updated to `Expired` status
- [ ] Customer cannot see insurance info on any portal or app screen
- [ ] Vehicle agreements → insurance validator silently passes

---

## 10. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (DocType + config child table + validator + scheduler + API) | 2 days |
| Web (N/A — Desk only) | 0 days |
| Flutter (N/A — Desk only) | 0 days |
| **Total** | **2 days** |
