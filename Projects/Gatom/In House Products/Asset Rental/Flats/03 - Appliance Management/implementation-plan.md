# Domain F03 — Appliance Management: Implementation Plan

> **Variant**: Flats (child app `rental_flats`)
> **Domain**: Appliance Management
> **Sequence**: 3 of 5
> **Depends on**: F01 (custom fields: `custom_appliances` child table), F05 (inspection updates condition)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Flats often come with appliances (refrigerator, washing machine, oven, etc.) that are owned by the landlord and included in the rental. The **Appliance Management** domain tracks these appliances per flat, monitors their condition through inspections, and alerts property managers when warranties are about to expire. Tenants can view the list of included appliances (with condition info) on the web detail page and in the mobile app, but **cannot** see serial numbers or warranty dates — those are internal asset management data.

This domain is tightly coupled with F05 (Inspection) — inspection checklists update appliance conditions, and F01 (Property Registry) — which hosts the `custom_appliances` child table on Rental Asset.

---

## 2. Frappe — `Flat Appliance` Child Table

### 2.1 Schema Definition

> **Requires**: F01-2.3 (`custom_appliances` Table field injected on Rental Asset)

The **Flat Appliance** child table stores the inventory of appliances included with each flat. It's a child table on `Rental Asset` (injected by F01), so appliances are managed inline on the asset form in Frappe Desk. Each row tracks the appliance's identity (name, brand, model), its current condition (updated by inspections), and optional warranty information. The `serial_number` is stored for internal asset tracking but is **never exposed** to customers through any API, web page, or mobile screen.

| Field | Type | Required | Notes |
|---|---|---|---|
| `appliance_name` | Data | ✅ | e.g., Refrigerator, Washing Machine |
| `brand` | Data | | |
| `model` | Data | | |
| `serial_number` | Data | | Desk-only — NEVER shown to customers |
| `purchase_date` | Date | | |
| `warranty_expiry` | Date | | |
| `condition` | Select | ✅ | `Excellent`, `Good`, `Fair`, `Damaged`, `Missing` |

**Acceptance Criteria**:
- [ ] Child table rows are addable inline on Rental Asset form (when asset_type = Flat)
- [ ] `appliance_name` and `condition` are mandatory
- [ ] `serial_number` field exists but is NEVER included in customer-facing API responses
- [ ] `warranty_expiry` is optional — omitted when unknown
- [ ] `condition` defaults to `Good` for new rows

---

### 2.2 Condition Update from Inspection

> **Requires**: 2.1, F05-2.1 (Flat Inspection with per-room checklist)

When an inspection (entry or exit) is completed, the inspector records the condition of each item in the flat — including appliances. This function syncs those inspection findings back to the appliance inventory. It matches inspection checklist items to appliances by name and updates their `condition` field. This means the appliance inventory always reflects the **most recent inspection state**.

For example, if the inspector marks the refrigerator as "Damaged" during an exit inspection, that condition is immediately reflected on the Rental Asset's appliance list.

```python
def update_appliance_conditions(inspection):
    """Called after inspection submission to sync appliance conditions."""
    asset = frappe.get_doc("Rental Asset", inspection.asset)
    for checklist_item in inspection.checklist_items:
        if checklist_item.item_type == "Appliance":
            for appliance in asset.custom_appliances:
                if appliance.appliance_name == checklist_item.item_name:
                    appliance.condition = checklist_item.condition
                    break
    asset.save(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Entry inspection updates appliance conditions to reflect move-in state
- [ ] Exit inspection updates appliance conditions to reflect move-out state
- [ ] Unmatched checklist items (no matching appliance name) are silently skipped
- [ ] Matched items update `condition` to the inspection's recorded condition
- [ ] Asset is saved after update (change persisted)

---

## 3. Frappe — Warranty Expiry Alert

### 3.1 `alert_appliance_warranty_expiry` Scheduler Job

> **Requires**: 2.1 (Flat Appliance with `warranty_expiry`), F01-2.2 (hooks.py)

Appliance warranties expire silently unless someone is watching. This daily scheduler job scans all appliances across all flats and finds those with warranties expiring within the next 30 days. For each one, it sends an **email** and creates a **ToDo** for the property manager, giving them time to arrange replacement or renewal before the warranty lapses. The job must be idempotent — running it twice on the same day should not create duplicate ToDos.

```python
def alert_appliance_warranty_expiry():
    target = frappe.utils.add_days(frappe.utils.today(), 30)
    rows = frappe.db.sql("""
        SELECT fa.appliance_name, fa.warranty_expiry, fa.parent AS asset
        FROM `tabFlat Appliance` fa
        WHERE fa.warranty_expiry BETWEEN %s AND %s
    """, (frappe.utils.today(), target), as_dict=True)
    for r in rows:
        manager = frappe.db.get_value("Rental Asset", r.asset, "owner")
        # Send email
        frappe.sendmail(recipients=[manager],
            subject=f"Warranty expiring: {r.appliance_name}",
            message=f"Warranty for {r.appliance_name} in flat {r.asset} expires on {r.warranty_expiry}.")
        # Create ToDo
        frappe.get_doc({
            "doctype": "ToDo",
            "owner": manager,
            "priority": "Medium",
            "date": r.warranty_expiry,
            "description": f"Warranty for {r.appliance_name} in {r.asset} expires on {r.warranty_expiry}. Arrange replacement or renewal.",
            "reference_type": "Rental Asset",
            "reference_name": r.asset,
        }).insert(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Appliance with warranty expiring in exactly 30 days → email + ToDo sent
- [ ] Appliance with warranty expiring in 15 days → email + ToDo sent (within 30-day window)
- [ ] Appliance with warranty expiring in 45 days → NO alert (outside window)
- [ ] Already-expired warranty (past date) → NO alert
- [ ] Appliance with no `warranty_expiry` → skipped
- [ ] Email sent to the asset `owner` (Property Manager)
- [ ] ToDo created with `Medium` priority and link to the asset
- [ ] Idempotent: running twice on the same day doesn't create duplicate ToDos (check by existing ToDo for same asset+appliance)

---

## 4. Web — Appliance Display (Detail Page)

### 4.1 Collapsible Appliance Section

> **Requires**: F01-8.3 (base detail conditional block renders), 2.1 (appliance data in context)

On the web detail page for a flat, tenants can see what appliances are included. This section is rendered as a **collapsible** `<details>` element (collapsed by default) so it doesn't overwhelm the page. It shows the appliance name, brand, and condition as a color-coded badge (green for Good, orange for Fair, red for Damaged). Serial numbers and warranty dates are intentionally excluded from the template context.

Already defined in F01-8.3. This section documents the specific acceptance criteria for the appliance content:

**Acceptance Criteria**:
- [ ] Collapsible `<details>` element with count in summary: "Included Appliances (5)"
- [ ] Table shows: Appliance Name, Brand, Condition Badge
- [ ] Condition badge colors: green (`Excellent`/`Good`), orange (`Fair`), red (`Damaged`/`Missing`)
- [ ] Serial number NOT shown (excluded from context)
- [ ] Warranty expiry NOT shown (excluded from context — Desk only)
- [ ] No appliances → section hidden entirely (not empty table)
- [ ] Section collapsed by default

---

## 5. Flutter — Appliance Display

### 5.1 `AppliancesScreen`

> **Requires**: F01-12.1 (already defined in F01). This section provides the detailed acceptance criteria:

A dedicated screen in the Flutter app listing all appliances for a flat. The user navigates here from the "Appliances" button on the flat detail screen. Each appliance is shown as a tile (see 5.2) with its name, brand, condition badge, and warranty countdown. The screen is entirely read-only — tenants can view but not modify appliance data.

**Acceptance Criteria**:
- [ ] Receives `List<FlatAppliance>` via GoRouter `extra` parameter
- [ ] Lists appliances in a `ListView`
- [ ] Each tile: appliance icon, name, brand, model (subtitle), condition badge, warranty countdown
- [ ] Condition badge colors: green (`Excellent`/`Good`/`New`), blue (`Good`), orange (`Fair`), red (`Needs Repair`/`Damaged`/`Missing`)
- [ ] Warranty countdown: green (>30 days), orange (≤30 days), red (expired)
- [ ] Warranty countdown hidden when `warrantyExpiry` is null
- [ ] Serial number NOT shown anywhere on this screen
- [ ] Screen is read-only — no edit buttons

---

### 5.2 `ApplianceTile` Widget

> **Requires**: 5.1

An individual list tile representing one appliance. Shows the appliance name as the title, brand and model as subtitle, and two trailing elements: a **condition badge** (color-coded: green for Excellent/Good, orange for Fair, red for Damaged/Missing) and a **warranty countdown** (green if >30 days, orange if ≤30 days, red if expired, hidden if no warranty date). This gives tenants a quick visual assessment of each appliance's state.

```dart
class ApplianceTile extends StatelessWidget {
  final FlatAppliance appliance;
  const ApplianceTile({required this.appliance, super.key});

  @override
  Widget build(BuildContext context) => ListTile(
    leading: CircleAvatar(
      backgroundColor: _conditionColor(appliance.condition).withOpacity(0.15),
      child: Icon(Icons.kitchen, color: _conditionColor(appliance.condition)),
    ),
    title: Text(appliance.name),
    subtitle: Text([appliance.brand, appliance.model].whereType<String>().join(' · ')),
    trailing: Column(mainAxisAlignment: MainAxisAlignment.center, crossAxisAlignment: CrossAxisAlignment.end, children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
        decoration: BoxDecoration(color: _conditionColor(appliance.condition), borderRadius: BorderRadius.circular(12)),
        child: Text(appliance.condition, style: const TextStyle(color: Colors.white, fontSize: 11)),
      ),
      if (appliance.warrantyExpiry != null) ...[
        const SizedBox(height: 4),
        Text(_warrantyText(appliance.warrantyExpiry!),
          style: TextStyle(fontSize: 11, color: _warrantyColor(appliance.warrantyExpiry!))),
      ],
    ]),
  );

  Color _conditionColor(String c) => switch (c) {
    'Excellent' || 'New' || 'Good' => Colors.green,
    'Fair' => Colors.orange,
    _ => Colors.red,
  };
  String _warrantyText(DateTime d) {
    final days = d.difference(DateTime.now()).inDays;
    return days > 0 ? '${days}d warranty' : 'Warranty expired';
  }
  Color _warrantyColor(DateTime d) {
    final days = d.difference(DateTime.now()).inDays;
    return days > 30 ? Colors.green : days > 0 ? Colors.orange : Colors.red;
  }
}
```

**Acceptance Criteria**:
- [ ] `ListTile` with `CircleAvatar` icon, title (name), subtitle (brand + model)
- [ ] Trailing column: condition badge (top), warranty countdown text (bottom)
- [ ] Warranty text: "{N}d warranty" for active, "Warranty expired" for past
- [ ] Text color matches countdown status (green/orange/red)

---

## 6. Domain-Level Acceptance Criteria

- [ ] Appliances tracked per flat with all required fields
- [ ] Condition updated after each entry/exit inspection
- [ ] Warranty alert fires 30 days before expiry (email + ToDo)
- [ ] Customer sees name, brand, condition on web and app — NOT serial number or warranty
- [ ] Collapsible section on web; dedicated screen on Flutter
- [ ] No appliances → section/button hidden

---

## 7. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (child table + condition sync + warranty alerts) | 1 day |
| Web (collapsible section — included in F01 detail) | 0.5 days |
| Flutter (appliance screen + tile widget) | 1 day |
| **Total** | **2.5 days** |
