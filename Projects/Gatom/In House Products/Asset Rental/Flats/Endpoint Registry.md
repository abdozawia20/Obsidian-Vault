---
tags: [asset-rental, flats, endpoints, api, registry]
---

# 🔌 Flats — Endpoint Registry

> **Module**: `rental_flats`
> **Purpose**: Single source of truth for all endpoints, whitelisted methods, scheduler jobs, webhook hooks, and portal routes in the Flats variant.
> **Last Updated**: 2026-06-12

---

## 1. Whitelisted API Endpoints (Customer-Facing)

| Method | Path | Auth | Rate Limit | Domain | Purpose |
|---|---|---|---|---|---|
| `GET` | `rental_flats.api.get_flat_catalog` | Guest / Customer | 30 req/min per IP | F01 | Flat catalog with filters (bedrooms, area, amenities) |
| `GET` | `rental_flats.api.get_flat_detail` | Guest / Customer | 60 req/min per IP | F01 | Single flat detail with amenities, appliances, schema.org |
| `GET` | `rental_flats.api.get_utility_history` | Customer (session) | 20 req/min per user | F02 | Tenant utility reading history (last 24 readings) |

---

## 2. Whitelisted API Endpoints (Staff-Only)

| Method | Path | Auth | Rate Limit | Domain | Purpose |
|---|---|---|---|---|---|
| `POST` | `rental_flats.api.submit_meter_reading` | Property Manager / System Manager | 60 req/min per user | F02 | Submit meter reading (creates + submits document) |
| `GET` | `rental_flats.api.get_flat_insurance_status` | Property Manager / Rental Manager / System Manager | 30 req/min per user | F04 | Active insurance policies for a flat |

---

## 3. Internal Utility Functions (Not Whitelisted)

| Function | Module | Domain | Purpose |
|---|---|---|---|
| `inject_reading_into_invoice(reading)` | `rental_flats.utils.utility_billing` | F02 | Append utility line item to draft invoice |
| `sweep_unbilled_utilities(agreement, invoice)` | `rental_flats.utils.utility_billing` | F02 | Sweep unbilled readings onto new subscription invoice |
| `_append_utility_line(invoice, reading)` | `rental_flats.utils.utility_billing` | F02 | Shared helper: create invoice line item from reading |
| `validate_flat_insurance(agreement, method)` | `rental_flats.utils.insurance_validator` | F04 | Agreement validate hook — blocks if mandatory insurance missing |
| `_create_insurance_todo(agreement, missing, country)` | `rental_flats.utils.insurance_validator` | F04 | Create high-priority ToDo for insurance gap |
| `update_appliance_conditions(inspection)` | `rental_flats.utils.appliance_manager` | F03 | Sync appliance conditions from inspection checklist |
| `get_occupancy_rate(parent_type, parent_name)` | `rental_flats.utils.property_utils` | F01 | Compute occupancy % for Property or Building |
| `_notify_pm(agreement, message)` | `rental_flats.utils.notifications` | F05 | Email + ToDo notification to Property Manager (idempotent) |

---

## 4. Doc Events (hooks.py)

| DocType | Event | Handler | Domain | Purpose |
|---|---|---|---|---|
| `Rental Agreement` | `validate` | `rental_flats.utils.insurance_validator.validate_flat_insurance` | F04 | Block agreement if mandatory insurance is missing |

---

## 5. Scheduler Events (hooks.py)

| Frequency | Handler | Domain | Purpose |
|---|---|---|---|
| Daily | `rental_flats.scheduler_events.remind_utility_meter_readings` | F02 | On 25th: remind PM to submit meter readings |
| Daily | `rental_flats.scheduler_events.alert_missing_readings` | F02 | On 1st: escalation for missing readings |
| Daily | `rental_flats.scheduler_events.alert_appliance_warranty_expiry` | F03 | Warranty expiring within 30 days → email + ToDo |
| Daily | `rental_flats.scheduler_events.check_flat_annual_inspection_due` | F05 | Inspections overdue (>11 months) → reminder |
| Daily | `rental_flats.scheduler_events.alert_insurance_expiry` | F04 | Policies expiring in 30 or 7 days → email |
| Daily | `rental_flats.scheduler_events.update_expired_insurance_policies` | F04 | Auto-flip Active → Expired for past-due policies |

---

## 6. Portal Routes

| Route | Auth | Template | Domain | Purpose |
|---|---|---|---|---|
| `/rentals/flats` | Guest | `rental_flats/www/flats.html` | F01 | Public flat catalog with filters |
| `/rentals/{flat}` | Guest | Base detail + flat extensions | F01 | Public flat detail page |
| `/my-utilities` | Customer | `rental_flats/www/my-utilities.html` | F02 | Tenant utility history (tabbed charts + tables) |

---

## 7. Portal Menu Items (hooks.py)

| Title | Route | Reference DocType | Role | Domain |
|---|---|---|---|---|
| Utility Usage | `/my-utilities` | `Utility Meter Reading` | Customer | F02 |

---

## 8. Flutter Routes (GoRouter)

| Path | Screen | Auth | Domain | Purpose |
|---|---|---|---|---|
| `/flats` | `FlatCatalogScreen` | Guest / Customer | F01 | Flat catalog with filter sheet |
| `/flats/:id` | `FlatDetailScreen` | Guest / Customer | F01 | Flat detail view |
| `/appliances` | `AppliancesScreen` | Customer | F03 | Appliance list (via `extra`) |
| `/floor-plan?url=...` | `FloorPlanViewerScreen` | Customer | F01 | PDF/image floor plan viewer |
| `/agreement/:id/utilities` | `UtilityReadingsScreen` | Customer | F02 | Utility reading history |

---

## 9. Security Constraints

| Constraint | Scope | Enforcement |
|---|---|---|
| `custom_access_code` exclusion | All API responses, web templates, Flutter models | Explicit removal in `get_flat_detail`; Password fieldtype; no template reference; no Dart field |
| Customer isolation (utility) | `get_utility_history` API | Server-side filter by `frappe.session.user` → 403 for other customers |
| Customer isolation (insurance) | `get_flat_insurance_status` API | Role check: Property Manager / Rental Manager / System Manager only |
| Serial number exclusion | All customer-facing surfaces | Excluded from API response, web template, Flutter model |
| Floor plan URL | CDN delivery | Signed CDN URL with short expiry window |
| Utility submission | `submit_meter_reading` API | Role check: Property Manager / System Manager only → 403 for Customer |

---

## 10. Rate Limiting Summary

| Endpoint Category | Limit | Scope |
|---|---|---|
| Public catalog / detail | 30–60 req/min | Per IP |
| Authenticated customer reads | 20 req/min | Per user session |
| Staff writes | 60 req/min | Per user session |
| Scheduler jobs | N/A (server-side) | Daily batch |

> [!IMPORTANT]
> Rate limits should be enforced via Frappe's rate limiting middleware or a reverse proxy (Nginx `limit_req`). The exact implementation depends on the deployment architecture.

---

## Related

- [[Flats MOC|🧱 Flats MOC]]
- [[Flats Overview|🏗️ Flats Variant Overview]]
