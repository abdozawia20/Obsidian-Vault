# Fleet & Vehicle Registry — Flutter: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Fleet & Vehicle Registry
> **Module**: Customer Mobile App — Vehicle Catalog & Detail
> **Document Type**: Functional

---

## 1. Purpose & Scope

The Flutter app exposes the vehicle catalog with filters, detail screen with specs, mileage policy, and license validation in the booking flow.

---

## 2. Screen Requirements

### 2.1 Vehicle Catalog

| # | Requirement |
|---|---|
| VF-001 | Filter sheet: Category, Fuel Type, Transmission, Minimum Seats |
| VF-002 | Each card: cover photo, make + model, year, fuel type, seat count, monthly rate |
| VF-003 | Active filter chips above the grid |

### 2.2 Vehicle Detail

| # | Requirement |
|---|---|
| VF-010 | Spec grid: make/model, year, fuel type, engine CC, transmission, seats, category |
| VF-011 | **Mileage Policy card**: included km/day, overage rate/km |
| VF-012 | **Fuel Policy** shown below mileage figures |
| VF-013 | Availability calendar includes maintenance windows (no reason shown) |
| VF-014 | 3D preview button → WebView if configured |

### 2.3 Booking Flow Extension

| # | Requirement |
|---|---|
| VF-020 | Collect license details in Step 2 (Personal Details) |
| VF-021 | License expiry ≥ rental end date — reject before advancing |
| VF-022 | Driver age ≥ minimum — reject before advancing |
| VF-023 | Client-side + server-side validation |

> **Note**: KYC is a standalone pre-requisite, not part of the booking flow.

---

## 3. Business Rules

1. VIN excluded from customer-facing API.
2. Unavailable calendar dates do not disclose reason.
