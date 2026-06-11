# Domain V02 — Insurance & Registration: Implementation Plan

> **Variant**: Vehicles (child app `rental_vehicles`)
> **Domain**: Insurance & Registration
> **Sequence**: 2 of 7
> **Depends on**: V01 (custom fields for insurance/registration/roadworthiness on Rental Asset), Base D01 (Rental Configuration, hooks.py)
> **Functional Refs**: [[frappe-functional|Frappe]]

---

## 1. Overview

This domain tracks the **legal compliance documents** attached to each vehicle: insurance policy, registration card, and roadworthiness/MOT certificate. Each has an expiry date that triggers proactive alerts (30 days and 7 days before expiry).

The critical business logic is the **two-level gating system**: expired registration is a **hard block** (the system refuses to create a new agreement for that vehicle — no override possible), while expired insurance is a **soft alert** (the Fleet Manager sees a warning but can acknowledge it and proceed). This distinction exists because operating a vehicle with expired registration is typically illegal, while insurance gaps may have legitimate short-term reasons (policy renewal in progress).

This domain is entirely **Desk-managed** — there are no customer-facing pages or screens.

---

## 2. Frappe — Document Expiry Validation

### 2.1 Registration Hard-Block (`validate` hook on Rental Agreement)

> **Requires**: V01-2.2 (hooks.py registers `doc_events`), V01-2.3 (custom fields: `custom_registration_expiry`)

Every country requires vehicles used commercially (for rental, ride-sharing, delivery, etc.) to maintain a valid **registration card** issued by the transport authority. Driving an unregistered vehicle is a criminal offence in most jurisdictions — it can result in the vehicle being impounded, fines for the rental company, and voided insurance coverage. This is not a "nice to have" check — it's a legal requirement.

When a Rental Agreement is validated (before submission), this hook checks whether the linked vehicle's registration has expired. If `custom_registration_expiry < today()`, the agreement is **rejected with a `frappe.throw()`** — no override, no bypass, not even for a System Manager. The error message includes the vehicle name and the expired date so the Fleet Manager knows exactly which vehicle and what action to take ("go renew the registration first").

The hook checks `asset_type` first and returns early for non-Vehicle assets (flats don't have registration). It also handles the `null` case gracefully — a newly added vehicle that hasn't been registered yet (no expiry date set) is NOT blocked, since the Fleet Manager may be adding the vehicle to the system before the registration arrives.

```python
def validate_vehicle_documents(agreement, method=None):
    asset = frappe.get_doc("Rental Asset", agreement.asset)
    if asset.asset_type != "Vehicle":
        return
    # Hard block — registration
    if asset.custom_registration_expiry and getdate(asset.custom_registration_expiry) < getdate(today()):
        frappe.throw(
            f"Vehicle {asset.asset_name} has expired registration "
            f"(expired {asset.custom_registration_expiry}). "
            f"Renew registration before creating a new agreement.")
```

**Acceptance Criteria**:
- [ ] Vehicle with expired registration → `frappe.throw()` when agreement is submitted
- [ ] Vehicle with valid registration → agreement proceeds normally
- [ ] Vehicle with no registration expiry set (null) → no block (new vehicle, not yet registered)
- [ ] Error message includes vehicle name and expiry date
- [ ] Non-Vehicle assets (Flat type) are unaffected
- [ ] Block cannot be overridden by any role (no manual bypass)

---

### 2.2 Insurance Soft-Alert (`validate` hook on Rental Agreement)

> **Requires**: V01-2.2 (hooks.py), V01-2.3 (custom fields: `custom_insurance_expiry`)

Insurance is different from registration — while you should never rent out an uninsured vehicle, insurance renewals often involve short gaps (the old policy expires on Monday, the new policy is issued on Wednesday). During this gap, the fleet can't shut down completely. That's why expired insurance generates a **warning** instead of a hard block.

The hook uses `frappe.msgprint()` with `alert=True` to show a dismissible warning dialog. The Fleet Manager sees the warning ("Vehicle ABC has expired insurance — proceed with caution"), acknowledges it, and can still submit the agreement. This is a conscious business decision — the company accepts the risk during the coverage gap.

However, the warning is **logged** in the agreement's comment history for audit purposes. If an accident occurs during the uninsured rental, there's a permanent record that the manager was explicitly warned and chose to proceed. This protects the company in internal audits and legal proceedings by showing that the decision was informed, not accidental.

```python
    # Soft alert — insurance
    if asset.custom_insurance_expiry and getdate(asset.custom_insurance_expiry) < getdate(today()):
        frappe.msgprint(
            f"⚠️ Vehicle {asset.asset_name} has expired insurance "
            f"(expired {asset.custom_insurance_expiry}). "
            f"Proceed with caution.",
            alert=True, indicator="orange")
        frappe.get_doc("Comment", {
            "comment_type": "Info",
            "reference_doctype": "Rental Agreement",
            "reference_name": agreement.name,
            "content": f"Insurance expired warning acknowledged for {asset.asset_name}",
        }).insert(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Vehicle with expired insurance → warning dialog shown (not a hard block)
- [ ] Fleet Manager can dismiss the warning and proceed with the agreement
- [ ] Warning is logged as a Comment on the Rental Agreement
- [ ] Vehicle with valid insurance → no warning
- [ ] Vehicle with no insurance expiry set (null) → no warning
- [ ] Warning appears as an orange alert indicator

---

## 3. Frappe — Expiry Alert Schedulers

### 3.1 `alert_registration_expiry` Scheduler Job

> **Requires**: V01-2.2 (hooks.py daily scheduler), V01-2.3 (custom fields)

Vehicle documents expire on a fixed date — but the Fleet Manager can't be expected to manually check every vehicle's registration expiry date every day. This scheduler job runs **daily** and automatically scans all active vehicles, identifying those with registration expiring in the next 30 or 7 days.

The 30-day alert gives the Fleet Manager time to start the renewal process (which can involve government office visits, payment processing, and document delivery). The 7-day alert is the final warning — "this vehicle's registration expires in a week, if you haven't started renewal, do it now." Each alert creates a **Frappe ToDo** (a task item visible in the Desk sidebar) assigned to all users with the `Fleet Manager` role, plus an **email notification** for visibility outside the Desk interface.

Critically, the job is **idempotent** — if it runs on Monday and creates a "30-day" alert for Vehicle X, running again on Tuesday won't create a duplicate. It checks for existing ToDos with the same vehicle + expiry date combination before creating new ones. This prevents the Fleet Manager's inbox from being flooded with duplicate alerts.

**Acceptance Criteria**:
- [ ] Registration expiring in 30 days → ToDo created for Fleet Manager + email sent
- [ ] Registration expiring in 7 days → ToDo created for Fleet Manager + email sent
- [ ] Registration expiring in 15 days → NO alert (not in the configured windows)
- [ ] Already-expired registration → no further alerts (the hard-block handles it)
- [ ] Duplicate alert for same vehicle + same expiry date → prevented (idempotent)
- [ ] Inactive vehicles (`is_active = 0`) are excluded from the scan
- [ ] Scheduler runs daily without error when no vehicles have upcoming expiry

---

### 3.2 `alert_insurance_expiry` Scheduler Job

> **Requires**: V01-2.2 (hooks.py), V01-2.3 (custom fields)

Identical pattern to the registration alert (3.1), but for **insurance expiry**. The 30-day and 7-day windows give the Fleet Manager time to initiate policy renewal with the insurance provider. Since insurance is a soft-alert (not a hard block at booking time), the urgency is slightly lower than registration — but the alert still ensures the Fleet Manager is proactively aware rather than discovering the gap when a customer tries to book.

In practice, insurance renewals can take 1–2 weeks depending on the provider and the required documentation (updated vehicle inspection, premium payment, etc.). The 30-day window covers this timeline comfortably.

**Acceptance Criteria**:
- [ ] Insurance expiring in 30 days → ToDo + email to Fleet Manager
- [ ] Insurance expiring in 7 days → ToDo + email to Fleet Manager
- [ ] Insurance expiring in 15 days → NO alert
- [ ] Duplicate alert prevented (idempotent by vehicle + expiry date)
- [ ] Inactive vehicles excluded

---

### 3.3 `alert_roadworthiness_expiry` Scheduler Job

> **Requires**: V01-2.2 (hooks.py), V01-2.3 (custom fields: `custom_roadworthiness_expiry`)

In many jurisdictions (UAE, UK, EU countries), commercially operated vehicles must undergo periodic **roadworthiness inspections** (called MOT in the UK, Fahas in the UAE) to certify they're safe to drive. These certificates have expiry dates, and operating a vehicle past expiry can result in fines and liability issues.

This scheduler follows the identical pattern as registration and insurance alerts: 30-day and 7-day advance warnings via ToDo and email. The implementation is deliberately repetitive (not abstracted into a generic "document expiry" system) because each document type may evolve independently in the future — for example, roadworthiness might eventually become a hard-block like registration, while insurance remains a soft-alert.

**Acceptance Criteria**:
- [ ] Roadworthiness expiring in 30 days → ToDo + email to Fleet Manager
- [ ] Roadworthiness expiring in 7 days → ToDo + email to Fleet Manager
- [ ] Duplicate alert prevented (idempotent)
- [ ] Inactive vehicles excluded
- [ ] Vehicles without a roadworthiness expiry date set → no alert

---

## 4. Frappe — Document Expiry Report

### 4.1 Document Expiry Dashboard View

> **Requires**: V01-2.3 (custom fields), Base D08 (reporting patterns)

The scheduler alerts are proactive (they notify before expiry), but the Fleet Manager also needs a way to see the **current state** of the entire fleet's document compliance at a glance. This dashboard view answers the question: "Which of my 50 vehicles have expired or soon-expiring documents right now?"

This is implemented as a **saved filter configuration** on the existing `Rental Asset` list view in Frappe Desk — not as a standalone report. This approach leverages Frappe's built-in list view with sorting, search, and export, avoiding the need to build custom report infrastructure. The Fleet Manager can filter by: `Registration Expired`, `Insurance Expired`, `Roadworthiness Expired`, or `Expiring in 30 Days`. Expired documents are highlighted red, near-expiry documents are highlighted orange.

**Acceptance Criteria**:
- [ ] Fleet Manager can filter Rental Asset list by: `Registration Expired`, `Insurance Expired`, `Roadworthiness Expired`, `Expiring in 30 Days`
- [ ] Expired documents highlighted with red indicator
- [ ] Near-expiry (within 30 days) highlighted with orange indicator
- [ ] Only Vehicle-type assets appear in the filtered view
- [ ] Only Fleet Manager and System Manager can access

---

## 5. Domain-Level Acceptance Criteria

- [ ] Expired registration hard-blocks agreement creation (no override)
- [ ] Expired insurance shows dismissible warning with audit log
- [ ] Alerts fire at 30 days and 7 days before any document expiry
- [ ] No duplicate alerts for the same vehicle + expiry combination
- [ ] All three document types tracked: insurance, registration, roadworthiness
- [ ] Inactive vehicles excluded from all alert scans
- [ ] Alerts delivered via email and Frappe ToDo

---

## 6. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (validation hooks + 3 scheduler jobs + dashboard filter) | 3 days |
| Web (N/A — Desk-only domain) | 0 days |
| Flutter (N/A — Desk-only domain) | 0 days |
| **Total** | **3 days** |
