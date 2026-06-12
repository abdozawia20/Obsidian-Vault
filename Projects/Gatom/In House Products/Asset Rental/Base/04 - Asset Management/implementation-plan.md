# Domain 04 — Asset Management: Implementation Plan

> **Variant**: Base
> **Domain**: Asset Management
> **Sequence**: 4 of 8
> **Depends on**: Domain 01 (config), Domain 03 (KYC status for CTA)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

This domain manages the **rental assets themselves** — the properties and vehicles that customers can browse, reserve, and rent. It covers the full asset lifecycle (Available → Reserved → Rented → Maintenance → Retired), the public-facing catalog that customers browse on the web and app, the availability calendar showing which dates are blocked, and the **concurrency-safe reservation** mechanism that prevents two customers from booking the same asset simultaneously.

The domain also handles draft booking expiry (unreviewable bookings auto-expire after a configured time), rejection handling (staff can reject bookings with a required reason), and SEO optimization for the public catalog pages.

---

## 2. Frappe — `Rental Asset` DocType

### 2.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory `rental_asset/` must exist), D01-5.2 (role permissions)

The **Rental Asset** is the central DocType of the entire platform — everything revolves around it. It represents a single rentable unit (a flat, a vehicle, or any future asset type). The schema includes pricing (`monthly_rate`, `deposit_amount`), location data (city/region + GPS coordinates for map display), a media gallery (`images` child table), and status tracking through a defined state machine. The `version` field enables optimistic concurrency control for race-safe reservations.

Child apps (Flats, Vehicles) extend this DocType with **custom fields** rather than modifying the base schema.

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

Assets follow a **strict state machine** — not every status change is allowed. An Available asset can be Reserved (booking started) or put into Maintenance, but it cannot jump directly to Rented (must go through Reserved first). A Rented asset can return to Available (lease ended) or go to Maintenance (repair needed). A Retired asset is a **terminal state** — it can never be reactivated. This prevents data inconsistencies and provides clear lifecycle tracking.

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

An **Asset Inspection** records the physical condition of an asset at a specific point in time — typically at move-in (Entry) and move-out (Exit). Entry inspections document the baseline condition. Exit inspections compare against the entry state and calculate repair costs for any new damage. The inspection includes a photo evidence table, damage notes, estimated repair cost, and a tenant signature acknowledgment.

Child apps extend the `checklist` with variant-specific rows (e.g., Flats adds appliance checks, Vehicles adds mileage and bodywork items).

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

### 3.2 Exit Inspection → Domain Event Dispatch

> **Requires**: 3.1 (inspection schema), D01-2.4 (extension hook architecture)

When a tenant moves out and damage is found, the **exit inspection** fires a domain event rather than writing directly to the Accounting domain's tables. This preserves **bounded context separation** — the Asset Management domain (D04) knows about inspections, not deposit ledgers.

> [!IMPORTANT]
> **Architecture Decision**: This subtask previously had D04 directly creating `Deposit Deduction` rows in D06's `Deposit Ledger`. That violated DDD's bounded context principle — D04 was importing and manipulating D06's internal schema. The refactored version uses the **domain event pattern** (same as `on_invoice_created` in D06-§2.5) to decouple the domains.

If `estimated_repair_cost > 0` on an Exit inspection, the controller dispatches an `exit_inspection_completed` event with the inspection data. D06 listens to this event (via `rental_hooks` in hooks.py) and creates the `Deposit Deduction` row internally. D04 never imports, references, or knows about the `Deposit Ledger` DocType.

```python
# In D04's Asset Inspection controller
def on_submit(self):
    if self.inspection_type == "Exit" and self.estimated_repair_cost > 0:
        from rental_core.utils.events import dispatch_rental_event
        dispatch_rental_event("exit_inspection_completed", {
            "inspection": self.name,
            "agreement": self.agreement,
            "estimated_repair_cost": self.estimated_repair_cost,
            "damage_notes": self.damage_notes,
            "photo_evidence": self.photos[0].photo if self.photos else None,
        })
```

```python
# D06 registers a handler in hooks.py:
# rental_hooks = {"exit_inspection_completed": "rental_core.accounting.deposits.handle_exit_inspection"}

# In rental_core/accounting/deposits.py (D06 owned)
def handle_exit_inspection(inspection, agreement, estimated_repair_cost, **kwargs):
    ledger = frappe.get_doc("Deposit Ledger", {"agreement": agreement})
    ledger.append("deductions", {
        "reason": f"Damage per inspection {inspection}",
        "amount": estimated_repair_cost,
        "deduction_status": "Pending",
        "photo_evidence": kwargs.get("photo_evidence"),
    })
    ledger.save(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Submitting an `Exit` inspection with `estimated_repair_cost > 0` dispatches `exit_inspection_completed` event
- [ ] D06's handler creates a `Deposit Deduction` row with `deduction_status = Pending`
- [ ] Deduction `reason` includes reference to the inspection name
- [ ] Submitting an `Entry` inspection does NOT dispatch the event
- [ ] D04 code does NOT import or reference `Deposit Ledger` or `Deposit Deduction` DocTypes
- [ ] If D06's handler is not registered (edge case), the event fires without error

---

## 4. Frappe — Catalog Query Service

### 4.1 `asset_catalog_query.py`

> **Requires**: 2.1 (Rental Asset schema with all filter fields)

The **catalog query service** is the core search engine for the platform. Both the web portal (SSR rendering) and the API endpoint (Flutter app) use this same function — ensuring identical search behavior across all channels. It filters by asset type, location (with SQL injection protection), and price range, and returns paginated results with cover images.

Performance optimization: cover images are fetched in a **single batch query** (not N+1), and the location filter sanitizes `%` and `_` wildcards to prevent SQL injection through the LIKE clause.

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

The most critical concurrency challenge in the platform: **two customers trying to book the same asset at the same time**. Without protection, both would see `Available`, both would proceed, and you'd have a double-booking. The `SELECT FOR UPDATE` statement acquires a database-level row lock, so the second request blocks until the first completes. If the first request reserved the asset, the second finds `Reserved` status and gets a conflict error.

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

Some database configurations (Galera/MariaDB clusters) don't guarantee `SELECT FOR UPDATE` isolation. This **fallback mechanism** uses optimistic concurrency control: the `version` column is incremented atomically in the same `UPDATE` statement that changes the status. If two requests read the same version and both try to update, only one succeeds (the one where `version` still matches). The other gets zero rows affected and knows a concurrent write happened.

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

When a customer creates a booking, it starts as a `Draft` agreement awaiting staff review. If the staff doesn't review it within the configured time window (default 48 hours), the booking **auto-expires**: the agreement status changes to `Expired`, the asset returns to `Available`, and the customer receives a notification. This prevents assets from being tied up indefinitely in limbo. The scheduler runs every 5 minutes (registered in D01 hooks.py) for time-sensitive expiration.

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

Staff can **reject a booking** if they decide the customer or terms aren't suitable. The rejection requires a reason of at least 20 characters (to prevent lazy "no" rejections and give the customer actionable feedback). On rejection, the asset returns to `Available` and the customer receives the rejection reason via push + email. Already-active agreements cannot be rejected — they go through the termination flow instead.

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

The public-facing API that the Flutter app calls to populate the catalog screen. It wraps the catalog query service (4.1) and exposes it as a Frappe whitelisted method with token auth and rate limiting. The response follows the D01-6.2 pagination standard.

**Acceptance Criteria**:
- [ ] Returns paginated list matching D01-6.2 pagination standard
- [ ] Token auth required
- [ ] Rate limit: 60/min
- [ ] Filters: `asset_type`, `location`, `max_price`, `page`, `page_size`

---

### 7.2 `get_asset_detail`

> **Requires**: 2.1 (Rental Asset schema)

Returns the **full details** of a single asset for the detail page/screen. This includes everything: all images, full description, pricing, location, and any custom fields set by child apps (e.g., number of bedrooms for flats, vehicle make/model). Returns HTTP 404 for non-existent assets instead of an empty result.

**Acceptance Criteria**:
- [ ] Returns full asset data including images, description, preview info
- [ ] Returns variant-specific custom fields (set by child apps)
- [ ] Non-existent asset name returns HTTP 404

---

### 7.3 `get_asset_availability`

> **Requires**: 2.1 (Rental Asset), D05-2.1 (Rental Agreement with date ranges)

Returns the **blocked date ranges** for a given asset in a given month. The response is intentionally **opaque** — it shows which dates are blocked but not why (could be another tenant's booking, a maintenance window, or a hold). This protects tenant privacy while letting prospective renters know when the asset is free.

**Acceptance Criteria**:
- [ ] Returns blocked date ranges for the given month/year
- [ ] Does NOT return the reason for blocking (opaque to customer)
- [ ] Blocked ranges include: active agreements, reserved periods, maintenance windows
- [ ] Available dates are not explicitly listed (only blocked ranges)

---

### 7.4 `get_featured_assets`

> **Requires**: 2.1 (`is_featured` field)

Returns **curated assets** that the operator wants to promote. These appear in carousels on the home page and app home screen. Only assets that are both `is_featured=1` AND `status=Available` are returned — no point featuring an asset that can't be booked.

**Acceptance Criteria**:
- [ ] Returns only assets where `is_featured=1` AND `status=Available`
- [ ] Paginated per D01-6.2 standard
- [ ] Empty result when no assets are featured (not an error)

---

### 7.5 `get_active_rental_summary`

> **Requires**: D05-2.1 (Rental Agreement), D06 (invoices)

Powers the **"My Active Rentals" summary card** on the home screen. Returns the logged-in customer's active agreements with their next invoice amount and due date. This gives customers an at-a-glance view of their financial obligations without navigating to the full invoices page.

**Acceptance Criteria**:
- [ ] Returns current customer's active agreements with next invoice data
- [ ] Each entry includes: `asset_name`, `status`, `next_invoice_amount`, `next_invoice_due_date`
- [ ] No active agreements → empty list (not error)

---

### 7.6 Redis Cache Layer for Catalog APIs

> **Requires**: 7.1 (get_available_assets), 7.4 (get_featured_assets), D01 Frappe cache (`frappe.cache()`)

The catalog APIs (§7.1 and §7.4) are the **highest-traffic endpoints** in the platform — every visitor hits them. Without caching, each request runs a multi-table SQL query against `Rental Asset`, `Rental Agreement`, and `File` tables. This caching layer uses **Frappe's built-in Redis cache** (`frappe.cache()`) to avoid redundant database queries.

> [!NOTE]
> **Library-First**: We use `frappe.cache().get_value()` / `set_value()` (which wraps Redis) — NOT a custom Redis client. Frappe manages the Redis connection, serialization, and cluster compatibility.

**Caching strategy**:
- **`get_available_assets`**: Cache key = `catalog:{hash(filters)}`, TTL = 60 seconds. The filter hash includes `asset_type`, `location`, `max_price`, `page`, `page_size`. This means the same filter combination returns cached results for up to 60 seconds.
- **`get_featured_assets`**: Cache key = `featured_assets`, TTL = 300 seconds. Featured assets change infrequently (operator curates them), so a 5-minute cache is acceptable.

**Cache invalidation**:
- On `Rental Asset` save/submit/cancel → invalidate all `catalog:*` keys (Frappe's `frappe.cache().delete_keys("catalog:")` supports prefix deletion)
- On `is_featured` flag change → invalidate `featured_assets` key
- Pull-to-refresh from Flutter → API call includes `?no_cache=1` parameter that bypasses the cache

```python
@frappe.whitelist(allow_guest=True)
def get_available_assets(asset_type=None, location=None, max_price=None, page=1, page_size=24, no_cache=False):
    cache_key = f"catalog:{hashlib.md5(f'{asset_type}:{location}:{max_price}:{page}:{page_size}'.encode()).hexdigest()}"
    if not no_cache:
        cached = frappe.cache().get_value(cache_key)
        if cached:
            return cached
    result = _query_catalog(asset_type, location, max_price, page, page_size)  # §4.1
    frappe.cache().set_value(cache_key, result, expires_in_sec=60)
    return result
```

**Acceptance Criteria**:
- [ ] Second identical catalog request within 60s returns cached result (no SQL query)
- [ ] Cache key includes all filter parameters (different filters = different cache entries)
- [ ] Saving a `Rental Asset` invalidates all catalog cache entries
- [ ] Changing `is_featured` invalidates the featured assets cache
- [ ] `no_cache=1` parameter bypasses cache and refreshes it
- [ ] Cache uses `frappe.cache()` (Redis) — not database or in-memory
- [ ] Featured assets cache TTL is 300 seconds
- [ ] Cache miss → normal SQL query → result stored in cache

---

## 8. Web — Catalog Page

### 8.1 Controller `www/rentals.py`

> **Requires**: 4.1 (catalog query service), D01-7.3 (page stub)

The **catalog page** is the main public-facing page of the rental platform. It's **server-side rendered** (SSR) so search engines can crawl and index the available assets. The controller calls the same catalog query service that the API uses, ensuring identical results. URL parameters (`?type=Flat&max_price=2000`) are passed through as filters for bookmarkable/shareable filtered URLs.

**Acceptance Criteria**:
- [ ] `/rentals` renders SSR with first 24 assets
- [ ] `curl /rentals` returns HTML with asset cards (SEO-crawlable)
- [ ] Filter parameters in URL (`?type=Flat&max_price=2000`) are passed to query
- [ ] No assets matching filters → "No assets found" message

---

### 8.2 AJAX Filter (`catalog.js`)

> **Requires**: 8.1 (page renders), 7.1 (API endpoint)

After the initial SSR page load, **filter changes happen via AJAX** without full page reloads. When a user changes the asset type dropdown, adjusts the price range, or types a location, the JavaScript calls the API and re-renders only the asset grid. A shimmer loading skeleton provides visual feedback during the fetch. Pagination controls appear at the bottom when results span multiple pages.

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

### 8.3 Variant-Aware Card Rendering

> **Requires**: 8.2 (AJAX filter), D01-2.4 (extension hook architecture)

The base catalog displays **both Flats and Vehicles** when both child apps are installed. However, a Flat card and a Vehicle card look different — a Flat shows bedrooms, bathrooms, and floor area, while a Vehicle shows make, model, seats, and transmission. The base layer must support this **without hardcoding variant-specific fields**.

The card template uses an **attribute slot pattern**: the base card renders the cover image, name, price, location, and availability badge (these are common to all assets). Below the common fields, a `<div class="asset-card-attributes">` section renders a **dynamic attribute grid** populated from the asset's `variant_attributes` API field. This field is a list of `{label, value}` pairs that the child app injects via a `doc_events` hook on `Rental Asset`.

For example, `rental_flats` hooks into `Rental Asset.on_load` and adds `[{"label": "Bedrooms", "value": "3"}, {"label": "Area", "value": "120 sqm"}]`. The base template iterates over this list and renders each pair as a `<span class="attr"><strong>{{ attr.label }}:</strong> {{ attr.value }}</span>`.

If no child app is installed (unlikely but possible during development), the attribute section is simply empty — the card still renders correctly with just the base fields.

```html
<!-- In catalog card template -->
<div class="asset-card-attributes">
  {% for attr in asset.variant_attributes or [] %}
    <span class="attr"><strong>{{ attr.label }}:</strong> {{ attr.value }}</span>
  {% endfor %}
</div>
```

**Acceptance Criteria**:
- [ ] Flat assets display bedroom count, bathroom count, and area in the attribute grid
- [ ] Vehicle assets display make, model, seats, and transmission in the attribute grid
- [ ] Cards render correctly with zero variant attributes (base-only installation)
- [ ] The base template does NOT import or reference `rental_flats` or `rental_vehicles` code
- [ ] Variant attributes are injected via `doc_events` hook (child app responsibility)
- [ ] Attribute grid layout adapts to 2–5 attributes without breaking

---

### 8.4 Sitemap Verification

> **Requires**: 8.1 (catalog page must be a `www/` route), D01-7.4 (robots.txt references sitemap)

Frappe automatically generates a `sitemap.xml` for all pages under `www/`. However, **dynamic catalog pages** (asset detail pages rendered via `www/rentals/{asset}.py`) may not be automatically included because they use wildcard routing rather than static files. This subtask verifies that:

1. The main `/rentals` catalog page is in the sitemap
2. All individual asset detail pages (`/rentals/ASSET-001`, `/rentals/ASSET-002`, etc.) are included
3. Portal pages (`/my-rentals`, `/my-invoices`, `/my-kyc`) are **excluded** (they're behind auth)
4. The sitemap is accessible at the URL referenced in `robots.txt` (D01-7.4)

If Frappe's automatic sitemap doesn't include the dynamic asset pages, a custom sitemap generator must be implemented using Frappe's `get_sitemap_routes` hook to dynamically list all `Available` assets.

```python
# In hooks.py (if dynamic pages need explicit inclusion)
def get_sitemap_routes():
    assets = frappe.get_all("Rental Asset", filters={"status": "Available"}, pluck="name")
    return [{"route": f"rentals/{a}", "lastmod": frappe.utils.now()} for a in assets]
```

**Acceptance Criteria**:
- [ ] `curl /sitemap.xml` returns a valid XML sitemap
- [ ] `/rentals` is listed in the sitemap
- [ ] At least one asset detail page (`/rentals/{name}`) is listed
- [ ] Portal pages (`/my-rentals`, `/my-invoices`) are NOT in the sitemap
- [ ] Sitemap URL in `robots.txt` resolves correctly

---

## 9. Web — Asset Detail Page

### 9.1 Controller `www/rentals/{asset}.py`

> **Requires**: 2.1 (Rental Asset schema), D01-7.3 (page stub)

The **asset detail page** shows everything about a single asset: full description, image gallery, pricing, location, and the booking CTA. It's also SSR-rendered with **Open Graph meta tags** (`og:title`, `og:description`, `og:image`) for social media sharing — when someone shares a listing on WhatsApp or Facebook, it shows a rich preview. If the asset has a 3D model or 360° photo, the preview embed is rendered inline.

**Acceptance Criteria**:
- [ ] Page renders with asset name, description, images, monthly rate, deposit
- [ ] `og:title`, `og:description`, `og:image` meta tags set for social sharing
- [ ] Non-existent asset name returns 404 (not 500)
- [ ] Preview embed (3D/360°) renders when `custom_preview_mode` is set

---

### 9.2 Availability Calendar (`asset_detail.js`)

> **Requires**: 9.1 (page context), 7.3 (availability API)

An **interactive calendar** embedded in the asset detail page showing which dates are available and which are blocked. Blocked dates are visually styled (grayed out, non-clickable) but no reason is disclosed for privacy. The calendar fetches data month-by-month as the user navigates forward/backward, keeping the initial page load lightweight.

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

A Riverpod provider that fetches available assets from the API. It accepts an `AssetFilter` parameter (type, location, price) and re-fetches when filters change. The provider uses `keepAlive: true` so catalog data survives navigation (going to asset detail and back doesn't re-fetch the catalog).

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

The main **catalog screen** in the Flutter app. Each asset is displayed as an `AssetCardWidget` showing the cover image, name, monthly price, and location. The list uses **infinite scroll** — when the user reaches the bottom, the next page loads automatically. A shimmer skeleton shows during initial loading, and an empty state appears when no assets match the current filters.

**Acceptance Criteria**:
- [ ] Grid of `AssetCardWidget` with cover image, name, price, location
- [ ] Infinite scroll loads next page when reaching bottom
- [ ] Shimmer loading skeleton shown during fetch
- [ ] Empty state shown when no assets match filter

---

### 10.3 Filter Sheet

> **Requires**: 10.2 (catalog screen)

A **bottom sheet** that opens from the catalog screen, providing filter controls: asset type tabs (All / Flat / Vehicle), a text input for location, and a slider for maximum price. Applying filters dismisses the sheet and refreshes the catalog grid. A "Clear Filters" button resets everything to defaults.

**Acceptance Criteria**:
- [ ] Bottom sheet with type tabs (All / Flat / Vehicle), location input, max price slider
- [ ] Applying filters refreshes the catalog grid
- [ ] "Clear Filters" resets all to default

---

### 10.4 Asset Detail Screen

> **Requires**: D01-8.6 (FrappeClient), 7.2 (asset detail API), D01-8.3 (screen stub)

The Flutter equivalent of the web asset detail page (9.1). Displays all asset information with a **swipeable image carousel**, full description, pricing, and CTA buttons. If the asset has a 3D/360° preview configured, a "Preview" button is shown.

**Acceptance Criteria**:
- [ ] Displays all asset info: name, description, images, rate, deposit
- [ ] Image gallery is swipeable (carousel)
- [ ] Preview button shown when `custom_preview_mode != None`

---

### 10.5 Availability Calendar Widget

> **Requires**: 10.4 (detail screen), 7.3 (availability API)

A **reusable calendar widget** that renders inside the asset detail screen. It uses `table_calendar` to show a month view where blocked dates are visually distinct and non-tappable. Month navigation triggers a provider invalidation to fetch fresh availability data. The widget handles loading and error states gracefully.

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

Two widgets added to the Flutter **home screen**: (1) `FeaturedAssetsCarousel` — a horizontally scrollable row of operator-promoted assets, and (2) `ActiveRentalSummaryCard` — showing the logged-in customer's next invoice amount and due date. Both sections **hide themselves** when there's no data (no featured assets = hidden carousel, no active rental = hidden card), keeping the home screen clean.

**Acceptance Criteria**:
- [ ] `FeaturedAssetsCarousel` shows horizontal scroll of featured assets
- [ ] `ActiveRentalSummaryCard` shows next invoice amount + due date
- [ ] No featured assets → section hidden (not empty carousel)
- [ ] No active rentals → summary card hidden

---

### 10.7 Variant-Aware Card Widget (Flutter)

> **Requires**: 10.2 (base card widget), D01-2.4 (extension hook architecture)

The Flutter counterpart to the web's variant-aware card rendering (8.3). The `AssetCardWidget` renders common fields (image, name, price, location) and a **dynamic attribute row** below them. The attribute data comes from the same `variant_attributes` field in the API response — a list of `{label, value}` maps.

The widget renders attributes as a horizontal `Wrap` of `Chip`-style labels (e.g., "🛏 3 Beds" · "📐 120 sqm" for flats, "⚙️ Automatic" · "💺 5 Seats" for vehicles). If the list is empty, the attribute row is hidden entirely.

Child apps provide the attributes server-side — the Flutter app never checks `asset_type` to decide what to show. This keeps the base app free of variant-specific UI logic.

```dart
class AssetAttributeRow extends StatelessWidget {
  final List<Map<String, String>> attributes;
  @override
  Widget build(BuildContext context) {
    if (attributes.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: 8, runSpacing: 4,
      children: attributes.map((a) => Chip(
        label: Text('${a["label"]}: ${a["value"]}'),
        visualDensity: VisualDensity.compact,
      )).toList(),
    );
  }
}
```

**Acceptance Criteria**:
- [ ] Flat assets show bedroom, bathroom, area chips in the card
- [ ] Vehicle assets show make, model, seats, transmission chips in the card
- [ ] Zero attributes → attribute row is hidden (not an empty Wrap)
- [ ] Base Flutter code does NOT import or reference child app packages
- [ ] Chip row wraps gracefully on narrow screens

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
