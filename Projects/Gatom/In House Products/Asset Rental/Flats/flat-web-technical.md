# Flat — Web: Technical Document

> **Product**: Asset Rental Platform  
> **Module**: Flat Web Layer  
> **Document Type**: Technical  
> **Audience**: Frontend developers (Jinja2, JS, CSS)  
> **Companion**: [flat-web-functional.md](./flat-web-functional.md)

---

## 1. Architecture Strategy

Flat-specific web functionality is **layered on the base templates** using `{% if asset.asset_type == "Flat" %}` conditional blocks. A new catalog page (`/rentals/flats`) is added in `rental_flats/www/`, and a new portal page (`/my-utilities`) is added alongside it.

---

## 2. File Structure

```
rental_flats/
└── www/
    ├── flats.html / flats.py           # Flat-only catalog
    └── my-utilities.html / my-utilities.py   # Utility history portal page

rental_core/www/
└── rentals/
    └── {asset}.html                    # Base detail — flat section injected conditionally
```

---

## 3. Flat Catalog Controller (`rental_flats/www/flats.py`)

```python
import frappe

def get_context(context):
    context.no_cache = 1
    filters = {"status": "Available", "is_active": 1, "asset_type": "Flat"}

    bedrooms    = frappe.form_dict.get("bedrooms", "")
    furnished   = frappe.form_dict.get("furnished", "")
    min_area    = frappe.form_dict.get("min_area", "")
    max_area    = frappe.form_dict.get("max_area", "")
    view_type   = frappe.form_dict.get("view", "")
    max_price   = frappe.form_dict.get("max_price", "")
    has_parking = frappe.form_dict.get("parking", "")
    pets        = frappe.form_dict.get("pets", "")
    amenity     = frappe.form_dict.get("amenity", "")   # comma-separated

    if bedrooms == "studio":          filters["custom_bedrooms"] = 0
    elif bedrooms:                    filters["custom_bedrooms"] = [">=", int(bedrooms)]
    if furnished:                     filters["custom_furnished"] = furnished
    if min_area and max_area:
        filters["custom_area_sqm"] = ["between", [float(min_area), float(max_area)]]
    elif min_area:                    filters["custom_area_sqm"] = [">=", float(min_area)]
    if view_type:                     filters["custom_view_type"] = view_type
    if max_price:                     filters["monthly_rate"] = ["<=", float(max_price)]
    if has_parking == "yes":          filters["custom_parking_included"] = 1
    if pets == "yes":                 filters["custom_pets_allowed"] = 1

    # Amenity join: find buildings that have ALL selected amenities
    if amenity:
        amenity_list = [a.strip() for a in amenity.split(",") if a.strip()]
        if amenity_list:
            buildings = frappe.db.sql("""
                SELECT ba.parent
                FROM `tabBuilding Amenity` ba
                WHERE ba.amenity IN %(amenities)s
                GROUP BY ba.parent
                HAVING COUNT(DISTINCT ba.amenity) = %(count)s
            """, {"amenities": amenity_list, "count": len(amenity_list)}, as_list=True)
            if buildings:
                filters["custom_building"] = ["in", [b[0] for b in buildings]]
            else:
                context.assets = []
                return

    context.assets = frappe.get_all("Rental Asset", filters=filters,
        fields=["name", "asset_name", "location", "monthly_rate", "deposit_amount",
                "custom_bedrooms", "custom_bathrooms", "custom_area_sqm",
                "custom_furnished", "custom_floor_number", "custom_view_type",
                "custom_parking_included"],
        limit=24, order_by="monthly_rate asc")

    for a in context.assets:
        img = frappe.db.get_value("Asset Image", {"parent": a.name}, "image", order_by="idx")
        a.cover_image = img or "/assets/rental_core/images/flat_placeholder.jpg"

    context.all_amenities = frappe.db.sql(
        "SELECT DISTINCT amenity FROM `tabBuilding Amenity` ORDER BY amenity",
        as_list=True)
    context.all_amenities = [r[0] for r in context.all_amenities]
    context.title = "Browse Flats for Rent"
    context.metatags = {
        "title": "Browse Flats for Rent",
        "description": "Find furnished and unfurnished flats. Filter by bedrooms, area, and amenities.",
    }
```

---

## 4. Flat Detail — Controller Extension

```python
# In rental_core/www/rentals/{asset}.py
if asset.asset_type == "Flat":
    # Building amenities
    building_name = asset.get("custom_building")
    if building_name:
        amenity_rows = frappe.get_all("Building Amenity",
            filters={"parent": building_name}, pluck="amenity")
        context.building_amenities = amenity_rows
    else:
        context.building_amenities = []

    # Appliances (from child table)
    context.appliances = [
        {"appliance_name": a.appliance_name, "brand": a.brand,
         "condition": a.condition, "warranty_expiry": a.warranty_expiry}
        for a in asset.get("custom_appliances", [])
    ]

    # SEO structured data
    context.schema_json = frappe.as_json({
        "@context": "https://schema.org",
        "@type": "Apartment",
        "name": asset.asset_name,
        "numberOfRooms": asset.get("custom_bedrooms"),
        "floorSize": {"@type": "QuantitativeValue",
                      "value": asset.get("custom_area_sqm"), "unitCode": "MTK"},
        "address": {"@type": "PostalAddress", "addressLocality": asset.location},
        "offers": {"@type": "Offer", "price": asset.monthly_rate,
                   "priceCurrency": config.default_currency},
    })
```

---

## 5. Flat Detail — Template Additions

```html
{% if asset.asset_type == "Flat" %}
<!-- Spec Grid -->
<div class="row g-2 mb-4">
  {% set specs = [
    ("🛏", _("Bedrooms"),   asset.custom_bedrooms | string if asset.custom_bedrooms is not none else "—"),
    ("🛁", _("Bathrooms"),  asset.custom_bathrooms | string if asset.custom_bathrooms is not none else "—"),
    ("📐", _("Area"),       (asset.custom_area_sqm | string) ~ " m²" if asset.custom_area_sqm else "—"),
    ("🏢", _("Floor"),      asset.custom_floor_number | string if asset.custom_floor_number else "—"),
    ("🛋", _("Furnishing"), asset.custom_furnished or "—"),
    ("🌅", _("View"),       asset.custom_view_type or "—"),
    ("🧭", _("Direction"),  asset.custom_direction_facing or "—"),
    ("🅿", _("Parking"),    _("Included") if asset.custom_parking_included else _("Not included")),
  ] %}
  {% for icon, label, value in specs %}
  <div class="col-6 col-md-3">
    <div class="spec-tile p-3 border rounded text-center">
      <div>{{ icon }}</div>
      <div class="text-muted small">{{ label }}</div>
      <div class="fw-semibold small">{{ value }}</div>
    </div>
  </div>
  {% endfor %}
</div>

<!-- Building Amenities -->
{% if building_amenities %}
<div class="mb-4">
  <h5 class="fw-semibold mb-2">{{ _("Building Amenities") }}</h5>
  <div class="d-flex flex-wrap gap-2">
    {% for am in building_amenities %}
    <span class="badge bg-primary bg-opacity-10 text-primary border border-primary px-3 py-2">
      {{ am }}
    </span>
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- Appliances (collapsed) -->
{% if appliances %}
<details class="mb-4">
  <summary class="fw-semibold">🏠 {{ _("Included Appliances") }} ({{ appliances | length }})</summary>
  <table class="table table-sm mt-2">
    <thead><tr><th>{{ _("Appliance") }}</th><th>{{ _("Brand") }}</th><th>{{ _("Condition") }}</th></tr></thead>
    <tbody>
      {% for ap in appliances %}
      <tr>
        <td>{{ ap.appliance_name }}</td>
        <td>{{ ap.brand or "—" }}</td>
        <td><span class="badge bg-{{ 'success' if ap.condition in ('New','Good') else 'warning' }}">
          {{ ap.condition }}</span></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</details>
{% endif %}

<!-- Floor Plan -->
{% if asset.custom_floor_plan %}
<a href="{{ asset.custom_floor_plan }}" target="_blank" rel="noopener"
   class="btn btn-outline-secondary mb-4">
  📄 {{ _("View Floor Plan") }}
</a>
{% endif %}

<!-- Utilities badge -->
{% if asset.custom_utilities_included %}
<div class="alert alert-success py-2 mb-4">✅ {{ _("Utilities included in rent") }}</div>
{% endif %}

<!-- SEO structured data -->
<script type="application/ld+json">{{ schema_json }}</script>
{% endif %}
```

---

## 6. Flat Catalog Filter Sidebar Template

```html
{% if show_flat_filters %}
<!-- Bedrooms -->
<div class="filter-group mb-3">
  <label class="fw-semibold small">{{ _("Bedrooms") }}</label>
  <div class="d-flex flex-wrap gap-1 mt-1">
    {% for b, v in [("Studio","studio"),("1","1"),("2","2"),("3","3"),("4","4"),("5+","5")] %}
    <button class="btn-rental-outline btn-sm bed-tab" data-val="{{ v }}">{{ b }}</button>
    {% endfor %}
  </div>
</div>
<!-- Furnishing -->
<div class="filter-group mb-3">
  <label class="fw-semibold small">{{ _("Furnishing") }}</label>
  <select id="filter-furnished" class="form-select form-select-sm">
    <option value="">{{ _("Any") }}</option>
    <option>Unfurnished</option><option>Semi-Furnished</option><option>Fully Furnished</option>
  </select>
</div>
<!-- Area range -->
<div class="filter-group mb-3">
  <label class="fw-semibold small">{{ _("Area (m²)") }}</label>
  <div class="d-flex gap-2">
    <input type="number" id="filter-min-area" class="form-control form-control-sm"
           placeholder="{{ _('Min') }}">
    <input type="number" id="filter-max-area" class="form-control form-control-sm"
           placeholder="{{ _('Max') }}">
  </div>
</div>
<!-- View -->
<div class="filter-group mb-3">
  <label class="fw-semibold small">{{ _("View") }}</label>
  <select id="filter-view" class="form-select form-select-sm">
    <option value="">{{ _("Any") }}</option>
    <option>Street</option><option>Garden</option><option>Sea</option><option>City</option>
  </select>
</div>
<!-- Amenities (multi-check) -->
{% if all_amenities %}
<div class="filter-group mb-3">
  <label class="fw-semibold small">{{ _("Amenities") }}</label>
  {% for am in all_amenities %}
  <div class="form-check">
    <input class="form-check-input amenity-check" type="checkbox"
           value="{{ am }}" id="am-{{ loop.index }}">
    <label class="form-check-label small" for="am-{{ loop.index }}">{{ am }}</label>
  </div>
  {% endfor %}
</div>
{% endif %}
<!-- Toggles -->
<div class="filter-group mb-3">
  <div class="form-check form-switch mb-1">
    <input class="form-check-input" type="checkbox" id="filter-parking">
    <label class="form-check-label small">{{ _("Parking Included") }}</label>
  </div>
  <div class="form-check form-switch">
    <input class="form-check-input" type="checkbox" id="filter-pets">
    <label class="form-check-label small">{{ _("Pets Allowed") }}</label>
  </div>
</div>
{% endif %}
```

---

## 7. `/my-utilities` Portal Controller

```python
# rental_flats/www/my-utilities.py
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/my-utilities"
        raise frappe.Redirect

    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    flat_agreements = [
        a.name for a in frappe.get_all("Rental Agreement",
            filters={"customer": customer, "status": "Active"})
        if frappe.db.get_value("Rental Asset",
            frappe.db.get_value("Rental Agreement", a.name, "asset"),
            "asset_type") == "Flat"
    ]

    context.utility_data = {}
    for agr in flat_agreements:
        asset = frappe.db.get_value("Rental Agreement", agr, "asset")
        if frappe.db.get_value("Rental Asset", asset, "custom_utilities_included"):
            continue  # skip: utilities included in rent
        for meter in ("Electricity", "Water", "Gas"):
            readings = frappe.get_all("Utility Meter Reading", filters={
                "agreement": agr, "meter_type": meter, "docstatus": 1,
            }, fields=["reading_date", "consumption", "unit_rate", "total_charge"],
            order_by="reading_date desc", limit=6)
            if readings:
                context.utility_data.setdefault(agr, {})[meter] = readings

    context.title = "Utility Usage"
```

---

## 8. `/my-utilities` Template (Key Excerpt)

```html
{% block head_include %}
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
{% endblock %}

{% for agr, meters in utility_data.items() %}
<div class="card mb-4">
  <div class="card-header fw-semibold">🏠 {{ frappe.db.get_value("Rental Agreement", agr, "asset") }}</div>
  <div class="card-body">
    <ul class="nav nav-tabs mb-3">
      {% for meter in meters.keys() %}
      <li class="nav-item">
        <button class="nav-link {% if loop.first %}active{% endif %}"
                data-bs-toggle="tab"
                data-bs-target="#tab-{{ agr }}-{{ meter|lower|replace(' ','') }}">
          {{ meter }}
        </button>
      </li>
      {% endfor %}
    </ul>
    <div class="tab-content">
      {% for meter, readings in meters.items() %}
      {% set tab_id = "tab-" ~ agr ~ "-" ~ meter|lower|replace(' ','') %}
      <div class="tab-pane fade {% if loop.first %}show active{% endif %}" id="{{ tab_id }}">
        <canvas id="chart-{{ tab_id }}" height="80"></canvas>
        <script>
        new Chart(document.getElementById('chart-{{ tab_id }}'), {
          type: 'bar',
          data: {
            labels: {{ readings | map(attribute='reading_date') | list | tojson }},
            datasets: [{ label: 'Consumption (units)',
              data: {{ readings | map(attribute='consumption') | list | tojson }},
              backgroundColor: 'rgba(37,99,235,0.7)', borderRadius: 6 }]
          },
          options: { plugins: { legend: { display: false } } }
        });
        </script>
        <table class="table table-sm mt-3">
          <thead><tr><th>Date</th><th>Units</th><th>Rate</th><th>Charge</th></tr></thead>
          <tbody>
            {% for r in readings %}
            <tr>
              <td>{{ r.reading_date }}</td>
              <td>{{ r.consumption }}</td>
              <td>{{ frappe.utils.fmt_money(r.unit_rate) }}</td>
              <td><strong>{{ frappe.utils.fmt_money(r.total_charge) }}</strong></td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
      {% endfor %}
    </div>
  </div>
</div>
{% endfor %}
```

---

## 9. AJAX `collectFilters()` (Flat Extension)

```javascript
function collectFilters() {
  const activeBed = document.querySelector('.bed-tab.active');
  const amenities = [...document.querySelectorAll('.amenity-check:checked')]
    .map(el => el.value).join(',');
  return {
    asset_type:  'Flat',
    bedrooms:    activeBed?.dataset.val || '',
    furnished:   document.getElementById('filter-furnished')?.value    || '',
    min_area:    document.getElementById('filter-min-area')?.value     || '',
    max_area:    document.getElementById('filter-max-area')?.value     || '',
    view_type:   document.getElementById('filter-view')?.value         || '',
    max_price:   document.getElementById('filter-max-price')?.value    || '',
    has_parking: document.getElementById('filter-parking')?.checked ? 'yes' : '',
    pets:        document.getElementById('filter-pets')?.checked ? 'yes' : '',
    amenity:     amenities,
  };
}
```

---

## 10. Implementation Phases

| Phase | Deliverables |
|---|---|
| **1** | Flat catalog with bedroom/furnishing/area/parking/pets filters |
| **2** | Flat detail spec grid + building amenities chips + appliances collapsible |
| **3** | Floor plan button, utilities included badge, schema.org structured data |
| **4** | `/my-utilities` portal page (Chart.js chart + table + portal sidebar entry) |

---

## 11. Testing Checklist

- [ ] Flat catalog filters by bedrooms, furnishing, area, view, parking, pets
- [ ] Amenity filter performs correct SQL join through Building table
- [ ] Flat detail shows building amenities from linked Rental Building
- [ ] Appliances section collapses by default; toggle works
- [ ] Floor plan button only renders if `custom_floor_plan` is set
- [ ] Utilities included badge shown correctly when flag is set
- [ ] `/my-utilities` returns 302 to login for guest access
- [ ] Chart.js bar chart renders with reading dates as labels
- [ ] Portal sidebar "Utility Usage" entry appears only when `rental_flats` is installed
- [ ] schema.org `Apartment` structured data present on flat detail pages
