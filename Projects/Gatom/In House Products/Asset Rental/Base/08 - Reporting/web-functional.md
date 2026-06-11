# Reporting — Web: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Reporting & Analytics
> **Module**: Customer-Facing Website — Tenant-Visible Summaries
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

Management reports are accessed exclusively via Frappe Desk. The web portal exposes only tenant-facing summaries that help the customer understand their own financial position.

---

## 2. Page Requirements

### 2.1 Tenant-Facing Summaries

| # | Requirement |
|---|---|
| RW-001 | `/my-rentals` must show the next invoice amount and due date for each active agreement |
| RW-002 | `/my-invoices` must sort outstanding invoices by due date ascending, giving the tenant a clear priority view |
| RW-003 | Deposit status (amount held, any pending deductions) must be visible on the agreement detail page |

> **Note**: Full management reports (occupancy, revenue, collection efficiency, churn) are Frappe Desk–only. The web portal does not provide management analytics.
