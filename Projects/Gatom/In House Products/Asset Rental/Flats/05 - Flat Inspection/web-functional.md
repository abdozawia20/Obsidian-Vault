# Flat Inspection — Web: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Flat Inspection
> **Module**: Customer-Facing Website — Inspection Results (Read-Only)
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

Inspection management (checklists, photos, scheduling) is performed entirely in Frappe Desk. The web portal exposes only **exit inspection deposit deductions** that affect the tenant's deposit, enabling them to review and dispute.

---

## 2. Page Requirements

| # | Requirement |
|---|---|
| FW-060 | When deposit deductions have been proposed after an exit inspection, the tenant must be able to view the deduction line items (description, amount, photo) on their agreement detail page in `/my-rentals`. This complements the deposit dispute banner defined in base WR-048. |
| FW-061 | Entry inspection results are **not** shown to the tenant — only exit inspection deductions that affect the deposit are visible. |

---

## 3. Security Requirements

| Requirement | Description |
|---|---|
| **Access code** | Flat access code is never served to any web page or API |
