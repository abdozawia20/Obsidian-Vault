# Reporting — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Reporting & Analytics
> **Module**: Customer Mobile App — Tenant-Visible Summaries
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

Management reports are accessed exclusively via Frappe Desk. The Flutter app exposes only tenant-facing summaries that help the customer understand their own financial position at a glance.

---

## 2. Screen Requirements

### 2.1 Tenant-Facing Summaries

| # | Requirement |
|---|---|
| RF-001 | The home screen must show the customer's active rental summary: next invoice amount, due date, and agreement status |
| RF-002 | The Payments screen must sort outstanding invoices by due date ascending |
| RF-003 | Deposit status (amount held, any pending deductions) must be visible on the agreement detail screen |

> **Note**: Full management reports (occupancy, revenue, collection efficiency, churn) are Frappe Desk–only. The mobile app does not provide management analytics.
