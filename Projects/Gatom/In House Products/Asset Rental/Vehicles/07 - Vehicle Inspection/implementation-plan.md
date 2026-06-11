# Domain V07 — Vehicle Inspection: Implementation Plan

> **Variant**: Vehicles (child app `rental_vehicles`)
> **Domain**: Vehicle Inspection
> **Sequence**: 7 of 7
> **Depends on**: V01 (Rental Asset vehicle fields), Base D05 (Rental Agreement), Base D06 (deposit deduction system), Base D04 (Asset Inspection base)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Every vehicle rental requires a **physical inspection** at pickup (entry) and return (exit). The Rental Agent walks around the vehicle with a structured checklist covering: exterior (bumpers, doors, roof, bonnet, boot, windscreen, windows, lights, mirrors), interior (dashboard, seats, seatbelts, carpets, headliner, A/C), mechanicals (4 tyres, spare tyre, oil, coolant, brake fluid), and keys/documents (ignition key, remote/fob, registration card, insurance card).

Damage found during the **exit inspection** is photographed, priced, and deducted from the tenant's deposit. This creates a clear audit trail: the entry inspection proves the vehicle's condition at handover, and the exit inspection documents any new damage.

Inspections are entirely **staff-operated** — the Rental Agent performs them at the rental counter. Customers see the inspection results in **read-only mode** on the web portal and Flutter app for transparency and dispute purposes. The customer can review what was recorded about the vehicle's condition at pickup — this gives them an opportunity to dispute inaccuracies immediately rather than waiting until return. For completed agreements, both pickup and return inspections are visible with the damage comparison highlighted.

Damage photos from the pickup inspection are included in the customer view (so they can see the pre-existing damage documentation). Damage photos from the return inspection are excluded from customer-facing views — those are internal evidence for the rental company's damage assessment. Guarantors are blocked from accessing inspection data.

---

## 2. Frappe — Inspection Checklist

### 2.1 Vehicle Inspection Checklist Configuration

> **Requires**: V01-2.1 (app scaffold), Base D04 (Asset Inspection base DocType if exists)

The **vehicle-specific inspection checklist** defines the standardized list of items that must be checked at every inspection. This is configured at the system level (not per-vehicle) and used as the template for every new inspection.

| Area | Items |
|---|---|
| **Exterior** | Front bumper, Rear bumper, Driver door, Passenger door, Rear doors, Roof, Bonnet, Boot, Windscreen, All windows, Headlights, Taillights, Indicators, Mirrors |
| **Interior** | Dashboard, Driver seat, Passenger seats, Seatbelts, Carpets/floor mats, Headliner, A/C system, Infotainment |
| **Mechanicals** | Tyre FL, Tyre FR, Tyre RL, Tyre RR, Spare tyre, Oil level, Coolant level, Brake fluid |
| **Keys & Documents** | Ignition key, Remote/fob, Registration card, Insurance card |

Each checklist row records: `condition` (Good / Damaged / Missing), `photo` (evidence), `deduct_from_deposit` (yes/no flag), `estimated_repair_cost` (currency), and `notes` (free text).

**Acceptance Criteria**:
- [ ] Checklist template configurable in Frappe Desk
- [ ] Template includes all 4 areas: Exterior, Interior, Mechanicals, Keys & Documents
- [ ] Each item has condition options: `Good`, `Damaged`, `Missing`
- [ ] Each item supports photo evidence upload
- [ ] Each item supports `estimated_repair_cost` (currency field)
- [ ] Each item has a `deduct_from_deposit` flag
- [ ] Fleet Manager can add/remove checklist items from the template
- [ ] Changing the template does NOT affect past completed inspections (snapshot at creation time)

---

### 2.2 `Vehicle Inspection` DocType (extending `Asset Inspection`)

> **Requires**: 2.1, Base D05-2.1 (Rental Agreement)

The **Vehicle Inspection** DocType represents a single inspection event — one person examining one vehicle at one point in time. It's linked to both the vehicle and the agreement, and its `inspection_type` distinguishes pickup from return.

The schema captures the metadata (who inspected, when, what type) and contains a **child table** of individual item assessments. Each item in the child table corresponds to one line from the snapshotted template (e.g., "Front Bumper") and has its own `condition_rating`, `damage_description`, and `damage_photo`.

Key business rules:
- **One inspection per type per agreement**: You can't submit two pickup inspections for the same agreement. This prevents data conflicts (which pickup baseline do we use?).
- **Pickup before Return**: A return inspection for an agreement requires a submitted pickup inspection to exist. Without a baseline, the damage comparison (2.4) has nothing to compare against.
- **Immutability after submission**: Once a Rental Agent submits an inspection (`docstatus = 1`), no one can edit it — not even a System Manager. This protects the evidentiary integrity. If a mistake was made, the correct process is to amend (create a corrected copy that links to the original).

| Field | Type | Notes |
|---|---|---|
| `agreement` | Link → Rental Agreement | |
| `vehicle` | Link → Rental Asset | |
| `inspection_type` | Select | `Entry`, `Exit` |
| `inspection_date` | Date | |
| `inspected_by` | Link → User | The Rental Agent |
| `checklist` | Table (child) | `Vehicle Inspection Item` rows |
| `total_damage_cost` | Currency | Sum of all `estimated_repair_cost` where condition = Damaged |
| `deduct_from_deposit` | Currency | Sum of flagged deductions |
| `overall_condition` | Select | `Good`, `Fair`, `Poor` — auto-computed |
| `notes` | Text | General notes |
| `photos` | Table (child) | `Vehicle Inspection Photo` rows for overview photos |

**Acceptance Criteria**:
- [ ] DocType created in Frappe Desk
- [ ] `inspection_type` includes: `Entry`, `Exit`
- [ ] Checklist child table pre-populated from the template when creating a new inspection
- [ ] `total_damage_cost` auto-computed from child rows
- [ ] `deduct_from_deposit` auto-computed from flagged child rows
- [ ] `overall_condition` auto-computed: all Good → Good; any Damaged → Fair; multiple Damaged → Poor
- [ ] Only one Entry and one Exit inspection per agreement (duplicate insertion blocked)
- [ ] Rental Agent and Fleet Manager can create/submit; Customer role cannot create

---

## 3. Frappe — Entry Inspection

### 3.1 Entry Inspection Workflow

> **Requires**: 2.2, Base D05 (Rental Agreement active)

Every time a vehicle changes hands — from the rental company to a customer (pickup) and from the customer back to the company (return) — both parties need to agree on the vehicle's physical condition. Without a documented inspection, there's no way to determine who caused a scratch, dent, or interior stain. The customer might claim "it was already damaged when I got it," and the company might claim "you damaged it." This domain eliminates the ambiguity by creating a **timestamped, photo-documented inspection record** at both ends of the rental.

The inspection process is based on a **template-based checklist**. The Fleet Manager defines a global `Vehicle Inspection Template` with all the items that should be checked (exterior body, windshield, tyres, interior upholstery, etc.). When an inspection is created at pickup or return, the system **snapshots** this template — copying all items into the specific inspection record. This means that if the template is updated later (e.g., adding "check for EV charging cable"), existing inspections are unaffected. Only future inspections use the updated template.

Each inspection item is scored on a condition scale: `Good`, `Fair`, `Poor`, or `Damaged`. Items rated `Damaged` require a photo and a text description of the damage. The **damage comparison engine** then diffs the pickup and return inspections to identify **new damage** that appeared during the rental — the basis for potential damage charges.

The entry inspection is typically done alongside the mileage/fuel pickup log (V03).

**Acceptance Criteria**:
- [ ] Entry inspection created with `inspection_type = Entry`
- [ ] All checklist items pre-populated from the template
- [ ] Each item's condition recorded: Good, Damaged, or Missing
- [ ] Pre-existing damage photographed and noted (not charged to current tenant)
- [ ] Entry inspection cannot be edited after submission (locked for audit integrity)
- [ ] Entry inspection must exist before an Exit inspection can be created
- [ ] `inspected_by` auto-set to current user

---

## 4. Frappe — Exit Inspection & Deposit Deductions

### 4.1 Exit Inspection Workflow

> **Requires**: 3.1 (entry inspection exists), 2.2, Base D06-3.1 (deposit ledger)

The **exit inspection** is performed when the customer returns the vehicle. The Rental Agent walks through every checklist item and compares the current condition against the entry inspection. **New damage** (condition was Good at entry but Damaged at exit) is flagged for deposit deduction. **Pre-existing damage** (condition was Damaged at both entry and exit) is NOT charged.

The **damage comparison widget** is the most important customer-facing element in this domain. After a vehicle is returned and both inspections exist, this widget shows a **side-by-side comparison** of each item's condition at pickup vs. return, clearly highlighting items where the condition degraded.

The widget uses a **card-based layout** where each damaged item gets its own card showing:
- Item name (e.g., "Front Bumper")
- Pickup condition (e.g., "Good" in green) → Return condition (e.g., "Damaged" in red)
- Pickup photo (if available) next to Return photo (showing the new damage)
- Damage description from the return inspection

Items where the condition stayed the same or improved are collapsed into a "No change" summary at the bottom to keep the focus on the actual damage. The widget only appears after both pickup and return inspections are submitted — during an active rental (only pickup exists), it shows a message: "Return inspection not yet completed."

This transparency is critical for customer trust. Rather than just receiving a damage charge, the customer can see exactly what was recorded, by whom, and when. It significantly reduces damage disputes because the evidence is objective and timestamped.

**Acceptance Criteria**:
- [ ] Exit inspection created with `inspection_type = Exit`
- [ ] Entry inspection conditions loaded for comparison
- [ ] Items where condition worsened (e.g., Good → Damaged) are auto-highlighted
- [ ] Pre-existing damage items NOT flagged for deduction
- [ ] New damage items require: photo evidence + justification text + estimated repair cost
- [ ] `deduct_from_deposit` flag set for items that should be charged to tenant
- [ ] Exit inspection cannot be created without a submitted Entry inspection

---

### 4.2 Deposit Deduction Processing

> **Requires**: 4.1, Base D06-3.1 (deposit ledger)

When the exit inspection is **submitted**, flagged damage items are summed and deducted from the tenant's deposit. The deduction creates a line item in the deposit ledger (Base D06) with a reference to the inspection and the specific damage item.

The deduction processing handles three scenarios based on the total damage amount vs. available deposit:

**Scenario 1: Damage ≤ Deposit balance** — The most common case. The full damage amount is deducted from the deposit. The tenant sees the deduction in their portal/app with a description like "Exit Inspection — Front Bumper Damage — 350 AED" and a photo thumbnail.

**Scenario 2: Damage > Deposit balance** — The deposit covers part of the damage, and the excess is added as a line item on the final Sales Invoice. Example: damage = 2,000 AED, deposit = 1,500 AED → deduct 1,500 from deposit + add 500 to invoice.

**Scenario 3: No damage (all items Good)** — No deduction is created, no invoice items are added. The deposit is fully available for refund at settlement.

Each deduction **requires photo evidence** — the system enforces that items without damage photos cannot be flagged for deduction. This protects the company in disputes: if a tenant contests a charge, the company can produce timestamped photos showing the damage.

The processing is **idempotent** — submitting the same inspection twice (e.g., from a retry after a network timeout) does not create duplicate deductions. The system checks for existing deductions linked to the same inspection before creating new ones.

**Acceptance Criteria**:
- [ ] Flagged damage items → deposit deduction created in the ledger
- [ ] Each deduction includes: description ("Exit Inspection — Front Bumper Damage"), amount, inspection reference
- [ ] Deduction requires photo evidence (enforcement: items without photos cannot be flagged for deduction)
- [ ] Total damage > deposit → excess added to final Sales Invoice
- [ ] Total damage = 0 → no deduction, no invoice item
- [ ] Deduction is idempotent (submitting same inspection twice → no duplicate deductions)
- [ ] Tenant notified of deposit deductions (via base notification system D07)

---

## 5. Web — Exit Deductions Portal

### 5.1 Agreement Detail — Exit Deduction View

> **Requires**: Base D05 (My Rentals portal), 4.2 (deposit deductions processed)

When the customer views their agreement on the **My Rentals** web portal, the inspection section provides a read-only view of the pickup inspection — what was recorded about the vehicle's condition when they received it. This is important for transparency: if the customer notices something that wasn't recorded (a scratch the agent missed), they can contact support immediately rather than being surprised at return.

For **completed agreements** (vehicle returned), both the pickup and return inspections are shown side-by-side with the damage summary highlighted. Items with new damage are marked with a red indicator and include the damage description. This gives the customer full visibility into why they may have been charged for damage.

Photos from the pickup inspection are shown inline (so the customer can verify the pre-existing condition documentation). Return inspection photos are NOT shown to customers — they're internal evidence for the company's damage assessment process.

**Acceptance Criteria**:
- [ ] Exit deduction line items visible on the agreement detail page
- [ ] Each item shows: description, amount, photo thumbnail
- [ ] Tapping the photo opens a full-size view
- [ ] Entry inspection results are NOT shown
- [ ] Non-vehicle agreements do not show this section
- [ ] Deduction total matches the deposit deduction amount

---

## 6. Flutter — Exit Deductions View

### 6.1 Agreement Detail — Exit Deduction Widget

> **Requires**: Base D01-8.3 (Flutter screens), 4.2 (deposit deductions)

The Flutter **agreement detail screen** includes a deduction section for vehicle agreements showing exit inspection damage items. This mirrors the web portal functionality but is optimized for mobile interaction.

Each damage item is displayed as a **card** showing: the item description ("Front Bumper — Scratch and dent"), the deduction amount ("350 AED" in red), and a **photo thumbnail** of the damage. Tapping the thumbnail opens a full-screen image viewer with pinch-to-zoom — important because damage photos are often close-up shots where the customer needs to zoom in to see the detail.

The deduction section only appears for **vehicle agreements** — flat agreements don't have vehicle inspections. If no damage was found during the exit inspection (all items rated Good), the section shows an empty state: "No exit deductions — vehicle returned in good condition." This positive messaging reassures the customer that their deposit is intact.

Entry inspection data is **NOT shown** to customers in the Flutter app — only exit deductions are visible. This matches the web portal behavior.

**Acceptance Criteria**:
- [ ] Exit deduction items visible on the agreement detail screen
- [ ] Each item shows: description, amount, photo thumbnail
- [ ] Tapping photo opens full-size view
- [ ] Entry inspection data NOT shown to customers
- [ ] Deduction section only appears for vehicle agreements
- [ ] Empty state: "No exit deductions" (if no damage found)

---

## 7. Domain-Level Acceptance Criteria

- [ ] Entry inspection documented at every vehicle pickup
- [ ] Exit inspection documented at every vehicle return
- [ ] New damage identified by comparing entry vs exit conditions
- [ ] Pre-existing damage NOT charged to current tenant
- [ ] Damage deductions require photo evidence + justification
- [ ] Deductions processed through the deposit ledger
- [ ] Excess damage (beyond deposit) added to final invoice
- [ ] Customers see only exit deductions (not entry inspection data)
- [ ] Inspections locked after submission (audit integrity)

---

## 8. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (checklist config + Inspection DocType + entry/exit workflow + deposit deductions) | 4 days |
| Web (exit deduction view in My Rentals) | 1 day |
| Flutter (exit deduction widget) | 1 day |
| **Total** | **6 days** |
