# GPS Telematics — Flutter: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: GPS Telematics
> **Module**: Flutter App — Live Map (Fleet Manager Only)

---

## 1. Purpose & Scope

The Flutter app provides a **Live Map** screen exclusively for Fleet Managers. Customers cannot access GPS data (except estimated mileage via the Mileage domain).

---

## 2. Screen Requirements

| # | Requirement |
|---|---|
| VF-050 | Live map shows real-time positions of all GPS-equipped vehicles |
| VF-051 | Tapping a marker: vehicle name, plate, current speed, last update timestamp |
| VF-052 | **Inaccessible to customers** — role guard enforced |

---

## 3. Security Requirements

| Requirement | Description |
|---|---|
| **Live map API** | `get_vehicle_location` role-gated to Fleet Manager |
| **Customer 403** | Customers receive 403 if attempting direct API access |
