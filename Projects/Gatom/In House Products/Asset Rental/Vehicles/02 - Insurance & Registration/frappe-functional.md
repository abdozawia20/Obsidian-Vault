# Insurance & Registration — Frappe: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Insurance & Registration
> **Module**: `rental_vehicles` — Document Lifecycle & Agreement Gating

---

## 1. Purpose & Scope

Tracks insurance, registration, and roadworthiness documents per vehicle. Expired registration hard-blocks agreements; expired insurance is a soft-alert with manual override.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| VR-010 | Each vehicle must track: insurance policy number, provider, expiry date, and document |
| VR-011 | **Expired registration is a hard-block** — a vehicle with expired registration cannot be assigned to a new agreement |
| VR-012 | **Expired insurance is a soft-alert** — the fleet manager sees a warning but is not hard-blocked (they must manually acknowledge) |
| VR-013 | Roadworthiness / MOT certificate must also be tracked with expiry |
| VR-014 | Alerts must fire at 30 days and 7 days before any document expiry |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| VS-001 | Fleet Manager | See all vehicles with expired or near-expiry documents | I maintain compliance before renting |

---

## 4. Business Rules

1. Registration expiry is a hard system block — no override.
2. Insurance expiry is a soft-alert — Fleet Manager must acknowledge with justification before renting.
3. Alerts fire via email and Frappe ToDo.
