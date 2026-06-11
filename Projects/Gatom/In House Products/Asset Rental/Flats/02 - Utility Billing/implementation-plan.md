# Domain F02 — Utility Billing: Implementation Plan

> **Variant**: Flats (child app `rental_flats`)
> **Domain**: Utility Billing
> **Sequence**: 2 of 5
> **Depends on**: F01 (custom fields: meter IDs, `custom_utilities_included`), Base D05 (Rental Agreement), Base D06 (billing engine, invoices)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

In many rental markets, tenants pay for their actual utility consumption (electricity, water, gas) on top of the base rent. The **Utility Billing** domain handles this end-to-end: property managers enter monthly meter readings, the system computes consumption and charges, those charges get injected into the tenant's invoice, and tenants can view their usage history on the web portal and mobile app.

Some flats have utilities **included in rent** (`custom_utilities_included = 1`) — those skip this entire workflow. The billing integration ties into the base module's invoice engine (Base D06), and readings that arrive before an invoice exists are automatically swept onto the next invoice.

---

## 2. Frappe — `Utility Meter Reading` DocType

### 2.1 Schema Definition

> **Requires**: F01-2.3 (custom fields: meter IDs on Rental Asset), Base D04-2.1 (Rental Asset), Base D05-2.1 (Rental Agreement)

A **Utility Meter Reading** is the core document in this domain. Each record captures a single reading event: a staff member visits the flat, reads the electricity/water/gas meter, and enters the `current_reading`. The system then auto-computes the `consumption` (current − previous) and `total_charge` (consumption × rate). The `billed` flag tracks whether this charge has been added to an invoice yet.

This is a **staff-only** workflow — tenants never enter readings themselves. The `entered_by` field is auto-set for audit purposes.

| Field | Type | Required | Notes |
|---|---|---|---|
| `flat` | Link → Rental Asset | ✅ | Filtered to `asset_type = Flat` |
| `agreement` | Link → Rental Agreement | ✅ | |
| `meter_type` | Select | ✅ | `Electricity`, `Water`, `Gas` |
| `reading_date` | Date | ✅ | |
| `previous_reading` | Float | auto | Auto-fetched from last submitted reading |
| `current_reading` | Float | ✅ | |
| `consumption` | Float | computed | `current_reading - previous_reading` |
| `unit_rate` | Currency | computed | From `Rental Configuration` |
| `total_charge` | Currency | computed | `consumption × unit_rate` |
| `reading_photo` | Attach | | Photo evidence of meter |
| `entered_by` | Link → User | auto | `frappe.session.user` |
| `billed` | Check | | Default 0. Set to 1 when injected into invoice |

**Acceptance Criteria**:
- [ ] DocType exists in Frappe Desk under "Rental" module
- [ ] `flat`, `agreement`, `meter_type`, `reading_date`, `current_reading` are mandatory
- [ ] `previous_reading` is read-only (auto-fetched)
- [ ] `consumption` and `total_charge` are read-only (computed)
- [ ] `billed` is read-only (set programmatically)
- [ ] Only `Property Manager` and `System Manager` can create/submit

---

### 2.2 Controller — `validate()`

> **Requires**: 2.1, Base D01-3.1 (utility rate fields on Rental Configuration)

This hook fires before save and does the heavy computation. It looks up the **last submitted reading** for the same flat and meter type to determine `previous_reading`, then calculates `consumption` and fetches the per-unit rate from the global configuration. The tricky edge case: the **very first reading** for a meter has no predecessor, so `previous_reading` defaults to `current_reading`, resulting in zero consumption (a fair baseline).

```python
def validate(self):
    prev = frappe.db.get_value("Utility Meter Reading",
        filters={"flat": self.flat, "meter_type": self.meter_type, "docstatus": 1},
        fieldname="current_reading", order_by="reading_date desc")
    self.previous_reading = prev or self.current_reading  # first reading = 0 consumption
    self.consumption = self.current_reading - self.previous_reading
    config = frappe.get_single("Rental Configuration")
    rate_field = {"Electricity": "electricity_rate_per_unit",
                  "Water": "water_rate_per_unit", "Gas": "gas_rate_per_unit"}[self.meter_type]
    self.unit_rate = getattr(config, rate_field) or 0
    self.total_charge = self.consumption * self.unit_rate
```

**Acceptance Criteria**:
- [ ] Previous reading auto-fetched from last submitted reading for same flat + meter type
- [ ] First reading ever: `previous_reading = current_reading`, `consumption = 0`, `total_charge = 0`
- [ ] First reading logs a warning (audit trail for the zero-consumption edge case)
- [ ] `consumption = current_reading - previous_reading`
- [ ] `total_charge = consumption × unit_rate` from config
- [ ] Rate for Electricity fetched from `electricity_rate_per_unit` config field
- [ ] Rate for Water fetched from `water_rate_per_unit` config field
- [ ] Rate for Gas fetched from `gas_rate_per_unit` config field
- [ ] Missing rate field → `unit_rate = 0`, `total_charge = 0` (no crash)

---

### 2.3 Controller — `on_submit()`

> **Requires**: 2.2, 3.1 (`inject_reading_into_invoice` utility)

When the property manager submits (finalizes) a meter reading, the system immediately tries to add the charge to the tenant's current draft invoice. If no draft invoice exists yet (e.g., the reading was entered mid-month before the billing cycle created the invoice), the reading stays `billed = 0` and will be picked up later by the unbilled sweep (3.2).

```python
def on_submit(self):
    from rental_flats.utils.utility_billing import inject_reading_into_invoice
    inject_reading_into_invoice(self)
```

**Acceptance Criteria**:
- [ ] On submit, `inject_reading_into_invoice` is called
- [ ] If injection succeeds, `billed = 1` is set
- [ ] If no draft invoice exists, reading stays `billed = 0` (unbilled)

---

## 3. Frappe — Utility Billing Engine

### 3.1 `inject_reading_into_invoice()`

> **Requires**: 2.1 (reading schema), Base D06-2.1 (Sales Invoice linked to agreement)

This utility function takes a submitted meter reading and attempts to add it as a **line item** on the agreement's current draft invoice. It looks for an existing draft (unpaid, unsubmitted) invoice linked to the reading's agreement. If found, it appends a line item with the item code `UTIL-ELECTRICITY` (or WATER/GAS), the consumption as quantity, and the unit rate as price. If no draft invoice exists, the function silently returns — the reading will be caught by the sweep job later.

```python
def inject_reading_into_invoice(reading):
    if not reading.total_charge or not reading.agreement:
        return
    draft_invoice = frappe.db.get_value("Sales Invoice", {
        "custom_rental_agreement": reading.agreement, "docstatus": 0}, "name")
    if draft_invoice:
        inv = frappe.get_doc("Sales Invoice", draft_invoice)
        _append_utility_line(inv, reading)
        inv.save(ignore_permissions=True)
        frappe.db.set_value("Utility Meter Reading", reading.name, "billed", 1)
```

**Acceptance Criteria**:
- [ ] Reading with `total_charge = 0` → no injection (silent return)
- [ ] Reading with no `agreement` → no injection
- [ ] Draft invoice exists for agreement → utility line item appended
- [ ] Line item includes: `item_code = UTIL-ELECTRICITY` (or WATER/GAS), `qty = consumption`, `rate = unit_rate`
- [ ] Line item description: `"Electricity: 1500 → 1650 units"` (previous → current)
- [ ] `billed = 1` set after successful injection
- [ ] No draft invoice → reading stays `billed = 0`

---

### 3.2 `sweep_unbilled_utilities()`

> **Requires**: 3.1, Base D06-2.2 (billing hook — new invoice creation triggers this)

This is the **catch-up mechanism** for utility charges. When the base billing engine creates a new monthly subscription invoice, it calls this function. It finds all meter readings that are submitted (`docstatus = 1`) but not yet billed (`billed = 0`) for the agreement, and appends them all as line items to the new invoice. This ensures no utility charges are ever lost — even if the reading was entered days before the invoice was created.

This function is called by the base module's invoice creation hook, not by a scheduler.

```python
def sweep_unbilled_utilities(agreement_name, invoice_name):
    unbilled = frappe.get_all("Utility Meter Reading", filters={
        "agreement": agreement_name, "billed": 0, "docstatus": 1},
        fields=["name", "meter_type", "consumption", "unit_rate",
                "total_charge", "reading_date", "previous_reading", "current_reading"])
    if not unbilled:
        return
    inv = frappe.get_doc("Sales Invoice", invoice_name)
    for r in unbilled:
        _append_utility_line(inv, r)
        frappe.db.set_value("Utility Meter Reading", r.name, "billed", 1)
    inv.save(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Called when `rental_core` creates a new subscription invoice
- [ ] Finds all unbilled (billed=0, docstatus=1) readings for the agreement
- [ ] Appends each as a line item to the new invoice
- [ ] Sets `billed = 1` on each swept reading
- [ ] No unbilled readings → silent return (no error)
- [ ] Multiple unbilled readings across different meter types → all appended

---

### 3.3 `_append_utility_line()` Helper

> **Requires**: 3.1

A private helper used by both `inject_reading_into_invoice` (3.1) and `sweep_unbilled_utilities` (3.2). It creates a single Sales Invoice line item from a meter reading. The item code follows the pattern `UTIL-{METER_TYPE}` (e.g., `UTIL-ELECTRICITY`), and the description shows the reading range (e.g., "Electricity: 1500 → 1650 units") so the tenant understands the charge on their invoice.

Shared helper that appends a single utility charge line item to a Sales Invoice:

```python
def _append_utility_line(invoice, reading):
    item_code = f"UTIL-{reading.meter_type.upper()}"
    invoice.append("items", {
        "item_code": item_code,
        "item_name": f"{reading.meter_type} ({reading.reading_date})",
        "qty": reading.consumption,
        "rate": reading.unit_rate,
        "amount": reading.total_charge,
        "description": f"{reading.meter_type}: {reading.previous_reading} → {reading.current_reading} units"
    })
```

**Acceptance Criteria**:
- [ ] Creates a Sales Invoice Item with `item_code = UTIL-{METER_TYPE}`
- [ ] `item_name = "{meter_type} ({reading_date})"`
- [ ] `qty = consumption`, `rate = unit_rate`
- [ ] `description` includes previous → current reading range
- [ ] Utility Items (`UTIL-ELECTRICITY`, `UTIL-WATER`, `UTIL-GAS`) must be pre-created as non-stock Items

---

### 3.4 Utility Item Seeding

> **Requires**: F01-2.1 (app scaffold)

The invoice line items reference ERPNext **Item** documents (like products in a catalog). Utility charges need three special non-stock Items: `UTIL-ELECTRICITY`, `UTIL-WATER`, and `UTIL-GAS`. These are created automatically when `rental_flats` is installed, in the `after_install()` hook. Without these Items, the billing engine would fail when trying to append utility line items.

In `setup.py after_install()`, create the non-stock Items needed for utility line items:

```python
def _seed_utility_items():
    for code, name in [
        ("UTIL-ELECTRICITY", "Electricity Utility Charge"),
        ("UTIL-WATER", "Water Utility Charge"),
        ("UTIL-GAS", "Gas Utility Charge"),
    ]:
        if not frappe.db.exists("Item", code):
            frappe.get_doc({
                "doctype": "Item", "item_code": code, "item_name": name,
                "item_group": "Rental Services", "is_stock_item": 0,
                "include_item_in_manufacturing": 0,
            }).insert(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] `after_install()` creates 3 non-stock Items: `UTIL-ELECTRICITY`, `UTIL-WATER`, `UTIL-GAS`
- [ ] Items are in item group "Rental Services"
- [ ] Duplicate creation handled gracefully (`ignore_if_duplicate`)

---

## 4. Frappe — Configuration Fields

### 4.1 Utility Rate Fields on `Rental Configuration`

> **Requires**: Base D01-3.1 (Rental Configuration singleton), F01-2.3 (custom field injection)

The platform operator sets **per-unit rates** for each utility type (electricity per kWh, water per m³, gas per unit) in the global Rental Configuration. These rates are used by the `validate()` hook (2.2) to compute charges. Changing a rate does NOT retroactively affect already-submitted readings — only new readings use the current rate.

Added via `setup.py` custom field injection:

```python
create_custom_fields({"Rental Configuration": [
    {"fieldname": "utility_rates_section", "fieldtype": "Section Break", "label": "Utility Rates"},
    {"fieldname": "electricity_rate_per_unit", "fieldtype": "Currency", "label": "Electricity Rate (per kWh)", "default": "0"},
    {"fieldname": "water_rate_per_unit", "fieldtype": "Currency", "label": "Water Rate (per m³)", "default": "0"},
    {"fieldname": "gas_rate_per_unit", "fieldtype": "Currency", "label": "Gas Rate (per unit)", "default": "0"},
]})
```

| Field | Type | Notes |
|---|---|---|
| `electricity_rate_per_unit` | Currency | Rate per kWh |
| `water_rate_per_unit` | Currency | Rate per m³ |
| `gas_rate_per_unit` | Currency | Rate per unit |

**Acceptance Criteria**:
- [ ] Fields exist on `Rental Configuration` after `rental_flats` is installed
- [ ] Default values are 0 (not null)
- [ ] Changing rates does NOT retroactively affect already-submitted readings

---

## 5. Frappe — Scheduler Events

### 5.1 `remind_utility_meter_readings` (25th of Month)

> **Requires**: F01-2.2 (hooks.py), Base D05-2.1 (Rental Agreement)

Property managers are busy and may forget to take meter readings. This scheduler job fires on the **25th of every month** and checks each active flat agreement: if no meter reading has been submitted this month, it sends an email reminder + ToDo to the property manager. This gives them 5 days before month-end to enter readings before the billing cycle runs.

Flats with `custom_utilities_included = 1` are skipped since they don't require readings.

Fires on the 25th of each month. For each active flat agreement with metered utilities, checks if readings have been submitted this month:

```python
def remind_utility_meter_readings():
    if getdate(today()).day != 25:
        return
    active = frappe.get_all("Rental Agreement", {"status": "Active"}, ["name", "asset"])
    for agr in active:
        asset = frappe.get_doc("Rental Asset", agr.asset)
        if asset.asset_type != "Flat" or asset.custom_utilities_included:
            continue
        this_month_start = frappe.utils.get_first_day(today())
        submitted = frappe.db.exists("Utility Meter Reading", {
            "agreement": agr.name, "docstatus": 1, "reading_date": [">=", this_month_start]})
        if not submitted:
            _notify_pm(agr, "Utility reading due for this month")
```

**Acceptance Criteria**:
- [ ] Fires on the 25th of each month only
- [ ] Runs but does nothing on any other day
- [ ] For each active flat agreement with metered utilities: checks if readings submitted this month
- [ ] Missing readings → email + ToDo sent to Property Manager
- [ ] Already-submitted readings → no notification
- [ ] Flats with `custom_utilities_included = 1` → skipped
- [ ] Vehicle agreements → skipped

---

### 5.2 Missing Reading Alert

> **Requires**: 5.1

If a property manager ignores the 25th reminder and still hasn't entered readings by the 1st of the next month, this **escalation alert** fires. It lists which specific meter types are missing (e.g., "Missing readings for last month: Electricity, Water") so the manager knows exactly what to address. This is a safety net to prevent billing gaps that would snowball into large catch-up charges.

Fires on the 1st of the month. If the previous month had no readings for an active agreement, sends an alert:

```python
def alert_missing_readings():
    if getdate(today()).day != 1:
        return
    last_month_start = add_months(get_first_day(today()), -1)
    last_month_end = get_last_day(last_month_start)
    active = frappe.get_all("Rental Agreement", {"status": "Active"}, ["name", "asset"])
    for agr in active:
        asset = frappe.get_doc("Rental Asset", agr.asset)
        if asset.asset_type != "Flat" or asset.custom_utilities_included:
            continue
        submitted = frappe.db.exists("Utility Meter Reading", {
            "agreement": agr.name, "docstatus": 1,
            "reading_date": ["between", [last_month_start, last_month_end]]})
        if not submitted:
            missing_meters = [m for m in ["Electricity", "Water", "Gas"]
                if not frappe.db.exists("Utility Meter Reading", {
                    "agreement": agr.name, "meter_type": m, "docstatus": 1,
                    "reading_date": ["between", [last_month_start, last_month_end]]})]
            _notify_pm(agr, f"Missing readings for last month: {', '.join(missing_meters)}")
```

**Acceptance Criteria**:
- [ ] On the 1st of the month, if last month had no readings for an active agreement → alert fires
- [ ] Alert includes: flat name, agreement number, missing meter types
- [ ] Sent to `managed_by` user on the building/property

---

## 6. Frappe — Utility History API

### 6.1 `get_utility_history`

> **Requires**: 2.1 (Utility Meter Reading schema)

This is the **customer-facing API** that returns a tenant's utility usage history. It's used by both the web portal page and the Flutter app. For security, it only returns readings belonging to the authenticated customer's agreement — attempting to access another customer's data returns HTTP 403. The response is intentionally stripped down: tenants see `consumption`, `unit_rate`, and `total_charge`, but NOT the raw meter readings or photo evidence (those are internal).

```python
@frappe.whitelist()
def get_utility_history(agreement, meter_type=None):
    """Returns last 24 submitted readings for the agreement (customer-facing)."""
```

**Acceptance Criteria**:
- [ ] Returns last 24 submitted readings for the given agreement
- [ ] Optional `meter_type` filter (Electricity, Water, Gas, or all)
- [ ] Sorted by `reading_date` descending
- [ ] Only returns readings for the current customer's agreement (server-side filter by `frappe.session.user`)
- [ ] Another customer's agreement → HTTP 403
- [ ] Returns: `reading_date`, `consumption`, `unit_rate`, `total_charge`, `meter_type`
- [ ] Does NOT return: `previous_reading`, `current_reading`, `reading_photo` (customer doesn't need raw readings)

---

### 6.2 `submit_meter_reading` (Staff Only)

> **Requires**: 2.1

A convenience API for property managers to enter meter readings without navigating Frappe Desk. Only users with the `Property Manager` or `System Manager` role can call it — customers are blocked with HTTP 403. It creates and immediately submits a reading, triggering the full billing pipeline (consumption computation → invoice injection). Returns the computed charge so the manager gets instant feedback.

```python
@frappe.whitelist()
def submit_meter_reading(agreement, meter_type, current_reading, reading_photo=None):
    """Staff-only. Creates and submits a Utility Meter Reading; returns computed charge."""
```

**Acceptance Criteria**:
- [ ] Only users with `Property Manager` or `System Manager` role can call
- [ ] Customer role → HTTP 403
- [ ] Creates and submits a `Utility Meter Reading` document
- [ ] Returns computed: `consumption`, `unit_rate`, `total_charge`
- [ ] Optionally accepts `reading_photo` attachment

---

## 7. Web — Utility History Portal (`/my-utilities`)

### 7.1 Controller `rental_flats/www/my-utilities.py`

> **Requires**: 6.1 (utility history API), F01-2.2 (portal menu entry)

The **"Utility Usage" portal page** (`/my-utilities`) is a customer-facing page accessible from the sidebar menu. It shows tenants their electricity, water, and gas usage history with charts and tables. The controller identifies the logged-in customer, finds their active flat agreements, filters out those with included utilities, and fetches the last 6 readings per meter type. The page is server-rendered (SSR) for fast initial load.

Server-rendered portal page. Redirects guests, fetches utility data for active flat agreements:

```python
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/my-utilities"
        raise frappe.Redirect
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    flat_agreements = [a.name for a in frappe.get_all("Rental Agreement",
        filters={"customer": customer, "status": "Active"})
        if frappe.db.get_value("Rental Asset",
            frappe.db.get_value("Rental Agreement", a.name, "asset"), "asset_type") == "Flat"]
    context.utility_data = {}
    for agr in flat_agreements:
        asset = frappe.db.get_value("Rental Agreement", agr, "asset")
        if frappe.db.get_value("Rental Asset", asset, "custom_utilities_included"):
            continue  # skip: utilities included
        for meter in ("Electricity", "Water", "Gas"):
            readings = frappe.get_all("Utility Meter Reading", filters={
                "agreement": agr, "meter_type": meter, "docstatus": 1},
                fields=["reading_date", "consumption", "unit_rate", "total_charge"],
                order_by="reading_date desc", limit=6)
            if readings:
                context.utility_data.setdefault(agr, {})[meter] = readings
    context.title = "Utility Usage"
```

**Acceptance Criteria**:
- [ ] Guest → redirected to `/login?redirect-to=/my-utilities`
- [ ] Logged-in customer with active flat agreements → utility data rendered
- [ ] Flats with `custom_utilities_included = 1` → skipped (no utility data)
- [ ] Customer with no flat agreements → empty state / redirect
- [ ] Data fetched for last 6 months per meter type per agreement

---

### 7.2 Tabbed Layout per Meter Type

> **Requires**: 7.1 (context has utility data)

Each agreement's utility data is organized into **Bootstrap tabs** — one tab per meter type (Electricity, Water, Gas). If a customer has multiple flat agreements, each gets its own card with its own set of tabs. Tabs only appear if readings exist for that meter type, so a flat that only has electricity and water won't show a Gas tab.

Template uses Bootstrap tabs per meter type per agreement:

```html
{% for agr, meters in utility_data.items() %}
<div class="card mb-4">
  <div class="card-header fw-semibold">🏠 {{ frappe.db.get_value("Rental Agreement", agr, "asset") }}</div>
  <div class="card-body">
    <ul class="nav nav-tabs mb-3">
      {% for meter in meters.keys() %}
      <li class="nav-item"><button class="nav-link {% if loop.first %}active{% endif %}"
        data-bs-toggle="tab" data-bs-target="#tab-{{ agr }}-{{ meter|lower }}">{{ meter }}</button></li>
      {% endfor %}
    </ul>
    <div class="tab-content"><!-- chart + table per tab (see 7.3, 7.4) --></div>
  </div>
</div>
{% endfor %}
```

**Acceptance Criteria**:
- [ ] Tabs: Electricity, Water, Gas
- [ ] Active tab shows chart + table
- [ ] Tab only shown if readings exist for that meter type
- [ ] Multiple active agreements → separate card per agreement

---

### 7.3 Bar Chart (Chart.js)

> **Requires**: 7.2

Inside each utility tab, a **bar chart** visualizes monthly consumption trends. Tenants can instantly see if their usage is going up or down. Built with Chart.js (loaded from CDN). Each bar represents one month's consumption in natural units (kWh for electricity, m³ for water). If there are no readings for a meter type, the chart is not rendered and a "No readings yet" message is shown instead.

Chart.js bar chart rendering consumption per month:

```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<canvas id="chart-{{ tab_id }}" height="80"></canvas>
<script>
new Chart(document.getElementById('chart-{{ tab_id }}'), {
  type: 'bar',
  data: {
    labels: {{ readings|map(attribute='reading_date')|list|tojson }},
    datasets: [{ label: 'Consumption (units)',
      data: {{ readings|map(attribute='consumption')|list|tojson }},
      backgroundColor: 'rgba(37,99,235,0.7)', borderRadius: 6 }]
  },
  options: { plugins: { legend: { display: false } } }
});
</script>
```

**Acceptance Criteria**:
- [ ] Bar chart shows monthly consumption (units) for last 6 months
- [ ] X-axis: reading dates; Y-axis: consumption
- [ ] Chart renders with no JS errors
- [ ] Empty data → chart not rendered (table shows "No readings yet")

---

### 7.4 Readings Table

> **Requires**: 7.2

Below the chart, a simple data table shows the exact numbers: reading date, consumption (units), per-unit rate, and total charge. This gives tenants transparency into how their bill was calculated. The table is sorted newest-first and is completely read-only — no edit or submit actions.

Below the chart, a data table for numeric detail:

```html
<table class="table table-sm mt-3">
  <thead><tr><th>Date</th><th>Units</th><th>Rate</th><th>Charge</th></tr></thead>
  <tbody>
    {% for r in readings %}
    <tr>
      <td>{{ r.reading_date }}</td><td>{{ r.consumption }}</td>
      <td>{{ frappe.utils.fmt_money(r.unit_rate) }}</td>
      <td><strong>{{ frappe.utils.fmt_money(r.total_charge) }}</strong></td>
    </tr>
    {% endfor %}
  </tbody>
</table>
```

**Acceptance Criteria**:
- [ ] Columns: Date, Units (consumption), Rate, Charge
- [ ] Sorted by date descending (newest first)
- [ ] Currency values formatted with `frappe.utils.fmt_money()`
- [ ] Table is read-only (no edit/submit actions)

---

## 8. Web — My Rentals Extension

### 8.1 Utility Summary on Agreement Card

> **Requires**: Base D05-10.1 (My Rentals portal), 6.1 (utility data)

The base platform has a **"My Rentals"** portal page (`/my-rentals`) showing the tenant's active agreements as cards. This subtask extends those cards for flat-type agreements to include a utility summary: either a "Utilities included" badge (for inclusive flats) or the last charge per meter type (e.g., "Electricity: $45.00 | Water: $12.00"). A "View full utility history" link navigates to the dedicated `/my-utilities` page.

Extend the base `/my-rentals` agreement card template to show utility summary for flat agreements:

```html
{% if agr.asset_type == "Flat" %}
  {% if agr.utilities_included %}
    <span class="badge bg-success">Utilities included</span>
  {% else %}
    <div class="d-flex gap-2 mt-2">
      {% for meter, charge in agr.last_utility_charges.items() %}
      <span class="badge bg-light text-dark">{{ meter }}: {{ frappe.utils.fmt_money(charge) }}</span>
      {% endfor %}
    </div>
    <a href="/my-utilities" class="small">View full utility history →</a>
  {% endif %}
{% endif %}
```

Controller extension adds `last_utility_charges` dict per agreement.

**Acceptance Criteria**:
- [ ] For flat agreements with metered utilities: last charge per meter type shown inline
- [ ] For flat agreements with included utilities: "Utilities included" badge shown
- [ ] "View full utility history" link navigates to `/my-utilities`
- [ ] Vehicle agreements → no utility section

---

## 9. Flutter — Utility Readings Screen

### 9.1 `UtilityReading` Model

> **Requires**: Base D01-8.1 (Flutter project)

The Dart data model for a single utility reading as returned by the customer-facing API. Uses Freezed for immutability and automatic JSON serialization. Note that `previousReading` and `currentReading` are included (for display context like "1500 → 1650 units") even though they're not editable by the customer.

```dart
@freezed
class UtilityReading with _$UtilityReading {
  const factory UtilityReading({
    required DateTime readingDate,
    required String meterType,
    required double previousReading,
    required double currentReading,
    required double consumption,
    required double unitRate,
    required double totalCharge,
  }) = _UtilityReading;
  factory UtilityReading.fromJson(Map<String, dynamic> json) => _$UtilityReadingFromJson(json);
}
```

**Acceptance Criteria**:
- [ ] Fields: `readingDate`, `meterType`, `consumption`, `unitRate`, `totalCharge`
- [ ] `fromJson` maps Frappe response correctly
- [ ] `previousReading` and `currentReading` included (for display context)

---

### 9.2 `utilityHistoryProvider`

> **Requires**: 9.1, 6.1 (utility history API), Base D01-8.6 (FrappeClient)

A Riverpod FutureProvider that calls the `get_utility_history` API endpoint and returns a typed list of readings. The provider is parameterized by `agreementId` so the app can show utility history for specific agreements. Used by the `UtilityReadingsScreen` (9.3) and the agreement detail tab (10.1).

```dart
@riverpod
Future<List<UtilityReading>> utilityHistory(Ref ref, String agreementId) =>
    FlatsApi().getUtilityHistory(agreementId);
```

**Acceptance Criteria**:
- [ ] Fetches last 24 readings for the agreement
- [ ] Returns `List<UtilityReading>`
- [ ] Error state on API failure

---

### 9.3 `UtilityReadingsScreen`

> **Requires**: 9.2, 9.1

The **main utility history screen** in the mobile app. It has three tabs (Electricity, Water, Gas), each containing a bar chart (top) and a chronological reading list (bottom). If the flat's utilities are included in rent, the screen shows a simple "Utilities are included in your rent" message with a checkmark icon instead. The screen is entirely **read-only** — only property managers can enter readings, and they do so through Desk or the staff API.

Tabbed screen per meter type with chart and reading list:

```dart
class UtilityReadingsScreen extends ConsumerWidget {
  final String agreementId;
  final bool utilitiesIncluded;
  const UtilityReadingsScreen({required this.agreementId, this.utilitiesIncluded = false, super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (utilitiesIncluded) {
      return Scaffold(appBar: AppBar(title: const Text('Utility Usage')),
        body: const Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(Icons.check_circle_outline, size: 64, color: Colors.green),
          SizedBox(height: 16), Text('Utilities are included in your rent.')])));
    }
    final history = ref.watch(utilityHistoryProvider(agreementId));
    return DefaultTabController(length: 3, child: Scaffold(
      appBar: AppBar(title: const Text('Utility Usage'),
        bottom: const TabBar(tabs: [Tab(text: '⚡ Electricity'), Tab(text: '💧 Water'), Tab(text: '🔥 Gas')])),
      body: history.when(
        data: (readings) => TabBarView(children: ['Electricity', 'Water', 'Gas'].map((meter) {
          final filtered = readings.where((r) => r.meterType == meter).toList();
          if (filtered.isEmpty) return Center(child: Text('No $meter readings yet'));
          return ListView(padding: const EdgeInsets.all(16), children: [
            UtilityChartWidget(readings: filtered), const SizedBox(height: 16),
            ...filtered.map((r) => UtilityReadingTile(reading: r)),
          ]);
        }).toList()),
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => ErrorView(message: '$e'),
      ),
    ));
  }
}
```

**Acceptance Criteria**:
- [ ] If `utilitiesIncluded = true` → shows "Utilities are included in your rent" message with icon
- [ ] If metered: 3 tabs (Electricity, Water, Gas)
- [ ] Each tab: bar chart (top) + reading list (bottom)
- [ ] Empty tab (no readings for meter type) → "No {meter} readings yet"
- [ ] Screen is read-only — no submit button visible for Customer role
- [ ] Loading: `CircularProgressIndicator`
- [ ] Error: `ErrorView`

---

### 9.4 `UtilityChartWidget` (fl_chart)

> **Requires**: 9.3, Base D01-8.2 (`fl_chart` dependency)

A bar chart widget built with the `fl_chart` package that visualizes monthly utility consumption. Bars are ordered oldest-to-newest (left to right) with month labels on the X-axis and consumption units on the Y-axis. Limited to 6 bars (last 6 months) for readability. This is the Flutter equivalent of the web Chart.js bar chart (7.3).

Bar chart widget using `fl_chart`:

```dart
class UtilityChartWidget extends StatelessWidget {
  final List<UtilityReading> readings;
  const UtilityChartWidget({required this.readings, super.key});
  @override
  Widget build(BuildContext context) {
    final sorted = readings.reversed.toList(); // oldest → newest
    return SizedBox(height: 180, child: BarChart(BarChartData(
      barGroups: sorted.asMap().entries.map((e) => BarChartGroupData(
        x: e.key, barRods: [BarChartRodData(
          toY: e.value.consumption, color: Theme.of(context).colorScheme.primary,
          width: 18, borderRadius: BorderRadius.circular(4))],
      )).toList(),
      titlesData: FlTitlesData(
        bottomTitles: AxisTitles(sideTitles: SideTitles(showTitles: true,
          getTitlesWidget: (v, _) => Text(DateFormatter.shortMonth(sorted[v.toInt()].readingDate),
              style: const TextStyle(fontSize: 10)))),
        leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: true, reservedSize: 40)),
        rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
        topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
      ),
      gridData: FlGridData(show: false), borderData: FlBorderData(show: false),
    )));
  }
}
```

**Acceptance Criteria**:
- [ ] Bar chart with consumption on Y-axis, month labels on X-axis
- [ ] Data sorted oldest → newest (left to right)
- [ ] Bars use theme primary color with border radius
- [ ] Max 6 bars visible (last 6 months)
- [ ] No grid lines (clean look)

---

### 9.5 `UtilityReadingTile` Widget

> **Requires**: 9.3

A single row in the reading list below the chart. Shows the reading date, consumption formula ("X units × Y/unit"), and total charge. The charge amount is bold to make it the visual focal point. This is the mobile equivalent of a row in the web readings table (7.4).

List tile showing a single reading's data:

```dart
class UtilityReadingTile extends StatelessWidget {
  final UtilityReading reading;
  const UtilityReadingTile({required this.reading, super.key});
  @override
  Widget build(BuildContext context) => ListTile(
    title: Text(DateFormatter.fullDate(reading.readingDate)),
    subtitle: Text('${reading.consumption} units × ${reading.unitRate}/unit'),
    trailing: Text(CurrencyFormatter.format(reading.totalCharge),
        style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
  );
}
```

**Acceptance Criteria**:
- [ ] Shows: date, consumption value, unit rate, total charge
- [ ] Charge is bold/emphasized
- [ ] Uses consistent date formatting

---

## 10. Flutter — Agreement Detail Extension

### 10.1 Utilities Tab on Agreement Detail

> **Requires**: Base D05-12.2 (Agreement Detail Screen)

The base agreement detail screen in the app shows general rental info. This subtask adds a **"Utilities" tab** specifically for flat-type agreements. The tab shows a compact summary: the last charge per meter type as small cards, plus a "View Full History" button that navigates to the full `UtilityReadingsScreen`. For flats with included utilities, it shows a simple "included" card instead.

Add a "Utilities" tab to the agreement detail screen for flat-type agreements:

```dart
// In agreement detail screen TabBar
if (agreement.assetType == 'Flat') ...[
  Tab(text: 'Utilities'),
]
// Tab content:
if (agreement.utilitiesIncluded)
  _utilitiesIncludedCard()
else
  Column(children: [
    // Summary cards: last charge per meter type
    ...['Electricity', 'Water', 'Gas'].map((m) => _lastChargeCard(m, agreement)),
    // Link to full history
    TextButton(onPressed: () => context.push('/agreement/${agreement.name}/utilities'),
      child: const Text('View Full History →')),
  ])
```

**Acceptance Criteria**:
- [ ] "Utilities" tab shown only for flat-type agreements
- [ ] Tab shows: last charge per meter type as summary cards
- [ ] "View Full History" button navigates to `UtilityReadingsScreen`
- [ ] Vehicle agreements → no Utilities tab

---

## 11. Flutter — Route Registration

### 11.1 Utility Routes

> **Requires**: Base D01-8.9 (GoRouter)

Registers the `/agreement/:id/utilities` route in the app's router. The `included` query parameter controls which variant to show: `included=true` displays the simple "utilities included" screen, while the default shows the full tabbed reading history.

Added to `app_router.dart`:

```dart
GoRoute(
  path: '/agreement/:id/utilities',
  builder: (_, s) => UtilityReadingsScreen(
    agreementId: s.pathParameters['id']!,
    utilitiesIncluded: s.uri.queryParameters['included'] == 'true'),
),
```

**Acceptance Criteria**:
- [ ] `/agreement/:id/utilities` → `UtilityReadingsScreen`
- [ ] Query param `included=true` shows the "included" variant

---

## 12. Domain-Level Acceptance Criteria

- [ ] Staff submits meter reading → consumption and charge computed correctly
- [ ] Reading injected into draft invoice as line item
- [ ] Unbilled readings swept onto next subscription invoice
- [ ] First reading for a meter = 0 consumption (edge case handled)
- [ ] 25th-of-month reminder fires for missing readings
- [ ] Tenants see utility history (read-only) — no submit capability
- [ ] Guarantors CANNOT see utility charges
- [ ] Flats with `utilities_included` flag → no billing, no readings expected
- [ ] Chart renders correctly with real data

---

## 13. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (DocType + billing engine + scheduler + config + API) | 3 days |
| Web (portal page + chart + table + my-rentals extension) | 1.5 days |
| Flutter (model + screen + chart + agreement tab) | 2.5 days |
| **Total** | **7 days** |
