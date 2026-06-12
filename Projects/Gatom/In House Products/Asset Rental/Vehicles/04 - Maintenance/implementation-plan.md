# Domain V04 — Maintenance: Implementation Plan

> **Variant**: Vehicles (child app `rental_vehicles`)
> **Domain**: Maintenance Scheduling
> **Sequence**: 4 of 7
> **Depends on**: V01 (custom fields for mileage/usage profile), V03 (Mileage Log for driven_km data), Base D05 (Rental Agreement for conflict detection)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]]

---

## 1. Overview

Vehicle maintenance is fundamentally different from property maintenance — it's driven by **usage patterns** (how many km the vehicle has driven) rather than calendar schedules alone. This domain implements a **5-tier usage profiling system** that classifies each vehicle daily (Idle → Light → Normal → High → Heavy) and adjusts the maintenance interval accordingly. Heavy-use vehicles (ride-sharing, delivery) need service every 2,000 km; idle vehicles need service every 6 months regardless of mileage.

The domain also handles **reservation conflict detection**: planned maintenance windows block the vehicle's availability calendar. If a maintenance window overlaps an existing confirmed reservation, the Fleet Manager is notified to resolve the conflict (typically by rescheduling maintenance or moving the customer to another vehicle).

Maintenance management is entirely **Desk-managed** — the only customer-facing impact is that maintenance windows appear as blocked dates on the availability calendar with no reason disclosed.

---

## 2. Frappe — Usage Profile Engine

### 2.1 `update_usage_profiles` Scheduler Job

> **Requires**: V01-2.2 (hooks.py daily scheduler), V03-2.1 (Vehicle Mileage Log for driven_km data), V01-2.3 (`custom_usage_profile` field)

Unlike a flat (which needs maintenance on a calendar schedule — quarterly HVAC filter changes regardless of occupancy), a vehicle's maintenance needs are driven by **how much it's used**. A ride-sharing sedan that drives 300 km/day needs an oil change every 2-3 weeks. A backup van that sits in the lot and drives 100 km/month needs service every 6 months. Scheduling maintenance on a fixed calendar ("service every 3 months") would either waste money on lightly-used vehicles or miss critical service intervals on heavily-used ones.

The **usage profiling engine** solves this by classifying each vehicle daily into one of 5 tiers (Idle, Light, Normal, High, Heavy) based on how far it's driven in the last 30 days. Each tier maps to a maintenance interval: Heavy-use vehicles get serviced every 2,000 km, while Idle vehicles get serviced every 180 days regardless of mileage. The profile is stored on the `Rental Asset` record and consumed by the maintenance scheduler to determine when to create the next service appointment.

The 5 tiers and their thresholds were designed based on standard fleet management industry practices:

| Profile | 30-day km | Service Interval |
|---|---|---|
| **Heavy** | > 8,000 km | Every 2,000 km |
| **High** | 4,000–8,000 km | Every 5,000 km |
| **Normal** | 1,500–4,000 km | Every 8,000 km (or 120 days) |
| **Light** | 300–1,500 km | Every 10,000 km (or 180 days) |
| **Idle** | < 300 km | Every 180 days (calendar-based) |

After classification, the engine checks whether the vehicle needs maintenance scheduled based on the new interval and the distance since last service (`custom_mileage_at_last_service_km`). For mileage-triggered profiles (Heavy, High, Normal, Light): if `current_mileage - last_service_mileage >= interval_km`, maintenance is scheduled. For calendar-triggered profiles (Idle, and calendar fallbacks for Normal/Light): if `days_since_last_service >= interval_days`, maintenance is scheduled. When maintenance is needed, the engine calls `_maybe_schedule_maintenance()` to create a `Vehicle Maintenance Schedule` record (3.1).

```python
PROFILE_THRESHOLDS = [
    ("Heavy",  8000, 2000,  None),
    ("High",   4000, 5000,  None),
    ("Normal", 1500, 8000,  120),
    ("Light",   300, 10000, 180),
    ("Idle",      0,  None, 180),
]
```

**Acceptance Criteria**:
- [ ] Vehicle with 9,000 km in 30 days → classified as `Heavy`
- [ ] Vehicle with 5,000 km in 30 days → classified as `High`
- [ ] Vehicle with 2,500 km in 30 days → classified as `Normal`
- [ ] Vehicle with 800 km in 30 days → classified as `Light`
- [ ] Vehicle with 100 km in 30 days → classified as `Idle`
- [ ] `custom_usage_profile` field on Rental Asset is updated
- [ ] Scheduler runs at 2 AM daily (off-peak)
- [ ] Only active vehicles (`is_active = 1`) are processed
- [ ] Non-Vehicle assets are excluded
- [ ] Scheduler runs without error when no vehicles have mileage logs

---

### 2.2 30-Day Km Computation (`_compute_30d_km`)

> **Requires**: V03-2.1 (Vehicle Mileage Log)

The usage profile classification depends on knowing how far each vehicle has driven recently. This helper function computes the **total kilometres driven in the last 30 days** for a specific vehicle by querying the `Vehicle Mileage Log` table (from V03).

The computation sums `driven_km` from all submitted (`docstatus = 1`) Return-type mileage logs where `log_date` falls within the last 30 days. Only Return logs are used because `driven_km` is only computed when a vehicle is returned — Pickup and Mid-Term logs don't have this field populated.

The SQL query uses an index on `(vehicle, log_date)` for performance — in a fleet of 500+ vehicles, scanning every mileage log in the table would be slow. A vehicle with no Return logs in the last 30 days (e.g., parked in the lot with no rentals) returns 0.0 and is classified as `Idle`.

**Acceptance Criteria**:
- [ ] Sums `driven_km` from all submitted Return logs in the last 30 days
- [ ] Only includes `docstatus = 1` (submitted) logs
- [ ] Only includes `log_type = 'Return'` logs
- [ ] Vehicle with no Return logs → returns 0.0
- [ ] Query uses index on `(vehicle, log_date)` for performance

---

## 3. Frappe — Maintenance Schedule DocType

### 3.1 `Vehicle Maintenance Schedule` Schema

> **Requires**: V01-2.1 (app scaffold)

The **Maintenance Schedule** is a planned service appointment for a vehicle. It represents a future window of time when the vehicle will be unavailable for rental because it's being serviced. This is the fleet equivalent of a calendar event — it blocks the vehicle's availability and can be tracked through a lifecycle.

Each schedule has a `trigger_type` that records *why* the maintenance was scheduled: `Mileage-High` (the usage profiler detected the vehicle exceeded its mileage-based interval), `Mileage-Low` (the vehicle hit a calendar-based interval because it's idle), `Calendar` (time-based scheduling independent of mileage), or `Manual` (the Fleet Manager manually scheduled maintenance, e.g., after a breakdown or customer complaint about unusual noise).

The status lifecycle tracks the work through completion: `Planned` (scheduled but not started — the vehicle is still available until the scheduled date), `In Progress` (currently at the service centre), `Completed` (work done, vehicle returned to fleet), or `Cancelled` (the Fleet Manager decided the maintenance wasn't needed). Only `Planned` and `In Progress` windows block the vehicle's availability calendar — completed and cancelled windows are historical records.

| Field | Type | Notes |
|---|---|---|
| `vehicle` | Link → Rental Asset | |
| `trigger_type` | Select | `Mileage-High`, `Mileage-Low`, `Calendar`, `Manual` |
| `scheduled_date` | Date | Start of maintenance window |
| `scheduled_end_date` | Date | End of maintenance window |
| `estimated_duration_days` | Int | |
| `status` | Select | `Planned`, `In Progress`, `Completed`, `Cancelled` |
| `service_type` | Select | `Oil Change`, `Tyres`, `Brakes`, `Full Service`, `Other` |
| `notes` | Text | |
| `linked_service_record` | Link → Vehicle Service Record | Created on completion |

**Acceptance Criteria**:
- [ ] DocType created in Frappe Desk
- [ ] `trigger_type` includes: `Mileage-High`, `Mileage-Low`, `Calendar`, `Manual`
- [ ] `status` transitions: `Planned` → `In Progress` → `Completed`; `Planned` → `Cancelled`
- [ ] `Completed` requires a linked `Vehicle Service Record`
- [ ] Fleet Manager can create/edit; Rental Agent has read-only access
- [ ] `scheduled_end_date` must be ≥ `scheduled_date` (validation)
- [ ] Manual creation allowed (not only via scheduler)

---

### 3.2 `Vehicle Service Record` Schema

> **Requires**: 3.1

When maintenance is **completed**, the Fleet Manager needs to record what was actually done — which parts were replaced, who did the work, how much it cost, and at what mileage. This service record serves multiple business purposes: (1) **maintenance history** for the vehicle's lifecycle — essential when selling the vehicle or proving warranty compliance, (2) **cost tracking** — aggregating service costs per vehicle helps identify money pits, (3) **audit trail** — compliance audits may require proof that fleet vehicles are properly maintained, and (4) **mileage reset** — the `odometer_at_service_km` becomes the new baseline for the next service interval calculation.

When a service record is created and linked to a maintenance schedule: the schedule's status automatically transitions to `Completed`, the vehicle's `custom_mileage_at_last_service_km` is updated to the service odometer reading, and `custom_next_service_km` is computed by adding the current usage profile's service interval to the current mileage.

Service records are **Fleet Manager-only** — customers never see them. The internal maintenance details (parts, costs, technician names) are business intelligence that shouldn't be customer-visible.

| Field | Type | Notes |
|---|---|---|
| `vehicle` | Link → Rental Asset | |
| `service_date` | Date | |
| `odometer_at_service_km` | Float | |
| `service_type` | Select | Same as Maintenance Schedule |
| `technician` | Data | Name of the technician |
| `cost` | Currency | Total maintenance cost |
| `parts_replaced` | Text | Description of parts |
| `notes` | Text | |
| `maintenance_schedule` | Link → Vehicle Maintenance Schedule | Back-link |

**Acceptance Criteria**:
- [ ] DocType created in Frappe Desk
- [ ] Creating a service record updates the vehicle's `custom_mileage_at_last_service_km`
- [ ] Creating a service record updates `custom_next_service_km` based on usage profile
- [ ] Linked `maintenance_schedule` status set to `Completed` automatically
- [ ] Fleet Manager has full CRUD
- [ ] Customer CANNOT see service records

---

## 4. Frappe — Reservation Conflict Detection

### 4.1 `validate_no_maintenance_conflict` Hook

> **Requires**: 3.1, V01-2.2 (registered in hooks.py `doc_events`)

This is a **critical safety check** that prevents double-booking a vehicle during its maintenance window. Imagine a customer tries to book a sedan from March 5–15, but the sedan has planned tyre replacement from March 8–10. Without this validation, the system would create the agreement and the customer would show up on March 5 expecting a car that's sitting on blocks in the garage on March 8.

The validation hook fires whenever a `Rental Agreement` is saved or submitted (`validate` event). It queries all `Planned` and `In Progress` maintenance windows for the vehicle and checks for date overlap using standard interval intersection logic: `scheduled_date <= rental_end_date AND scheduled_end_date >= rental_start_date`.

If there's a conflict, the agreement is **rejected with a `frappe.throw()`** that lists the conflicting maintenance dates. The Fleet Manager then has three options: (1) reschedule the maintenance to after the rental, (2) cancel the maintenance window, or (3) offer the customer alternative dates or a different vehicle.

The hook returns early for non-Vehicle assets (flats don't have maintenance windows). For open-ended agreements (no `end_date`), a far-future fallback of 2099-12-31 is used — this means any future maintenance window would conflict, which is the safe default.

```python
def validate_no_maintenance_conflict(agreement, method=None):
    if frappe.db.get_value("Rental Asset", agreement.asset, "asset_type") != "Vehicle":
        return
    end = agreement.end_date or "2099-12-31"
    conflicts = frappe.get_all("Vehicle Maintenance Schedule", filters={
        "vehicle": agreement.asset,
        "status": ["in", ["Planned", "In Progress"]],
        "scheduled_date": ["<=", end],
        "scheduled_end_date": [">=", agreement.start_date],
    }, fields=["scheduled_date", "scheduled_end_date"])
    if conflicts:
        dates = ", ".join(f"{c.scheduled_date} → {c.scheduled_end_date}" for c in conflicts)
        frappe.throw(
            f"This vehicle has planned maintenance overlapping your requested dates: "
            f"{dates}. Please choose different rental dates.")
```

**Acceptance Criteria**:
- [ ] Rental dates overlap maintenance window → `frappe.throw` with conflicting dates listed
- [ ] Rental dates do not overlap → agreement proceeds normally
- [ ] `Completed` maintenance windows → no conflict (already done)
- [ ] `Cancelled` maintenance windows → no conflict (no longer planned)
- [ ] Non-Vehicle assets → hook returns early (no check)
- [ ] Agreement with no `end_date` → uses 2099-12-31 as fallback for open-ended rentals

---

### 4.2 Retroactive Conflict Notification

> **Requires**: 3.1, Base D07 (notification system)

The conflict validation hook (4.1) prevents *new* bookings from overlapping maintenance. But what happens when a Fleet Manager creates an *urgent* maintenance window that overlaps an *existing* confirmed reservation? For example, a vehicle develops an oil leak and needs emergency service from March 8–10, but it already has a confirmed rental from March 5–15.

The system **cannot block** the maintenance creation — the maintenance may be safety-critical. Instead, it sends a **notification** to the Fleet Manager immediately after the maintenance schedule is saved, listing all conflicting reservations. The notification includes: vehicle name, conflicting agreement names, customer names, and the overlapping dates.

The Fleet Manager is then responsible for resolving the conflict — typically by calling the customer to arrange a vehicle swap ("We're moving you from the white Camry to the silver Camry for March 8–10") or rescheduling the customer to different dates.

The notification is logged in `Rental Notification Log` with `notification_type = Booking Status` for audit purposes. If the maintenance window doesn't overlap any existing reservations, no notification is sent.

**Acceptance Criteria**:
- [ ] New maintenance window overlapping existing confirmed reservation → notification sent to Fleet Manager
- [ ] Notification includes: vehicle name, conflicting agreement names, conflicting dates
- [ ] Maintenance window is still created (not blocked)
- [ ] Notification logged in `Rental Notification Log` with `notification_type = Booking Status`
- [ ] No notification when no conflicts exist

---

## 5. Web — Maintenance Calendar Integration

### 5.1 Availability Calendar — Maintenance Blocking

> **Requires**: V01-4.2 (maintenance schedule API), Base D01-7.2 (detail page with calendar)

The customer should never know that a vehicle is unavailable because of maintenance vs. another booking — from their perspective, the dates are simply "unavailable." This subtask ensures that **maintenance-blocked dates** are merged into the vehicle's availability calendar alongside booking-blocked dates, using the same visual treatment (greyed out, non-selectable).

The implementation queries `Vehicle Maintenance Schedule` for windows with `status IN ('Planned', 'In Progress')` and merges those date ranges into the calendar data already provided by the base availability API. Completed and Cancelled windows are not included — those dates are available again.

The important thing here is that the calendar **never discloses the reason** for unavailability. Whether a date is blocked by another customer's booking, planned maintenance, or a management hold, it all looks the same. This protects business intelligence (utilization rates, maintenance frequency) and prevents customers from making assumptions about vehicle reliability.

**Acceptance Criteria**:
- [ ] Maintenance-blocked dates appear as unavailable on the calendar
- [ ] No reason is shown (the customer sees the same "unavailable" styling as booked dates)
- [ ] Completed/Cancelled maintenance windows do NOT block the calendar
- [ ] Only `Planned` and `In Progress` windows block dates

---

## 6. Cross-Cutting Concerns

### 6.1 Logging

All critical decision points in this domain must emit structured log entries for auditability and debugging:

| Location | Log Level | What to Log |
|---|---|---|
| `update_usage_profiles` scheduler | `INFO` | Total vehicles processed, profile transitions (e.g., "Vehicle X: Normal → Heavy"), execution time |
| `_compute_30d_km` | `DEBUG` | Vehicle name, return log count in 30-day window, computed total km |
| `_maybe_schedule_maintenance` | `INFO` | Vehicle name, trigger type, scheduled dates, conflict status |
| `validate_no_maintenance_conflict` — block | `WARNING` | Agreement name, vehicle name, conflicting maintenance dates, user who attempted booking |
| `validate_no_maintenance_conflict` — pass | `DEBUG` | Agreement name, vehicle name, no conflicts found |
| Retroactive conflict notification | `INFO` | Maintenance schedule name, conflicting agreement names, notification sent to Fleet Manager |
| Service record creation | `INFO` | Vehicle name, service type, odometer at service, cost, next service milestone |
| Maintenance status transition | `INFO` | Schedule name, old status → new status, transitioned by user |
| Calendar integration query | `DEBUG` | Vehicle name, window count merged into availability calendar |

**Acceptance Criteria**:
- [ ] Usage profile transitions logged at `INFO` (only when profile changes, not every vehicle every day)
- [ ] Maintenance conflict blocks logged at `WARNING` with full context
- [ ] Service record creation logged with mileage reset details
- [ ] Structured logging uses `frappe.logger()` with the `rental_vehicles` namespace
- [ ] Scheduler execution time logged for performance monitoring

---

### 6.2 Caching

| Data | Cache Key Pattern | TTL | Invalidation Trigger |
|---|---|---|---|
| Vehicle usage profiles (batch) | `usage_profiles:batch:{date}` | 24 hr | Scheduler re-run (daily) |
| 30-day km computation | `vehicle_30d_km:{vehicle_name}` | 6 hr | Vehicle Mileage Log submission |
| Maintenance schedule windows (per vehicle) | `maint_windows:{vehicle_name}` | 15 min | Vehicle Maintenance Schedule create/update |
| Service record history (per vehicle) | `service_history:{vehicle_name}` | 30 min | Vehicle Service Record create |

**Implementation**: Use Frappe's `frappe.cache()` (Redis-backed). The 30-day km computation cache is particularly important because the scheduler queries all vehicles daily — caching reduces the repeated mileage log table scans.

**Acceptance Criteria**:
- [ ] 30-day km computation cached with 6-hour TTL (refreshed by daily scheduler)
- [ ] Maintenance window cache invalidated on schedule create/update/status change
- [ ] Scheduler does NOT rely on stale cache for profile classification (computes fresh daily)
- [ ] Service history cache invalidated when new service records are created

---

### 6.3 Rate Limiting

This domain is primarily Desk-managed with server-side schedulers. The calendar integration API is the only endpoint exposed to customers:

| Endpoint | Limit | Scope | Response on Limit |
|---|---|---|---|
| Calendar integration (maintenance windows) | 30 req/min | Per IP / Per user | HTTP 429 with `Retry-After` header |
| Maintenance Schedule CRUD (Desk) | Frappe default | Per user session | Standard Frappe rate limiting |
| Scheduler jobs | N/A (server-side) | Daily batch at 2 AM | Not applicable |

**Acceptance Criteria**:
- [ ] Calendar API rate-limited to prevent scraping of maintenance schedule patterns
- [ ] Scheduler protected by Frappe's built-in scheduler lock (no parallel execution)
- [ ] Manual maintenance creation (Desk) uses standard Frappe rate limiting

---

### 6.4 Security Validation

| Check | Location | Rule |
|---|---|---|
| `asset_type` filter | `validate_no_maintenance_conflict` | Early return for non-Vehicle assets |
| Open-ended agreement safety | Conflict detection | No `end_date` → uses 2099-12-31 fallback (safe default: all future maintenance conflicts) |
| Calendar reason hiding | Availability calendar API | Customer response never discloses why a date is blocked (maintenance vs booking) |
| Service record role gate | `Vehicle Service Record` DocType | Only Fleet Manager can create/view; Customer CANNOT see service records |
| Maintenance Schedule role gate | `Vehicle Maintenance Schedule` DocType | Fleet Manager: full CRUD; Rental Agent: read-only; Customer: no access |
| Status transition enforcement | Maintenance Schedule workflow | `Completed` requires linked `Vehicle Service Record`; `Planned` → `In Progress` → `Completed` |
| Retroactive notification | Conflict notification | Notifications logged in `Rental Notification Log` for audit (tamper-proof) |
| Scheduler execution isolation | `update_usage_profiles` | Only processes `is_active = 1` vehicles; non-Vehicle assets excluded |

**Acceptance Criteria**:
- [ ] Customers never see maintenance schedule details (service type, cost, technician)
- [ ] Calendar shows blocked dates without reason (indistinguishable from bookings)
- [ ] Service records restricted to Fleet Manager role
- [ ] Status transitions enforce the correct sequence (Planned → In Progress → Completed)
- [ ] Open-ended agreements correctly use far-future fallback for conflict detection
- [ ] Inactive vehicles excluded from usage profiling

---

## 7. Domain-Level Acceptance Criteria

- [ ] Usage profile updated daily for all active vehicles
- [ ] Profile classification matches the 5-tier table
- [ ] Maintenance scheduled automatically when vehicle exceeds service interval
- [ ] Reservation conflict detection blocks overlapping bookings
- [ ] Retroactive maintenance overlapping existing reservations → notification to Fleet Manager
- [ ] Completed maintenance creates a service record and updates last-service mileage
- [ ] Maintenance-blocked dates visible on availability calendar (no reason disclosed)

---

## 8. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (usage profiling + Maintenance Schedule + Service Record + conflict hooks + notifications) | 5 days |
| Web (calendar integration) | 0.5 days |
| Flutter (N/A — maintenance is Desk-only; calendar blocking handled by base) | 0 days |
| **Total** | **5.5 days** |
