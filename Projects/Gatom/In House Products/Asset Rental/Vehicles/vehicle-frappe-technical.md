# Vehicle — Frappe: Technical Document

> **Product**: Asset Rental Platform  
> **Module**: `rental_vehicles` — Vehicle-Specific Backend  
> **Document Type**: Technical  
> **Audience**: Backend developers (Python/Frappe)  
> **Companion**: [vehicle-frappe-functional.md](./vehicle-frappe-functional.md)

---

## 1. App Scaffold

```bash
bench new-app rental_vehicles
# required_apps = ["frappe", "erpnext", "rental_core"]
bench --site rental.localhost install-app rental_vehicles
```

---

## 2. Directory Layout

```
rental_vehicles/
├── rental_vehicles/
│   ├── doctype/
│   │   ├── vehicle_category/
│   │   ├── vehicle_mileage_log/
│   │   ├── vehicle_service_record/
│   │   ├── vehicle_maintenance_schedule/
│   │   ├── vehicle_usage_profile/
│   │   ├── vehicle_inspection_checklist/
│   │   └── traffic_violation/
│   ├── api/
│   │   ├── vehicles.py
│   │   └── telematics.py
│   ├── utils/
│   │   ├── maintenance.py
│   │   ├── mileage.py
│   │   └── violations.py
│   ├── overrides/
│   │   └── rental_asset_override.py
│   ├── scheduler_events.py
│   ├── hooks.py
│   └── setup.py
```

---

## 3. Custom Fields Injected on Install (`setup.py`)

These fields are added to `Rental Asset` and only visible when `asset_type == "Vehicle"`:

```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    create_custom_fields({"Rental Asset": [
        # Section break — conditional visibility
        {"fieldname": "vehicle_section",           "fieldtype": "Section Break",
         "label": "Vehicle Details",
         "depends_on": "eval:doc.asset_type=='Vehicle'"},
        # Category and identification
        {"fieldname": "custom_category",           "fieldtype": "Link",   "options": "Vehicle Category"},
        {"fieldname": "custom_plate_number",       "fieldtype": "Data",   "unique": 1},
        {"fieldname": "custom_plate_country",      "fieldtype": "Link",   "options": "Country"},
        {"fieldname": "custom_make",               "fieldtype": "Data"},
        {"fieldname": "custom_model",              "fieldtype": "Data"},
        {"fieldname": "custom_year",               "fieldtype": "Int"},
        {"fieldname": "custom_color",              "fieldtype": "Data"},
        {"fieldname": "custom_vin",                "fieldtype": "Data",   "unique": 1},
        # Mechanical specs
        {"fieldname": "custom_fuel_type",          "fieldtype": "Select",
         "options": "Petrol\nDiesel\nElectric\nHybrid\nCNG"},
        {"fieldname": "custom_engine_cc",          "fieldtype": "Float"},
        {"fieldname": "custom_transmission",       "fieldtype": "Select",
         "options": "Manual\nAutomatic"},
        {"fieldname": "custom_seats",              "fieldtype": "Int"},
        # Mileage tracking
        {"fieldname": "custom_current_mileage_km",         "fieldtype": "Float"},
        {"fieldname": "custom_mileage_at_last_service_km", "fieldtype": "Float"},
        {"fieldname": "custom_next_service_km",            "fieldtype": "Float"},
        {"fieldname": "custom_next_service_date",          "fieldtype": "Date"},
        {"fieldname": "custom_usage_profile",              "fieldtype": "Select",
         "options": "Idle\nLight\nNormal\nHigh\nHeavy"},
        {"fieldname": "custom_fuel_level_pct",             "fieldtype": "Int"},
        # GPS
        {"fieldname": "custom_has_gps",            "fieldtype": "Check"},
        {"fieldname": "custom_gps_device_id",      "fieldtype": "Data"},
        # Documents
        {"fieldname": "custom_insurance_policy_number", "fieldtype": "Data"},
        {"fieldname": "custom_insurance_provider",      "fieldtype": "Data"},
        {"fieldname": "custom_insurance_expiry",        "fieldtype": "Date"},
        {"fieldname": "custom_insurance_doc",           "fieldtype": "Attach"},
        {"fieldname": "custom_registration_number",     "fieldtype": "Data"},
        {"fieldname": "custom_registration_expiry",     "fieldtype": "Date"},
        {"fieldname": "custom_registration_doc",        "fieldtype": "Attach"},
        {"fieldname": "custom_roadworthiness_expiry",   "fieldtype": "Date"},
        {"fieldname": "custom_roadworthiness_doc",      "fieldtype": "Attach"},
    ]})
```

---

## 4. DocType Schemas

### 4.1 `Vehicle Category`

| Field | Type | Notes |
|---|---|---|
| `category_name` | Data | |
| `type` | Select | Sedan, SUV, Van, Truck, Motorcycle, Bus, Special |
| `daily_rate` / `weekly_rate` / `monthly_rate` | Currency | |
| `included_km_per_day` | Float | |
| `overage_rate_per_km` | Currency | |
| `fuel_policy` | Select | Full-to-Full, Full-to-Empty, Pre-Purchase |
| `min_driver_age` | Int | |
| `required_license_class` | Data | e.g. "B", "C" |

### 4.2 `Vehicle Mileage Log`

| Field | Type | Notes |
|---|---|---|
| `agreement` | Link → Rental Agreement | |
| `vehicle` | Link → Rental Asset | |
| `log_type` | Select | `Pickup`, `Return`, `Mid-Term Check` |
| `log_date` | Date | |
| `odometer_reading_km` | Float | |
| `fuel_level_pct` | Int | 0–100 |
| `driven_km` | Float | Computed on Return |
| `overage_km` | Float | Computed on Return |
| `overage_charge` | Currency | Computed on Return |
| `photo_odometer` | Attach | |
| `photo_fuel_gauge` | Attach | |
| `noted_by` | Link → User | |

**Controller — `on_submit` for Return type:**

```python
def on_submit(self):
    if self.log_type != "Return":
        return
    pickup = frappe.db.get_value("Vehicle Mileage Log", {
        "agreement": self.agreement, "log_type": "Pickup", "docstatus": 1,
    }, "odometer_reading_km")
    if not pickup:
        frappe.throw("No submitted Pickup log found for this agreement.")

    agr = frappe.get_doc("Rental Agreement", self.agreement)
    category = frappe.get_doc("Vehicle Category",
        frappe.db.get_value("Rental Asset", agr.asset, "custom_category"))
    rental_days = (getdate(agr.end_date or today()) - getdate(agr.start_date)).days or 1

    self.driven_km = self.odometer_reading_km - pickup
    included = category.included_km_per_day * rental_days
    self.overage_km = max(0, self.driven_km - included)
    self.overage_charge = self.overage_km * category.overage_rate_per_km

    if self.overage_charge > 0:
        _append_overage_to_invoice(agr, self.overage_charge, self.driven_km, included)

    # Update asset's current mileage
    frappe.db.set_value("Rental Asset", agr.asset,
        "custom_current_mileage_km", self.odometer_reading_km)
```

### 4.3 `Vehicle Maintenance Schedule`

| Field | Type | Notes |
|---|---|---|
| `vehicle` | Link → Rental Asset | |
| `trigger_type` | Select | Mileage-High, Mileage-Low, Calendar, Manual |
| `scheduled_date` | Date | |
| `scheduled_end_date` | Date | |
| `estimated_duration_days` | Int | |
| `status` | Select | Planned, In Progress, Completed, Cancelled |
| `service_type` | Select | Oil Change, Tyres, Brakes, Full Service, Other |
| `notes` | Text | |
| `linked_service_record` | Link → Vehicle Service Record | |

### 4.4 `Traffic Violation`

| Field | Type |
|---|---|
| `vehicle` | Link → Rental Asset |
| `agreement` | Link → Rental Agreement |
| `violation_date` | Date |
| `violation_type` | Select: Speeding, Parking, Signal, Other |
| `authority` | Data |
| `fine_amount` | Currency |
| `charge_to` | Select: Tenant, Fleet Account |
| `status` | Select: Open, Paid, Disputed |
| `evidence_doc` | Attach |

---

## 5. Maintenance Conflict Validation (`utils/mileage.py`)

Called from `doc_events["Rental Agreement"]["validate"]`:

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
        dates = ", ".join(
            f"{c.scheduled_date} → {c.scheduled_end_date}" for c in conflicts)
        frappe.throw(
            f"This vehicle has planned maintenance overlapping your requested dates: "
            f"{dates}. Please choose different rental dates.")
```

---

## 6. Usage Profile Engine (`scheduler_events.py`)

```python
PROFILE_THRESHOLDS = [
    ("Heavy",  8000, 2000,  None),
    ("High",   4000, 5000,  None),
    ("Normal", 1500, 8000,  120),
    ("Light",   300, 10000, 180),
    ("Idle",      0,  None, 180),
]

def update_usage_profiles():
    for v in frappe.get_all("Rental Asset",
            filters={"asset_type": "Vehicle", "is_active": 1}, pluck="name"):
        km_30d = _compute_30d_km(v)
        profile, service_km_interval, service_day_interval = _classify(km_30d)
        frappe.db.set_value("Rental Asset", v, "custom_usage_profile", profile)
        _maybe_schedule_maintenance(v, profile, service_km_interval, service_day_interval)

def _compute_30d_km(vehicle: str) -> float:
    cutoff = add_days(today(), -30)
    rows = frappe.db.sql("""
        SELECT SUM(driven_km) FROM `tabVehicle Mileage Log`
        WHERE vehicle = %s AND docstatus = 1 AND log_type = 'Return'
        AND log_date >= %s
    """, (vehicle, cutoff))
    return rows[0][0] or 0.0
```

---

## 7. GPS Telematics — Raw SQL Ingestion

GPS events bypass the ORM for performance (high frequency ingestion):

```sql
-- Run once via bench execute or migration
CREATE TABLE IF NOT EXISTS `tabVehicle GPS Event` (
    `name`      VARCHAR(20)  PRIMARY KEY,
    `device_id` VARCHAR(50)  NOT NULL,
    `asset`     VARCHAR(140),
    `lat`        DECIMAL(10,7),
    `lng`        DECIMAL(10,7),
    `speed_kmh`  SMALLINT,
    `timestamp`  DATETIME     NOT NULL,
    INDEX idx_asset_ts (`asset`, `timestamp`)
) ENGINE=InnoDB;
```

Webhook endpoint:

```python
# api/telematics.py
@frappe.whitelist(allow_guest=True)
def receive_gps_event():
    payload = frappe.request.get_json()
    _verify_hmac(payload, frappe.get_single("Rental Configuration").gps_webhook_secret)
    frappe.db.sql("""
        INSERT INTO `tabVehicle GPS Event`
        (name, device_id, asset, lat, lng, speed_kmh, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (
        frappe.generate_hash(8),
        payload["device_id"],
        _resolve_asset(payload["device_id"]),
        payload["lat"], payload["lng"],
        payload.get("speed", 0),
        payload["ts"],
    ))
    frappe.db.commit()
```

---

## 8. `hooks.py`

```python
required_apps = ["frappe", "erpnext", "rental_core"]

scheduler_events = {
    "daily": [
        "rental_vehicles.scheduler_events.update_usage_profiles",
        "rental_vehicles.scheduler_events.alert_insurance_expiry",
        "rental_vehicles.scheduler_events.alert_registration_expiry",
        "rental_vehicles.scheduler_events.alert_roadworthiness_expiry",
    ],
}

doc_events = {
    "Rental Agreement": {
        "validate": "rental_vehicles.utils.mileage.validate_no_maintenance_conflict",
    },
}

override_doctype_class = {
    "Rental Asset": "rental_vehicles.overrides.rental_asset_override.VehicleAsset",
}
```

---

## 9. REST API Endpoints

```python
# api/vehicles.py

@frappe.whitelist()
def get_vehicle_detail(asset_name): ...
# Returns: custom_category, plate_number, make, model, year, fuel_type,
#          transmission, seats, engine_cc, insurance_expiry, registration_expiry

@frappe.whitelist()
def log_mileage(agreement, log_type, odometer_reading_km, fuel_level_pct,
                photo_odometer=None, photo_fuel_gauge=None): ...
# Creates + submits a Vehicle Mileage Log; returns computed overage on Return type

@frappe.whitelist()
def get_mileage_history(agreement): ...
# Returns list of submitted mileage logs for the agreement

@frappe.whitelist()
def get_vehicle_location(asset_name): ...
# Returns: last GPS event (lat, lng, speed, timestamp) — Fleet Manager role only

@frappe.whitelist()
def get_maintenance_schedule(asset_name): ...
# Returns all Planned + In Progress maintenance windows for availability display

@frappe.whitelist()
def report_traffic_violation(agreement, violation_type, fine_amount,
                              violation_date, authority, evidence_doc=None): ...
```

---

## 10. Vehicle Inspection Checklist (child rows provided to `Asset Inspection`)

| Area | Items |
|---|---|
| Exterior | Front/Rear bumper, Driver/Passenger doors, Roof, Bonnet, Boot, Windscreen, All windows, Lights, Mirrors |
| Interior | Dashboard, Seats, Seatbelts, Carpets, Headliner, A/C |
| Mechanicals | Tyre condition (FL/FR/RL/RR), Spare tyre, Oil, Coolant, Brake fluid |
| Keys/Docs | Ignition key, Remote/fob, Registration card, Insurance card |

Each row: `condition` (Good / Damaged / Missing), `photo`, `deduct_from_deposit`, `estimated_repair_cost`.

---

## 11. Implementation Phases

| Phase | Deliverables |
|---|---|
| **1** | Custom fields, Vehicle Category, Mileage Log + overage billing, inspection checklist |
| **2** | Insurance/registration validation, scheduler alerts, conflict-blocking on Agreement validate |
| **3** | GPS webhook + raw SQL table, usage profile engine, maintenance scheduling |
| **4** | Traffic violation workflow, roadworthiness tracking |

---

## 12. Testing Checklist

- [ ] Agreement validation throws error if vehicle registration is expired
- [ ] Agreement validation throws error if maintenance window overlaps dates (with dates listed)
- [ ] Return mileage log computes `driven_km`, `overage_km`, `overage_charge` correctly
- [ ] Overage charge is appended to the final Sales Invoice
- [ ] `update_usage_profiles` scheduler runs and updates `custom_usage_profile` on assets
- [ ] GPS webhook stores event in `tabVehicle GPS Event` raw table
- [ ] `get_vehicle_location` returns 403 for non-Fleet-Manager role
- [ ] Insurance expiry alert fires at 30 days and 7 days before expiry
