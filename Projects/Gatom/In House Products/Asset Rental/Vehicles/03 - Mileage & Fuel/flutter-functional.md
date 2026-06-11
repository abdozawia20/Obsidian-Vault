# Mileage & Fuel — Flutter: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Mileage & Fuel Tracking
> **Module**: Customer Mobile App — Mileage Log Screen

---

## 1. Purpose & Scope

The Flutter app provides a read-only mileage log showing odometer entries (pickup/return/mid-term) and a mid-rental mileage estimate for GPS vehicles.

---

## 2. Screen Requirements

| # | Requirement |
|---|---|
| VF-030 | View pickup and return odometer readings |
| VF-031 | Each entry: log type (Pickup/Return/Mid-Term), date, odometer, fuel level |
| VF-032 | Return entry: computed driven km, overage km, overage charge |
| VF-033 | Mileage log creation is staff-only — customers view only |
| VF-035 | For GPS vehicles: show estimated current mileage. Non-GPS: "Mileage available at return." |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| VFS-002 | Customer | See the mileage and fuel policy | I understand costs before booking |
| VFS-004 | Active tenant | View my pickup and return odometer | I can verify overage calculation |

---

## 4. Business Rules

1. Mileage log is view-only for Customer role.
2. Guarantors do NOT see mileage data.
