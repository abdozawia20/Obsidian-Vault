# Utility Billing — Web: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Utility Billing
> **Module**: Customer-Facing Website — Utility History Portal
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

This document defines the tenant-facing utility history pages on the web portal. Meter reading submission is staff-only (Frappe Desk) — the portal provides read-only history and charts.

---

## 2. Page Requirements

### 2.1 My Rentals Extension (`/my-rentals`)

| # | Requirement |
|---|---|
| FW-040 | For flat agreements with metered utilities, the last recorded charge per meter type must be shown inline |
| FW-041 | If utilities are included in rent, a "Utilities included" indicator must be shown |
| FW-042 | A "View full utility history" link must navigate to `/my-utilities` |

### 2.2 Utility History (`/my-utilities`)

| # | Requirement |
|---|---|
| FW-050 | Active flat tenants must be able to view up to 6 months of historical meter readings per meter type |
| FW-051 | Data must be shown in **tabbed** layout: one tab per meter type (Electricity, Water, Gas) |
| FW-052 | Each tab must include a **bar chart** showing monthly consumption |
| FW-053 | Each tab must include a **table** showing: reading date, consumption units, unit rate, total charge |
| FW-054 | The page must be **read-only** — tenants cannot submit readings from the portal |
| FW-055 | The page must only be shown to customers with at least one active flat agreement with metered utilities |
| FW-056 | The page must be inaccessible to guests (redirect to login) |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FWS-005 | Active tenant | View my monthly electricity and water bills in the portal | I can verify the charges are correct |
| FWS-006 | Active tenant | See a chart of my utility usage trend | I can identify spikes or anomalies |

---

## 4. Business Rules

1. `/my-utilities` is only added to the portal sidebar when `rental_flats` is installed.
2. The utility chart and table are read-only — no submission form exists.
3. If a tenant has both flat and vehicle agreements, only the flat agreement's utility data appears on `/my-utilities`.
4. **Guarantor utility visibility**: Guarantors do NOT see the tenant's utility charges or readings.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Utility portal auth** | `/my-utilities` redirects guests to `/login` |
| **Customer isolation** | Utility history API filters strictly by `frappe.session.user` |
