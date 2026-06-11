# Reporting — Frappe: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Reporting & Analytics
> **Module**: `rental_core` — Management Reports
> **Document Type**: Functional
> **Audience**: Management, operations managers, QA

---

## 1. Purpose & Scope

This document defines the reporting requirements for management-level analytics. All reports are built as Frappe Report Builder or Script Reports accessible from Frappe Desk. Customer-facing summaries are defined in their respective domain docs (Accounting, Contracting).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| BR-090 | Occupancy rate report: % of assets rented vs. available by period |
| BR-091 | Revenue report: by asset, category, location, and period |
| BR-092 | Collection efficiency: invoiced vs. collected ratio |
| BR-093 | Tenant lifetime value: total revenue per customer |
| BR-094 | Asset ROI: revenue generated vs. acquisition and maintenance cost |
| BR-095 | Churn analysis: tenants who did not renew |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-003 | Accountant | See all overdue invoices with aging | I can prioritise collections |
| US-RP1 | Rental Manager | View occupancy rates across all assets | I can identify underperforming assets |
| US-RP2 | Management | See revenue by location and period | I can make data-driven expansion decisions |

---

## 4. Business Rules

1. All reports are accessible from Frappe Desk only — not from the customer portal or mobile app.
2. Report access is governed by role permissions: Rental Manager and above for operational reports, Accountant for financial reports.
