# Utility Billing — Flutter: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Utility Billing
> **Module**: Customer Mobile App — Utility Reading History
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the tenant-facing utility reading history and consumption charts in the Flutter app. Meter reading submission is staff-only — the app provides read-only history.

---

## 2. Screen Requirements

### 2.1 Utility Readings Screen

| # | Requirement |
|---|---|
| FF-040 | Active flat tenants must be able to view their utility reading history |
| FF-041 | History must be tabbed by meter type: Electricity, Water, Gas |
| FF-042 | Each tab must show a **bar chart** of monthly consumption (last 6 months) |
| FF-043 | Each tab must show a list of readings: date, consumption, unit rate, charge |
| FF-044 | The screen is **read-only** — customers cannot submit readings from the app |
| FF-045 | If utilities are included in rent, the screen must show an "Utilities included" message instead of meter data |

### 2.2 Agreement Detail Extension

| # | Requirement |
|---|---|
| FF-050 | The agreement detail screen must show a **"Utilities" tab** for flat agreements |
| FF-051 | The Utilities tab must show a summary of last charges per meter type |
| FF-052 | A "View Full History" button must navigate to the full Utility Readings screen |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FFS-005 | Active tenant | View my monthly utility charges in the app | I verify the billing on my phone |
| FFS-006 | Active tenant | See a consumption trend chart | I spot unusual spikes quickly |

---

## 4. Business Rules

1. The "Utilities" tab in Agreement Detail only appears for flat-type agreements.
2. The Utility Readings screen is view-only — no submit form.
3. **Guarantor utility visibility**: Guarantors do NOT see the tenant's utility charges or readings.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Utility read-only** | No submit/create endpoint is available from the customer-facing API for utility readings |
| **Customer isolation** | Utility history API filters by authenticated user server-side |
