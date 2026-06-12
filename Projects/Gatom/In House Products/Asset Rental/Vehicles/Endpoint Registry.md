---
tags: [asset-rental, vehicles, endpoints, api, registry]
---

# 🔌 Vehicles — Endpoint Registry

> **Module**: `rental_vehicles`
> **Purpose**: Single source of truth for all endpoints, whitelisted methods, scheduler jobs, webhook hooks, doc events, portal routes, and Flutter routes in the Vehicles variant.
> **Last Updated**: 2026-06-12

---

## 1. Whitelisted API Endpoints (Customer-Facing)

| Method | Path | Auth | Rate Limit | Domain | Purpose |
|---|---|---|---|---|---|
| `GET` | `rental_vehicles.api.get_vehicle_detail` | Guest / Customer | 60 req/min per IP | V01 | Vehicle detail with category rates, mileage policy, specs |
| `GET` | `rental_vehicles.api.get_maintenance_schedule` | Customer (session) | 30 req/min per user | V01 | Maintenance-blocked dates for availability calendar (no detail) |
| `POST` | `rental_vehicles.api.submit_vehicle_booking` | Customer (session) | 10 req/min per user | V01 | Vehicle booking with license + age validation |
| `GET` | `rental_vehicles.api.get_mileage_history` | Customer (session) | 30 req/min per user | V03 | Agreement mileage log entries (read-only) |
| `GET` | `rental_vehicles.api.get_estimated_mileage` | Customer (session) | 20 req/min per user | V03 | Real-time estimated km for GPS-equipped vehicles |
| `POST` | `rental_vehicles.api.report_traffic_violation` | Customer (session) | 5 req/hour per user | V06 | Tenant self-report of traffic violation |
| `GET` | `rental_vehicles.api.get_violation_history` | Customer (session) | 30 req/min per user | V06 | Violation history (status, charges, no evidence docs) |

---

## 2. Whitelisted API Endpoints (Staff-Only)

| Method | Path | Auth | Rate Limit | Domain | Purpose |
|---|---|---|---|---|---|
| `POST` | `rental_vehicles.api.log_mileage` | Rental Agent / Fleet Manager | 30 req/min per user | V03 | Log odometer + fuel at pickup/return |
| `POST` | `rental_vehicles.api.report_traffic_violation` | Rental Agent / Fleet Manager | 60 req/min per user | V06 | Staff-reported violation (auto-Confirmed) |
| `GET` | `rental_vehicles.api.get_vehicle_location` | Fleet Manager | 60 req/min per user | V05 | Latest GPS position for a single vehicle |
| `GET` | `rental_vehicles.api.get_all_vehicle_locations` | Fleet Manager | 30 req/min per user | V05 | All GPS-equipped vehicle positions (fleet map) |

---

## 3. Webhook Endpoints (Public)

| Method | Path | Auth | Rate Limit | Domain | Purpose |
|---|---|---|---|---|---|
| `POST` | `rental_vehicles.api.telematics.receive_gps_event` | HMAC-SHA256 (`X-Signature` header) | 1000 req/min per source IP (Nginx) | V05 | GPS event ingestion from hardware providers |

> [!IMPORTANT]
> The GPS webhook is `allow_guest=True` — GPS hardware devices authenticate via HMAC signatures, not Frappe sessions. Rate limiting is enforced at the Nginx reverse proxy layer for minimal latency.

---

## 4. Internal Utility Functions (Not Whitelisted)

| Function | Module | Domain | Purpose |
|---|---|---|---|
| `validate_vehicle_documents(agreement, method)` | `rental_vehicles.utils.document_validator` | V02 | Registration hard-block + insurance soft-alert on agreement validate |
| `validate_no_maintenance_conflict(agreement, method)` | `rental_vehicles.utils.mileage` | V04 | Block agreements overlapping maintenance windows |
| `_append_overage_to_invoice(agr, charge, driven, included)` | `rental_vehicles.utils.mileage` | V03 | Append mileage overage line item to final invoice |
| `_compute_fuel_deficit(agr, return_fuel_pct)` | `rental_vehicles.utils.mileage` | V03 | Compute and append fuel deficit charge |
| `_verify_hmac(payload, secret)` | `rental_vehicles.api.telematics` | V05 | HMAC-SHA256 verification for GPS webhook |
| `_resolve_asset(device_id)` | `rental_vehicles.api.telematics` | V05 | Map GPS device ID → Rental Asset name |
| `_compute_30d_km(vehicle_name)` | `rental_vehicles.utils.usage_profiling` | V04 | Sum driven_km from last 30 days of Return logs |
| `_maybe_schedule_maintenance(vehicle, profile)` | `rental_vehicles.utils.usage_profiling` | V04 | Create maintenance schedule if interval exceeded |
| `_process_violation_charge(violation)` | `rental_vehicles.utils.violation_charging` | V06 | Route violation charge to deposit/invoice/standalone |
| `update_appliance_conditions(inspection)` | `rental_vehicles.utils.inspection_manager` | V07 | Sync item conditions from exit inspection |

---

## 5. Doc Events (hooks.py)

| DocType | Event | Handler | Domain | Purpose |
|---|---|---|---|---|
| `Rental Agreement` | `validate` | `rental_vehicles.utils.document_validator.validate_vehicle_documents` | V02 | Registration hard-block + insurance soft-alert |
| `Rental Agreement` | `validate` | `rental_vehicles.utils.mileage.validate_no_maintenance_conflict` | V04 | Block agreements overlapping maintenance windows |

> [!NOTE]
> Both `validate` hooks fire on every Rental Agreement save/submit. They check `asset_type` early and return immediately for non-Vehicle assets (Flats).

---

## 6. Scheduler Events (hooks.py)

| Frequency | Handler | Domain | Purpose |
|---|---|---|---|
| Daily | `rental_vehicles.scheduler_events.update_usage_profiles` | V04 | Classify vehicles into usage tiers (Idle → Heavy) |
| Daily | `rental_vehicles.scheduler_events.alert_insurance_expiry` | V02 | Insurance expiring in 30/7 days → ToDo + email |
| Daily | `rental_vehicles.scheduler_events.alert_registration_expiry` | V02 | Registration expiring in 30/7 days → ToDo + email |
| Daily | `rental_vehicles.scheduler_events.alert_roadworthiness_expiry` | V02 | Roadworthiness expiring in 30/7 days → ToDo + email |
| Daily (2 AM) | `rental_vehicles.scheduler_events.aggregate_gps_daily_summaries` | V05 | Aggregate previous day's GPS events into daily summary |
| Daily (3 AM) | `rental_vehicles.scheduler_events.purge_old_gps_events` | V05 | Delete raw GPS events older than 90 days |

> [!WARNING]
> The V05 GPS schedulers (`aggregate_gps_daily_summaries` and `purge_old_gps_events`) are **missing from the current V01 hooks.py documentation** (Section 2.2). They must be registered in `scheduler_events.daily` alongside the existing 4 scheduler jobs. The aggregation MUST run before the purge (2 AM before 3 AM) to avoid deleting raw events before they're summarized.

---

## 7. Portal Routes

| Route | Auth | Template | Domain | Purpose |
|---|---|---|---|---|
| `/rentals/vehicles` | Guest | `rental_vehicles/www/vehicles.html` | V01 | Public vehicle catalog with category/fuel/transmission filters |
| `/rentals/{vehicle}` | Guest | Base detail + vehicle spec extensions | V01 | Public vehicle detail page (specs, mileage policy, calendar) |

---

## 8. Portal Menu Items (hooks.py)

| Title | Route | Reference DocType | Role | Domain |
|---|---|---|---|---|
| Browse Vehicles | `/rentals/vehicles` | `Rental Asset` | Guest / Customer | V01 |

---

## 9. Flutter Routes (GoRouter)

| Path | Screen | Auth | Domain | Purpose |
|---|---|---|---|---|
| `/vehicles` | `VehicleCatalogScreen` | Guest / Customer | V01 | Vehicle catalog with filter sheet |
| `/vehicles/:id` | `VehicleDetailScreen` | Guest / Customer | V01 | Vehicle detail view (specs + mileage policy + calendar) |
| `/agreement/:id/mileage` | `MileageLogScreen` | Customer | V03 | Timeline-style mileage log history |
| `/agreement/:id/violations` | `TrafficViolationHistoryScreen` | Customer | V06 | Violation history with status badges |
| `/agreement/:id/violations/new` | `TrafficViolationReportScreen` | Customer | V06 | Self-report violation form |
| `/fleet-map` | `VehicleMapScreen` | Fleet Manager (route-guarded) | V05 | Live fleet map (Google Maps) |

---

## 10. Security Constraints

| Constraint | Scope | Enforcement |
|---|---|---|
| VIN exclusion | All customer-facing API responses, web templates, Flutter models | Explicit stripping in `get_vehicle_detail`; no Dart field on `VehicleAsset` model |
| GPS data prohibition | All customer-facing surfaces | Fleet Manager role-gate on GPS APIs; Socketio channel auth |
| Guarantor exclusion (mileage) | `get_mileage_history`, `get_estimated_mileage` | Server-side role check → HTTP 403 |
| Guarantor exclusion (violations) | `get_violation_history` | Server-side role check → HTTP 403 |
| Guarantor exclusion (inspections) | Inspection views (web + Flutter) | Server-side role check → HTTP 403 |
| Evidence document access | `get_violation_history` | Fleet Manager + Accountant only (not Customer) |
| Return inspection photos | Customer-facing views | Exit inspection photos excluded from customer views |
| Service record access | `Vehicle Service Record`, `Vehicle Maintenance Schedule` | Fleet Manager only; Customer cannot see |
| GPS webhook authentication | `receive_gps_event` | HMAC-SHA256 signature verification with timing-safe comparison |
| Plate number uniqueness | Database level | `UNIQUE` constraint on `custom_plate_number` |
| VIN uniqueness | Database level | `UNIQUE` constraint on `custom_vin` |

---

## 11. Rate Limiting Summary

| Endpoint Category | Limit | Scope |
|---|---|---|
| Public catalog / detail | 30–60 req/min | Per IP |
| Authenticated customer reads | 20–30 req/min | Per user session |
| Staff writes (mileage, violations) | 30–60 req/min | Per user session |
| Booking submission | 10 req/min | Per user session |
| Tenant violation self-report | 5 req/hour | Per user session |
| GPS webhook | 1000 req/min | Per source IP (Nginx) |
| Fleet map APIs (GPS) | 30–60 req/min | Per user session (Fleet Manager) |
| Scheduler jobs | N/A (server-side) | Daily batch |

> [!IMPORTANT]
> Rate limits should be enforced via Frappe's rate limiting middleware or a reverse proxy (Nginx `limit_req`). The GPS webhook MUST be rate-limited at Nginx for minimal latency — Frappe-level rate limiting adds unacceptable overhead at telemetry scale.

---

## Related

- [[Vehicles MOC|🧱 Vehicles MOC]]
- [[Vehicles Overview|🏗️ Vehicles Variant Overview]]
