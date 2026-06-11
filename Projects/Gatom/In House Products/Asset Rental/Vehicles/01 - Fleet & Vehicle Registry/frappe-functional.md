# Fleet & Vehicle Registry — Frappe: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Fleet & Vehicle Registry
> **Module**: `rental_vehicles` — Categories, Vehicle Attributes & Fleet Hierarchy
> **Document Type**: Functional

---

## 1. Purpose & Scope

This document defines the vehicle category system and vehicle-specific attributes that extend the base `Rental Asset` DocType. Fleet hierarchy and category rate configuration are managed exclusively in Frappe Desk.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| VR-001 | Vehicles must be grouped into categories (Sedan, SUV, Van, Truck, Motorcycle, Bus, Special) |
| VR-002 | Each category must define: daily/weekly/monthly rate, included km/day, overage rate/km, fuel policy, minimum driver age, and required license class |
| VR-003 | Each vehicle must record: plate number (unique), VIN (unique), make, model, year, colour, fuel type, transmission type, seat count, and engine capacity |
| VR-004 | Current mileage, last service mileage, and next service date/mileage must be tracked per vehicle |
| VR-005 | GPS device ID must be linkable to a vehicle for telematics integration |

---

## 3. User Roles

| Role | Responsibilities |
|---|---|
| **Fleet Manager** | Full CRUD on categories and vehicles, GPS linking |
| **Rental Agent** | Read access to vehicles; creates agreements |

---

## 4. Business Rules

1. Plate number and VIN must both be unique across all vehicles — enforced at DB level.
2. VIN is not exposed in any customer-facing API response.
3. **v1 supports a single named driver per agreement.** Authorized driver lists for company tenants are a planned v2 enhancement.
