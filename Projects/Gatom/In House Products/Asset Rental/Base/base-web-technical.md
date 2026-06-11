# Base — Web: Technical Document

> **Product**: Asset Rental Platform
> **Module**: Customer-Facing Website (Base Layer)
> **Document Type**: Technical
> **Audience**: Frontend developers (Jinja2, JS, CSS)
> **Companion**: [[../Base Overview|Base Platform Overview]]

---

## 1. Technology Decisions

| Choice | Rationale |
|---|---|
| Frappe Web (not React/Vue) | Shared auth session, same domain, SSR for SEO, one codebase |
| Jinja2 templates | Native Frappe, direct Python context, no build step |
| Bootstrap 5 | Provided by Frappe web layer; responsive grid out of the box |
| Vanilla JS | No framework overhead; `frappe.call()` handles AJAX |
| CSS custom properties | Client-overridable design tokens via Site Settings |

---

## 2. File Structure

```
rental_core/
├── www/
│   ├── rentals.html / .py            # Combined catalog (all asset types)
│   ├── rentals/
│   │   ├── {asset}.html / .py        # Asset detail (dynamic slug)
│   │   └── {asset}/
│   │       └── book.html / .py       # Booking form
│   ├── my-rentals.html / .py
│   ├── my-invoices.html / .py
│   ├── my-documents.html / .py
│   ├── guarantor-portal.html / .py   # Guarantor-only: view balance + pay
│   ├── pay.html / .py
│   └── rental-signup.html / .py
├── templates/
│   └── includes/
│       ├── asset_card.html
│       ├── catalog_filters.html
│       ├── availability_calendar.html
│       ├── booking_steps.html
│       ├── signature_pad.html
│       └── portal_header.html
├── public/
│   ├── css/
│   │   ├── rental_web.css
│   │   └── rental_rtl.css
│   └── js/
│       ├── catalog.js
│       ├── asset_detail.js
│       ├── booking.js
│       ├── signature_pad.js
│       └── portal.js
└── hooks.py                          # Portal menu + route rules (see Frappe Technical § 4)
```

---

## 3. Design System (`rental_web.css`)

```css
:root {
  --rental-primary:      #2563EB;
  --rental-primary-dark: #1D4ED8;
  --rental-accent:       #F59E0B;
  --rental-bg:           #F8FAFC;
  --rental-surface:      #FFFFFF;
  --rental-text:         #0F172A;
  --rental-muted:        #64748B;
  --rental-border:       #E2E8F0;
  --rental-radius:       12px;
  --rental-shadow:       0 4px 24px rgba(0,0,0,.08);
  --rental-font:         'Inter', system-ui, sans-serif;
}
/* Asset card hover lift */
.rental-card:hover { transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,.14); }
/* Availability calendar day classes: --available, --blocked, --past, --selected */
/* Booking step indicator: .active (primary) / .done (green) */
```

---

## 4. Catalog Page

### Controller `www/rentals.py`

> [!NOTE]
> The catalog controller delegates all filtering to the **shared `AssetCatalogQuery` service** (`rental_core.catalog.asset_catalog_query`). This ensures the SSR controller and the REST API use identical filter logic.

```python
from rental_core.catalog.asset_catalog_query import query_available_assets

def get_context(context):
    context.no_cache = 1
    asset_type = frappe.form_dict.get("type", "")
    max_price  = frappe.form_dict.get("max_price", "")
    location   = frappe.form_dict.get("location", "")

    result = query_available_assets(
        asset_type=asset_type,
        location=location,
        max_price=float(max_price) if max_price else None,
        page=1,
        page_size=24,
    )

    context.assets = result["assets"]
    context.total = result["total"]
    context.title = "Browse Rentals"
    context.asset_type_filter = asset_type
```

### AJAX Filter (`catalog.js`)

> [!IMPORTANT]
> **CSRF Requirement**: All AJAX calls MUST use `frappe.call()`, which automatically includes the `X-Frappe-CSRF-Token` header. Direct `fetch()` or `XMLHttpRequest` calls to `/api/method/` without this token will be rejected with HTTP 403.

```javascript
function loadAssets(filters = {}, page = 1) {
  document.getElementById('catalog-loading').style.display = 'block';
  frappe.call({
    method: 'rental_core.api.assets.get_available_assets',
    args: { ...filters, page, page_size: 12 },
    callback(r) {
      renderCards(r.message.assets);
      renderPagination(r.message.total, page, r.message.page_size, r.message.has_next);
      document.getElementById('catalog-loading').style.display = 'none';
    },
  });
}
// Event delegation: filter changes + type tab clicks → loadAssets(collectFilters())
```

---

## 5. Asset Detail Page

### Controller `www/rentals/{asset}.py`

```python
def get_context(context):
    asset = frappe.get_doc("Rental Asset", context.get('asset'))
    context.asset = asset
    context.images = asset.get("images", [])
    context.has_3d_preview = asset.get("custom_preview_mode") not in (None, "None", "")
    context.is_logged_in   = frappe.session.user != "Guest"
    context.metatags = {
        "title": asset.asset_name,
        "description": (asset.description or "")[:160],
        "image": get_url(context.images[0].image) if context.images else "",
        "og:type": "product",
    }
```

### Availability Calendar (`asset_detail.js`)

```javascript
async function loadAvailability(year, month) {
  const r = await frappe.call({
    method: 'rental_core.api.assets.get_asset_availability',
    args: { asset_name: window.ASSET_NAME, year, month },
  });
  renderCalendar(year, month, r.message.unavailable);
  // Blocked ranges → CSS class --blocked; no reason shown
}
```

---

## 6. Booking Form (5-Step)

### Controller `www/rentals/{asset}/book.py`

```python
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = f"/login?redirect-to=/rentals/{context.asset}/book"
        raise frappe.Redirect
    context.asset = frappe.get_doc("Rental Asset", context.get('asset'))
    customer_name = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    context.customer = frappe.get_doc("Customer", customer_name) if customer_name else None
    config = frappe.get_single("Rental Configuration")
    context.kyc_id_types = config.get("kyc_id_types", [])
```

### Step Validation Pattern (`booking.js`)

```javascript
const STEPS = ['dates', 'details', 'kyc', 'sign', 'confirm'];
let currentStep = 0;

document.getElementById('btn-next').addEventListener('click', () => {
  if (!validateStep(currentStep)) return;
  document.querySelectorAll('.booking-panel')[currentStep].classList.add('d-none');
  currentStep++;
  document.querySelectorAll('.booking-panel')[currentStep].classList.remove('d-none');
  updateStepIndicator(currentStep);
});
```

### Submission API Call

```javascript
document.getElementById('booking-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const r = await frappe.call({
    method: 'rental_core.api.bookings.submit_booking_request',
    args: collectFormData(),
  });
  if (r.message.payment_url) window.location = r.message.payment_url;
  else window.location = '/my-rentals';
});
```

---

## 7. Customer Portal Pages

### `www/my-rentals.py`

```python
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/my-rentals"
        raise frappe.Redirect
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    context.active_agreements = frappe.get_all("Rental Agreement",
        filters={"customer": customer, "status": ["in", ["Active", "Draft"]]},
        fields=["name", "asset", "start_date", "end_date", "monthly_rate", "status"])
    context.past_agreements = frappe.get_all("Rental Agreement",
        filters={"customer": customer, "status": ["in", ["Expired", "Terminated"]]},
        fields=["name", "asset", "start_date", "end_date", "status"],
        limit=10, order_by="end_date desc")
```

### `www/guarantor-portal.py`

> [!NOTE]
> The Guarantor portal is a restricted view where guarantors can see the outstanding balance on agreements they guarantee and optionally make a payment.

```python
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/guarantor-portal"
        raise frappe.Redirect

    # Find agreements where this user is listed as guarantor
    context.guaranteed_agreements = frappe.get_all("Rental Agreement",
        filters={
            "custom_guarantor_email": frappe.session.user,
            "status": ["in", ["Active"]],
        },
        fields=["name", "customer", "start_date", "monthly_rate", "status"])

    # For each agreement, fetch overdue invoices
    for agr in context.guaranteed_agreements:
        agr.overdue_invoices = frappe.get_all("Sales Invoice",
            filters={
                "custom_rental_agreement": agr.name,
                "status": ["in", ["Unpaid", "Overdue"]],
            },
            fields=["name", "grand_total", "due_date", "outstanding_amount"],
            order_by="due_date asc")
        agr.total_outstanding = sum(inv.outstanding_amount for inv in agr.overdue_invoices)

    context.title = "Guarantor Portal"
```

**Template**: Shows a card per guaranteed agreement with outstanding balance, overdue invoice list, and a "Pay Now" button that redirects to `/pay/{invoice_name}`.

**Access**: The Guarantor does **not** see variant-specific details (flat utilities, vehicle mileage), tenant personal information, or deposit ledger. Only invoice amounts and due dates.

Portal sidebar registration (in `hooks.py` — see Frappe Technical § 4):

```python
portal_menu_items = [
    # ... existing Customer items ...
    {"title": "Guarantor Portal", "route": "/guarantor-portal", "role": "Guarantor"},
]
```

---

## 8. RTL Support

```css
/* rental_rtl.css — loaded only for RTL locales */
[dir="rtl"] .booking-steps      { flex-direction: row-reverse; }
[dir="rtl"] .catalog-filters    { border-right: none; border-left: 1px solid var(--rental-border); }
[dir="rtl"] .breadcrumb-item + .breadcrumb-item::before { content: "\\"; }
```

Conditional load in base template:
```html
{% if frappe.lang in ("ar", "fa", "ur", "he") %}
<link rel="stylesheet" href="/assets/rental_core/css/rental_rtl.css">
{% endif %}
```

---

## 9. `robots.txt`

```
User-agent: *
Allow: /rentals/
Disallow: /my-rentals
Disallow: /my-invoices
Disallow: /my-documents
Disallow: /guarantor-portal
Disallow: /pay/
Disallow: /app/
Sitemap: https://CLIENT_DOMAIN/sitemap.xml
```

---

## 10. Security Requirements

> [!IMPORTANT]
> These requirements apply to all web pages and AJAX calls.

| Requirement | Implementation |
|---|---|
| **CSRF protection** | All form submissions and AJAX calls MUST use `frappe.call()` which auto-includes `X-Frappe-CSRF-Token`. Direct `fetch()` to `/api/method/` without the token is rejected with 403. |
| **Guest redirect** | All portal pages (`/my-*`, `/guarantor-portal`, `/pay/`, `/book`) check `frappe.session.user != "Guest"` and redirect to `/login?redirect-to=...` |
| **Customer isolation** | All portal queries filter by `frappe.session.user` — no cross-customer data access |
| **Guarantor isolation** | Guarantor portal filters by `custom_guarantor_email` — guarantors only see overdue invoice amounts, not tenant details or variant-specific data |
| **TLS enforcement** | All pages must be served over HTTPS. HTTP requests must redirect to HTTPS via server config. |
| **Input sanitization** | Location filter input is sanitized (SQL wildcard stripping) in the shared `AssetCatalogQuery` service |

---

## 11. Testing Checklist

- [ ] `curl` the catalog URL — response must contain asset cards (SSR)
- [ ] Changing a filter updates grid without page reload
- [ ] Pagination metadata (`total`, `has_next`) renders correctly
- [ ] Blocked dates shown on calendar without reason
- [ ] Guest visiting `/book` is redirected to `/login?redirect-to=...`
- [ ] After login, user is returned to `/book` page
- [ ] Portal pages return 302 redirect to login for guest access
- [ ] `og:image` and `<meta description>` are present and unique per asset
- [ ] `robots.txt` disallows `/my-*`, `/guarantor-portal`, and `/pay/`
- [ ] RTL layout renders for Arabic language users (html dir="rtl")
- [ ] All user-facing strings are wrapped in `_()` / `__()`
- [ ] Guarantor portal shows only overdue invoices for guaranteed agreements
- [ ] Guarantor cannot see tenant personal details or variant-specific data
- [ ] CSRF token is present on all `frappe.call()` requests (verify with browser devtools)
- [ ] Location filter with `%` or `_` characters does not cause unexpected SQL behavior
