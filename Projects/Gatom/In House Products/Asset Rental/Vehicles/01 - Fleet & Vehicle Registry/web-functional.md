# Fleet & Vehicle Registry — Web: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Fleet & Vehicle Registry
> **Module**: Customer-Facing Website — Vehicle Catalog & Detail
> **Document Type**: Functional

---

## 1. Purpose & Scope

The web portal exposes the vehicle catalog with category-specific filters and the detail page with specs, mileage policy, and availability. Fleet hierarchy management is Desk-only.

---

## 2. Page Requirements

### 2.1 Vehicle Catalog (`/rentals/vehicles`)

| # | Requirement |
|---|---|
| VW-001 | Filterable by: **Category** (Sedan, SUV, Van, Truck, Motorcycle, Bus, Special) |
| VW-002 | Filter by **Fuel Type**: Petrol, Diesel, Electric, Hybrid, CNG |
| VW-003 | Filter by **Transmission**: Manual / Automatic |
| VW-004 | Filter by **Minimum Seats**: 2+, 4+, 5+, 7+, 9+ |
| VW-005 | Each card: cover photo, make + model, year, fuel type, seat count, monthly rate |
| VW-006 | Publicly accessible (no login required) |
| VW-007 | All filters via AJAX without full page reload |

### 2.2 Vehicle Detail (`/rentals/{vehicle}`)

| # | Requirement |
|---|---|
| VW-010 | Spec grid: make/model, year, fuel type, engine CC, transmission, seat count, category |
| VW-011 | **Mileage Policy box**: included km/day, overage rate/km |
| VW-012 | **Fuel Policy**: Full-to-Full, Full-to-Empty, or Pre-Purchase |
| VW-013 | Availability calendar includes maintenance windows as blocked dates (no reason shown) |
| VW-014 | VIN must **not** be displayed on the public detail page |
| VW-015 | Plate number may be displayed (for pickup identification) |

---

## 3. Booking Form Extension

| # | Requirement |
|---|---|
| VW-020 | Collect driver's license number, class, expiry, DOB in Step 2 (Personal Details) |
| VW-024 | **License expiry ≥ rental end date** — reject with explanation |
| VW-025 | **Driver age ≥ category minimum** — reject with explanation |
| VW-026 | Server-side re-validation at submission |
| VW-030 | Mileage & Fuel Policy acknowledgement box in Step 4 (Confirmation) |
| VW-032 | Customer must tick checkbox before submit |

> **Note**: KYC is a standalone pre-requisite, not part of the booking form.

---

## 4. Business Rules

1. VIN is excluded from all customer-facing pages and API responses.
2. Maintenance-blocked dates show as unavailable — no reason disclosed.
