# Asset Management — Frappe: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Asset Management
> **Module**: `rental_core` — Asset Lifecycle & Availability
> **Document Type**: Functional
> **Audience**: Operations managers, property managers, QA

---

## 1. Purpose & Scope

This document defines the asset lifecycle, availability calendar, status transitions, and the concurrency controls that prevent double-booking. An "asset" is any rentable item — the base layer is product-agnostic (flats and vehicles are defined in child apps).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| BR-020 | Every rentable asset must have a unique code, type, status, and location |
| BR-021 | Asset status must follow a defined lifecycle: `Available → Reserved → Rented → Maintenance → Retired` |
| BR-022 | Status transitions must be atomic — no two agreements can claim the same asset simultaneously. Reservation must use a database-level row lock (`SELECT … FOR UPDATE`) or optimistic version check to prevent double-booking under concurrent access from web and mobile |
| BR-023 | Assets must support photo uploads, document attachments, and GPS coordinates |
| BR-024 | An availability calendar must exist per asset, showing bookings and gaps |
| BR-025 | When a customer submits a booking, the asset status must immediately move to `Reserved` — only one pending booking can exist per asset at any time |
| BR-026 | If a Draft Agreement is not reviewed within the configurable draft expiry window (default: 48 hours, set in `Rental Configuration`), the booking must auto-expire: the asset returns to `Available` and the customer is notified via push and email. **The 48-hour window is measured from booking submission** — KYC is already verified before this point. Auto-expire precision depends on the Frappe scheduler frequency (default: 5 minutes); exact-second precision is not guaranteed. |
| BR-027 | On booking rejection by the internal team, the asset must immediately return to `Available` |

---

## 3. Business Rules

1. An agreement can only be submitted if the asset status is `Available` — submission immediately moves it to `Reserved`.
2. Only one Draft Agreement can exist per asset at any time. A second booking attempt for a `Reserved` asset is rejected.
3. A Draft Agreement not acted upon within the configurable expiry window auto-expires; the asset returns to `Available` and the customer is notified.
4. Business-initiated termination (eviction/breach) requires an exit inspection before the asset is freed.

---

## 4. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **S3 / MinIO** | Bidirectional | Asset photos, document attachments |
