# Domain F05 — Flat Inspection: Implementation Plan

> **Variant**: Flats (child app `rental_flats`)
> **Domain**: Flat Inspection
> **Sequence**: 5 of 5
> **Depends on**: F01 (custom fields, Rental Building), F03 (appliance condition sync), Base D04-3.1 (Asset Inspection stub), Base D06-4.1 (Deposit Ledger)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

When a tenant moves into or out of a flat, the property manager conducts a **physical inspection** — walking through every room, checking walls, floors, appliances, fixtures, and building items (keys, fobs, parking passes). The **Flat Inspection** domain digitizes this workflow with room-by-room checklists, photo evidence capture, and — critically — a **damage → deposit deduction pipeline**: any damage found during an exit inspection automatically creates Pending deposit deductions that the tenant can view and dispute.

This domain connects to F03 (appliance conditions are synced from inspections), Base D06 (deposit deductions are written to the Deposit Ledger), and F01 (security rules for access codes and floor plans).

---

## 2. Frappe — Flat Inspection Checklist

### 2.1 `Flat Inspection Checklist Item` Child Table

> **Requires**: Base D04-3.1 (Asset Inspection — `checklist` Table field accepts child rows)

This child table defines what gets inspected in each room. Each row represents a single item (e.g., "Kitchen → Sink" or "Bedroom 1 → Built-in Wardrobe") with its observed condition, optional photo, and — if damage is found — the estimated repair cost and a written justification. The `is_damage` flag is the critical trigger: when checked, it means this item will generate a **deposit deduction** for the tenant on exit inspections.

The three evidence fields (`estimated_repair_cost`, `damage_justification`, `photo`) are **mandatory when `is_damage = 1`** — this protects tenants from unjustified deductions and gives them documentation for disputes.

This child table extends the base `Asset Inspection` DocType's `checklist` field with flat-specific rooms and items.

| Field | Type | Required | Notes |
|---|---|---|---|
| `room` | Select | ✅ | Options below |
| `item_name` | Data | ✅ | e.g., Walls, Ceiling, Floor, AC Unit |
| `item_type` | Select | ✅ | `Fixture`, `Appliance`, `Building Item` |
| `condition` | Select | ✅ | `Excellent`, `Good`, `Fair`, `Damaged`, `Missing` |
| `notes` | Small Text | | |
| `photo` | Attach | | Photo evidence |
| `is_damage` | Check | | Marks item for deposit deduction |
| `estimated_repair_cost` | Currency | | Required when `is_damage = 1` |
| `damage_justification` | Small Text | | Required when `is_damage = 1` |

**Room Options**:
`Living Room`, `Bedroom 1`, `Bedroom 2`, `Bedroom 3`, `Bedroom 4`, `Kitchen`, `Bathroom 1`, `Bathroom 2`, `Balcony`, `Storage`, `Building Items`

**Acceptance Criteria**:
- [ ] Child table is usable within the base `Asset Inspection` form
- [ ] `room`, `item_name`, `item_type`, `condition` are mandatory
- [ ] `is_damage = 1` requires `estimated_repair_cost > 0` (validation error otherwise)
- [ ] `is_damage = 1` requires non-empty `damage_justification` (min 10 chars)
- [ ] `is_damage = 1` requires a `photo` attachment (validation error otherwise)
- [ ] Room options include all 11 listed areas
- [ ] `item_type` distinguishes fixtures from appliances (for appliance condition sync)

---

### 2.2 Default Checklist Template

> **Requires**: 2.1

To save property managers from manually adding 30+ checklist items every time they create an inspection, the system **auto-populates** a default checklist based on the flat's configuration. A 2-bedroom flat gets Living Room, Bedroom 1, Bedroom 2, Kitchen, Bathroom 1, Balcony, Storage, and Building Items — but NOT Bedroom 3 or Bedroom 4. Appliances from the flat's inventory (F03) are also auto-added as rows. The manager can still add or remove items after the template is applied.

Pre-populated checklist items per room for standard flat inspections:

| Room | Default Items |
|---|---|
| Living Room | Walls, Ceiling, Floor, Windows, Curtains/Blinds, Main Door, AC Unit |
| Bedroom 1–4 | Walls, Ceiling, Floor, Window, Built-in Wardrobe, AC, Door |
| Kitchen | Walls, Ceiling, Floor, Sink, Taps, Cabinets, Hood, Countertop, Hob |
| Bathroom 1–2 | Walls, Floor, Shower/Bath, Toilet, Sink, Taps, Towel Rails, Mirror |
| Balcony | Floor, Railings, Drainage |
| Storage | Floor, Shelving |
| Building Items | Key Set Count, Remote/Fob, Parking Pass |

**Acceptance Criteria**:
- [ ] Creating a new inspection for a flat auto-populates the checklist with the default template
- [ ] Template items are based on the flat's actual configuration (e.g., 2-bedroom flat → Bedroom 1 & 2 only, no 3 & 4)
- [ ] Building Items section always includes key set, remote, parking pass
- [ ] Property Manager can add/remove items from the pre-populated list
- [ ] Appliances from the flat's `custom_appliances` child table are auto-added as `item_type = Appliance` rows

---

## 3. Frappe — Inspection Controllers

### 3.1 `on_submit()` — Entry Inspection

> **Requires**: 2.1, F03-2.2 (appliance condition sync)

An **entry inspection** happens when a new tenant moves in. Its purpose is to record the **baseline condition** of the flat — this is what the exit inspection will later be compared against. Entry inspections sync appliance conditions to the inventory (so the flat record reflects the current state) but they do NOT create any deposit deductions, even if damage is noted. Any pre-existing damage is simply documented as the starting condition.

Entry inspections record baseline condition — no deposit impact:

```python
def on_submit(self):
    if self.inspection_type == "Entry":
        from rental_flats.utils.appliance_manager import update_appliance_conditions
        update_appliance_conditions(self)
        return  # No deposit deductions for entry inspections
    # ... exit inspection logic (see 3.2) ...
```

**Acceptance Criteria**:
- [ ] When `inspection_type = Entry`: appliance conditions are synced to the flat's appliance inventory
- [ ] No deposit deductions created for Entry inspections (even if damage is noted)
- [ ] Checklist item conditions become the baseline for future comparisons

---

### 3.2 `on_submit()` — Exit Inspection

> **Requires**: 2.1, F03-2.2 (appliance condition sync), Base D06-4.1 (Deposit Ledger + Deduction)

An **exit inspection** happens when a tenant moves out. Like entry inspections, it syncs appliance conditions. But the critical difference: any checklist item marked `is_damage = 1` triggers a **Deposit Deduction** row on the tenant's Deposit Ledger. Each deduction starts with status "Pending" — the tenant can see it on their portal/app and has a dispute window (defined in Base D06-4.2) to challenge it. The deduction includes the reason (formatted as "Room – Item: justification"), the repair cost estimate, and a link to the photo evidence.

```python
def on_submit(self):
    if self.inspection_type == "Entry":
        update_appliance_conditions(self)
        return

    # Exit inspection
    update_appliance_conditions(self)
    damage_items = [item for item in self.checklist_items if item.is_damage]
    if damage_items:
        ledger = frappe.get_doc("Deposit Ledger", {"agreement": self.agreement})
        for item in damage_items:
            ledger.append("deductions", {
                "reason": f"{item.room} – {item.item_name}: {item.damage_justification}",
                "amount": item.estimated_repair_cost,
                "deduction_date": frappe.utils.today(),
                "deduction_status": "Pending",
                "photo_evidence": item.photo,
            })
        ledger.save(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Exit inspection with `is_damage` items → Deposit Deduction rows created
- [ ] Each deduction has: reason (formatted: "Room – Item: justification"), amount, date, status=Pending
- [ ] Photo evidence linked to the deduction row
- [ ] Deduction starts as `Pending` (triggers dispute window per Base D06-4.2)
- [ ] Exit inspection with no damage items → no deductions created
- [ ] Appliance conditions synced for exit inspection (same as entry)
- [ ] If no Deposit Ledger exists for the agreement → error logged (shouldn't happen if Base D06 is correct)

---

### 3.3 Validation — Damage Requirements

> **Requires**: 2.1

Before an inspection can be saved, this validation ensures that **every damage item has proper evidence**. If a property manager marks an item as damaged but forgets the photo or provides a one-word justification, the system blocks the save. This is a tenant protection measure — deposit deductions must be substantiated with a repair cost estimate, a written explanation (minimum 10 characters), and photographic proof.

In the `validate()` method, enforce evidence requirements for damage items:

```python
def validate(self):
    for item in self.checklist_items:
        if item.is_damage:
            if not item.estimated_repair_cost or item.estimated_repair_cost <= 0:
                frappe.throw(_("Repair cost required for damage item: {0} in {1}").format(
                    item.item_name, item.room))
            if not item.damage_justification or len(item.damage_justification.strip()) < 10:
                frappe.throw(_("Justification too short for damage item: {0} in {1}. "
                    "Minimum 10 characters required.").format(item.item_name, item.room))
            if not item.photo:
                frappe.throw(_("Photo evidence required for damage item: {0} in {1}").format(
                    item.item_name, item.room))
```

**Acceptance Criteria**:
- [ ] `is_damage = 1` + `estimated_repair_cost = 0` → validation error: "Repair cost required for damage items"
- [ ] `is_damage = 1` + empty `damage_justification` → validation error: "Justification required"
- [ ] `is_damage = 1` + `damage_justification` < 10 chars → validation error: "Justification too short"
- [ ] `is_damage = 1` + no `photo` → validation error: "Photo evidence required for damage items"
- [ ] `is_damage = 0` → no validation on repair cost, justification, or photo

---

## 4. Frappe — Annual Inspection Reminder

### 4.1 `check_flat_annual_inspection_due` Scheduler Job

> **Requires**: F01-2.2 (hooks.py), Base D05-2.1 (Rental Agreement), Base D04-3.1 (Asset Inspection)

For long-term tenancies, an annual property inspection ensures ongoing maintenance and documentation. This daily scheduler job identifies flats where the last inspection was more than **11 months ago** (giving 1 month of buffer before the 12-month mark) and sends a reminder to the property manager. This is an internal operational reminder — tenants are not notified about upcoming inspections through this system.

```python
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

**Acceptance Criteria**:
- [ ] Agreement active for 12+ months with no inspection in last 11 months → reminder fires
- [ ] Agreement active for 10 months with inspection 5 months ago → NO reminder
- [ ] Reminder sent via email AND Frappe ToDo to Property Manager
- [ ] Vehicle agreements → skipped
- [ ] Terminated/Expired agreements → skipped
- [ ] Reminder includes: flat name, agreement number, last inspection date (or "Never inspected")

---

### 4.2 `_notify_pm()` Helper

> **Requires**: 4.1

A shared utility function used by multiple scheduler jobs (inspection reminders, utility reading alerts) to send notifications to property managers. It creates both an **email** (for immediate visibility) and a **Frappe ToDo** (for task tracking in Desk). The function includes **idempotency protection**: it checks for existing open ToDos for the same agreement within the current week, preventing duplicate reminders if the scheduler runs multiple times.

Shared helper to send email + ToDo to the Property Manager:

```python
def _notify_pm(agreement, message):
    asset_name = agreement.asset if isinstance(agreement, dict) else agreement.get("asset")
    agr_name = agreement.name if isinstance(agreement, dict) else agreement.get("name")
    manager = frappe.db.get_value("Rental Asset", asset_name, "owner") or frappe.session.user
    
    # Check for existing recent ToDo (idempotency within same week)
    week_start = frappe.utils.get_first_day_of_week(frappe.utils.today())
    existing = frappe.db.exists("ToDo", {
        "owner": manager, "reference_name": agr_name,
        "creation": [">=", week_start], "status": "Open"})
    if existing:
        return
    
    frappe.get_doc({
        "doctype": "ToDo", "owner": manager, "priority": "Medium",
        "date": frappe.utils.add_days(frappe.utils.today(), 3),
        "description": f"{message}\nFlat: {asset_name}\nAgreement: {agr_name}",
        "reference_type": "Rental Agreement", "reference_name": agr_name,
    }).insert(ignore_permissions=True)
    
    frappe.sendmail(recipients=[manager], subject=message,
        message=f"{message}\nFlat: {asset_name}\nAgreement: {agr_name}")
```

**Acceptance Criteria**:
- [ ] Sends email to the Property Manager (from building/property `managed_by` or asset `owner`)
- [ ] Creates Frappe ToDo with `Medium` priority
- [ ] ToDo links to the Rental Agreement
- [ ] Idempotent: doesn't create duplicate ToDos for the same agreement in the same week

---

## 5. Web — Exit Deduction Visibility

### 5.1 Deduction Display on Agreement Detail

> **Requires**: Base D05-10.1 (My Rentals portal), Base D06-4.1 (Deposit Ledger), Base D06-9.1 (deposit section)

After a tenant moves out and an exit inspection is completed, the tenant needs to see what was deducted from their security deposit and why. This template block extends the base deposit section on the agreement detail page (`/my-rentals/{agreement}`) to show each deduction: a photo thumbnail of the damage, the description ("Kitchen – Countertop: deep scratch marks from knife usage"), the deduction amount, and a status badge (Pending/Disputed/Committed). While the deduction is still "Pending" and within the dispute window, a "Dispute" button is shown.

This extends the base deposit section on the agreement detail page to show inspection-originated deductions:

```html
{% if deposit_deductions %}
<div class="mt-3">
  <h6 class="fw-semibold">Exit Inspection Deductions</h6>
  {% for ded in deposit_deductions %}
  <div class="d-flex align-items-start border rounded p-2 mb-2">
    {% if ded.photo_evidence %}
    <img src="{{ ded.photo_evidence }}" class="rounded me-2" style="width:48px; height:48px; object-fit:cover;">
    {% endif %}
    <div class="flex-grow-1">
      <div class="small fw-semibold">{{ ded.reason }}</div>
      <div class="text-danger fw-bold">-{{ frappe.utils.fmt_money(ded.amount) }}</div>
    </div>
    <span class="badge bg-{{ 'warning' if ded.deduction_status == 'Pending' else 'info' if ded.deduction_status == 'Disputed' else 'secondary' }}">
      {{ ded.deduction_status }}
    </span>
    {% if ded.deduction_status == 'Pending' and dispute_window_open %}
    <button class="btn btn-outline-danger btn-sm ms-2" data-ded="{{ ded.name }}">Dispute</button>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endif %}
```

**Acceptance Criteria**:
- [ ] Exit inspection deductions visible to tenant on their agreement detail page (`/my-rentals`)
- [ ] Each deduction shows: description (room + item), amount, photo thumbnail, status badge (Pending/Disputed/Committed)
- [ ] "Dispute" button available for Pending deductions within dispute window (per Base D06-4.2)
- [ ] Entry inspection results NOT shown to tenant
- [ ] Flat access code NEVER shown on any web page

---

## 6. Flutter — Exit Deduction Visibility

### 6.1 Deduction Display on Agreement Detail

> **Requires**: Base D05-12.2 (Agreement Detail Screen), Base D06-10.3 (Deposit Detail Widget)

The Flutter equivalent of the web deduction display (5.1). On the agreement detail screen in the mobile app, this widget shows a card for each exit inspection deduction. Each card has a photo thumbnail (or a warning icon if no photo), the damage description, the deduction amount in red, and a status badge. The dispute button follows the same eligibility logic as the base deposit module.

Extend the base deposit section with deduction cards:

```dart
class InspectionDeductionCard extends StatelessWidget {
  final DepositDeduction deduction;
  const InspectionDeductionCard({required this.deduction, super.key});
  @override
  Widget build(BuildContext context) => Card(
    child: ListTile(
      leading: deduction.photoEvidence != null
          ? ClipRRect(borderRadius: BorderRadius.circular(6),
              child: Image.network(deduction.photoEvidence!, width: 48, height: 48, fit: BoxFit.cover))
          : const Icon(Icons.warning_amber, color: Colors.orange),
      title: Text(deduction.reason, style: const TextStyle(fontSize: 13)),
      subtitle: Text('-${CurrencyFormatter.format(deduction.amount)}',
          style: const TextStyle(color: Colors.red, fontWeight: FontWeight.bold)),
      trailing: _StatusBadge(status: deduction.status),
    ),
  );
}
```

**Acceptance Criteria**:
- [ ] Exit inspection deductions visible on agreement detail screen
- [ ] Each deduction: description, amount, photo thumbnail, status badge
- [ ] "Dispute" button for eligible deductions (same logic as Base D06-10.3)
- [ ] Entry inspection results NOT shown
- [ ] Flat access code NEVER included in any API response

---

## 7. Security Rules

### 7.1 Access Code Protection

Flat access codes (door codes, gate codes) and floor plans are **sensitive information** that must be protected across all layers of the application. These constraints are not about a single subtask — they're **cross-cutting rules** that every developer touching flat data must be aware of.

Security constraints that apply across ALL layers:

1. **Storage**: `custom_access_code` uses `Password` fieldtype — encrypted at rest in the database.
2. **API Exclusion**: `get_flat_detail` API explicitly removes `custom_access_code` from the response dict before returning.
3. **Web Templates**: No Jinja template references `asset.custom_access_code`.
4. **Flutter Model**: `FlatAsset` model does NOT include an `accessCode` field.
5. **Floor Plan CDN**: Floor plan URLs should use signed CDN URLs with short expiry windows (implementation-dependent on CDN provider).

**Acceptance Criteria**:
- [ ] `custom_access_code` is `Password` fieldtype → encrypted at rest
- [ ] `get_flat_detail` API excludes `custom_access_code` from response
- [ ] No web template renders `custom_access_code`
- [ ] Floor plan URL served via CDN (signed URL preferred; expires after short window)

---

## 8. Domain-Level Acceptance Criteria

- [ ] Entry inspection: room-by-room checklist submitted, appliance conditions synced
- [ ] Exit inspection: damage items → Pending deposit deductions with photo + justification
- [ ] Damage without photo → blocked by validation
- [ ] Damage without justification → blocked by validation
- [ ] Annual inspection reminder at 11-month gap
- [ ] Tenant sees exit deductions on portal/app — can dispute within window
- [ ] Entry results NOT visible to tenant
- [ ] Access code never exposed

---

## 9. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (checklist child table + controllers + annual reminder + validation) | 2.5 days |
| Web (deduction display on agreement detail) | 0.5 days |
| Flutter (deduction display on agreement detail) | 0.5 days |
| **Total** | **3.5 days** |
