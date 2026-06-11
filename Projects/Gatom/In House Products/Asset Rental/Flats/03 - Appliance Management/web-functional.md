# Appliance Management — Web: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Appliance Management
> **Module**: Customer-Facing Website — Appliance Display
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

The web portal displays the appliance inventory on the flat detail page as a read-only collapsible section. Customers can see what's included before booking. Warranty and condition management is Desk-only.

---

## 2. Page Requirements

| # | Requirement |
|---|---|
| FW-022 | If an appliance inventory exists, a **collapsible section** on the flat detail page must show appliances with name, brand, and condition badge |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FWS-004 | Customer | See the appliance list before booking | I know what's included in a furnished flat |

---

## 4. Business Rules

1. The appliance section is collapsed by default to keep the page clean; users must expand it.
2. Warranty expiry dates and serial numbers are **not** shown to customers — only name, brand, and condition.
