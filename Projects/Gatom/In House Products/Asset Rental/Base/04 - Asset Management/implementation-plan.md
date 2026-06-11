# Domain 04 — Asset Management: Implementation Plan

> **Variant**: Base
> **Domain**: Asset Management
> **Sequence**: 4 of 8
> **Depends on**: Domain 01 (config), Domain 03 (KYC status for CTA)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Asset lifecycle, availability calendar, concurrency-safe reservation, SEO-optimised public catalog, and browsing experience on web and Flutter.

---

## 2. Frappe — `Rental Asset` DocType

### 2.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory `rental_asset/` must exist), D01-5.2 (role permissions)

| Field | Type | Required | Notes |
|---|---|---|---|
| `asset_name` | Data | ✅ | |
| `asset_code` | Data | ✅ | Auto: `FL-XXXXXXXX` / `VH-XXXXXXXX` |
| `asset_type` | Select | ✅ | `Flat`, `Vehicle` |
| `status` | Select | ✅ | `Available`, `Reserved`, `Rented`, `Maintenance`, `Retired` |
| `location` | Data | | City/region |
| `geo_lat` / `geo_lng` | Float | | |
| `monthly_rate` | Currency | ✅ | |
| `deposit_amount` | Currency | ✅ | |
| `description` | Text Editor | | |
| `images` | Table → `Asset Image` | | |
| `is_active` | Check | | Default 1 |
| `is_featured` | Check | | For curated homepage carousel |
| `version` | Int | | For optimistic concurrency (default: 0) |
| `acquisition_cost` | Currency | | For ROI calculation (D08) |
| `custom_preview_mode` | Select | | `None`, `Embed URL`, `3D Model (GLB)`, `360° Photo Sphere` |
| `custom_preview_embed_url` | Data | | |
| `custom_preview_model_file` | Attach | | |
| `custom_preview_sphere_file` | Attach | | |

**Acceptance Criteria**:
- [ ] DocType is accessible in Frappe Desk under "Rental" module
- [ ] `asset_code` auto-generates with prefix `FL-` for Flat and `VH-` for Vehicle
- [ ] `status` defaults to `Available` on creation
- [ ] `monthly_rate` and `deposit_amount` are mandatory
- [ ] `is_active` defaults to 1 (checked)
- [ ] `version` defaults to 0 and is hidden from form (used only programmatically)
- [ ] `images` child table allows adding multiple images with upload

---

### 2.2 Status Transition Logic

> **Requires**: 2.1 (schema with `status` field)

```python
ALLOWED = {
    "Available": ["Reserved", "Maintenance", "Retired"],
    "Reserved": ["Available", "Rented"],
    "Rented": ["Available", "Maintenance"],
    "Maintenance": ["Available", "Retired"],
    "Retired": [],
}

def set_status(self, new_status):
    if new_status not in ALLOWED.get(self.status, []):
        frappe.throw(_(f"Cannot transition from {self.status} to {new_status}"))
    frappe.db.set_value("Rental Asset", self.name, "status", new_status, update_modified=False)
```

**Acceptance Criteria**:
- [ ] `Available → Reserved` succeeds
- [ ] `Available → Rented` fails (must go through Reserved first)
- [ ] `Reserved → Rented` succeeds
- [ ] `Reserved → Available` succeeds (cancellation releases asset)
- [ ] `Retired → anything` fails (terminal state)
- [ ] `Rented → Maintenance` succeeds
- [ ] `Maintenance → Retired` succeeds
- [ ] Invalid transition raises `ValidationError` with descriptive message

---

## 3. Frappe — `Asset Inspection` DocType

### 3.1 Schema Definition

> **Requires**: 2.1 (Rental Asset for link), D05-2.1 (Rental Agreement for link — can stub)

| Field | Type | Notes |
|---|---|---|
| `agreement` | Link → Rental Agreement | |
| `asset` | Link → Rental Asset | |
| `inspection_type` | Select: `Entry`, `Exit` | |
| `inspection_date` | Date | |
| `inspector` | Link → User | |
| `checklist` | Table (child app provides rows) | |
| `photos` | Table → `Inspection Photo` | |
| `damage_notes` | Text | |
| `estimated_repair_cost` | Currency | |
| `signed_by_tenant` | Check | |

**Acceptance Criteria**:
- [ ] DocType exists in Frappe Desk
- [ ] `inspection_type` is mandatory with options `Entry` and `Exit`
- [ ] `photos` child table allows multiple image uploads
- [ ] `signed_by_tenant` is a checkbox (default unchecked)
- [ ] `estimated_repair_cost` is Currency type with 2 decimal places

---

### 3.2 Exit Inspection → Deposit Deduction

> **Requires**: 3.1 (inspection schema), D06-4.1 (Deposit Ledger schema)

**Acceptance Criteria**:
- [ ] Submitting an `Exit` inspection with `estimated_repair_cost > 0` creates a `Deposit Deduction` row
- [ ] Deduction row has `deduction_status = Pending` (not auto-committed)
- [ ] Deduction `reason` includes reference to the inspection name
- [ ] Submitting an `Entry` inspection does NOT create a deposit deduction

---

## 4. Frappe — Catalog Query Service

### 4.1 `asset_catalog_query.py`

> **Requires**: 2.1 (Rental Asset schema with all filter fields)

```python
def query_available_assets(asset_type="", location="", max_price=None,
                          page=1, page_size=12, extra_filters=None) -> dict:
    filters = {"status": "Available", "is_active": 1}
    if asset_type in ("Flat", "Vehicle"):
        filters["asset_type"] = asset_type
    if max_price:
        filters["monthly_rate"] = ["<=", float(max_price)]
    if location:
        safe_location = re.sub(r'[%_]', '', location)[:50]
        if safe_location:
            filters["location"] = ["like", f"%{safe_location}%"]
    if extra_filters:
        filters.update(extra_filters)
    total = frappe.db.count("Rental Asset", filters)
    offset = (page - 1) * page_size
    assets = frappe.get_all("Rental Asset", filters=filters,
        fields=["name", "asset_name", "asset_type", "location",
                "monthly_rate", "deposit_amount", "status"],
        limit_start=offset, limit_page_length=page_size,
        order_by="monthly_rate asc")
    # Batch cover image query
    if assets:
        asset_names = [a.name for a in assets]
        images = frappe.db.sql("""
            SELECT parent, image FROM `tabAsset Image`
            WHERE parent IN %(assets)s AND idx = 1
        """, {"assets": asset_names}, as_dict=True)
        image_map = {i.parent: i.image for i in images}
        for a in assets:
            a.cover_image = image_map.get(a.name, "/assets/rental_core/images/placeholder.jpg")
    return {"assets": assets, "total": total, "page": page, "page_size": page_size,
            "has_next": (offset + page_size) < total}
```

**Acceptance Criteria**:
- [ ] Returns only `Available` and `is_active=1` assets
- [ ] `asset_type="Flat"` filters to flats only
- [ ] `max_price=2000` returns only assets with `monthly_rate <= 2000`
- [ ] Location filter with `%` or `_` characters has them stripped (SQL injection prevention)
- [ ] Location filter truncated to 50 chars
- [ ] Empty location filter returns all locations
- [ ] Pagination: `page=1, page_size=12` returns first 12 assets
- [ ] `has_next=true` when more assets exist beyond current page
- [ ] `has_next=false` on the last page
- [ ] Cover image query uses single batch SQL (not N+1)
- [ ] Asset without images gets placeholder image URL
- [ ] Both SSR controller and API endpoint use this same function (no logic duplication)

---

## 5. Frappe — Concurrency-Safe Reservation

### 5.1 `SELECT FOR UPDATE` Lock

> **Requires**: 2.1 (Rental Asset with `status` field)

```python
def reserve_asset(asset_name):
    frappe.db.sql("SELECT status FROM `tabRental Asset` WHERE name = %s FOR UPDATE", asset_name)
    current_status = frappe.db.get_value("Rental Asset", asset_name, "status")
    if current_status != "Available":
        frappe.throw(_("This asset is no longer available."), exc=frappe.ValidationError)
    frappe.db.set_value("Rental Asset", asset_name, "status", "Reserved")
```

**Acceptance Criteria**:
- [ ] Two simultaneous booking requests for the same asset: one succeeds, one gets "no longer available" error
- [ ] Successful reservation sets status to `Reserved` (NOT `Rented`)
- [ ] `SELECT FOR UPDATE` blocks concurrent reads until the transaction commits
- [ ] Error response returns HTTP 409 (Conflict)

---

### 5.2 Optimistic Concurrency Fallback

> **Requires**: 2.1 (`version` field on Rental Asset), 5.1

```python
rows = frappe.db.sql(
    "UPDATE `tabRental Asset` SET status='Reserved', version=version+1 WHERE name=%s AND version=%s",
    (asset_name, current_version))
if rows == 0:
    frappe.throw(_("Concurrency conflict — please try again"))
```

**Acceptance Criteria**:
- [ ] Works on Galera/MariaDB clusters where `SELECT FOR UPDATE` may not guarantee isolation
- [ ] Version mismatch returns "Concurrency conflict" error
- [ ] Successful reservation increments `version` by 1
- [ ] This is used as fallback when `FOR UPDATE` is not available

---

## 6. Frappe — Draft Expiry & Rejection

### 6.1 Draft Expiry Scheduler

> **Requires**: D01-3.1 (`draft_expiry_hours` config field), 2.2 (status transitions), D05-2.1 (Rental Agreement schema)

```python
def expire_unreviewed_bookings():
    config = frappe.get_single("Rental Configuration")
    expiry_hours = config.draft_expiry_hours or 48
    cutoff = add_to_date(now_datetime(), hours=-expiry_hours)
    stale = frappe.get_all("Rental Agreement",
        filters={"docstatus": 0, "status": "Draft", "creation": ["<", cutoff]},
        fields=["name", "asset", "customer"])
    for agr in stale:
        frappe.db.set_value("Rental Agreement", agr.name, "status", "Expired")
        frappe.db.set_value("Rental Asset", agr.asset, "status", "Available")
        send_reminder(agr, "Booking Expired")
```

**Acceptance Criteria**:
- [ ] Draft agreement created 49 hours ago (with `draft_expiry_hours=48`) → status set to `Expired`
- [ ] Draft agreement created 47 hours ago → NOT expired
- [ ] Expired agreement's asset returns to `Available`
- [ ] Customer receives "Booking Expired" notification
- [ ] Scheduler runs every 5 minutes without error when no stale drafts exist
- [ ] Non-Draft agreements (Active, Terminated) are never touched

---

### 6.2 Rejection Handler

> **Requires**: D05-2.1 (Rental Agreement with `rejection_reason` field), 2.2 (status transitions)

```python
def reject_booking(self, reason):
    if len(reason or "") < 20:
        frappe.throw(_("Rejection reason must be at least 20 characters"))
    self.rejection_reason = reason
    self.status = "Rejected"
    self.save(ignore_permissions=True)
    asset = frappe.get_doc("Rental Asset", self.asset)
    asset.set_status("Available")
    send_reminder(self, "Booking Rejected")
```

**Acceptance Criteria**:
- [ ] Rejection with reason < 20 chars returns validation error
- [ ] Rejection with reason >= 20 chars succeeds
- [ ] Rejected agreement's asset returns to `Available`
- [ ] Customer receives push + email with the rejection reason text
- [ ] Already-Active agreements cannot be rejected (status transition check fails)

---

## 7. Frappe — API Endpoints

### 7.1 `get_available_assets`

> **Requires**: 4.1 (catalog query service)

**Acceptance Criteria**:
- [ ] Returns paginated list matching D01-6.2 pagination standard
- [ ] Token auth required
- [ ] Rate limit: 60/min
- [ ] Filters: `asset_type`, `location`, `max_price`, `page`, `page_size`

---

### 7.2 `get_asset_detail`

> **Requires**: 2.1 (Rental Asset schema)

**Acceptance Criteria**:
- [ ] Returns full asset data including images, description, preview info
- [ ] Returns variant-specific custom fields (set by child apps)
- [ ] Non-existent asset name returns HTTP 404

---

### 7.3 `get_asset_availability`

> **Requires**: 2.1 (Rental Asset), D05-2.1 (Rental Agreement with date ranges)

**Acceptance Criteria**:
- [ ] Returns blocked date ranges for the given month/year
- [ ] Does NOT return the reason for blocking (opaque to customer)
- [ ] Blocked ranges include: active agreements, reserved periods, maintenance windows
- [ ] Available dates are not explicitly listed (only blocked ranges)

---

### 7.4 `get_featured_assets`

> **Requires**: 2.1 (`is_featured` field)

**Acceptance Criteria**:
- [ ] Returns only assets where `is_featured=1` AND `status=Available`
- [ ] Paginated per D01-6.2 standard
- [ ] Empty result when no assets are featured (not an error)

---

### 7.5 `get_active_rental_summary`

> **Requires**: D05-2.1 (Rental Agreement), D06 (invoices)

**Acceptance Criteria**:
- [ ] Returns current customer's active agreements with next invoice data
- [ ] Each entry includes: `asset_name`, `status`, `next_invoice_amount`, `next_invoice_due_date`
- [ ] No active agreements → empty list (not error)

---

## 8. Web — Catalog Page

### 8.1 Controller `www/rentals.py`

> **Requires**: 4.1 (catalog query service), D01-7.3 (page stub)

**Acceptance Criteria**:
- [ ] `/rentals` renders SSR with first 24 assets
- [ ] `curl /rentals` returns HTML with asset cards (SEO-crawlable)
- [ ] Filter parameters in URL (`?type=Flat&max_price=2000`) are passed to query
- [ ] No assets matching filters → "No assets found" message

---

### 8.2 AJAX Filter (`catalog.js`)

> **Requires**: 8.1 (page renders), 7.1 (API endpoint)

```javascript
function loadAssets(filters = {}, page = 1) {
  frappe.call({
    method: 'rental_core.api.assets.get_available_assets',
    args: { ...filters, page, page_size: 12 },
    callback(r) {
      renderCards(r.message.assets);
      renderPagination(r.message.total, page, r.message.page_size, r.message.has_next);
    },
  });
}
```

**Acceptance Criteria**:
- [ ] Changing filter dropdown updates the grid without page reload
- [ ] Loading skeleton (shimmer) shows during fetch
- [ ] Pagination controls appear when `has_next=true`
- [ ] "Previous" disabled on page 1; "Next" disabled on last page
- [ ] All calls use `frappe.call()` (CSRF-safe)

---

## 9. Web — Asset Detail Page

### 9.1 Controller `www/rentals/{asset}.py`

> **Requires**: 2.1 (Rental Asset schema), D01-7.3 (page stub)

**Acceptance Criteria**:
- [ ] Page renders with asset name, description, images, monthly rate, deposit
- [ ] `og:title`, `og:description`, `og:image` meta tags set for social sharing
- [ ] Non-existent asset name returns 404 (not 500)
- [ ] Preview embed (3D/360°) renders when `custom_preview_mode` is set

---

### 9.2 Availability Calendar (`asset_detail.js`)

> **Requires**: 9.1 (page context), 7.3 (availability API)

**Acceptance Criteria**:
- [ ] Calendar renders with current month focused
- [ ] Blocked dates have visual styling (grayed out / crossed)
- [ ] Blocked dates are non-clickable
- [ ] Navigating to next/previous month fetches new availability data
- [ ] No reason shown for why a date is blocked

---

## 10. Flutter — Catalog & Asset Detail

### 10.1 Catalog Provider

> **Requires**: D01-8.6 (FrappeClient), 7.1 (API endpoint)

```dart
@riverpod
Future<List<RentalAsset>> availableAssets(Ref ref, AssetFilter filter) => /* ... */
```

**Acceptance Criteria**:
- [ ] Provider fetches from `get_available_assets` API
- [ ] Filter changes invalidate and re-fetch
- [ ] `keepAlive: true` — data survives screen navigation

---

### 10.2 Catalog Screen + Card Widget

> **Requires**: 10.1 (provider), D01-8.3 (screen stub)

**Acceptance Criteria**:
- [ ] Grid of `AssetCardWidget` with cover image, name, price, location
- [ ] Infinite scroll loads next page when reaching bottom
- [ ] Shimmer loading skeleton shown during fetch
- [ ] Empty state shown when no assets match filter

---

### 10.3 Filter Sheet

> **Requires**: 10.2 (catalog screen)

**Acceptance Criteria**:
- [ ] Bottom sheet with type tabs (All / Flat / Vehicle), location input, max price slider
- [ ] Applying filters refreshes the catalog grid
- [ ] "Clear Filters" resets all to default

---

### 10.4 Asset Detail Screen

> **Requires**: D01-8.6 (FrappeClient), 7.2 (asset detail API), D01-8.3 (screen stub)

**Acceptance Criteria**:
- [ ] Displays all asset info: name, description, images, rate, deposit
- [ ] Image gallery is swipeable (carousel)
- [ ] Preview button shown when `custom_preview_mode != None`

---

### 10.5 Availability Calendar Widget

> **Requires**: 10.4 (detail screen), 7.3 (availability API)

```dart
class AvailabilityCalendarWidget extends ConsumerWidget { /* ... */ }
```

**Acceptance Criteria**:
- [ ] Calendar renders with blocked dates non-tappable
- [ ] Month navigation fetches new data via `ref.invalidate()`
- [ ] Loading state shows `CircularProgressIndicator`
- [ ] Error state shows `ErrorView` with message

---

### 10.6 Home Screen Enhancements

> **Requires**: 7.4 (featured assets API), 7.5 (active rental summary API)

**Acceptance Criteria**:
- [ ] `FeaturedAssetsCarousel` shows horizontal scroll of featured assets
- [ ] `ActiveRentalSummaryCard` shows next invoice amount + due date
- [ ] No featured assets → section hidden (not empty carousel)
- [ ] No active rentals → summary card hidden

---

## 11. Domain-Level Acceptance Criteria

- [ ] Two concurrent booking attempts: one succeeds, one gets conflict error
- [ ] Draft agreement auto-expires after configured hours — asset freed
- [ ] Rejected booking: asset freed, customer notified with reason
- [ ] Calendar never discloses reason for blocked dates
- [ ] SSR catalog is SEO-crawlable
- [ ] Location filter with SQL wildcards is sanitized
- [ ] Featured assets appear on Flutter home screen

---

## 12. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (Asset + Inspection + Catalog + Concurrency + Expiry + APIs) | 5 days |
| Web (Catalog + Detail + Calendar) | 2 days |
| Flutter (Catalog + Detail + Calendar + Home widgets) | 3 days |
| **Total** | **10 days** |
