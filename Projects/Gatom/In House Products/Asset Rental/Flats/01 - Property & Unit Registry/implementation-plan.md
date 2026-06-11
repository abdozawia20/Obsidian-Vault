# Domain F01 — Property & Unit Registry: Implementation Plan

> **Variant**: Flats (child app `rental_flats`)
> **Domain**: Property & Unit Registry
> **Sequence**: 1 of 5
> **Depends on**: Base D01 (app scaffold, Rental Asset DocType, Rental Configuration, API patterns, web stubs, Flutter stubs)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

The Flats variant adds a **three-level property hierarchy** on top of the base rental platform: a **Property** (e.g., "Sunset Residences") contains one or more **Buildings** (e.g., "Block A"), which in turn contain individual **Flat Units** (apartments). This hierarchy lets operators manage portfolios of hundreds of units, compute occupancy rates at any level, and expose rich filtering (bedrooms, area, amenities) on the customer-facing catalog.

This domain is the **foundation** of the Flats module — all other Flats domains (Utility Billing, Appliances, Insurance, Inspection) depend on the DocTypes, custom fields, and API endpoints created here.

---

## 2. Frappe — App Scaffold

### 2.1 App Initialization

> **Requires**: Base D01-2.1 (`rental_core` installed and functional)

The `rental_flats` app is a **Frappe child app** — it depends on `rental_core` (the base platform) and extends it with flat-specific features. It cannot be installed standalone. This subtask creates the app skeleton and verifies the dependency chain works correctly.

```bash
bench new-app rental_flats
# required_apps = ["frappe", "erpnext", "rental_core"]
bench --site rental.localhost install-app rental_flats
```

**Acceptance Criteria**:
- [ ] `bench new-app rental_flats` creates the app directory
- [ ] `required_apps` includes `frappe`, `erpnext`, `rental_core`
- [ ] App installs without errors on a site that already has `rental_core`
- [ ] Installing `rental_flats` without `rental_core` fails with a dependency error

---

### 2.2 `hooks.py` — Events & Portal Menu

> **Requires**: 2.1

Frappe's `hooks.py` is the app's central wiring file — it tells the framework what background jobs to run, what events to listen for, and what portal pages to expose. This subtask registers **4 daily scheduler jobs** (utility reminders, warranty alerts, inspection checks, insurance expiry), **1 doc_event** (insurance validation fires whenever a Rental Agreement is submitted), and **1 portal menu item** ("Utility Usage" link in the customer sidebar).

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
    {"title": "Utility Usage", "route": "/my-utilities",
     "reference_doctype": "Utility Meter Reading", "role": "Customer"},
]
```

**Acceptance Criteria**:
- [ ] 4 daily scheduler events registered
- [ ] `validate` event on `Rental Agreement` fires the insurance validator
- [ ] "Utility Usage" appears in portal sidebar for Customer role
- [ ] "Utility Usage" does NOT appear in portal when `rental_flats` is uninstalled

---

### 2.3 `setup.py` — Custom Fields Injection

> **Requires**: 2.1, Base D04-2.1 (Rental Asset DocType exists)

Rather than modifying the base `Rental Asset` DocType directly, the Flats module **injects custom fields** at install time using Frappe's `create_custom_fields()` API. This keeps the base app clean — if `rental_flats` is uninstalled, all flat-specific fields disappear. The fields are wrapped in a conditional section (`depends_on: eval:doc.asset_type=='Flat'`) so they're invisible when managing vehicles or other asset types.

This subtask also injects the `country_insurance_requirements` child table onto `Rental Configuration` (the global settings singleton), which domain F04 (Insurance) uses to define mandatory insurance per country.

Injects flat-specific fields onto `Rental Asset` and `Rental Configuration`:

| Target DocType | Fields Injected |
|---|---|
| `Rental Asset` | `flat_section`, `custom_property`, `custom_building`, `custom_unit_number`, `custom_floor_number`, `custom_area_sqm`, `custom_living_area_sqm`, `custom_bedrooms`, `custom_bathrooms`, `custom_balcony`, `custom_storage_room`, `custom_parking_included`, `custom_parking_slot_number`, `custom_furnished`, `custom_appliances`, `custom_floor_plan`, `custom_direction_facing`, `custom_view_type`, `custom_electricity_meter_id`, `custom_water_meter_id`, `custom_gas_meter_id`, `custom_utilities_included`, `custom_max_occupants`, `custom_pets_allowed`, `custom_smoking_allowed`, `custom_key_count`, `custom_access_code` |
| `Rental Configuration` | `country_insurance_requirements` (Table) |

**Acceptance Criteria**:
- [ ] After `bench --site ... install-app rental_flats`, all custom fields exist on `Rental Asset`
- [ ] `flat_section` has `depends_on` = `eval:doc.asset_type=='Flat'` — only visible for Flat assets
- [ ] `custom_access_code` is `Password` fieldtype (encrypted, never shown in API)
- [ ] `custom_furnished` has options: `Unfurnished`, `Semi-Furnished`, `Fully Furnished`
- [ ] `custom_direction_facing` has options: `North`, `South`, `East`, `West`, `Corner`
- [ ] `custom_view_type` has options: `Street`, `Garden`, `Sea`, `City`, `Internal`
- [ ] `custom_appliances` is a Table linking to `Flat Appliance` child table
- [ ] `country_insurance_requirements` is a Table on `Rental Configuration`
- [ ] Uninstalling `rental_flats` cleans up custom fields

---

## 3. Frappe — `Rental Property` DocType

### 3.1 Schema Definition

> **Requires**: 2.1 (app directory exists)

A **Rental Property** represents a physical real estate complex or estate — e.g., "Sunset Residences" or "Park Avenue Towers". It's the top level of the hierarchy. Properties group multiple buildings under a single management entity. The `managed_by` field links to the User responsible for the portfolio, which is used by alert and ToDo systems throughout the Flats module to route notifications.

| Field | Type | Required | Notes |
|---|---|---|---|
| `property_name` | Data | ✅ | |
| `property_code` | Data | auto | Series: `PROP-.####` |
| `address` | Data | | |
| `city` | Data | | |
| `country` | Link → Country | | |
| `geo_lat` / `geo_lng` | Float | | |
| `managed_by` | Link → User | | |

**Acceptance Criteria**:
- [ ] DocType exists in Frappe Desk under "Rental" module
- [ ] `property_code` auto-generates with series `PROP-.####`
- [ ] `property_name` is mandatory
- [ ] Only `Property Manager` and `System Manager` can create/edit

---

## 4. Frappe — `Rental Building` DocType

### 4.1 Schema Definition

> **Requires**: 3.1 (Rental Property for Link field)

A **Rental Building** is a physical structure within a Property — e.g., "Block A" within "Sunset Residences". Buildings track structural attributes (floors, elevator availability, parking capacity) and shared **amenities** (pool, gym, security) that are inherited by all flat units inside them. When a customer filters the catalog by "Pool", the system checks whether the flat's **building** has that amenity — not the flat itself.

| Field | Type | Required | Notes |
|---|---|---|---|
| `building_name` | Data | ✅ | |
| `property` | Link → Rental Property | ✅ | |
| `floors` | Int | | |
| `has_elevator` | Check | | |
| `parking_slots` | Int | | |
| `service_charge_monthly` | Currency | | |
| `amenities` | Table → `Building Amenity` | | |

**Acceptance Criteria**:
- [ ] DocType exists in Frappe Desk
- [ ] `building_name` and `property` are mandatory
- [ ] `amenities` child table allows adding: Pool, Gym, Parking, Security, Elevator (and custom values)
- [ ] Only `Property Manager` and `System Manager` can create/edit

---

### 4.2 `Building Amenity` Child Table

> **Requires**: 4.1

A simple child table that stores amenities available in a building. Amenities are free-text (not a fixed list) so operators can add location-specific ones like "Rooftop Garden" or "Co-working Space". These values power the catalog filter checkboxes on both web and mobile.

| Field | Type | Notes |
|---|---|---|
| `amenity` | Data | e.g., Pool, Gym, Parking, Security, Elevator |

**Acceptance Criteria**:
- [ ] Child table rows are addable inline in the Building form
- [ ] Duplicate amenity values are allowed (no unique constraint — flexibility)
- [ ] Amenity values are queryable for catalog filtering

---

## 5. Frappe — Flat Unit Extensions (on Rental Asset)

### 5.1 Occupancy Rate Computed Property

> **Requires**: 2.3 (custom fields), 3.1 (Property), 4.1 (Building)

Property managers need to see how full their buildings/properties are at a glance. This utility function computes the **occupancy percentage** (rented units ÷ total active units × 100) at either the Building or Property level. It's used in Desk dashboards and internal reports — not exposed to customers.

```python
def get_occupancy_rate(parent_type, parent_name):
    """Returns occupancy percentage for a Property or Building."""
    if parent_type == "Rental Property":
        buildings = frappe.get_all("Rental Building", {"property": parent_name}, pluck="name")
        filters = {"custom_building": ["in", buildings], "is_active": 1, "asset_type": "Flat"}
    else:
        filters = {"custom_building": parent_name, "is_active": 1, "asset_type": "Flat"}
    total = frappe.db.count("Rental Asset", filters)
    rented = frappe.db.count("Rental Asset", {**filters, "status": "Rented"})
    return round((rented / total * 100), 1) if total else 0
```

**Acceptance Criteria**:
- [ ] Building with 10 units, 7 rented → `70.0%`
- [ ] Building with 0 units → `0%` (no division by zero)
- [ ] Property occupancy aggregates across all buildings under it
- [ ] Only `is_active = 1` units are counted (retired excluded)

---

### 5.2 Hierarchy Validation

> **Requires**: 2.3 (custom fields on Rental Asset)

The three-level hierarchy must be enforced: every **Flat** must belong to a **Building**, and every Building must belong to a **Property**. Without this validation, orphan flats could exist in the system with no building or property context, breaking occupancy calculations, amenity lookups, and insurance country resolution. This check runs on every save of a Rental Asset.

Importantly, **vehicle-type assets are excluded** — they don't use the property hierarchy at all.

In the `Rental Asset` controller, add a `validate()` check:

```python
def validate(self):
    if self.asset_type == "Flat" and not self.custom_building:
        frappe.throw(_("Flat-type assets must have a Building assigned."))
```

This enforces the property hierarchy: every Flat must link to a Building, and every Building must link to a Property.

**Acceptance Criteria**:
- [ ] Flat unit must have `custom_building` set (mandatory for `asset_type == Flat`)
- [ ] Building must have `property` set (mandatory)
- [ ] Saving a Flat without a building raises validation error
- [ ] Vehicle-type assets do NOT require `custom_building`

---

## 6. Frappe — Flat-Specific API Endpoints

### 6.1 `get_flat_detail`

> **Requires**: 2.3 (custom fields), 4.2 (Building Amenity for join)

This API endpoint returns the **full detail view** for a single flat — used by both the web detail page and the Flutter detail screen. It aggregates data from three sources: the base Rental Asset fields, the flat-specific custom fields, and the building's amenities (joined from the parent Building). For security, it explicitly **excludes** the `custom_access_code` field (the door/gate access code), which is Desk-only and must never be exposed to customers or APIs.

```python
@frappe.whitelist()
def get_flat_detail(asset_name):
    """Returns flat-specific fields + appliances + building amenities."""
```

**Acceptance Criteria**:
- [ ] Returns all base `Rental Asset` fields + all flat custom fields
- [ ] Includes `building_amenities[]` from linked Building
- [ ] Includes `appliances[]` from `custom_appliances` child table (name, brand, condition only — no serial number, no warranty for customer API)
- [ ] `custom_access_code` is NEVER included in the response
- [ ] Non-existent asset returns HTTP 404
- [ ] Includes `schema_org` object with `@type: Apartment`, `numberOfRooms`, `floorSize`, `address`

---

### 6.2 `get_flat_catalog` (extends base catalog)

> **Requires**: Base D04-4.1 (base catalog query), 2.3 (custom fields), 4.2 (Building Amenity)

The base platform provides a generic `get_available_assets` endpoint, but flats need **rich filtering** that doesn't apply to vehicles — bedrooms, area range, furnishing level, amenities, parking, pets. This endpoint extends the base catalog with flat-specific filter handling. The tricky part is the **amenity filter**: since amenities belong to the Building (not the flat), the query must JOIN through the Building Amenity table and only return flats whose building has *all* selected amenities (AND logic, not OR).

Extends the base `get_available_assets` query by adding flat-specific filter handling. Key logic:

```python
def get_flat_catalog(filters):
    base_filters = {"status": "Available", "is_active": 1, "asset_type": "Flat"}
    if filters.get("bedrooms") == "studio":  base_filters["custom_bedrooms"] = 0
    elif filters.get("bedrooms"):             base_filters["custom_bedrooms"] = [">=", int(filters["bedrooms"])]
    if filters.get("furnished"):              base_filters["custom_furnished"] = filters["furnished"]
    if filters.get("min_area") and filters.get("max_area"):
        base_filters["custom_area_sqm"] = ["between", [float(filters["min_area"]), float(filters["max_area"])]]
    if filters.get("max_price"):              base_filters["monthly_rate"] = ["<=", float(filters["max_price"])]
    if filters.get("parking") == "yes":       base_filters["custom_parking_included"] = 1
    if filters.get("pets") == "yes":          base_filters["custom_pets_allowed"] = 1
    if filters.get("amenity"):
        # SQL join: buildings that have ALL selected amenities
        amenity_list = [a.strip() for a in filters["amenity"].split(",")]
        buildings = frappe.db.sql("""SELECT ba.parent FROM `tabBuilding Amenity` ba
            WHERE ba.amenity IN %(amenities)s GROUP BY ba.parent
            HAVING COUNT(DISTINCT ba.amenity) = %(count)s""",
            {"amenities": amenity_list, "count": len(amenity_list)}, as_list=True)
        base_filters["custom_building"] = ["in", [b[0] for b in buildings]] if buildings else ["in", []]
    return frappe.get_all("Rental Asset", filters=base_filters, fields=[...], limit=24)
```

**Acceptance Criteria**:
- [ ] Filters: `bedrooms` (0=Studio, 1-5+), `furnished`, `min_area`, `max_area`, `view_type`, `max_price`, `parking`, `pets`, `amenity` (comma-separated)
- [ ] `bedrooms=studio` maps to `custom_bedrooms = 0`
- [ ] `bedrooms=5` maps to `custom_bedrooms >= 5`
- [ ] Amenity filter performs SQL join through `Building Amenity` table — flat passes if its building has ALL selected amenities
- [ ] Flats without a linked building are invisible when amenity filter is active
- [ ] Each result includes `cover_image` (batch query, not N+1)
- [ ] Paginated per Base D01-6.2 standard

---

## 7. Web — Flat Catalog (`/rentals/flats`)

### 7.1 Controller `rental_flats/www/flats.py`

> **Requires**: 6.2 (flat catalog query logic), Base D01-7.3 (web stubs)

This is the **public-facing flat catalog page** — the first page a prospective tenant sees when browsing available apartments. It's a server-rendered (SSR) Jinja page, not a single-page app. The controller processes URL query parameters (e.g., `?bedrooms=2&max_price=3000`) into database filters, fetches matching flats with cover images, and also loads the distinct amenity list to populate the filter sidebar checkboxes.

The page must work without JavaScript for initial render (SEO), but AJAX filtering enhances the experience (see 7.3).

```python
def get_context(context):
    context.no_cache = 1
    filters = {"status": "Available", "is_active": 1, "asset_type": "Flat"}
    # Apply URL params to filters (bedrooms, furnished, min_area, max_area, etc.)
    # ... same logic as 6.2 ...
    context.assets = frappe.get_all("Rental Asset", filters=filters,
        fields=["name", "asset_name", "location", "monthly_rate", "custom_bedrooms",
                "custom_bathrooms", "custom_area_sqm", "custom_furnished"], limit=24)
    for a in context.assets:
        a.cover_image = frappe.db.get_value("Asset Image", {"parent": a.name}, "image", order_by="idx") \
            or "/assets/rental_core/images/flat_placeholder.jpg"
    context.all_amenities = [r[0] for r in frappe.db.sql(
        "SELECT DISTINCT amenity FROM `tabBuilding Amenity` ORDER BY amenity", as_list=True)]
    context.title = "Browse Flats for Rent"
    context.metatags = {"title": context.title, "description": "Find flats. Filter by bedrooms, area, and amenities."}
```

**Acceptance Criteria**:
- [ ] `/rentals/flats` renders SSR with first 24 flat assets
- [ ] URL params (`?bedrooms=2&furnished=Fully+Furnished&max_price=3000`) are passed to query
- [ ] No matching flats → "No flats match your filters" message
- [ ] Meta tags set: `title = "Browse Flats for Rent"`, `description` includes filter summary

---

### 7.2 Filter Sidebar Template

> **Requires**: 7.1 (page renders), 4.2 (amenity list for checkboxes)

The left sidebar on the catalog page lets tenants narrow results without a page reload. It contains flat-specific filter controls: bedroom count (button group where Studio = 0 bedrooms), furnishing level, area range, view type, amenity checkboxes (dynamically populated from the database), and toggle switches for parking and pets. When any control changes, the AJAX handler (7.3) fires to refresh the grid.

Jinja sidebar with flat-specific controls:

```html
<!-- Bedrooms: button group -->
<div class="d-flex flex-wrap gap-1">
  {% for b, v in [("Studio","studio"),("1","1"),("2","2"),("3","3"),("4","4"),("5+","5")] %}
  <button class="btn-rental-outline btn-sm bed-tab" data-val="{{ v }}">{{ b }}</button>
  {% endfor %}
</div>
<!-- Furnishing: dropdown -->
<select id="filter-furnished" class="form-select form-select-sm">...</select>
<!-- Area: min/max inputs -->
<input type="number" id="filter-min-area" placeholder="Min">
<input type="number" id="filter-max-area" placeholder="Max">
<!-- Amenities: checkboxes from all_amenities -->
{% for am in all_amenities %}
<input class="amenity-check" type="checkbox" value="{{ am }}"> {{ am }}
{% endfor %}
<!-- Toggles: Parking, Pets -->
<input type="checkbox" id="filter-parking"> Parking Included
<input type="checkbox" id="filter-pets"> Pets Allowed
```

**Acceptance Criteria**:
- [ ] Bedrooms: button group (Studio, 1, 2, 3, 4, 5+) with active state
- [ ] Furnishing: dropdown (Any, Unfurnished, Semi-Furnished, Fully Furnished)
- [ ] Area: two number inputs (min/max m²)
- [ ] View: dropdown (Any, Street, Garden, Sea, City)
- [ ] Amenities: checkbox multi-select dynamically populated from `Building Amenity` distinct values
- [ ] Parking Included: toggle switch
- [ ] Pets Allowed: toggle switch
- [ ] All filters apply via AJAX without full page reload

---

### 7.3 AJAX Filter Handler (`collectFilters()`)

> **Requires**: 7.2 (filter elements exist), 6.2 (API endpoint)

When a tenant changes any filter control, this JavaScript function reads all filter values, sends them to the API, and replaces the grid HTML with fresh results. It uses `frappe.call()` (which handles CSRF tokens automatically) and shows a loading skeleton while the request is in-flight. This avoids full page reloads and gives a smoother browsing experience.

JavaScript function that reads all filter controls and fires an AJAX request:

```javascript
function collectFilters() {
  const activeBed = document.querySelector('.bed-tab.active');
  const amenities = [...document.querySelectorAll('.amenity-check:checked')].map(el => el.value).join(',');
  return {
    asset_type: 'Flat',
    bedrooms:    activeBed?.dataset.val || '',
    furnished:   document.getElementById('filter-furnished')?.value || '',
    min_area:    document.getElementById('filter-min-area')?.value || '',
    max_area:    document.getElementById('filter-max-area')?.value || '',
    max_price:   document.getElementById('filter-max-price')?.value || '',
    has_parking: document.getElementById('filter-parking')?.checked ? 'yes' : '',
    pets:        document.getElementById('filter-pets')?.checked ? 'yes' : '',
    amenity:     amenities,
  };
}
// On change: frappe.call({ method: ..., args: collectFilters(), callback: renderResults })
```

**Acceptance Criteria**:
- [ ] Collects all filter values and calls `get_flat_catalog` or base catalog API with `asset_type=Flat`
- [ ] Uses `frappe.call()` (CSRF-safe)
- [ ] Loading skeleton during fetch
- [ ] Pagination controls rendered correctly

---

## 8. Web — Flat Detail Extensions (on base `/rentals/{asset}`)

### 8.1 Spec Grid

> **Requires**: Base D04-9.1 (base detail page), 2.3 (custom fields available in context)

When a customer views a flat's detail page, the first thing they see below the photo gallery is a **spec grid** — an 8-tile grid showing key facts: bedrooms, bathrooms, area (m²), floor, furnishing, view, direction, and parking. This is the Jinja template block that renders it. The block is **conditional** — it only appears for flat-type assets, not vehicles.

Conditional Jinja block on the base detail template:

```html
{% if asset.asset_type == "Flat" %}
<div class="row g-2 mb-4">
  {% set specs = [
    ("🛏", _("Bedrooms"), asset.custom_bedrooms|string if asset.custom_bedrooms is not none else "—"),
    ("🛁", _("Bathrooms"), asset.custom_bathrooms|string if asset.custom_bathrooms is not none else "—"),
    ("📐", _("Area"), (asset.custom_area_sqm|string) ~ " m²" if asset.custom_area_sqm else "—"),
    ("🏢", _("Floor"), asset.custom_floor_number|string if asset.custom_floor_number else "—"),
    ("🛋", _("Furnishing"), asset.custom_furnished or "—"),
    ("🌅", _("View"), asset.custom_view_type or "—"),
    ("🧭", _("Direction"), asset.custom_direction_facing or "—"),
    ("🅿", _("Parking"), _("Included") if asset.custom_parking_included else _("Not included")),
  ] %}
  {% for icon, label, value in specs %}
  <div class="col-6 col-md-3"><div class="spec-tile p-3 border rounded text-center">
    <div>{{ icon }}</div><div class="text-muted small">{{ label }}</div>
    <div class="fw-semibold small">{{ value }}</div>
  </div></div>
  {% endfor %}
</div>
{% endif %}
```

**Acceptance Criteria**:
- [ ] 8-tile grid: Bedrooms, Bathrooms, Area (m²), Floor, Furnishing, View, Direction, Parking
- [ ] Each tile shows icon + label + value
- [ ] Missing values display "—" (not blank or error)
- [ ] Only rendered when `asset.asset_type == "Flat"` (conditional block)

---

### 8.2 Building Amenities Chips

> **Requires**: 8.1, 4.2 (amenity data in page context)

Below the spec grid, tenants want to know what shared facilities the building offers (pool, gym, parking, etc.). These amenities are stored on the **Building** (not the flat), so the controller must look up the flat's parent building and fetch its amenity list. The template renders them as styled badge chips in a flex-wrap layout. If the building has no amenities, the entire section is hidden.

Amenities from the linked Building, rendered as styled badge chips:

```html
{% if building_amenities %}
<div class="mb-4">
  <h5 class="fw-semibold mb-2">{{ _("Building Amenities") }}</h5>
  <div class="d-flex flex-wrap gap-2">
    {% for am in building_amenities %}
    <span class="badge bg-primary bg-opacity-10 text-primary border border-primary px-3 py-2">{{ am }}</span>
    {% endfor %}
  </div>
</div>
{% endif %}
```

Controller extension (in base detail page controller):

```python
if asset.asset_type == "Flat" and asset.get("custom_building"):
    context.building_amenities = frappe.get_all("Building Amenity",
        filters={"parent": asset.custom_building}, pluck="amenity")
else:
    context.building_amenities = []
```

**Acceptance Criteria**:
- [ ] Amenities displayed as styled badges/chips
- [ ] No amenities → section hidden (not empty row)
- [ ] Data comes from linked Building (no separate API call)

---

### 8.3 Appliance Collapsible Section

> **Requires**: 8.1, 2.3 (`custom_appliances` in context)

Tenants want to know what appliances come with the flat (refrigerator, washing machine, etc.) and their condition. This section uses an HTML `<details>` element so it's **collapsed by default** — it's useful information but not the first thing tenants need to see. The controller strips out **serial numbers** and **warranty dates** (internal/Desk-only data) before passing appliances to the template.

Collapsible `<details>` element showing customer-safe appliance data:

```html
{% if appliances %}
<details class="mb-4">
  <summary class="fw-semibold">🏠 {{ _("Included Appliances") }} ({{ appliances|length }})</summary>
  <table class="table table-sm mt-2">
    <thead><tr><th>{{ _("Appliance") }}</th><th>{{ _("Brand") }}</th><th>{{ _("Condition") }}</th></tr></thead>
    <tbody>
      {% for ap in appliances %}
      <tr><td>{{ ap.appliance_name }}</td><td>{{ ap.brand or "—" }}</td>
          <td><span class="badge bg-{{ 'success' if ap.condition in ('New','Good','Excellent') else 'warning' if ap.condition == 'Fair' else 'danger' }}">{{ ap.condition }}</span></td></tr>
      {% endfor %}
    </tbody>
  </table>
</details>
{% endif %}
```

Controller extension: pass only customer-safe fields:

```python
context.appliances = [{"appliance_name": a.appliance_name, "brand": a.brand,
    "condition": a.condition} for a in asset.get("custom_appliances", [])]
```

**Acceptance Criteria**:
- [ ] Uses `<details>` element — collapsed by default
- [ ] Shows: appliance name, brand, condition badge
- [ ] Warranty expiry and serial number NOT shown to customers
- [ ] No appliances → section hidden entirely
- [ ] Condition badge color: green for `New`/`Good`, orange for `Fair`, red for `Damaged`/`Missing`

---

### 8.4 Floor Plan Button

> **Requires**: 2.3 (`custom_floor_plan` field)

Some flats have a floor plan document (PDF or image) uploaded by the property manager. If one exists, the detail page shows a "View Floor Plan" button that opens the document in a new browser tab. If no floor plan is uploaded, the button is completely hidden — no broken links or empty states.

```html
{% if asset.custom_floor_plan %}
<a href="{{ asset.custom_floor_plan }}" target="_blank" rel="noopener"
   class="btn btn-outline-secondary mb-4">📄 {{ _("View Floor Plan") }}</a>
{% endif %}
```

**Acceptance Criteria**:
- [ ] "View Floor Plan" button visible only when `custom_floor_plan` is set
- [ ] Opens document in new browser tab (`target="_blank"`)
- [ ] Missing floor plan → button NOT rendered (no broken link)

---

### 8.5 Utilities Included Badge

> **Requires**: 2.3 (`custom_utilities_included` field)

Some flats include utility costs (electricity, water, gas) in the monthly rent, while others are metered separately. This badge gives tenants an immediate signal: if utilities are included, a green "Utilities included in rent" alert badge is shown prominently on the detail page. No specific rate information is shown either way — metered rates are internal.

```html
{% if asset.custom_utilities_included %}
<div class="alert alert-success py-2 mb-4">✅ {{ _("Utilities included in rent") }}</div>
{% endif %}
```

**Acceptance Criteria**:
- [ ] Green badge "Utilities included in rent" shown when `custom_utilities_included = 1`
- [ ] When utilities are metered, no rate details shown on public page
- [ ] Badge is visually distinct (success alert style)

---

### 8.6 SEO Structured Data

> **Requires**: 8.1 (context has flat data), Base D01-7.4 (SEO standards)

For search engines (Google, Bing) to display rich results for flat listings, the detail page must include **schema.org structured data** in JSON-LD format. This uses the `Apartment` type with fields like `numberOfRooms`, `floorSize`, and `offers.price`. This structured data is invisible to users but critical for SEO ranking and rich snippet display in search results.

Controller extension injects schema.org JSON-LD:

```python
context.schema_json = frappe.as_json({
    "@context": "https://schema.org", "@type": "Apartment",
    "name": asset.asset_name,
    "numberOfRooms": asset.get("custom_bedrooms"),
    "floorSize": {"@type": "QuantitativeValue", "value": asset.get("custom_area_sqm"), "unitCode": "MTK"},
    "address": {"@type": "PostalAddress", "addressLocality": asset.location},
    "offers": {"@type": "Offer", "price": asset.monthly_rate, "priceCurrency": config.default_currency},
})
```

Template:
```html
<script type="application/ld+json">{{ schema_json }}</script>
```

**Acceptance Criteria**:
- [ ] `<script type="application/ld+json">` with `@type: Apartment`
- [ ] Includes: `numberOfRooms` (bedrooms), `floorSize` (m² with `unitCode: MTK`), `address` (location)
- [ ] Includes: `offers.price` (monthly_rate), `offers.priceCurrency`
- [ ] `<title>`: `{bedrooms}-bedroom flat in {location} for rent – {site_name}`
- [ ] `<meta description>`: `{area}m² {furnished} flat on floor {floor}, {location}. {monthly_rate}/month.`

---

## 9. Flutter — Flat Models

### 9.1 `FlatAsset` Model

> **Requires**: Base D01-8.1 (Flutter project), 2.3 (custom field list)

The Dart data model representing a flat unit in the mobile app. It extends the base `RentalAsset` model with all flat-specific fields (bedrooms, bathrooms, area, furnishing, etc.), building amenities (as a flattened string list), and appliances (as a `List<FlatAppliance>`). Uses Freezed for immutability and JSON serialization. The `accessCode` field is intentionally **omitted** from this model — it must never be present in the app.

```dart
@freezed
class FlatAsset with _$FlatAsset { /* all flat-specific fields */ }
```

**Acceptance Criteria**:
- [ ] Model includes all base asset fields + all flat custom fields
- [ ] `fromJson` correctly maps Frappe's `custom_*` field names
- [ ] `buildingAmenities` is `List<String>` (flattened from child table)
- [ ] `appliances` is `List<FlatAppliance>`
- [ ] `accessCode` is NOT included in the model (never fetched from API)

---

### 9.2 `FlatAppliance` Model

> **Requires**: 9.1

Dart data model for a single appliance attached to a flat (e.g., Bosch washing machine, Samsung refrigerator). The model only contains **customer-safe fields** — serial numbers are excluded because they are internal asset management data that tenants don't need and shouldn't see.

```dart
@freezed
class FlatAppliance with _$FlatAppliance {
  const factory FlatAppliance({
    required String name,
    String? brand,
    String? model,
    DateTime? warrantyExpiry,
    required String condition,  // Excellent, Good, Fair, Damaged, Missing
  }) = _FlatAppliance;
  factory FlatAppliance.fromJson(Map<String, dynamic> json) => _$FlatApplianceFromJson(json);
}
```

**Acceptance Criteria**:
- [ ] Fields: name, brand, model, condition, warrantyExpiry (nullable)
- [ ] `serialNumber` NOT included (never shown to customer)
- [ ] `fromJson` maps Frappe response correctly

---

### 9.3 `FlatFilter` Model

> **Requires**: Base D01-8.1

Immutable data class that holds the current state of the catalog filter UI. When a tenant adjusts filters on the mobile app (bedroom count, price range, etc.), this model is updated via `copyWith()` and the catalog provider re-fetches data. The `toMap()` method converts the filter state into API query parameters that match the server's expected format (e.g., `bedrooms=0` for Studio, `parking=yes` for boolean).

```dart
@freezed
class FlatFilter with _$FlatFilter {
  const factory FlatFilter({
    int? bedrooms,
    String? furnished,
    double? minArea,
    double? maxArea,
    @Default(false) bool parkingIncluded,
    @Default(false) bool petsAllowed,
    double? maxPrice,
  }) = _FlatFilter;

  Map<String, dynamic> toMap() => {
    if (bedrooms != null) 'bedrooms': bedrooms == 0 ? 'studio' : '$bedrooms',
    if (furnished != null) 'furnished': furnished!,
    if (minArea != null) 'min_area': '${minArea!.toInt()}',
    if (maxArea != null) 'max_area': '${maxArea!.toInt()}',
    if (maxPrice != null) 'max_price': '${maxPrice!.toInt()}',
    if (parkingIncluded) 'parking': 'yes',
    if (petsAllowed) 'pets': 'yes',
  };
}
```

**Acceptance Criteria**:
- [ ] Fields: `bedrooms`, `furnished`, `minArea`, `maxArea`, `parkingIncluded`, `petsAllowed`, `maxPrice`
- [ ] `toMap()` produces query params compatible with the catalog API
- [ ] `copyWith()` supports immutable state updates
- [ ] Default state = no filters applied (all null/false)

---

## 10. Flutter — Flat Catalog Screen

### 10.1 `FlatFilterNotifier` Provider

> **Requires**: 9.3 (FlatFilter model), Base D01-8.6 (Riverpod setup)

A Riverpod state notifier that manages the flat catalog's active filters. When the tenant picks "2 bedrooms" in the filter sheet, the notifier updates the `FlatFilter` state, which automatically triggers the catalog provider to re-fetch data from the API. The `reset()` method clears all filters back to defaults (show everything).

```dart
@riverpod
class FlatFilterNotifier extends _$FlatFilterNotifier {
  @override
  FlatFilter build() => const FlatFilter();
  void setBedrooms(int? v)        => state = state.copyWith(bedrooms: v);
  void setFurnished(String? v)    => state = state.copyWith(furnished: v);
  void setAreaRange(double min, double max) => state = state.copyWith(minArea: min, maxArea: max);
  void setParkingIncluded(bool v) => state = state.copyWith(parkingIncluded: v);
  void setPetsAllowed(bool v)     => state = state.copyWith(petsAllowed: v);
  void setMaxPrice(double? v)     => state = state.copyWith(maxPrice: v);
  void reset()                    => state = const FlatFilter();
}
```

**Acceptance Criteria**:
- [ ] Methods: `setBedrooms`, `setFurnished`, `setAreaRange`, `setParkingIncluded`, `setPetsAllowed`, `setMaxPrice`, `reset`
- [ ] `reset()` returns all filters to default state
- [ ] Filter changes trigger re-fetch of catalog data

---

### 10.2 `flatAssetsProvider`

> **Requires**: 10.1, 6.2 (flat catalog API)

A Riverpod FutureProvider that fetches flat listings from the API. It's **parameterized by the current filter state** so different filter combinations produce different cache keys — switching from "2 bedrooms" to "3 bedrooms" triggers a new fetch, but switching back uses the cached result. `keepAlive: true` ensures data survives scrolling away and back.

```dart
@riverpod
Future<List<FlatAsset>> flatAssets(Ref ref, FlatFilter filter) =>
    FlatsApi().getFlats(filter);
```

**Acceptance Criteria**:
- [ ] Parameterized by `FlatFilter` — different filters produce different cache keys
- [ ] Returns `List<FlatAsset>`
- [ ] `keepAlive: true` for scroll-back survival

---

### 10.3 Flat Catalog Screen

> **Requires**: 10.1, 10.2, 9.1 (FlatAsset model)

The **main browsing screen** in the mobile app — equivalent to the web catalog page. It shows a 2-column grid of flat cards, each displaying a cover image, key specs (bedrooms, bathrooms, area), and monthly rate. A filter icon in the AppBar opens the `FlatFilterSheet` (10.4). Active filters are shown as dismissible chips above the grid so the user always knows what's filtered. Handles loading, empty, and error states.

A `ConsumerWidget` that displays flat assets in a 2-column grid with filter chip bar and AJAX refresh:

```dart
class FlatCatalogScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final filter = ref.watch(flatFilterNotifierProvider);
    final assets = ref.watch(flatAssetsProvider(filter));
    return Scaffold(
      appBar: AppBar(title: const Text('Flats'), actions: [
        IconButton(icon: const Icon(Icons.tune),
          onPressed: () => showModalBottomSheet(context: context,
            isScrollControlled: true, builder: (_) => FlatFilterSheet(filter: filter))),
      ]),
      body: Column(children: [
        _ActiveFlatFilterChips(filter: filter),
        Expanded(child: assets.when(
          data: (list) => list.isEmpty
            ? const Center(child: Text('No flats match your filters'))
            : GridView.builder(gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2, childAspectRatio: 0.72), itemCount: list.length,
                itemBuilder: (_, i) => _FlatCard(flat: list[i])),
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (e, _) => ErrorView(message: '$e'),
        )),
      ]),
    );
  }
}
```

**Acceptance Criteria**:
- [ ] 2-column grid of flat cards
- [ ] Each card: cover image, bedrooms, bathrooms, area, furnishing, monthly rate
- [ ] Tapping card navigates to flat detail screen
- [ ] Filter icon in AppBar opens `FlatFilterSheet`
- [ ] Active filter chips displayed as dismissible chips above grid
- [ ] Empty state: "No flats match your filters"
- [ ] Loading: `CircularProgressIndicator`
- [ ] Error: `ErrorView` with message

---

### 10.4 `FlatFilterSheet`

> **Requires**: 10.1 (FlatFilterNotifier)

A draggable bottom sheet that lets tenants set filter criteria. It mirrors the web sidebar (7.2) but uses mobile-native controls: `ChoiceChip` for bedrooms, `DropdownButtonFormField` for furnishing, `RangeSlider` for area (0–500 m²), and `SwitchListTile` for parking/pets toggles. The "Reset" button clears all filters; the "Apply" button dismisses the sheet and triggers a re-fetch.

Draggable bottom sheet with filter controls:

```dart
class FlatFilterSheet extends ConsumerWidget {
  final FlatFilter filter;
  const FlatFilterSheet({required this.filter, super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(flatFilterNotifierProvider.notifier);
    return DraggableScrollableSheet(initialChildSize: 0.85, expand: false,
      builder: (_, ctrl) => ListView(controller: ctrl, padding: const EdgeInsets.all(20), children: [
        // Header with Reset
        Row(children: [const Text('Filter Flats', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          const Spacer(), TextButton(onPressed: notifier.reset, child: const Text('Reset'))]),
        // Bedrooms: ChoiceChip row (Studio=0, 1, 2, 3, 4, 5+)
        // Furnishing: DropdownButtonFormField
        // Area: RangeSlider (0–500 m², step 10)
        // Parking: SwitchListTile
        // Pets: SwitchListTile
        FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Apply Filters')),
      ]),
    );
  }
}
```

**Acceptance Criteria**:
- [ ] Bottom sheet with: Bedrooms chips, Furnishing dropdown, Area range slider, Parking toggle, Pets toggle
- [ ] "Reset" button clears all filters
- [ ] "Apply Filters" dismisses sheet and triggers re-fetch
- [ ] Area slider range: 0–500 m², step 10

---

## 11. Flutter — Flat Detail Screen

### 11.1 `flatDetailProvider`

> **Requires**: 6.1 (flat detail API), Base D01-8.6 (FrappeClient)

A Riverpod FutureProvider that fetches the full detail of a single flat from the API (`get_flat_detail`). Used by the detail screen to load all flat-specific data, building amenities, and appliance list in a single API call.

```dart
@riverpod
Future<FlatAsset> flatDetail(Ref ref, String assetName) =>
    FlatsApi().getFlatDetail(assetName);
```

**Acceptance Criteria**:
- [ ] Fetches full flat detail including building amenities and appliances
- [ ] Returns `FlatAsset` model

---

### 11.2 Flat Detail Screen

> **Requires**: 11.1, 9.1 (FlatAsset), Base D04-10.4 (base detail structure)

The **full detail view** of a flat in the mobile app. Uses a `CustomScrollView` with a `SliverAppBar` for the image gallery (swipeable photo carousel), followed by the spec grid, amenity chips, utility badge, appliance/floor plan buttons, availability calendar, and the booking CTA. This screen is the equivalent of the web detail page (section 8) but built with Flutter-native widgets.

`CustomScrollView` with `SliverAppBar` image gallery and flat-specific sections:

```dart
class FlatDetailScreen extends ConsumerWidget {
  final String assetId;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final flat = ref.watch(flatDetailProvider(assetId));
    return flat.when(
      data: (f) => Scaffold(body: CustomScrollView(slivers: [
        SliverAppBar(expandedHeight: 280,
          flexibleSpace: FlexibleSpaceBar(background: PhotoGalleryWidget(images: f.images))),
        SliverToBoxAdapter(child: Padding(padding: const EdgeInsets.all(16), child: Column(children: [
          _buildSpecGrid(f),                          // 8.1 equivalent
          BuildingAmenitiesRow(amenities: f.buildingAmenities),  // 11.3
          if (f.utilitiesIncluded) _utilitiesBadge(),  // green badge
          if (f.appliances.isNotEmpty) _appliancesButton(context, f),
          if (f.floorPlanUrl != null) _floorPlanButton(context, f.floorPlanUrl!),
          AvailabilityCalendarWidget(assetName: f.name),
          _buildBookCTA(context, f),
        ]))),
      ])),
      loading: () => const Scaffold(body: Center(child: CircularProgressIndicator())),
      error: (e, _) => ErrorView(message: '$e'),
    );
  }
}
```

**Acceptance Criteria**:
- [ ] Image gallery carousel (swipeable)
- [ ] Spec grid: Bedrooms, Bathrooms, Area, Floor, Furnishing, View, Direction, Parking, Pets
- [ ] Building amenities as horizontal scrollable chip row
- [ ] "Utilities included" badge when flag is set
- [ ] "Appliances" button navigates to appliances screen (only when appliances exist)
- [ ] "View Floor Plan" button opens PDF/image viewer (only when floor plan is set)
- [ ] "View 3D Model" button opens WebView (only when preview mode is configured)
- [ ] Availability calendar widget (from base D04-10.5)
- [ ] Book Now / Request Info CTA (from base D04-10.4, D02-7.1)

---

### 11.3 `BuildingAmenitiesRow` Widget

> **Requires**: 11.2

A horizontal scrollable row of styled chips showing the building's amenities (Pool, Gym, Security, etc.). Returns `SizedBox.shrink()` if the amenities list is empty, so no empty space is wasted. This is the Flutter equivalent of the web amenity badges (8.2).

Horizontal scrollable chip row:

```dart
class BuildingAmenitiesRow extends StatelessWidget {
  final List<String> amenities;
  const BuildingAmenitiesRow({required this.amenities, super.key});
  @override
  Widget build(BuildContext context) {
    if (amenities.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('Building Amenities', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
      const SizedBox(height: 8),
      SingleChildScrollView(scrollDirection: Axis.horizontal,
        child: Row(children: amenities.map((a) => Container(
          margin: const EdgeInsets.only(right: 8),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          decoration: BoxDecoration(color: Colors.blue.shade50,
            borderRadius: BorderRadius.circular(20), border: Border.all(color: Colors.blue.shade200)),
          child: Text(a, style: TextStyle(fontSize: 13, color: Colors.blue.shade800)),
        )).toList()),
      ),
    ]);
  }
}
```

**Acceptance Criteria**:
- [ ] Horizontal `SingleChildScrollView` with styled chip containers
- [ ] Empty amenities list → widget returns `SizedBox.shrink()` (hidden)
- [ ] Each chip: blue-tinted background, rounded, readable text

---

### 11.4 `FlatSpecCard` Widget

> **Requires**: 11.2

A small stat card showing a single spec (e.g., "🛏 Bedrooms: 3"). Multiple cards are arranged in a `Wrap` layout to form the spec grid. Each card has an icon, a label, and a value. Missing values display "—" rather than blank or error text. This is the Flutter equivalent of the web spec grid tiles (8.1).

Small stat card used in the spec grid `Wrap`:

```dart
class FlatSpecCard extends StatelessWidget {
  final String icon, label, value;
  const FlatSpecCard({required this.icon, required this.label, required this.value, super.key});
  @override
  Widget build(BuildContext context) => Container(
    width: 80, padding: const EdgeInsets.all(8),
    decoration: BoxDecoration(border: Border.all(color: Colors.grey.shade300), borderRadius: BorderRadius.circular(8)),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      Text(icon, style: const TextStyle(fontSize: 20)),
      const SizedBox(height: 4),
      Text(label, style: TextStyle(fontSize: 10, color: Colors.grey.shade600)),
      Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
    ]),
  );
}
```

**Acceptance Criteria**:
- [ ] Small card with icon, label, and value
- [ ] Used in `Wrap` layout for responsive spec grid
- [ ] Missing value renders "—"

---

## 12. Flutter — Appliances Screen

### 12.1 `AppliancesScreen`

> **Requires**: 9.2 (FlatAppliance model), 11.2 (navigation from detail)

A dedicated screen listing all appliances in a flat. The user navigates here from the detail screen's "Appliances" button. Each appliance is displayed as an `ApplianceTile` (see F03-5.2) showing name, brand, condition badge, and warranty countdown. The screen is **read-only** — tenants can view appliance info but cannot modify anything.

A simple `ListView` of `ApplianceTile` widgets (see F03-5.2 for tile details):

```dart
class AppliancesScreen extends StatelessWidget {
  final List<FlatAppliance> appliances;
  const AppliancesScreen({required this.appliances, super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Appliances')),
    body: ListView.separated(
      padding: const EdgeInsets.all(16),
      itemCount: appliances.length,
      separatorBuilder: (_, __) => const Divider(),
      itemBuilder: (_, i) => ApplianceTile(appliance: appliances[i]),
    ),
  );
}
```

**Acceptance Criteria**:
- [ ] Lists all appliances with: name, brand, model, condition badge, warranty countdown
- [ ] Condition badge color: green (`New`/`Good`), blue (`Good`), orange (`Fair`), red (`Needs Repair`/`Damaged`)
- [ ] Warranty countdown: green (>30 days), orange (≤30 days), red (expired)
- [ ] Warranty countdown hidden when `warrantyExpiry` is null
- [ ] Serial number NOT shown
- [ ] Screen is read-only (no edit actions)

---

## 13. Flutter — Floor Plan Viewer

### 13.1 `FloorPlanViewerScreen`

> **Requires**: 11.2 (navigation), Base D01-8.2 (`flutter_pdfview` or similar dependency)

A full-screen viewer for floor plan documents. The viewer auto-detects the file type: **PDF files** open in an in-app PDF viewer (using `syncfusion_flutter_pdfviewer`), while **image files** open in an `InteractiveViewer` that supports pinch-to-zoom. The URL is passed via route query parameters.

Detects file type and renders accordingly:

```dart
class FloorPlanViewerScreen extends StatelessWidget {
  final String url;
  const FloorPlanViewerScreen({required this.url, super.key});
  @override
  Widget build(BuildContext context) {
    final isPdf = url.toLowerCase().endsWith('.pdf');
    return Scaffold(
      appBar: AppBar(title: const Text('Floor Plan')),
      body: isPdf
        ? SfPdfViewer.network(url)  // syncfusion_flutter_pdfviewer
        : InteractiveViewer(child: Image.network(url, fit: BoxFit.contain)),
    );
  }
}
```

**Acceptance Criteria**:
- [ ] PDF files open in in-app PDF viewer
- [ ] Image files open in full-screen image viewer
- [ ] URL passed via route query parameter
- [ ] Back button returns to flat detail

---

## 14. Flutter — Route Registration

### 14.1 GoRouter Routes

> **Requires**: Base D01-8.9 (GoRouter), all flat screens

Route registration for all flat-specific screens in the app's router. The flat catalog and detail use path-based parameters (`/flats/:id`), while the appliances screen receives its data via GoRouter's `extra` parameter (in-memory object passing) and the floor plan viewer uses query parameters for the document URL.

Added to `app_router.dart`:

```dart
GoRoute(path: '/flats', builder: (_, __) => const FlatCatalogScreen()),
GoRoute(path: '/flats/:id', builder: (_, s) => FlatDetailScreen(assetId: s.pathParameters['id']!)),
GoRoute(path: '/appliances', builder: (_, s) => AppliancesScreen(appliances: s.extra as List<FlatAppliance>)),
GoRoute(path: '/floor-plan', builder: (_, s) => FloorPlanViewerScreen(url: s.uri.queryParameters['url'] ?? '')),
```

**Acceptance Criteria**:
- [ ] `/flats` → `FlatCatalogScreen`
- [ ] `/flats/:id` → `FlatDetailScreen`
- [ ] `/appliances` → `AppliancesScreen` (receives `List<FlatAppliance>` via `extra`)
- [ ] `/floor-plan?url=...` → `FloorPlanViewerScreen`

---

## 15. Domain-Level Acceptance Criteria

- [ ] Property → Building → Flat hierarchy enforced (validation errors on missing links)
- [ ] Occupancy rate computed correctly at Building and Property level
- [ ] Flat catalog filters work: bedrooms, furnished, area, view, parking, pets, amenities
- [ ] Amenity filter joins through Building table correctly
- [ ] Flat detail shows spec grid, amenities, appliances, floor plan
- [ ] SEO structured data (`schema.org/Apartment`) rendered on flat detail pages
- [ ] `custom_access_code` NEVER exposed in any API or customer-facing surface
- [ ] Custom fields appear only for Flat-type assets (conditional section)

---

## 16. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (app scaffold + DocTypes + custom fields + API) | 3 days |
| Web (flat catalog + detail extensions + SEO) | 2 days |
| Flutter (models + catalog + detail + appliances + floor plan) | 3 days |
| **Total** | **8 days** |
