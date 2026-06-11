# Mileage & Fuel — Frappe: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Mileage & Fuel Tracking
> **Module**: `rental_vehicles` — Odometer Logging, Overage & Fuel Policy

---

## 1. Purpose & Scope

Tracks odometer readings at pickup/return, computes overage km and charges, enforces fuel policy, and appends charges to the final invoice.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| VR-020 | Odometer readings must be logged at pickup and return for every rental agreement |
| VR-021 | Mid-term mileage checks must be supportable (optional, logged as "Mid-Term Check") |
| VR-022 | Driven kilometres must be automatically computed from pickup and return odometer readings |
| VR-023 | Included kilometres must be computed as: `included_km_per_day × rental_days` |
| VR-024 | Overage kilometres and associated charge must be automatically computed and added to the final invoice |
| VR-025 | Fuel level (0–100%) must be recorded at pickup and return |
| VR-026 | Under-fuel on return (Full-to-Full policy) must trigger an automatic fuel deficit charge |

---

## 3. Business Rules

1. Overage km = `max(0, driven_km − (included_km_per_day × rental_days))`.
2. Overage charge appended to the final invoice — not a separate document.
3. **"Full tank" = ≥90% fuel level.** Deficit charge triggers below 90%. Threshold configurable in `Rental Configuration`.
4. **Guarantor visibility**: Guarantors do NOT see overage or mileage data.
