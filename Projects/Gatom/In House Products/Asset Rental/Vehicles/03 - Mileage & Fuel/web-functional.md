# Mileage & Fuel — Web: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Mileage & Fuel Tracking
> **Module**: Customer-Facing Website — Mileage Portal

---

## 1. Purpose & Scope

The web portal shows tenants their mileage summary (pickup/return odometer, overage) and estimated current mileage for GPS vehicles.

---

## 2. Page Requirements

### Customer Portal (`/my-rentals`)

| # | Requirement |
|---|---|
| VW-040 | Vehicle agreements must show: pickup odometer, last recorded odometer, included km total |
| VW-041 | Overage charge from return mileage log must be visible on agreement detail |
| VW-045 | For GPS-equipped vehicles, show estimated current mileage. For non-GPS: "Mileage available at return." |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| VWS-002 | Customer | See the mileage policy before booking | No surprise overage charges |
| VWS-005 | Active tenant | See my driven km vs. included km | I can track my usage |
