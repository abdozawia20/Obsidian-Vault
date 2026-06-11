# Vehicle — Web: Technical Document

> **Product**: Asset Rental Platform  
> **Module**: Vehicle Web Layer  
> **Document Type**: Technical  
> **Audience**: Frontend developers (Jinja2, JS, CSS)  
> **Companion**: [vehicle-web-functional.md](./vehicle-web-functional.md)

---

## 1. Architecture Strategy

Vehicle-specific web functionality is **layered on the base web templates** using Jinja `{% if asset.asset_type == "Vehicle" %}` conditional blocks. No new page files are created for the detail or booking pages — the base pages are extended in-place.

A dedicated catalog page (`/rentals/vehicles`) is added in `rental_vehicles/www/`.

---

## 2. File Structure

```
rental_vehicles/
└── www/
    └── vehicles.html / vehicles.py    # Vehicle-only catalog

rental_core/www/
└── rentals/
    └── {asset}.html                   # Base detail — vehicle section injected by asset_type check
    └── {asset}/
        └── book.html                  # Base booking — Step 2 + Step 5 extended for vehicles
```

---

## 3. Vehicle Catalog Controller (`rental_vehicles/www/vehicles.py`)

```python
import frappe

def get_context(context):
    context.no_cache = 1
    filters = {"status": "Available", "is_active": 1, "asset_type": "Vehicle"}

    category     = frappe.form_dict.get("category", "")
    fuel_type    = frappe.form_dict.get("fuel", "")
    transmission = frappe.form_dict.get("transmission", "")
    min_seats    = frappe.form_dict.get("seats", "")
    max_price    = frappe.form_dict.get("max_price", "")
    location     = frappe.form_dict.get("location", "")

    if category:     filters["custom_category"]     = category
    if fuel_type:    filters["custom_fuel_type"]    = fuel_type
    if transmission: filters["custom_transmission"] = transmission
    if min_seats:    filters["custom_seats"]        = [">=", int(min_seats)]
    if max_price:    filters["monthly_rate"]        = ["<=", float(max_price)]
    if location:     filters["location"]            = ["like", f"%{location}%"]

    context.assets = frappe.get_all("Rental Asset", filters=filters,
        fields=["name", "asset_name", "location", "monthly_rate",
                "custom_make", "custom_model", "custom_year",
                "custom_fuel_type", "custom_transmission",
                "custom_seats", "custom_category"],
        limit=24, order_by="monthly_rate asc")

    for a in context.assets:
        img = frappe.db.get_value("Asset Image", {"parent": a.name}, "image", order_by="idx")
        a.cover_image = img or "/assets/rental_core/images/vehicle_placeholder.jpg"

    context.categories = frappe.get_all("Vehicle Category", pluck="category_name")
    context.title = "Browse Vehicles for Rent"
    context.metatags = {
        "title": "Browse Vehicles for Rent",
        "description": "Rent a car, SUV, or van. Transparent pricing. Book online in minutes.",
    }
```

---

## 4. Vehicle Filter Sidebar Template (Partial)

```html
{% if asset_type == "Vehicle" %}
<!-- Category -->
<div class="filter-group mb-3">
  <label class="fw-semibold small mb-1">{{ _("Category") }}</label>
  <select id="filter-category" class="form-select form-select-sm">
    <option value="">{{ _("All Categories") }}</option>
    {% for cat in categories %}
    <option value="{{ cat }}">{{ cat }}</option>
    {% endfor %}
  </select>
</div>
<!-- Fuel Type -->
<div class="filter-group mb-3">
  <label class="fw-semibold small mb-1">{{ _("Fuel Type") }}</label>
  <select id="filter-fuel" class="form-select form-select-sm">
    <option value="">{{ _("Any") }}</option>
    <option>Petrol</option><option>Diesel</option>
    <option>Electric</option><option>Hybrid</option><option>CNG</option>
  </select>
</div>
<!-- Transmission -->
<div class="filter-group mb-3">
  <label class="fw-semibold small mb-1">{{ _("Transmission") }}</label>
  <div class="d-flex gap-2">
    <button class="btn-rental-outline btn-sm flex-fill trans-tab active" data-val="">{{ _("Any") }}</button>
    <button class="btn-rental-outline btn-sm flex-fill trans-tab" data-val="Automatic">{{ _("Auto") }}</button>
    <button class="btn-rental-outline btn-sm flex-fill trans-tab" data-val="Manual">{{ _("Manual") }}</button>
  </div>
</div>
<!-- Min Seats -->
<div class="filter-group mb-3">
  <label class="fw-semibold small mb-1">{{ _("Min Seats") }}</label>
  <select id="filter-seats" class="form-select form-select-sm">
    <option value="">{{ _("Any") }}</option>
    <option value="2">2+</option><option value="4">4+</option>
    <option value="5">5+</option><option value="7">7+</option>
  </select>
</div>
{% endif %}
```

---

## 5. Vehicle Detail Page — Spec Grid Template Block

```html
{% if asset.asset_type == "Vehicle" %}
<div class="row g-2 mb-4">
  {% set specs = [
    ("🚗", _("Make / Model"), (asset.custom_make or "") ~ " " ~ (asset.custom_model or "")),
    ("📅", _("Year"),         asset.custom_year | string),
    ("⛽", _("Fuel Type"),    asset.custom_fuel_type or "—"),
    ("🔧", _("Engine"),       (asset.custom_engine_cc | string) ~ " cc" if asset.custom_engine_cc else "—"),
    ("⚙️", _("Transmission"), asset.custom_transmission or "—"),
    ("💺", _("Seats"),        asset.custom_seats | string if asset.custom_seats else "—"),
  ] %}
  {% for icon, label, value in specs %}
  <div class="col-6 col-md-4">
    <div class="spec-tile p-3 border rounded">
      <div class="spec-icon mb-1">{{ icon }}</div>
      <div class="spec-label text-muted small">{{ label }}</div>
      <div class="spec-value fw-semibold">{{ value }}</div>
    </div>
  </div>
  {% endfor %}
</div>

{% if category %}
<!-- Mileage Policy Box -->
<div class="alert alert-light border mb-4">
  <h6 class="fw-semibold mb-2">📏 {{ _("Mileage Policy") }}</h6>
  <div class="row g-2 mb-2">
    <div class="col-6">
      <div class="text-muted small">{{ _("Included per day") }}</div>
      <div class="fw-semibold">{{ category.included_km_per_day | int }} km</div>
    </div>
    <div class="col-6">
      <div class="text-muted small">{{ _("Overage rate") }}</div>
      <div class="fw-semibold text-warning">
        +{{ frappe.utils.fmt_money(category.overage_rate_per_km) }}/km
      </div>
    </div>
  </div>
  <div class="small">⛽ {{ _("Fuel policy") }}: <strong>{{ category.fuel_policy }}</strong></div>
</div>
{% endif %}
{% endif %}
```

**Controller addition** for category fetching:
```python
# In www/rentals/{asset}.py
if asset.asset_type == "Vehicle" and asset.get("custom_category"):
    context.category = frappe.get_doc("Vehicle Category", asset.custom_category)
else:
    context.category = None
```

---

## 6. Booking Step 2 — Driver License Fields

```html
{% if asset.asset_type == "Vehicle" %}
<div class="col-12"><hr><h6 class="fw-semibold">🪪 {{ _("Driver License Details") }}</h6></div>
<div class="col-md-6">
  <label class="form-label">{{ _("License Number") }} <span class="text-danger">*</span></label>
  <input type="text" class="form-control" id="license_number" required>
</div>
<div class="col-md-6">
  <label class="form-label">{{ _("License Class") }}</label>
  <input type="text" class="form-control" id="license_class"
         placeholder="{{ category.required_license_class or 'e.g. B' }}">
</div>
<div class="col-md-6">
  <label class="form-label">{{ _("License Expiry") }} <span class="text-danger">*</span></label>
  <input type="date" class="form-control" id="license_expiry" required>
</div>
<div class="col-md-6">
  <label class="form-label">{{ _("Date of Birth") }} <span class="text-danger">*</span></label>
  <input type="date" class="form-control" id="date_of_birth" required>
</div>
{% endif %}
```

---

## 7. Client-Side Step 2 Validation (`booking.js`)

```javascript
function validateStep2() {
  // Base validation (name, phone, etc.)
  if (!validateBaseStep2()) return false;

  // Vehicle-specific
  if (!window.IS_VEHICLE) return true;

  const licExpiry  = new Date(document.getElementById('license_expiry').value);
  const endDate    = new Date(window.RENTAL_END_DATE);
  if (licExpiry < endDate) {
    showFieldError('license_expiry',
      'License must be valid for the entire rental period.');
    return false;
  }

  const dob = new Date(document.getElementById('date_of_birth').value);
  const age = (Date.now() - dob) / (365.25 * 24 * 3600 * 1000);
  if (age < window.MIN_DRIVER_AGE) {
    showFieldError('date_of_birth',
      `Driver must be at least ${window.MIN_DRIVER_AGE} years old.`);
    return false;
  }

  return true;
}
```

Template injects: `window.IS_VEHICLE`, `window.RENTAL_END_DATE`, `window.MIN_DRIVER_AGE`.

---

## 8. Server-Side Re-validation (Booking API)

```python
# rental_vehicles/api/vehicles.py — wraps base submit_booking_request
@frappe.whitelist()
def submit_vehicle_booking(**kwargs):
    from frappe.utils import getdate
    from datetime import date

    asset_doc = frappe.get_doc("Rental Asset", kwargs["asset"])
    category  = frappe.get_doc("Vehicle Category", asset_doc.get("custom_category"))
    end_date  = frappe.utils.add_months(kwargs["start_date"], int(kwargs["duration_months"]))

    # License expiry check
    if kwargs.get("license_expiry"):
        if getdate(kwargs["license_expiry"]) < getdate(end_date):
            frappe.throw("Driver license must be valid for the full rental period.")

    # Age check
    if kwargs.get("driver_dob"):
        age = (date.today() - getdate(kwargs["driver_dob"])).days / 365.25
        if age < (category.min_driver_age or 18):
            frappe.throw(f"Driver must be at least {category.min_driver_age} years old.")

    # Delegate to base booking
    from rental_core.api.bookings import submit_booking_request
    result = submit_booking_request(**kwargs)

    # Attach vehicle-specific fields
    if result.get("agreement"):
        frappe.db.set_value("Rental Agreement", result["agreement"], {
            "custom_license_number": kwargs.get("license_number"),
            "custom_license_class":  kwargs.get("license_class"),
            "custom_license_expiry": kwargs.get("license_expiry"),
            "custom_driver_dob":     kwargs.get("driver_dob"),
        })
    return result
```

---

## 9. Step 5 — Policy Acknowledgement Block

```html
{% if asset.asset_type == "Vehicle" and category %}
<div class="alert alert-warning">
  <h6 class="fw-bold">{{ _("Confirm You Understand the Rental Policy") }}</h6>
  <ul class="mb-2 small">
    <li>{{ _("Included:") }} {{ category.included_km_per_day | int }} km/day</li>
    <li>{{ _("Overage:") }} +{{ frappe.utils.fmt_money(category.overage_rate_per_km) }}/km</li>
    <li>{{ _("Fuel:") }} {{ category.fuel_policy }}</li>
  </ul>
</div>
<div class="form-check mb-3">
  <input type="checkbox" class="form-check-input" id="agree_mileage_policy" required>
  <label class="form-check-label" for="agree_mileage_policy">
    {{ _("I understand and accept the mileage and fuel policy.") }}
  </label>
</div>
{% endif %}
```

Step 5 `validateStep5()` in `booking.js` checks `#agree_mileage_policy.checked` for vehicle bookings before allowing submission.

---

## 10. AJAX Filter `collectFilters()` (Vehicle Extension)

```javascript
function collectFilters() {
  return {
    asset_type:   'Vehicle',
    location:     document.getElementById('filter-location')?.value     || '',
    max_price:    document.getElementById('filter-max-price')?.value    || '',
    category:     document.getElementById('filter-category')?.value     || '',
    fuel_type:    document.getElementById('filter-fuel')?.value         || '',
    transmission: document.querySelector('.trans-tab.active')?.dataset.val || '',
    min_seats:    document.getElementById('filter-seats')?.value        || '',
  };
}
```

---

## 11. My Rentals — Vehicle Mileage Summary

```html
{% if agreement.asset_type == "Vehicle" %}
<div class="mt-2 p-2 bg-light rounded small d-flex gap-3 flex-wrap">
  <span>📍 Pickup: <strong>{{ agreement.pickup_odometer or "—" }} km</strong></span>
  <span>🛣 Last: <strong>{{ agreement.current_odometer or "—" }} km</strong></span>
  <span>✅ Included: <strong>{{ agreement.included_km or "—" }} km</strong></span>
  {% if agreement.overage_charge %}
  <span class="text-danger fw-semibold">Overage: +{{ frappe.utils.fmt_money(agreement.overage_charge) }}</span>
  {% endif %}
</div>
{% endif %}
```

---

## 12. Implementation Phases

| Phase | Deliverables |
|---|---|
| **1** | Vehicle catalog with category/fuel/transmission/seats filters |
| **2** | Vehicle detail spec grid + mileage policy box (fetched from Vehicle Category) |
| **3** | Driver license + age fields in Step 2; client-side validation |
| **4** | Server-side re-validation in booking API; Step 5 policy acknowledgement; My Rentals mileage summary |

---

## 13. Testing Checklist

- [ ] Vehicle catalog returns correct results for each filter combination
- [ ] Mileage policy box shows correct `included_km_per_day` and `overage_rate_per_km` from Vehicle Category
- [ ] License expiry in the past or before rental end date → Step 2 blocked with error
- [ ] Driver age below minimum → Step 2 blocked with error
- [ ] Server-side API rejects invalid license/age even if client JS is bypassed
- [ ] Step 5 submit button disabled until policy checkbox is ticked
- [ ] Maintenance-blocked dates appear unavailable on the calendar
