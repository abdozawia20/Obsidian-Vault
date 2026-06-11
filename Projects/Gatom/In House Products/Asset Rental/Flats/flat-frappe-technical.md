# Flat — Frappe: Technical Document

> **Product**: Asset Rental Platform  
> **Module**: `rental_flats` — Flat-Specific Backend  
> **Document Type**: Technical  
> **Audience**: Backend developers (Python/Frappe)  
> **Companion**: [flat-frappe-functional.md](./flat-frappe-functional.md)

---

## 1. App Scaffold

```bash
bench new-app rental_flats
# required_apps = ["frappe", "erpnext", "rental_core"]
bench --site rental.localhost install-app rental_flats
```

---

## 2. Directory Layout

```
rental_flats/
├── rental_flats/
│   ├── doctype/
│   │   ├── rental_property/
│   │   ├── rental_building/
│   │   │   └── building_amenity.json       ← child table
│   │   ├── utility_meter_reading/
│   │   ├── flat_insurance_policy/
│   │   │   └── coverage_period.json
│   │   └── flat_inspection_checklist/      ← child of Asset Inspection
│   ├── api/
│   │   └── flats.py
│   ├── utils/
│   │   ├── utility_billing.py
│   │   └── insurance_validator.py
│   ├── scheduler_events.py
│   ├── hooks.py
│   └── setup.py
```

---

## 3. Custom Fields Injected on Install (`setup.py`)

```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def after_install():
    create_custom_fields({"Rental Asset": [
        {"fieldname": "flat_section",              "fieldtype": "Section Break",
         "depends_on": "eval:doc.asset_type=='Flat'"},
        {"fieldname": "custom_property",           "fieldtype": "Link",  "options": "Rental Property"},
        {"fieldname": "custom_building",           "fieldtype": "Link",  "options": "Rental Building"},
        {"fieldname": "custom_unit_number",        "fieldtype": "Data"},
        {"fieldname": "custom_floor_number",       "fieldtype": "Int"},
        {"fieldname": "custom_area_sqm",           "fieldtype": "Float"},
        {"fieldname": "custom_living_area_sqm",    "fieldtype": "Float"},
        {"fieldname": "custom_bedrooms",           "fieldtype": "Int"},
        {"fieldname": "custom_bathrooms",          "fieldtype": "Int"},
        {"fieldname": "custom_balcony",            "fieldtype": "Check"},
        {"fieldname": "custom_storage_room",       "fieldtype": "Check"},
        {"fieldname": "custom_parking_included",   "fieldtype": "Check"},
        {"fieldname": "custom_parking_slot_number","fieldtype": "Data"},
        {"fieldname": "custom_furnished",          "fieldtype": "Select",
         "options": "Unfurnished\nSemi-Furnished\nFully Furnished"},
        {"fieldname": "custom_appliances",         "fieldtype": "Table", "options": "Flat Appliance"},
        {"fieldname": "custom_floor_plan",         "fieldtype": "Attach"},
        {"fieldname": "custom_direction_facing",   "fieldtype": "Select",
         "options": "North\nSouth\nEast\nWest\nCorner"},
        {"fieldname": "custom_view_type",          "fieldtype": "Select",
         "options": "Street\nGarden\nSea\nCity\nInternal"},
        {"fieldname": "custom_electricity_meter_id","fieldtype": "Data"},
        {"fieldname": "custom_water_meter_id",     "fieldtype": "Data"},
        {"fieldname": "custom_gas_meter_id",       "fieldtype": "Data"},
        {"fieldname": "custom_utilities_included", "fieldtype": "Check"},
        {"fieldname": "custom_max_occupants",      "fieldtype": "Int"},
        {"fieldname": "custom_pets_allowed",       "fieldtype": "Check"},
        {"fieldname": "custom_smoking_allowed",    "fieldtype": "Check"},
        {"fieldname": "custom_key_count",          "fieldtype": "Int"},
        {"fieldname": "custom_access_code",        "fieldtype": "Password"},
    ]})
    # Singleton config extension: country insurance requirements
    create_custom_fields({"Rental Configuration": [
        {"fieldname": "country_insurance_requirements", "fieldtype": "Table",
         "options": "Country Insurance Requirement"},
    ]})
```

---

## 4. DocType Schemas

### 4.1 `Rental Property`

| Field | Type |
|---|---|
| `property_name` | Data |
| `property_code` | Data (auto: PROP-XXXX) |
| `address` / `city` / `country` | Data / Link |
| `geo_lat` / `geo_lng` | Float |
| `managed_by` | Link → User |
| `amenities` | Table → Property Amenity |

### 4.2 `Rental Building`

| Field | Type |
|---|---|
| `building_name` | Data |
| `property` | Link → Rental Property |
| `floors` | Int |
| `has_elevator` | Check |
| `parking_slots` | Int |
| `service_charge_monthly` | Currency |
| `amenities` | Table → Building Amenity |

### 4.3 `Utility Meter Reading`

| Field | Type | Notes |
|---|---|---|
| `flat` | Link → Rental Asset | |
| `agreement` | Link → Rental Agreement | |
| `meter_type` | Select | Electricity, Water, Gas |
| `reading_date` | Date | |
| `previous_reading` | Float | Auto-fetched |
| `current_reading` | Float | |
| `consumption` | Float | Computed |
| `unit_rate` | Currency | From config |
| `total_charge` | Currency | Computed |
| `reading_photo` | Attach | |
| `entered_by` | Link → User | |
| `billed` | Check | Set on invoice injection |

**Controller — `validate()`:**

```python
def validate(self):
    # Auto-fetch previous reading
    prev = frappe.db.get_value("Utility Meter Reading",
        filters={"flat": self.flat, "meter_type": self.meter_type, "docstatus": 1},
        fieldname="current_reading",
        order_by="reading_date desc",
    )
    self.previous_reading = prev or self.current_reading  # first reading = 0 consumption
    self.consumption  = self.current_reading - self.previous_reading
    config = frappe.get_single("Rental Configuration")
    rate_field = {
        "Electricity": "electricity_rate_per_unit",
        "Water":       "water_rate_per_unit",
        "Gas":         "gas_rate_per_unit",
    }[self.meter_type]
    self.unit_rate    = getattr(config, rate_field) or 0
    self.total_charge = self.consumption * self.unit_rate
```

**Controller — `on_submit()`:**

```python
def on_submit(self):
    from rental_flats.utils.utility_billing import inject_reading_into_invoice
    inject_reading_into_invoice(self)
```

### 4.4 `Flat Insurance Policy`

| Field | Type |
|---|---|
| `flat` | Link → Rental Asset |
| `provider` | Data |
| `policy_number` | Data |
| `coverage_type` | Select (Earthquake, Flood, Fire, Structural, Liability, Theft, Water Damage, Storm, Subsidence, Personal Injury, Glass, Terrorism) |
| `start_date` / `expiry_date` | Date |
| `premium_amount` / `coverage_amount` | Currency |
| `policy_document` | Attach |
| `status` | Select: Active, Expired, Cancelled |

---

## 5. Utility Billing Engine (`utils/utility_billing.py`)

```python
def inject_reading_into_invoice(reading):
    """Called on reading submit. Find draft invoice for the agreement and inject the charge."""
    if not reading.total_charge or not reading.agreement:
        return

    draft_invoice = frappe.db.get_value("Sales Invoice", {
        "custom_rental_agreement": reading.agreement,
        "docstatus": 0,
    }, "name")

    if draft_invoice:
        inv = frappe.get_doc("Sales Invoice", draft_invoice)
        _append_utility_line(inv, reading)
        inv.save(ignore_permissions=True)
        frappe.db.set_value("Utility Meter Reading", reading.name, "billed", 1)
    # else: stays unbilled; will be swept by sweep_unbilled_utilities()

def sweep_unbilled_utilities(agreement_name: str, invoice_name: str):
    """Called by rental_core billing hook on new subscription invoice creation."""
    unbilled = frappe.get_all("Utility Meter Reading", filters={
        "agreement": agreement_name, "billed": 0, "docstatus": 1,
    }, fields=["name", "meter_type", "consumption", "unit_rate",
               "total_charge", "reading_date", "previous_reading", "current_reading"])
    if not unbilled:
        return
    inv = frappe.get_doc("Sales Invoice", invoice_name)
    for r in unbilled:
        _append_utility_line(inv, r)
        frappe.db.set_value("Utility Meter Reading", r.name, "billed", 1)
    inv.save(ignore_permissions=True)

def _append_utility_line(invoice, reading):
    invoice.append("items", {
        "item_code":  f"UTIL-{reading.meter_type.upper()}",
        "item_name":  f"{reading.meter_type} ({reading.reading_date})",
        "qty":        reading.consumption,
        "rate":       reading.unit_rate,
        "description": (f"{reading.meter_type}: {reading.previous_reading} "
                        f"→ {reading.current_reading} units"),
    })
```

---

## 6. Insurance Validator (`utils/insurance_validator.py`)

```python
def validate_flat_insurance(agreement, method=None):
    asset = frappe.get_doc("Rental Asset", agreement.asset)
    if asset.asset_type != "Flat":
        return

    config = frappe.get_single("Rental Configuration")
    required = [
        r.coverage_type
        for r in config.get("country_insurance_requirements", [])
        if r.country == config.country and r.mandatory
    ]
    if not required:
        return

    active_coverage = frappe.get_all("Flat Insurance Policy", filters={
        "flat":   agreement.asset,
        "status": "Active",
        "expiry_date": [">=", agreement.start_date],
    }, pluck="coverage_type")

    missing = [c for c in required if c not in active_coverage]
    if missing:
        _create_insurance_todo(agreement, missing, config.country)
        frappe.throw(
            f"Agreement blocked. Mandatory insurance missing for {config.country}: "
            f"{', '.join(missing)}. An internal reminder has been created for the "
            "property manager."
        )


def _create_insurance_todo(agreement, missing_types: list, country: str):
    asset = agreement.asset
    manager = frappe.db.get_value("Rental Asset", asset, "owner") or frappe.session.user
    frappe.get_doc({
        "doctype":        "ToDo",
        "owner":          manager,
        "assigned_by":    frappe.session.user,
        "priority":       "High",
        "date":           frappe.utils.add_days(frappe.utils.today(), 3),
        "description": (
            f"⚠️ Insurance gap on flat {asset} is blocking agreement {agreement.name}.\n"
            f"Country: {country}\n"
            f"Missing coverage: {', '.join(missing_types)}\n"
            "Please obtain or renew the required policies before the agreement can proceed."
        ),
        "reference_type": "Rental Agreement",
        "reference_name": agreement.name,
    }).insert(ignore_permissions=True)
```

---

## 7. `hooks.py`

```python
required_apps = ["frappe", "erpnext", "rental_core"]

scheduler_events = {
    "daily": [
        "rental_flats.scheduler_events.remind_utility_meter_readings",
        "rental_flats.scheduler_events.alert_appliance_warranty_expiry",
        "rental_flats.scheduler_events.check_flat_annual_inspection_due",
        "rental_flats.scheduler_events.alert_insurance_expiry",
    ],
}

doc_events = {
    "Rental Agreement": {
        "validate": "rental_flats.utils.insurance_validator.validate_flat_insurance",
    },
}

portal_menu_items = [
    {
        "title": "Utility Usage",
        "route": "/my-utilities",
        "reference_doctype": "Utility Meter Reading",
        "role": "Customer",
    },
]
```

---

## 8. Scheduler Events (`scheduler_events.py`)

```python
def remind_utility_meter_readings():
    """Fire on the 25th of each month."""
    from frappe.utils import today, getdate
    if getdate(today()).day != 25:
        return
    active = frappe.get_all("Rental Agreement", filters={
        "status": "Active",
    }, fields=["name", "asset"])
    for agr in active:
        if frappe.db.get_value("Rental Asset", agr.asset, "asset_type") == "Flat":
            # Check if readings already submitted this month
            this_month_start = frappe.utils.get_first_day(today())
            submitted = frappe.db.exists("Utility Meter Reading", {
                "agreement": agr.name, "docstatus": 1,
                "reading_date": [">=", this_month_start],
            })
            if not submitted:
                _notify_pm(agr, "Utility reading due for this month")

def alert_appliance_warranty_expiry():
    target = frappe.utils.add_days(frappe.utils.today(), 30)
    rows = frappe.db.sql("""
        SELECT fa.appliance_name, fa.warranty_expiry, fa.parent AS asset
        FROM `tabFlat Appliance` fa
        WHERE fa.warranty_expiry BETWEEN %s AND %s
    """, (frappe.utils.today(), target), as_dict=True)
    for r in rows:
        manager = frappe.db.get_value("Rental Asset", r.asset, "owner")
        frappe.sendmail(recipients=[manager],
            subject=f"Warranty expiring: {r.appliance_name}",
            message=f"Warranty for {r.appliance_name} in flat {r.asset} expires on {r.warranty_expiry}.")

def check_flat_annual_inspection_due():
    cutoff = frappe.utils.add_months(frappe.utils.today(), -11)
    active_flats = frappe.get_all("Rental Agreement",
        filters={"status": "Active"}, fields=["name", "asset"])
    for agr in active_flats:
        if frappe.db.get_value("Rental Asset", agr.asset, "asset_type") != "Flat":
            continue
        last_inspection = frappe.db.get_value("Asset Inspection",
            {"agreement": agr.name, "docstatus": 1},
            "inspection_date", order_by="inspection_date desc")
        if not last_inspection or last_inspection < cutoff:
            _notify_pm(agr, "Annual inspection overdue")
```

---

## 9. REST API Endpoints (`api/flats.py`)

```python
@frappe.whitelist()
def get_flat_detail(asset_name):
    """Returns flat-specific fields + appliances + building amenities."""
    ...

@frappe.whitelist()
def submit_meter_reading(agreement, meter_type, current_reading, reading_photo=None):
    """Staff-only. Creates and submits a Utility Meter Reading; returns computed charge."""
    ...

@frappe.whitelist()
def get_utility_history(agreement, meter_type=None):
    """Returns last 24 submitted readings for the agreement (customer-facing portal)."""
    ...

@frappe.whitelist()
def get_flat_insurance_status(asset_name):
    """Returns active insurance policies list — internal role only."""
    ...
```

---

## 10. Flat Inspection Checklist Areas

| Area | Items |
|---|---|
| Living Room | Walls, Ceiling, Floor, Windows, Curtains/Blinds, Main Door, AC Unit |
| Bedroom 1–4 | Walls, Ceiling, Floor, Window, Built-in wardrobe, AC, Door |
| Kitchen | Walls, Ceiling, Floor, Sink, Taps, Cabinets, Hood, Countertop, Hob |
| Bathroom 1–2 | Walls, Floor, Shower/Bath, Toilet, Sink, Taps, Towel rails, Mirror |
| Balcony | Floor, Railings, Drainage |
| Storage | Floor, Shelving |
| Building items | Key set count, Remote/fob, Parking pass |

---

## 11. Implementation Phases

| Phase | Deliverables |
|---|---|
| **1** | Custom fields, Property/Building DocTypes, Utility meter reading + billing |
| **2** | Appliance tracking, Flat inspection checklist, scheduler alerts |
| **3** | Insurance validation + Country Insurance Requirement config + ToDo creation |
| **4** | Annual inspection scheduler, Building amenity management, portal utility history API |

---

## 12. Testing Checklist

- [ ] Agreement submit blocked when mandatory country insurance is missing; ToDo created and assigned to property manager
- [ ] Utility reading auto-fetches previous reading from last submitted entry
- [ ] Utility charge computed correctly (`consumption × rate`)
- [ ] Utility line item injected into draft invoice on reading submit
- [ ] Unbilled readings swept onto next invoice via `sweep_unbilled_utilities()` hook
- [ ] Appliance warranty alert fires at exactly 30 days before expiry
- [ ] Annual inspection reminder fires after 11-month gap
- [ ] Insurance expiry alerts fire at 30 and 7 days before expiry
- [ ] `get_utility_history` returns 403 for unauthenticated access and filters by session user
