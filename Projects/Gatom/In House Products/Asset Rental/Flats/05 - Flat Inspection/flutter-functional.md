# Flat Inspection — Flutter: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Flat Inspection
> **Module**: Customer Mobile App — Inspection Results (Read-Only)
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

Inspection management (checklists, photos, scheduling) is performed entirely in Frappe Desk. The Flutter app exposes only **exit inspection deposit deductions** that affect the tenant's deposit, enabling them to review and dispute.

---

## 2. Screen Requirements

| # | Requirement |
|---|---|
| FF-060 | When deposit deductions have been proposed after an exit inspection, the tenant must be able to view the deduction line items (description, amount, photo) on their agreement detail screen. This complements the deposit dispute banner defined in base FR-058. |
| FF-061 | Entry inspection results are **not** shown to the tenant — only exit inspection deductions that affect the deposit are visible. |

---

## 3. Security Requirements

| Requirement | Description |
|---|---|
| **Access code** | Flat access code is never included in any API response |
| **Floor plan URL** | Served via CDN signed URL; expires after a short window |
