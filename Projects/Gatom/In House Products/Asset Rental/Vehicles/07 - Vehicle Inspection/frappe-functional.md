# Vehicle Inspection — Frappe: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Vehicle Inspection
> **Module**: `rental_vehicles` — Entry/Exit Checklists & Deposit Deductions

---

## 1. Purpose & Scope

Defines the vehicle-specific inspection workflow: entry and exit checklists (exterior, interior, tyres, fluids, keys/documents), damage pricing, and deposit deductions.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| VR-060 | Every rental agreement must have an entry and exit vehicle inspection |
| VR-061 | Inspections must include checklist items for: exterior, interior, tyres, fluid levels, and keys/documents |
| VR-062 | Damage found during exit inspection must be photographed, priced, and deducted from the deposit |

---

## 3. Business Rules

1. Damage deductions require photo evidence and justification text before committing to the deposit ledger.
2. Inspection is staff-only — performed by the Rental Agent at pickup and return.
