# Domain V03 — Mileage & Fuel: Implementation Plan

> **Variant**: Vehicles (child app `rental_vehicles`)
> **Domain**: Mileage & Fuel Tracking
> **Sequence**: 3 of 7
> **Depends on**: V01 (Vehicle Category with mileage policy, custom fields for mileage tracking), Base D05 (Rental Agreement), Base D06 (invoice appending)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

This domain tracks every vehicle's **odometer and fuel level** at key lifecycle events (pickup, return, mid-term check) and automatically computes overage charges. When a vehicle is rented, the category defines how many kilometres are included per day. If the driver exceeds the allowance, the overage is computed and appended to the final invoice.

Fuel policy is also enforced: under a **Full-to-Full** policy, the vehicle must be returned at ≥90% fuel level. If the fuel gauge reads below 90% at return, an automatic fuel deficit charge is calculated and added to the invoice.

This domain is **staff-operated** — the Rental Agent logs odometer/fuel at pickup and return via Frappe Desk. Customers see the mileage data in read-only mode on the web portal and Flutter app.

---

## 2. Frappe — Mileage Log DocType

### 2.1 `Vehicle Mileage Log` Schema

> **Requires**: V01-2.1 (app scaffold), Base D05-2.1 (Rental Agreement), V01-2.3 (custom fields on Rental Asset)

Every time a vehicle changes hands — whether at pickup, return, or a mid-rental spot check — the Rental Agent records the odometer reading and fuel level. This data is the foundation for computing overage charges ("you drove more than the included allowance") and fuel deficit charges ("you returned the tank half-empty"). Without this log, there's no objective record of how far the customer drove or how much fuel they used.

The **Mileage Log** DocType records a single observation at one of three lifecycle events: `Pickup` (the baseline odometer when the customer takes the vehicle), `Return` (the final odometer when they bring it back), and `Mid-Term Check` (an optional mid-rental reading used for long-term rentals to monitor usage patterns). The Rental Agent enters only two values: `odometer_reading_km` (from the dashboard) and `fuel_level_pct` (from the fuel gauge). All computed fields (`driven_km`, `overage_km`, `overage_charge`) are calculated automatically by the return controller (2.2) — the agent doesn't manually compute these.

Photo evidence (`photo_odometer` and `photo_fuel_gauge`) serves as a dispute resolution mechanism. If a customer contests an overage charge, the company can produce the timestamped photos showing the odometer at pickup and return.

| Field | Type | Notes |
|---|---|---|
| `agreement` | Link → Rental Agreement | |
| `vehicle` | Link → Rental Asset | |
| `log_type` | Select | `Pickup`, `Return`, `Mid-Term Check` |
| `log_date` | Date | |
| `odometer_reading_km` | Float | Must be ≥ previous reading for same vehicle |
| `fuel_level_pct` | Int | 0–100% |
| `driven_km` | Float | Computed on Return: `return_odometer - pickup_odometer` |
| `overage_km` | Float | Computed on Return: `max(0, driven_km - included_km)` |
| `overage_charge` | Currency | Computed on Return: `overage_km × overage_rate_per_km` |
| `photo_odometer` | Attach | Photo proof of odometer reading |
| `photo_fuel_gauge` | Attach | Photo proof of fuel gauge |
| `noted_by` | Link → User | Auto-set to current user |

**Acceptance Criteria**:
- [ ] DocType created in Frappe Desk
- [ ] `log_type` includes: `Pickup`, `Return`, `Mid-Term Check`
- [ ] `odometer_reading_km` is required (cannot be 0 or empty)
- [ ] `fuel_level_pct` is validated: 0 ≤ value ≤ 100
- [ ] `noted_by` auto-populated with the current user
- [ ] Fleet Manager and Rental Agent can create/submit; Customer role is read-only
- [ ] Only one `Pickup` log per agreement (duplicate insertion blocked)
- [ ] Return log requires an existing submitted Pickup log for the same agreement

---

### 2.2 Return Log Controller (`on_submit`)

> **Requires**: 2.1, V01-3.1 (Vehicle Category with `included_km_per_day`, `overage_rate_per_km`)

This is the **core computation engine** of the mileage domain — the piece of code that actually computes how much the customer owes for driving beyond the included allowance. It fires automatically when a Return-type mileage log is submitted (the `on_submit` controller method).

Here's the real-world flow: a customer rents a sedan for 30 days. The category says "200 km/day included" and "0.50 AED per extra km." That's 6,000 km included for the rental. The Rental Agent records the pickup odometer as 45,000 km. When the customer returns the vehicle 30 days later, the agent records the return odometer as 52,500 km. The controller computes: driven = 52,500 − 45,000 = 7,500 km. Included = 200 × 30 = 6,000 km. Overage = max(0, 7,500 − 6,000) = 1,500 km. Charge = 1,500 × 0.50 = 750 AED. This 750 AED is automatically appended as a line item to the final Sales Invoice.

If the customer drove 5,000 km (under the allowance), overage = max(0, 5,000 − 6,000) = 0 — no charge.

Additionally, the vehicle's `custom_current_mileage_km` on the `Rental Asset` is updated to the return odometer (52,500 km). This keeps the asset's mileage current for the maintenance scheduling engine (V04), which uses this value to determine when the next oil change or service is due.

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

**Acceptance Criteria**:
- [ ] Return without Pickup → `frappe.throw("No submitted Pickup log found")`
- [ ] `driven_km` = `return_odometer - pickup_odometer`
- [ ] `overage_km` = `max(0, driven_km - (included_km_per_day × rental_days))`
- [ ] `overage_charge` = `overage_km × overage_rate_per_km`
- [ ] Overage charge > 0 → line item appended to the final Sales Invoice
- [ ] Overage = 0 → no invoice item created
- [ ] `custom_current_mileage_km` on the Rental Asset is updated to the return odometer
- [ ] Pickup log used for computation must be `docstatus = 1` (submitted)
- [ ] `rental_days` fallback: if `end_date` is null, uses `today()` as the end date

---

### 2.3 Fuel Deficit Computation

> **Requires**: 2.2, V01-3.1 (Vehicle Category with `fuel_policy`)

Fuel is the second source of post-rental charges, after mileage. There are three common fuel policies in vehicle rental:

- **Full-to-Full**: The customer receives the vehicle with a full tank and must return it full. If they return it half-empty, they pay for the missing fuel. This is the most common policy.
- **Full-to-Empty**: The customer pays for a full tank upfront at booking. They can return the vehicle with any fuel level — no fuel check at return. This is simpler but the customer loses money on unused fuel.
- **Pre-Purchase**: The fuel cost is baked into the rental rate. No fuel checks at all.

For the **Full-to-Full** policy, the system defines "full" as ≥90% fuel level (not literally 100%, because fuel gauges are imprecise). This threshold is configurable via `Rental Configuration.fuel_full_threshold_pct` (default 90). If the return fuel level is below the threshold, the **fuel deficit charge** is computed as: `(threshold - return_fuel_level) / 100 × estimated_tank_cost`, where `estimated_tank_cost` represents the cost to fill the tank from empty (configured per category or globally).

Example: threshold = 90%, return fuel = 70%, estimated tank cost = 300 AED → deficit = (90 − 70) / 100 × 300 = 60 AED. This charge is appended to the same final Sales Invoice as the overage charge (if any).

For Full-to-Empty and Pre-Purchase policies, no fuel check is performed at return.

**Acceptance Criteria**:
- [ ] Full-to-Full policy + return fuel 85% → fuel deficit charge applied
- [ ] Full-to-Full policy + return fuel 92% → NO charge (above threshold)
- [ ] Full-to-Empty policy → NO fuel deficit check (all fuel prepaid)
- [ ] Pre-Purchase policy → NO fuel deficit check (fuel cost included in rate)
- [ ] Fuel deficit charge appended to the same final invoice as overage
- [ ] Fuel threshold default is 90% (configurable)
- [ ] Guarantors do NOT see fuel deficit data

---

### 2.4 Odometer Validation

> **Requires**: 2.1

Odometers on cars are physical counters — they only go forward. A reading of 45,000 km today should never be followed by 44,000 km tomorrow (unless the car was shipped backwards through time). A lower reading almost always means a **data entry error** — the Rental Agent misread the odometer or typed the wrong number.

This validation prevents bad data from entering the system. When a mileage log is submitted, the system queries the most recent submitted reading for the **same vehicle** (not the same agreement — because a vehicle may have multiple agreements over time). If the new reading is lower than the previous one, the submission is rejected with an error message showing both values: "Odometer reading 44,000 km is below the previous reading of 45,230 km for this vehicle."

Edge cases: the first-ever reading for a newly added vehicle has no baseline and passes validation automatically. A Mid-Term reading during an active rental is validated against the Pickup reading, not against readings from previous agreements.

**Acceptance Criteria**:
- [ ] Odometer reading lower than previous reading for same vehicle → validation error
- [ ] First-ever reading for a vehicle → no validation (no previous baseline)
- [ ] Mid-Term reading between Pickup and Return → validated against Pickup odometer
- [ ] Error message includes: expected minimum, entered value

---

## 3. Frappe — Mileage API Endpoints

### 3.1 `log_mileage` API

> **Requires**: 2.1, 2.2

The **primary API endpoint** for recording odometer and fuel data at pickup and return. This is a staff-only endpoint — the Rental Agent at the rental counter calls this after physically reading the vehicle's dashboard. The API creates a `Vehicle Mileage Log`, populates all fields, and submits it immediately (so it's committed and cannot be accidentally deleted).

For Return-type logs, the response is especially important: it includes the **computed overage data** (`driven_km`, `overage_km`, `overage_charge`) so the Rental Agent gets immediate feedback at the counter. The agent can then inform the customer: "You drove 7,500 km against your 6,000 km allowance, so there's a 750 AED overage charge on your final invoice." For Pickup logs, the response simply confirms that the baseline was recorded.

Customers **cannot** call this API — mileage logging is a staff function. Allowing customers to self-report odometer readings would create a fraud vector (reporting lower readings to reduce overage charges).

**Acceptance Criteria**:
- [ ] Creates a `Vehicle Mileage Log` with all provided fields
- [ ] Submits the log (not left in Draft)
- [ ] For Return log: response includes `driven_km`, `overage_km`, `overage_charge`
- [ ] For Pickup log: response confirms creation
- [ ] Only Rental Agent and Fleet Manager roles can call this API
- [ ] Customer role → permission denied

---

### 3.2 `get_mileage_history` API

> **Requires**: 2.1

This API powers the **customer-facing mileage view** on both the web portal and the Flutter app. When a customer navigates to their agreement detail and opens the mileage section, this endpoint returns the complete history of odometer/fuel recordings for that agreement.

The response is read-only — customers can see what was recorded but cannot modify it. Each log entry includes: `log_type` (Pickup/Return/Mid-Term), `log_date`, `odometer_reading_km`, and `fuel_level_pct`. For Return entries, the computed fields (`driven_km`, `overage_km`, `overage_charge`) are also included so the customer can see the full breakdown.

Security constraints: customers can only view logs for their own agreements (server-side filtering by authenticated user). Guarantors (co-signers on the agreement) are explicitly blocked from accessing mileage data — this is a privacy boundary.

**Acceptance Criteria**:
- [ ] Returns all submitted mileage logs for the agreement
- [ ] Each entry includes: `log_type`, `log_date`, `odometer_reading_km`, `fuel_level_pct`
- [ ] Return entries include: `driven_km`, `overage_km`, `overage_charge`
- [ ] Sorted by `log_date` ascending (Pickup first, Return last)
- [ ] Customer can only view their own agreement's mileage logs
- [ ] Guarantors CANNOT access this API

---

### 3.3 `get_estimated_mileage` API

> **Requires**: V05 (GPS Telematics — provides current position data)

During an active rental, the customer naturally wants to know: "How many km have I driven so far? Am I close to my allowance limit?" For vehicles without GPS, the system can't answer this question until the vehicle is physically returned and the odometer is read. But for **GPS-equipped vehicles**, the system can provide a real-time estimate by summing the GPS-computed travel distance since the pickup date.

This API reads the `GPS Daily Summary` table (V05) and sums `total_km` for the vehicle from the pickup date through today, then adds it to the pickup odometer reading. The result is an **estimate** — GPS distance calculations have a small margin of error compared to the physical odometer. For non-GPS vehicles, the endpoint returns `null` with a user-friendly message: "Mileage available at return."

This is a customer-facing endpoint, scoped to the authenticated user's own vehicles only.

**Acceptance Criteria**:
- [ ] GPS vehicle → returns estimated current km (pickup_odometer + GPS distance since pickup)
- [ ] Non-GPS vehicle → returns `null` with `message: "Mileage available at return."`
- [ ] `custom_has_gps = 0` → non-GPS path
- [ ] Estimate uses the latest GPS daily summary data (not raw events)
- [ ] Customer can only access their own vehicle's estimate

---

## 4. Web — Mileage Portal

### 4.1 Agreement Detail — Mileage Section

> **Requires**: 3.2 (mileage history API), Base D05 (My Rentals portal)

When a customer visits their agreement detail on the **My Rentals** web portal, they need a quick summary of their mileage situation. For active vehicle agreements, this section shows: pickup odometer (the baseline), last recorded odometer (if a Mid-Term check was done), and the total included km for the rental duration (e.g., 200 km/day × 30 days = 6,000 km).

For GPS-equipped vehicles, the estimated current mileage is shown live. For non-GPS vehicles, a text message "Mileage available at return" is displayed instead — because the system has no way to know the current odometer without GPS.

For **completed agreements** (vehicle has been returned), the section expands to show the full breakdown: total driven km, total included km, overage km, and overage charge (highlighted in red/warning color if > 0). This gives the customer complete transparency into how the final charges were computed.

This section only renders for vehicle agreements — flat agreements don't have mileage tracking.

**Acceptance Criteria**:
- [ ] Active agreement: pickup odometer, last recorded odometer, included km total
- [ ] GPS vehicle: estimated current mileage shown
- [ ] Non-GPS vehicle: "Mileage available at return" text
- [ ] Completed agreement: full breakdown with overage
- [ ] Overage charge displayed in red/warning color
- [ ] Non-vehicle agreements do not show mileage section

---

## 5. Flutter — Mileage Log Screen

### 5.1 Mileage Log Screen (`mileage_log_screen.dart`)

> **Requires**: Base D01-8.3 (screen stubs), 3.2 (mileage history API), V01-6.5 (MileageLog model)

The Flutter app provides a **timeline-style screen** for customers to review their mileage log. This is the detailed view — while the Mileage Summary Widget (5.2) shows a quick glance, this screen shows every individual reading that was taken during the rental.

Each entry in the timeline has a **log type icon** for visual scanning (blue car icon for Pickup, green flag for Return, speedometer icon for Mid-Term), followed by the odometer reading, fuel level percentage, and date. For Return entries, the computed fields are displayed in a breakdown card: driven km, included km, overage km, and overage charge — with the charge amount rendered in red if > 0.

The screen is accessible from the agreement detail (tapping the Mileage Summary Widget navigates here). It's completely **read-only** — there's no button to create mileage entries. Only staff can log mileage through the Desk API.

Loading state shows a centered `CircularProgressIndicator`. If no mileage logs exist yet (the customer just booked but hasn't picked up the vehicle), the empty state shows: "No mileage entries yet."

**Acceptance Criteria**:
- [ ] Lists all mileage logs for the agreement
- [ ] Each entry shows: log type, date, odometer reading, fuel level
- [ ] Return entry shows: driven km, overage km, overage charge (in red if > 0)
- [ ] Pickup icon: blue car; Return icon: green flag; Mid-Term icon: speedometer
- [ ] Loading state: `CircularProgressIndicator`
- [ ] Empty state: "No mileage entries yet"
- [ ] Customer cannot create mileage entries (view-only)

---

### 5.2 Mileage Summary Widget

> **Requires**: 5.1, 3.3 (estimated mileage API)

The full mileage log screen (5.1) is detailed but requires navigation. For the **agreement detail screen** where the customer spends most of their time, a lightweight **summary widget** provides the key mileage information at a glance without leaving the page.

This is a compact card widget (approximately 100px tall) that sits within the agreement detail screen and shows 3–4 key data points: (1) **Pickup odometer** — where the rental started, (2) **Current estimate** (for GPS vehicles) or "Available at return" (for non-GPS), (3) **Included km total** — how many free km the customer has for the entire rental, and (4) **Overage charge** — displayed with warning/red styling if > 0.

The widget is **tappable** — tapping it navigates to the full mileage log screen (5.1) for the detailed timeline view. This follows the progressive disclosure pattern: show the summary by default, let the user drill down for details.

The widget is hidden for the Guarantor role — guarantors (co-signers) are not entitled to see the tenant's driving patterns.

**Acceptance Criteria**:
- [ ] Shows: pickup odometer, estimated/current, included km total
- [ ] GPS vehicle: live estimate shown
- [ ] Non-GPS vehicle: "Available at return" text
- [ ] Overage charge displayed with warning styling if > 0
- [ ] Tapping navigates to full mileage log screen
- [ ] Guarantor role does NOT see this widget

---

## 6. Domain-Level Acceptance Criteria

- [ ] Odometer logged at every pickup and return
- [ ] Overage computed correctly: `max(0, driven - included)`
- [ ] Overage charge appended to the final Sales Invoice
- [ ] Fuel deficit charge applied for Full-to-Full policy when return < 90%
- [ ] Asset's `custom_current_mileage_km` updated on return
- [ ] Customer sees mileage data read-only (cannot edit)
- [ ] Guarantors cannot access any mileage data
- [ ] GPS vehicles show estimated current mileage; non-GPS show "available at return"

---

## 7. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (Mileage Log + return controller + fuel deficit + APIs) | 4 days |
| Web (agreement mileage section) | 1 day |
| Flutter (mileage log screen + summary widget) | 2 days |
| **Total** | **7 days** |
