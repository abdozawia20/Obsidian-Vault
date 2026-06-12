# Domain V01 — Fleet & Vehicle Registry: Implementation Plan

> **Variant**: Vehicles (child app `rental_vehicles`)
> **Domain**: Fleet & Vehicle Registry
> **Sequence**: 1 of 7
> **Depends on**: Base D01 (app scaffold, Rental Asset, Rental Configuration, API patterns, web stubs, Flutter stubs), Base D04 (Rental Asset state machine)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

The Fleet & Vehicle Registry is the **foundation** of the Vehicles module — every other vehicle domain depends on the DocTypes, custom fields, and API endpoints created here. It adds a **Vehicle Category** system (rate classes like Sedan, SUV, Van with per-category pricing, mileage allowances, and driver requirements) and extends the base `Rental Asset` with vehicle-specific attributes (plate, VIN, make/model, fuel type, transmission, GPS device linkage).

The domain also builds the **customer-facing catalog** (web + Flutter) with vehicle-specific filters (category, fuel type, transmission, seats) and extends the **booking flow** with driver's license collection and age validation — because renting a car has legal requirements that renting a flat does not.

This domain does **not** duplicate agreement, billing, or notification logic — those are inherited from `rental_core`.

---

## 2. Frappe — App Scaffold

### 2.1 App Initialization

> **Requires**: Base D01-2.1 (`rental_core` installed and functional)

The `rental_vehicles` app is a **Frappe child app** — it depends on `rental_core` (the base platform) and extends it with fleet-specific features. It cannot be installed standalone. This is the exact same pattern used by `rental_flats` — the base platform provides agreements, billing, deposits, notifications, and asset management, while this app adds everything specific to cars, trucks, and motorcycles.

This subtask creates the app skeleton using `bench new-app`, sets up the directory layout (`doctype/` for schemas, `api/` for REST endpoints, `utils/` for shared business logic, `overrides/` for extending base DocTypes), and verifies the dependency chain works correctly. The most important thing to validate here is that Frappe resolves the `required_apps` list and refuses installation if `rental_core` is missing — this prevents a developer from accidentally deploying the vehicles module without the base platform.

```bash
bench new-app rental_vehicles
# required_apps = ["frappe", "erpnext", "rental_core"]
bench --site rental.localhost install-app rental_vehicles
```

**Acceptance Criteria**:
- [ ] `bench new-app rental_vehicles` creates the app directory
- [ ] `required_apps` includes `frappe`, `erpnext`, `rental_core`
- [ ] App installs without errors on a site that already has `rental_core`
- [ ] Installing `rental_vehicles` without `rental_core` fails with a dependency error
- [ ] Directory structure matches: `doctype/`, `api/`, `utils/`, `overrides/`

---

### 2.2 `hooks.py` — Events & Scheduler

> **Requires**: 2.1

Frappe's `hooks.py` is the app's central wiring file — think of it as the app's event subscription manifest. Every background job, every lifecycle hook, and every DocType override is declared here. Without this file being correct, none of the vehicle-specific logic will fire.

For the vehicles module, this file registers: **4 daily scheduler jobs** — one to compute each vehicle's usage profile (Heavy/High/Normal/Light/Idle) which drives maintenance scheduling, and three to scan for expiring insurance, registration, and roadworthiness documents so the Fleet Manager gets advance warning. It also registers **1 doc_event** — a `validate` hook on `Rental Agreement` that checks for maintenance conflicts before allowing a booking. Finally, it declares **1 override_doctype_class** that extends the base `Rental Asset` with vehicle-specific validation (requiring plate number, VIN, and category for vehicle-type assets). The critical thing to test here is that installing this app doesn't break existing `rental_core` functionality — the hooks must be additive, not disruptive.

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

**Acceptance Criteria**:
- [ ] All 4 scheduler jobs are registered and callable without import errors
- [ ] `validate` event fires when a Rental Agreement is saved/submitted
- [ ] `override_doctype_class` correctly extends the base `Rental Asset` class
- [ ] Installing `rental_vehicles` does not break existing `rental_core` functionality

---

### 2.3 Custom Fields Injected on Install (`setup.py`)

> **Requires**: 2.1, Base D04-2.1 (Rental Asset DocType exists)

The base platform has a generic `Rental Asset` DocType that represents any rentable thing — a flat, a vehicle, a piece of equipment. Instead of creating a completely separate "Vehicle" DocType (which would duplicate the asset lifecycle, status management, and agreement linking), the vehicles app injects **custom fields** into `Rental Asset` using Frappe's `create_custom_fields()` mechanism in the `after_install` hook.

These fields are **conditionally visible** — they only appear in the Desk form when `asset_type == "Vehicle"`. This means a Fleet Manager adding a new sedan sees plate number, VIN, make, model, fuel type, and transmission fields, while a Property Manager adding a new apartment sees none of these. The fields cover five categories: (1) **Category link** — connects to the Vehicle Category rate card, (2) **Identification** — plate number and VIN (both unique per vehicle in the real world and enforced at DB level), (3) **Mechanical specs** — fuel type, engine CC, transmission type, seat count, (4) **Mileage tracking** — current odometer, mileage at last service, next service date/mileage (consumed by the maintenance scheduling engine in V04), and (5) **GPS device linkage** — a checkbox and device ID for telematics integration (V05).

Additionally, the fields for **document tracking** (insurance policy number/provider/expiry, registration number/expiry, roadworthiness expiry) are included here because they're stored on the asset, not on a separate document. The V02 (Insurance & Registration) domain reads these fields to enforce booking blocks and fire expiry alerts.

**Critical design decision**: Plate number and VIN are both marked `unique: 1` — enforced at the database level. In the real world, no two vehicles share a plate number or VIN. If a data entry error creates a duplicate, the DB constraint catches it immediately rather than allowing inconsistent data to propagate through agreements and mileage logs.

**Acceptance Criteria**:
- [ ] All custom fields are created after `bench --site ... install-app rental_vehicles`
- [ ] Fields only appear in the Desk form when `asset_type == "Vehicle"`
- [ ] `custom_plate_number` is unique — inserting a duplicate raises a DB error
- [ ] `custom_vin` is unique — inserting a duplicate raises a DB error
- [ ] `custom_category` links to `Vehicle Category` DocType
- [ ] `custom_fuel_type` has options: `Petrol`, `Diesel`, `Electric`, `Hybrid`, `CNG`
- [ ] `custom_transmission` has options: `Manual`, `Automatic`
- [ ] `custom_usage_profile` has options: `Idle`, `Light`, `Normal`, `High`, `Heavy`
- [ ] GPS fields: `custom_has_gps` (Check), `custom_gps_device_id` (Data)
- [ ] Document fields: insurance (policy number, provider, expiry, doc), registration (number, expiry, doc), roadworthiness (expiry, doc)

---

## 3. Frappe — Vehicle Category DocType

### 3.1 `Vehicle Category` Schema

> **Requires**: 2.1

In fleet rental, vehicles are grouped into **categories** (Sedan, SUV, Van, Truck, etc.) and each category has its own pricing structure, mileage allowance, and rules. A compact sedan might cost 80 AED/day with 200 km included, while a luxury SUV costs 350 AED/day with 300 km included. A motorcycle requires a different license class than a bus. These category-level policies are what the **Vehicle Category** DocType manages.

This is the **rate card and policy template** for an entire class of vehicles. When the Fleet Manager wants to change the overage rate for all SUVs, they edit the SUV category once — not each individual vehicle. When a customer books a vehicle, the system looks up the category to determine: what to charge per day/week/month, how many free kilometres are included, what happens per extra km driven, what the fuel return policy is (must the tank be full?), and whether the driver meets the age and license requirements. Every downstream domain depends on this DocType: the mileage engine (V03) reads `included_km_per_day` and `overage_rate_per_km`, the booking flow reads `min_driver_age` and `required_license_class`, and the fuel deficit calculator reads `fuel_policy`.

| Field | Type | Notes |
|---|---|---|
| `category_name` | Data | e.g., "Economy Sedan", "Luxury SUV" |
| `type` | Select | Sedan, SUV, Van, Truck, Motorcycle, Bus, Special |
| `daily_rate` | Currency | |
| `weekly_rate` | Currency | |
| `monthly_rate` | Currency | |
| `included_km_per_day` | Float | Free km per rental day |
| `overage_rate_per_km` | Currency | Charge per km over the allowance |
| `fuel_policy` | Select | `Full-to-Full`, `Full-to-Empty`, `Pre-Purchase` |
| `min_driver_age` | Int | Default 18 |
| `required_license_class` | Data | e.g., "B", "C", "D" |

**Acceptance Criteria**:
- [ ] DocType created in Frappe Desk
- [ ] `category_name` is the name field
- [ ] `type` includes all 7 options: Sedan, SUV, Van, Truck, Motorcycle, Bus, Special
- [ ] `fuel_policy` includes 3 options: Full-to-Full, Full-to-Empty, Pre-Purchase
- [ ] `min_driver_age` defaults to 18
- [ ] Fleet Manager has full CRUD; Rental Agent has read-only access
- [ ] Deleting a category with linked vehicles is blocked (validation)

---

### 3.2 `Rental Asset` Override (`overrides/rental_asset_override.py`)

> **Requires**: 2.2, 2.3, 3.1

Frappe's `override_doctype_class` mechanism lets one app replace the controller class of a DocType defined in another app. The **VehicleAsset** class extends the base `Rental Asset` class to add vehicle-specific validation that fires every time a vehicle is saved or submitted.

Without this override, a Fleet Manager could create a vehicle without a plate number, without a VIN, or without assigning it to a category — all of which would break downstream logic (the mileage engine needs the category to know the overage rate; the booking flow needs the plate number for customer identification at pickup; the VIN is required for insurance and registration compliance). The override enforces these three mandatory fields whenever `asset_type == "Vehicle"`, while leaving non-vehicle assets (flats, equipment) completely unaffected.

The override class is also the extension point for the registration expiry hard-block (V02) — when the vehicle's registration has expired, the override prevents any new agreement from being created for that vehicle.

**Acceptance Criteria**:
- [ ] Saving a Vehicle asset without `custom_category` → validation error
- [ ] Saving a Vehicle asset without `custom_plate_number` → validation error
- [ ] Saving a Vehicle asset without `custom_vin` → validation error
- [ ] Non-Vehicle assets (Flat type) are unaffected by the override
- [ ] Override class is correctly resolved by Frappe at runtime

---

## 4. Frappe — Vehicle API Endpoints

### 4.1 `get_vehicle_detail` API

> **Requires**: 2.3 (custom fields exist), 3.1 (Vehicle Category)

This is the primary API endpoint that powers the vehicle detail page (both web and Flutter). When a customer taps on a vehicle in the catalog, this endpoint returns everything they need to see: make/model, year, fuel type, engine CC, transmission, seat count, plate number (so they can identify the vehicle at pickup), the category's rate card (daily/weekly/monthly pricing), the mileage policy (included km/day and overage rate), and the fuel policy.

The response also includes the category detail embedded (not just a category name) — this means the frontend doesn't need a second API call to fetch pricing information. For Fleet Manager callers, additional fields are included: insurance/registration expiry dates, current mileage, usage profile, and GPS device status.

**Critical security rule**: The VIN (Vehicle Identification Number) is a sensitive identifier — it can be used to look up a vehicle's ownership history, accident records, and financial liens. It must **never** be included in customer-facing API responses. The endpoint checks the caller's role and strips the VIN for Customer role but includes it for Fleet Manager and System Manager roles who need it for administrative purposes.

**Acceptance Criteria**:
- [ ] Returns: category, plate number, make, model, year, fuel type, transmission, seats, engine CC, insurance expiry, registration expiry
- [ ] **VIN is NOT included** for Customer role
- [ ] VIN IS included for Fleet Manager and System Manager roles
- [ ] Category detail (rates, included km, overage rate, fuel policy, min age) is embedded in the response
- [ ] Non-existent asset name → 404 error
- [ ] Inactive asset → excluded (not returned)

---

### 4.2 `get_maintenance_schedule` API

> **Requires**: V04-3.1 (Maintenance Schedule DocType — created later, stub here)

The availability calendar on the vehicle detail page shows customers which dates are available for booking. This endpoint returns the **maintenance-blocked dates** that need to be merged into the calendar's unavailability display. When a vehicle is scheduled for a tyre change from March 5–7, those dates must appear as "unavailable" on the calendar — just like dates blocked by another customer's reservation.

**Key UX principle**: Customers must never know *why* a date is blocked. Whether it's another booking, planned maintenance, or a management hold, all blocked dates look identical — a simple grey/unavailable state. This prevents customers from inferring fleet operational details ("this car needs a lot of maintenance, maybe I should pick a different one") and protects business intelligence about utilization rates.

For Fleet Manager callers, the full response includes service type, technician details, and notes — because they need this information to manage the fleet schedule.

**Acceptance Criteria**:
- [ ] Returns: `scheduled_date`, `scheduled_end_date`, `status` for each window
- [ ] Only `Planned` and `In Progress` windows are included (not Completed or Cancelled)
- [ ] Response does NOT include `service_type`, `technician`, or `notes` for customer-facing API
- [ ] Fleet Manager API response includes all fields

---

### 4.3 `submit_vehicle_booking` API

> **Requires**: 4.1, 3.1, Base D05 (booking API)

Renting a vehicle has legal requirements that renting a flat does not — the driver must have a valid license, the license must cover the entire rental period (you can't rent a car for 6 months if your license expires in 3), and some vehicle categories have minimum age requirements (e.g., you must be 25+ to rent a luxury sports car in many jurisdictions).

This API endpoint **wraps** the base `submit_booking_request` with vehicle-specific validation. It runs three checks before delegating to the base booking flow: (1) **License expiry** — computed from the rental start date + duration, the license must be valid through the end date. A 6-month rental starting January 1 with a license expiring March 15 → rejected. (2) **Age check** — the driver's age (from DOB) is compared against the category's `min_driver_age`. If the category requires 25+ and the driver is 22, the booking is rejected. (3) **Maintenance conflict** — the vehicle's maintenance schedule is checked for overlapping windows.

If all checks pass, the wrapper calls the base booking API to create the agreement, then attaches the vehicle-specific custom fields (`custom_license_number`, `custom_license_class`, `custom_license_expiry`, `custom_driver_dob`) to the agreement record. These fields are needed for compliance auditing and for the rental counter to verify the physical license at pickup.

**This is the server-side safety net** — even if a developer forgets client-side validation or a user bypasses JavaScript, these checks run on the server and cannot be circumvented.

**Acceptance Criteria**:
- [ ] License expiry before rental end date → `frappe.throw` with descriptive error
- [ ] Driver age below category's `min_driver_age` → `frappe.throw` with descriptive error
- [ ] Vehicle with maintenance conflict → `frappe.throw` with conflicting dates listed
- [ ] Vehicle with expired registration → booking blocked (D02 hard-block)
- [ ] Valid booking → agreement created with `custom_license_number`, `custom_license_class`, `custom_license_expiry`, `custom_driver_dob` set
- [ ] Server-side validation cannot be bypassed by skipping client-side checks

---

## 5. Web — Vehicle Catalog

### 5.1 Vehicle Catalog Controller (`rental_vehicles/www/vehicles.py`)

> **Requires**: Base D01-7.1 (web framework), 2.3 (custom fields), 3.1 (Vehicle Category)

The **vehicle catalog page** (`/rentals/vehicles`) is the storefront — the first thing a customer sees when they want to rent a car. It shows all available vehicles as cards in a grid layout, similar to how car rental websites like Hertz or Enterprise display their fleet. The page is **publicly accessible** (no login required) because the goal is to let potential customers browse the inventory and see pricing before they commit to creating an account.

Unlike the base asset catalog (which is generic), this page adds vehicle-specific filters that car renters expect: filter by category ("I want an SUV"), by fuel type ("I need a diesel for long-distance"), by transmission ("I can only drive automatic"), by minimum seats ("I need at least 7 seats for my family"), by maximum price, and by location. All filters are applied via AJAX — when the customer selects "SUV" from the category dropdown, the grid updates immediately without a full page reload.

The controller queries `Rental Asset` with `asset_type = "Vehicle"`, `status = "Available"`, and `is_active = 1`, then applies the user's filter selections. Each card shows: cover photo, make + model ("Toyota Camry"), year, fuel type, seat count, and monthly rate. The page is limited to 24 results to keep load times fast.

**Acceptance Criteria**:
- [ ] Page accessible at `/rentals/vehicles` without login
- [ ] Default view shows all available, active vehicles sorted by monthly rate ascending
- [ ] Category filter scopes results correctly (e.g., "SUV" → only SUVs)
- [ ] Fuel type filter: Petrol, Diesel, Electric, Hybrid, CNG
- [ ] Transmission filter: Manual, Automatic, or Any
- [ ] Minimum seats filter: 2+, 4+, 5+, 7+, 9+
- [ ] Max price filter scopes by `monthly_rate`
- [ ] Location filter is case-insensitive and uses `LIKE` matching
- [ ] Each card shows: cover image, make + model, year, fuel type, seat count, monthly rate
- [ ] Maximum 24 results per page
- [ ] SEO metatags set: title = "Browse Vehicles for Rent"

---

### 5.2 Vehicle Filter Sidebar Template

> **Requires**: 5.1

The **filter sidebar** is the UI that lets customers narrow down the vehicle catalog to find exactly what they need. It sits alongside the vehicle grid and provides controls for each filterable dimension. The sidebar is a Jinja2 template partial injected into the catalog page.

The **category dropdown** is dynamically populated from all active `Vehicle Category` records in the database — if the Fleet Manager creates a new category (e.g., "Electric SUV"), it automatically appears in the filter without any code changes. The **transmission filter** uses toggle buttons instead of a dropdown because there are only 3 options (Any / Auto / Manual) and toggle buttons provide faster one-tap selection on mobile. The **fuel type** and **min seats** filters use standard dropdowns.

All filters trigger an AJAX `GET` request to the catalog controller with the selected values as query parameters. The controller re-queries the database with the new filters and returns updated HTML that replaces the vehicle grid — no full page reload, no lost scroll position.

**Acceptance Criteria**:
- [ ] Category dropdown populated from `Vehicle Category` records
- [ ] Fuel type dropdown: Petrol, Diesel, Electric, Hybrid, CNG
- [ ] Transmission toggle buttons: Any, Auto, Manual
- [ ] Min seats dropdown: Any, 2+, 4+, 5+, 7+
- [ ] All filters trigger AJAX reload without full page refresh
- [ ] Active filters visible as state (selected values)
- [ ] Clearing a filter returns to "All" state

---

### 5.3 Vehicle Detail — Spec Grid & Mileage Policy

> **Requires**: Base D01-7.2 (detail page template), 4.1 (vehicle detail API), 3.1 (Vehicle Category)

When a customer clicks on a vehicle in the catalog, they land on the **detail page** which must give them everything they need to decide whether to book: what kind of car is it, what does it cost, and what's the fine print on mileage and fuel? This subtask extends the base asset detail template (which already handles images, availability calendar, and the "Book Now" button) with vehicle-specific blocks that only render when `asset_type == "Vehicle"`.

The **spec grid** displays vehicle specifications in a visually scannable tile format — 6 tiles showing Make/Model, Year, Fuel Type, Engine CC, Transmission, and Seats. Each tile has an emoji icon, a label, and a value. This is the equivalent of the "specifications" section on any car listing website.

The **mileage policy box** is critically important for customer transparency. Vehicle rentals often come with a mileage allowance (e.g., 200 km/day included) and an overage rate (e.g., +0.50 AED per extra km). If the customer drives 250 km in a day, they pay for 50 km of overage. This box makes the policy visible before booking, reducing disputes later. It pulls data from the linked `Vehicle Category` and displays: included km per day, overage rate per km, and the fuel policy (Full-to-Full means return with a full tank, Full-to-Empty means the customer pays for a full tank upfront and doesn't need to refuel before return).

**Critical rule**: The VIN (Vehicle Identification Number) must NEVER appear on this page — it's a sensitive identifier. The plate number is shown because customers need it to identify the vehicle at pickup ("your Toyota Camry is the white one with plate ABC-1234").

**Acceptance Criteria**:
- [ ] Spec grid shows 6 tiles: Make/Model, Year, Fuel Type, Engine, Transmission, Seats
- [ ] Mileage policy box shows: included km/day, overage rate/km, fuel policy
- [ ] Mileage policy data comes from the linked `Vehicle Category`
- [ ] VIN is **not** displayed anywhere on the page
- [ ] Plate number is displayed (for pickup identification)
- [ ] Availability calendar includes maintenance-blocked dates as unavailable (no reason shown)
- [ ] Non-vehicle assets do NOT show spec grid or mileage policy

---

### 5.4 Booking Step 2 — Driver License Fields

> **Requires**: 5.3, Base D05 (booking form), 3.1 (Vehicle Category for min age)

When booking a flat, Step 2 collects the customer's name, phone number, and tenant type (individual/company). When booking a vehicle, this step must also collect **driver information** required by law: license number, license class (e.g., "B" for cars, "C" for trucks), license expiry date, and date of birth. Without these, the rental company cannot legally hand over the vehicle.

This subtask adds 4 fields to Step 2 that are **conditionally rendered** — they only appear when the customer is booking a vehicle (not a flat). The Jinja template checks `asset.asset_type == "Vehicle"` and injects the fields along with JavaScript variables (`window.IS_VEHICLE`, `window.RENTAL_END_DATE`, `window.MIN_DRIVER_AGE`) that the validation logic needs.

Two client-side validations run before the customer can advance to Step 3:
- **License expiry ≥ rental end date**: If the customer's license expires on March 15 but the rental runs until June 30, the booking is rejected with an error: "License must be valid for the entire rental period." This prevents the scenario where a customer is driving with an expired license mid-rental.
- **Driver age ≥ category minimum**: Some vehicle categories (sports cars, commercial trucks) have minimum age requirements. If the SUV category requires 25+ and the customer is 22 (computed from DOB), the booking is rejected: "Driver must be at least 25 years old."

These are client-side checks for instant feedback — the server-side API (4.3) performs the same validation as a security backstop.

**Acceptance Criteria**:
- [ ] License Number field is required (validation error if empty)
- [ ] License Expiry field rejects dates before `RENTAL_END_DATE`
- [ ] DOB field rejects ages below `MIN_DRIVER_AGE`
- [ ] Error messages are descriptive: "License must be valid for the entire rental period" / "Driver must be at least X years old"
- [ ] Fields only appear for vehicle bookings (not flat bookings)
- [ ] Client-side validation prevents advancing to Step 3

---

### 5.5 Booking Step 5 — Policy Acknowledgement

> **Requires**: 5.4, 3.1 (Vehicle Category)

Overage charges are the #1 source of post-rental disputes in vehicle rental businesses. Customers often don't realize they're paying per-km past the included allowance, and when they see a 200 AED overage charge on their final invoice, they claim they were never told. The **policy acknowledgement box** solves this by making the customer explicitly confirm they understand the deal before submitting the booking.

The **confirmation step** (Step 5) is extended with a yellow/warning-styled box that displays three critical numbers from the Vehicle Category: (1) included km/day (e.g., "200 km"), (2) overage rate per km (e.g., "+0.50 AED/km"), and (3) the fuel policy (e.g., "Full-to-Full — return with a full tank"). Below the box is a mandatory checkbox: "I understand and accept the mileage and fuel policy." The submit button remains disabled until the checkbox is ticked.

This box only appears for vehicle bookings — flat bookings don't have mileage policies. The `validateStep5()` function in `booking.js` checks `#agree_mileage_policy.checked` before allowing form submission.

**Acceptance Criteria**:
- [ ] Policy box shows: included km/day, overage rate/km, fuel policy — from Vehicle Category
- [ ] Checkbox text: "I understand and accept the mileage and fuel policy."
- [ ] Submit button is disabled until checkbox is ticked
- [ ] Policy box only appears for vehicle bookings
- [ ] Non-vehicle bookings do not show the policy box

---

### 5.6 My Rentals — Vehicle Mileage Summary

> **Requires**: Base D05 (My Rentals portal), V03-3.1 (mileage log API)

Once a customer has an active vehicle rental, they want to know: "How many km have I driven? How many do I have left before overage charges kick in?" The **mileage summary bar** answers this question at a glance without the customer needing to dig into the mileage log screen (V03).

For vehicle agreements in the **My Rentals** portal, a compact bar is shown beneath the agreement card displaying: pickup odometer (e.g., "📍 Pickup: 45,230 km"), last recorded odometer (e.g., "🛣 Last: 45,890 km"), included km total (e.g., "✅ Included: 6,000 km"), and overage charge in red if applicable (e.g., "Overage: +150 AED"). For GPS-equipped vehicles, the system can show an estimated current mileage derived from GPS distance data; for non-GPS vehicles, the message "Mileage available at return" is shown instead — because without GPS, the system has no way to know the current odometer until the vehicle is physically returned.

This summary bar only appears for vehicle agreements — flat agreements don't have mileage tracking.

**Acceptance Criteria**:
- [ ] Pickup odometer shown for active vehicle agreements
- [ ] Last recorded odometer shown (from latest mileage log)
- [ ] Included km total shown (from Vehicle Category × rental days)
- [ ] Overage charge shown in red if applicable
- [ ] GPS vehicles: estimated current mileage shown
- [ ] Non-GPS vehicles: "Mileage available at return" text
- [ ] Non-vehicle agreements do not show mileage summary

---

## 6. Flutter — Vehicle Catalog & Detail

### 6.1 Vehicle Filter Sheet (`widgets/vehicle_filter_sheet.dart`)

> **Requires**: Base D01-8.3 (screen stubs), 3.1 (Vehicle Category)

On mobile, the filter sidebar used on the web doesn't work — there's no room for a persistent sidebar alongside a vehicle grid. Instead, the Flutter app uses a **modal bottom sheet** that slides up from the bottom of the screen when the user taps the filter icon. This is the standard mobile pattern used by apps like Airbnb and Booking.com.

The filter sheet provides the same vehicle-specific filter controls as the web sidebar: category dropdown (populated from `Vehicle Category` records), fuel type dropdown (Petrol/Diesel/Electric/Hybrid/CNG), transmission toggle (Any/Auto/Manual), minimum seats selector (Any/2+/4+/5+/7+), and a max price slider. When the user applies filters and closes the sheet, the selected filters appear as **chips** (small pill-shaped tags) above the vehicle grid — e.g., "SUV ×", "Automatic ×", "5+ seats ×". Tapping the "×" on a chip removes that filter and refreshes the results.

The filter state is managed by a Riverpod `VehicleFilterNotifier` — a reactive state holder that the `vehicleAssetsProvider` watches. When any filter changes, the provider automatically re-fetches the vehicle list from the API with the updated filter parameters.

**Acceptance Criteria**:
- [ ] Bottom sheet opens from filter icon in app bar
- [ ] Category dropdown populated from Vehicle Category records
- [ ] Fuel type dropdown: Petrol, Diesel, Electric, Hybrid, CNG
- [ ] Transmission toggle: Any / Auto / Manual
- [ ] Min seats options: Any, 2+, 4+, 5+, 7+
- [ ] Max price slider with configurable range
- [ ] Active filter chips displayed above the grid
- [ ] Removing a chip clears that filter and refreshes results
- [ ] Applying filters triggers `vehicleAssetsProvider` re-fetch

---

### 6.2 Vehicle Catalog Screen

> **Requires**: 6.1, 4.1 (vehicle API)

The Flutter **vehicle catalog screen** is the mobile equivalent of the web catalog page — it's what the customer sees when they open the app and start browsing for a car to rent. Vehicles are displayed in a 2-column grid of cards (similar to a Google Play Store layout). Each card shows: cover photo (or a placeholder if no photo is uploaded), make + model ("Toyota Camry"), year ("2024"), fuel type ("Petrol"), seat count ("5"), and monthly rate ("1,200 AED/mo"). Tapping a card navigates to the vehicle detail screen.

The screen uses the `vehicleAssetsProvider` which accepts a `VehicleFilter` object — when the user applies filters from the filter sheet (6.1), the provider automatically re-fetches with the new criteria. Loading state shows a centered spinner, error state shows a retry-enabled error view, and empty state shows a "No vehicles match your filters" message. The grid uses `SliverGridDelegateWithFixedCrossAxisCount` with `crossAxisCount: 2` and `childAspectRatio: 0.75` to ensure cards have enough vertical space for the photo and text.

**Acceptance Criteria**:
- [ ] 2-column grid with `childAspectRatio: 0.75`
- [ ] Each card shows: cover image, make + model, year, fuel type, seats, monthly rate
- [ ] Tapping a card navigates to the vehicle detail screen
- [ ] Loading state shows `CircularProgressIndicator`
- [ ] Error state shows `ErrorView` with message
- [ ] Empty state handled when no vehicles match filters

---

### 6.3 Vehicle Detail Screen

> **Requires**: 6.2, 4.1 (vehicle detail API), 3.1 (Vehicle Category)

The vehicle **detail screen** is the Flutter equivalent of the web detail page — it's where the customer makes their final decision to book. The screen is structured as a scrollable column with these sections from top to bottom:

1. **Image gallery**: Horizontal PageView of vehicle photos with dot indicators. If no photos are available, a branded placeholder is shown.
2. **Spec card** (`VehicleSpecCard` widget): A grid of labeled tiles showing make/model, year, fuel type, engine CC, transmission, and seat count — the essential facts about the car.
3. **Mileage policy card** (`MileagePolicyCard` widget): An orange-tinted card showing the included km/day, overage rate per km, and fuel policy. This is critically important — it's the customer's last chance to understand the mileage terms before booking.
4. **Availability calendar**: Shows available and blocked dates. Maintenance windows from V04 are merged in as blocked dates with no reason shown.
5. **Plate number**: Displayed for pickup identification ("Your vehicle: plate ABC-1234").
6. **"Book Now" CTA**: Primary action button that launches the booking flow.
7. **3D preview button** (optional): If the vehicle has a configured `previewUrl`, a button opens a WebView with a 3D model viewer. This is a premium feature for high-end vehicles.

VIN is intentionally omitted from this screen for security reasons (see V01-4.1).

**Acceptance Criteria**:
- [ ] Spec card shows 6 items: Make/Model, Year, Fuel Type, Engine CC, Transmission, Seats
- [ ] Mileage policy card shows: included km/day, overage rate/km, fuel policy
- [ ] VIN is NOT shown anywhere
- [ ] Plate number is shown
- [ ] Availability calendar includes maintenance-blocked dates (no reason shown)
- [ ] "Book Now" button navigates to booking flow
- [ ] 3D preview button opens WebView if `previewUrl` is configured
- [ ] Pull-to-refresh reloads detail data

---

### 6.4 Vehicle Booking Step 2 — Driver License Fields

> **Requires**: 6.3, Base D05 (booking flow), 3.1 (Vehicle Category)

The base booking flow has a generic Step 2 that collects personal details (name, phone, tenant type). For vehicle bookings, this step needs additional driver-specific fields that are legally required before handing over a car. The Flutter booking flow detects that the asset is a vehicle (`asset.assetType == 'Vehicle'`) and **swaps in** the `VehicleBookingStep2` widget, which includes all the base fields plus the driver license section.

The license section adds 4 fields: **license number** (text input, required), **license class** (text input with a hint showing the category's required class, e.g., "B"), **license expiry** (date picker), and **date of birth** (date picker). Both date fields have **inline validation** that runs when the user selects a date — not just at form submission:

- **License expiry**: The rental end date is computed from `startDate + (durationMonths × 30 days)`. If the license expires before this date, the field shows an error immediately: "License must cover the full rental period (ends June 30, 2025)." The date picker's `firstDate` is set to today, so past dates can't be selected.
- **Date of birth**: The driver's age is computed from the selected date. If the age is below the category's `min_driver_age`, the field shows: "Driver must be at least 25 years old." The date picker's `lastDate` is set to `DateTime.now() - (minDriverAge * 365 days)`, so underage dates can't be selected.

Even with these client-side checks, the server-side API (V01-4.3) performs identical validation as a security backstop against tampered requests.

**Acceptance Criteria**:
- [ ] License number field is required — form cannot advance if empty
- [ ] License expiry before rental end → inline error with end date mentioned
- [ ] DOB age below `min_driver_age` → inline error with required age mentioned
- [ ] License class hint shows `requiredLicenseClass` from category (e.g., "B")
- [ ] Widget only replaces Step 2 for vehicle bookings
- [ ] Server-side re-validation catches tampered submissions

---

### 6.5 Vehicle Models & Providers

> **Requires**: 6.1, Base D01-8.6 (FrappeClient)

Every Flutter feature needs a data layer: model classes that define the shape of API responses, and providers that fetch and cache the data. This subtask creates the foundational data layer for the entire vehicle feature set.

**Freezed models** provide immutable, JSON-serializable data classes with `copyWith()`, `==`, and `hashCode` built in. Three models are needed: (1) `VehicleAsset` — represents a vehicle with all customer-visible attributes (make, model, year, fuel type, etc.) and an embedded `VehicleCategory` for rate/policy data. (2) `VehicleCategory` — the rate card with included km/day, overage rate, fuel policy, min driver age, and required license class. (3) `MileageLog` — a single odometer/fuel reading with log type, date, computed fields (driven km, overage). **VIN is intentionally omitted** from `VehicleAsset` — the API never serves it to customers, so the model shouldn't expect it. This is a defence-in-depth measure: even if a future developer accidentally includes VIN in an API response, the Flutter model won't parse or display it.

**Riverpod providers** handle data fetching and caching: `vehicleFilterNotifier` (reactive filter state), `vehicleAssetsProvider` (fetches the catalog with current filters, re-fetches when filters change), `vehicleDetailProvider` (fetches and caches a single vehicle's details by asset name), and `mileageLogsProvider` (fetches mileage log entries for a specific agreement). These providers use Riverpod's code generation (`@riverpod` annotation) for automatic cache key management and lifecycle handling.

**Acceptance Criteria**:
- [ ] `VehicleAsset.fromJson()` parses all fields correctly
- [ ] `VehicleCategory.fromJson()` parses all fields correctly
- [ ] `MileageLog.fromJson()` parses all fields correctly
- [ ] VIN field does NOT exist on `VehicleAsset` model
- [ ] `vehicleAssetsProvider` re-fetches when filter changes
- [ ] `vehicleDetailProvider` caches by asset name
- [ ] `mileageLogsProvider` fetches logs for a specific agreement

---

## 7. Cross-Cutting Concerns

### 7.1 Logging

All critical decision points in this domain must emit structured log entries for auditability and debugging:

| Location | Log Level | What to Log |
|---|---|---|
| `get_vehicle_detail` API | `INFO` | Asset name requested, caller role, response size, cache hit/miss, execution time |
| `get_vehicle_detail` — VIN stripping | `DEBUG` | Confirmation that VIN was excluded from Customer-role response |
| `get_maintenance_schedule` API | `INFO` | Asset name, caller role, window count returned, execution time |
| `submit_vehicle_booking` API | `INFO` | Asset name, customer email, license expiry, driver age, validation result (pass/fail) |
| `submit_vehicle_booking` — validation failure | `WARNING` | Failure reason (expired license, underage, maintenance conflict), customer email, asset name |
| Vehicle Category delete attempt | `WARNING` | Category name, linked vehicle count, delete blocked |
| `setup.py` custom field injection | `INFO` | Fields injected, target DocTypes, success/failure per field |
| `VehicleAsset` override validation | `DEBUG` | Validation result for plate/VIN/category checks |
| Web catalog AJAX filter | `INFO` | Filter params received, result count, execution time |

**Acceptance Criteria**:
- [ ] All API endpoints log request parameters, result counts, and execution time
- [ ] Booking validation failures logged at `WARNING` with full context (asset, user, failure reason)
- [ ] Structured logging uses `frappe.logger()` with the `rental_vehicles` namespace
- [ ] No sensitive data (VIN, license numbers, personal DOB) appears in logs
- [ ] VIN stripping is logged at `DEBUG` level for audit confirmation

---

### 7.2 Caching

Frequently accessed data should be cached to avoid redundant database queries on high-traffic catalog pages:

| Data | Cache Key Pattern | TTL | Invalidation Trigger |
|---|---|---|---|
| Vehicle catalog results | `vehicle_catalog:{filter_hash}` | 5 min | Any Rental Asset status change, Vehicle Category update |
| Vehicle Category list (for filter sidebar) | `vehicle_categories:all` | 30 min | Vehicle Category create/update/delete |
| Vehicle detail response | `vehicle_detail:{asset_name}` | 10 min | Rental Asset save |
| Maintenance schedule windows (for calendar) | `maint_schedule:{asset_name}` | 15 min | Vehicle Maintenance Schedule status change |
| Fuel type / transmission distinct values | `vehicle_filters:distinct` | 60 min | Rental Asset create with `asset_type=Vehicle` |

**Implementation**: Use Frappe's `frappe.cache()` (Redis-backed). Cache warming happens on first request. Invalidation uses `doc_events` hooks on `Rental Asset`, `Vehicle Category`, and `Vehicle Maintenance Schedule` to clear relevant keys.

**Acceptance Criteria**:
- [ ] Catalog API caches results by filter hash; repeated identical queries hit Redis
- [ ] Vehicle Category list is cached and invalidated on category CRUD
- [ ] Vehicle detail response cached per asset name; invalidated on asset save
- [ ] Maintenance schedule cache invalidated when schedule status changes
- [ ] Cache TTLs are configurable via `Rental Configuration` fields

---

### 7.3 Rate Limiting

Public-facing and customer-facing APIs must be rate-limited to prevent abuse:

| Endpoint | Limit | Scope | Response on Limit |
|---|---|---|---|
| Web catalog `/rentals/vehicles` | 30 req/min | Per IP (guest) / Per user (auth) | HTTP 429 with `Retry-After` header |
| `get_vehicle_detail` API | 60 req/min | Per IP (guest) / Per user (auth) | HTTP 429 with `Retry-After` header |
| `get_maintenance_schedule` API | 30 req/min | Per user (auth) | HTTP 429 with `Retry-After` header |
| `submit_vehicle_booking` API | 10 req/min | Per user (auth) | HTTP 429 with `Retry-After` header |

**Implementation**: Enforce via Frappe's `frappe.rate_limiter.rate_limit()` decorator on whitelisted methods. For portal pages, use Nginx `limit_req_zone` at the reverse proxy layer. Booking endpoint has a tighter limit (10/min) to prevent automated booking abuse.

**Acceptance Criteria**:
- [ ] Catalog and detail endpoints rate-limited per table above
- [ ] Booking endpoint limited to 10 req/min per authenticated user
- [ ] Exceeding limit returns HTTP 429 with `Retry-After` header and friendly error message
- [ ] Rate limit logging at `WARNING` level when thresholds are approached (80%+)

---

### 7.4 Security Validation

Input validation and data sanitization at every entry point:

| Check | Location | Rule |
|---|---|---|
| `asset_type` filter | Catalog API, detail API | Only `Vehicle` type assets returned; reject invalid `asset_type` values |
| VIN exclusion | `get_vehicle_detail` | Explicitly strip VIN from response for Customer role; assertion test in AC |
| Numeric filter bounds | Catalog API | `min_seats`, `max_price` must be non-negative numbers; reject NaN/Infinity |
| SQL injection prevention | Catalog filter SQL | Use parameterized queries only (no raw string interpolation) |
| License expiry validation | `submit_vehicle_booking` | Server-side validation: `license_expiry >= rental_end_date` (cannot be bypassed) |
| Age validation | `submit_vehicle_booking` | Server-side validation: `driver_age >= category.min_driver_age` (cannot be bypassed) |
| XSS prevention | All web templates | All user-supplied values rendered via Jinja auto-escaping |
| CSRF protection | Booking AJAX handler | Use `frappe.call()` which auto-injects CSRF token |
| Maintenance schedule role-gate | `get_maintenance_schedule` | Customer response strips `service_type`, `technician`, `notes` |
| Plate number uniqueness | `VehicleAsset` override | DB-level `UNIQUE` constraint on `custom_plate_number` |
| VIN uniqueness | `VehicleAsset` override | DB-level `UNIQUE` constraint on `custom_vin` |

**Acceptance Criteria**:
- [ ] VIN verified absent from all Customer-role API responses via automated tests
- [ ] Negative or invalid numeric filter values are rejected with HTTP 400
- [ ] License and age validations run server-side regardless of client-side checks
- [ ] All Jinja templates use auto-escaping for user-supplied values
- [ ] Plate number and VIN uniqueness enforced at DB level (not just application logic)
- [ ] Maintenance schedule detail fields stripped for non-Fleet Manager roles

---

## 8. Domain-Level Acceptance Criteria

- [ ] Vehicle Category CRUD works for Fleet Manager
- [ ] Custom fields appear on Rental Asset only for Vehicle type
- [ ] Plate number and VIN uniqueness enforced at DB level
- [ ] VIN never appears in any customer-facing response or page
- [ ] Vehicle catalog filters work correctly across all dimensions
- [ ] License expiry validation works client-side AND server-side
- [ ] Age validation works client-side AND server-side
- [ ] Mileage policy acknowledgement required before vehicle booking submission
- [ ] Maintenance-blocked dates appear as unavailable with no reason disclosed

---

## 9. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (app scaffold + custom fields + Vehicle Category + APIs) | 4 days |
| Web (catalog + detail + booking extensions + my rentals mileage) | 3 days |
| Flutter (catalog + detail + filter sheet + booking step 2 + models) | 4 days |
| **Total** | **11 days** |
