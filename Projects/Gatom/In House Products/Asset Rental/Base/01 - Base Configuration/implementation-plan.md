# Domain 01 — Base Configuration: Implementation Plan

> **Variant**: Base
> **Domain**: Base Configuration
> **Sequence**: 1 of 8 — **Implement this first**
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

System-level configuration, user roles, license enforcement, and multi-region settings. This domain is the **foundation** — every other domain reads from `Rental Configuration`. Also includes the full app scaffold, directory layout, hooks.py, design system, and Flutter project setup.

---

## 2. Frappe — App Scaffold & Directory Layout

### 2.1 Create the App

> **Requires**: Nothing — first task in the project.

```bash
bench new-app rental_core
# App name: rental_core | Title: Rental Core | Publisher: Your Org
bench --site rental.localhost install-app rental_core
```

**Acceptance Criteria**:
- [ ] `bench new-app rental_core` creates the app directory under `apps/`
- [ ] `bench --site rental.localhost install-app rental_core` installs without errors
- [ ] `bench start` launches with no import errors from `rental_core`

---

### 2.2 Directory Structure

> **Requires**: 2.1

> [!NOTE]
> All modules use **domain-specific names** — no generic `utils/`, `helpers/`, or `shared/` directories.

```
rental_core/
├── rental_core/
│   ├── doctype/
│   │   ├── rental_asset/
│   │   │   ├── rental_asset.json
│   │   │   ├── rental_asset.py
│   │   │   └── asset_image.json          ← child table
│   │   ├── rental_agreement/
│   │   │   ├── rental_agreement.json
│   │   │   ├── rental_agreement.py
│   │   │   └── additional_charge.json    ← child table
│   │   ├── rental_lead/
│   │   │   ├── rental_lead.json
│   │   │   └── rental_lead.py
│   │   ├── rental_quotation/
│   │   │   ├── rental_quotation.json
│   │   │   └── rental_quotation.py
│   │   ├── deposit_ledger/
│   │   │   ├── deposit_ledger.json
│   │   │   └── deposit_deduction.json    ← child table
│   │   ├── asset_inspection/
│   │   │   └── inspection_photo.json     ← child table
│   │   ├── rental_notification_log/
│   │   ├── payment_webhook_log/
│   │   │   └── payment_webhook_log.json
│   │   └── rental_configuration/
│   │       └── kyc_id_type.json          ← child table
│   ├── api/
│   │   ├── assets.py
│   │   ├── agreements.py
│   │   ├── payments.py
│   │   ├── webhooks.py
│   │   ├── leads.py
│   │   ├── kyc.py
│   │   └── notifications.py
│   ├── billing/
│   │   ├── subscription_factory.py
│   │   └── late_fee_engine.py
│   ├── payment_routing/
│   │   ├── gateway_router.py
│   │   └── webhook_handler.py
│   ├── notification_pipeline/
│   │   ├── reminder_dispatcher.py
│   │   └── escalation_engine.py
│   ├── licensing/
│   │   └── license_validator.py
│   ├── catalog/
│   │   └── asset_catalog_query.py
│   ├── gateways/
│   │   ├── stripe_gateway.py
│   │   ├── tap_gateway.py
│   │   ├── paymob_gateway.py
│   │   ├── manual_gateway.py
│   │   ├── sms.py
│   │   └── fcm.py
│   ├── templates/
│   │   └── emails/
│   │       └── rental_reminder.html
│   ├── scheduler_events.py
│   ├── hooks.py
│   └── setup.py
├── pyproject.toml
└── README.md
```

**Acceptance Criteria**:
- [ ] Every directory listed above exists in the file system
- [ ] Every `.py` file contains a valid Python module stub (at minimum `pass` or a docstring)
- [ ] Every `.json` DocType file contains a valid empty JSON scaffold (`{"doctype": "DocType", ...}`)
- [ ] `bench start` still runs without import errors after directory creation

---

### 2.3 `hooks.py`

> **Requires**: 2.2 (all referenced modules must exist as stubs)

```python
app_name = "rental_core"
required_apps = ["frappe", "erpnext"]

scheduler_events = {
    "daily": [
        "rental_core.scheduler_events.send_payment_reminders",
        "rental_core.scheduler_events.check_contract_renewals",
        "rental_core.scheduler_events.auto_apply_late_fees",
        "rental_core.scheduler_events.expire_stale_quotations",
        "rental_core.scheduler_events.expire_unreviewed_bookings",
        "rental_core.scheduler_events.auto_commit_deposit_deductions",
        "rental_core.scheduler_events.run_overdue_escalation",
    ],
    "cron": {
        "every 5 minutes": [
            "rental_core.scheduler_events.expire_unreviewed_bookings",
        ],
    },
    "monthly": [
        "rental_core.scheduler_events.generate_monthly_report",
        "rental_core.scheduler_events.purge_old_webhook_logs",
    ],
}

on_session_creation = "rental_core.licensing.license_validator.validate_license"

doc_events = {
    "Subscription": {"on_submit": "rental_core.billing.subscription_factory.on_subscription_submit"},
    "Sales Invoice": {"on_submit": "rental_core.billing.subscription_factory.on_invoice_submit"},
    "Payment Entry": {"on_submit": "rental_core.billing.subscription_factory.on_payment_submit"},
}

portal_menu_items = [
    {"title": "My Rentals",   "route": "/my-rentals",   "role": "Customer"},
    {"title": "My Invoices",  "route": "/my-invoices",  "role": "Customer"},
    {"title": "My Documents", "route": "/my-documents", "role": "Customer"},
    {"title": "My KYC",       "route": "/my-kyc",       "role": "Customer"},
    {"title": "Guarantor Portal", "route": "/guarantor-portal", "role": "Guarantor"},
]

website_route_rules = [
    {"from_route": "/rentals/<asset>",      "to_route": "rentals/{asset}"},
    {"from_route": "/rentals/<asset>/book", "to_route": "rentals/{asset}/book"},
]
```

**Acceptance Criteria**:
- [ ] `bench start` resolves all `scheduler_events` dotted paths without `ImportError`
- [ ] `on_session_creation` hook fires on user login
- [ ] `doc_events` hooks are registered — `bench console` → `frappe.get_hooks("doc_events")` returns entries for `Subscription`, `Sales Invoice`, `Payment Entry`
- [ ] Portal menu shows "My Rentals", "My Invoices", "My Documents", "My KYC" for Customer role
- [ ] Portal menu shows "Guarantor Portal" for Guarantor role
- [ ] Route `/rentals/<asset>` resolves to the correct template

---

### 2.4 Child App Extension Pattern

> **Requires**: 2.3 (hooks.py must define `doc_events` structure)

> [!IMPORTANT]
> `rental_core` has **zero imports** from child apps (`rental_flats`, `rental_vehicles`). All extension points use Frappe's native `doc_events` hook system.

| Hook | Fired When | Purpose |
|---|---|---|
| `Rental Agreement.validate` | Agreement is being validated | Child app adds variant-specific checks |
| `Rental Agreement.on_invoice_created` | New subscription invoice generated | Child app injects variant-specific line items |
| `Rental Asset.before_save` | Asset is saved | Child app can enrich custom fields |

Example — `rental_flats/hooks.py`:
```python
doc_events = {
    "Rental Agreement": {
        "validate": "rental_flats.validation.insurance_gate.check_mandatory_coverage",
        "on_invoice_created": "rental_flats.billing.utility_injector.attach_unbilled_utilities",
    }
}
```

**Acceptance Criteria**:
- [ ] `grep -r "import rental_flats" rental_core/` returns zero results
- [ ] `grep -r "import rental_vehicles" rental_core/` returns zero results
- [ ] When `rental_flats` is installed, its `doc_events` fire on `Rental Agreement.validate`
- [ ] When no child app is installed, `Rental Agreement.validate` still works without error
- [ ] `Rental Asset.before_save` hook point exists and is callable by child apps

---

## 3. Frappe — `Rental Configuration` Singleton Schema

### 3.1 Full Schema

> **Requires**: 2.2 (DocType directory `rental_configuration/` must exist)

| Field | Type | Default | Source |
|---|---|---|---|
| `country` | Link → Country | | |
| `default_currency` | Link → Currency | | CFG-002 |
| `tax_template` | Link → Sales Taxes and Charges Template | | |
| `payment_gateway` | Select: Stripe, Tap, PayMob, Bank Transfer | | |
| `payment_gateway_api_key` | Password | | |
| `payment_gateway_secret` | Password | | |
| `kyc_id_types` | Table → `KYC ID Type` | | BR-011 |
| `contract_language` | Select | | |
| `grace_period_days` | Int | 5 | BR-053 |
| `late_fee_type` | Select: Fixed, Percentage | | |
| `late_fee_value` | Float | | |
| `renewal_alert_days` | Data | "90,60,30" | BR-072 |
| `electricity_rate_per_unit` | Currency | | |
| `water_rate_per_unit` | Currency | | |
| `gas_rate_per_unit` | Currency | | |
| `aws_access_key` / `aws_secret_key` | Password | | |
| `aws_region` / `s3_media_bucket` / `cdn_base_url` | Data | | |
| `license_key` | Data | | |
| `business_contact_email` | Data | | CFG-004 |
| `business_contact_phone` | Data | | CFG-004 |
| `draft_expiry_hours` | Int | 48 | BR-026 |
| `deposit_dispute_window_days` | Int | 5 | BR-065 |
| `rent_escalation_cap_pct` | Float | | BR-043 |
| `open_ended_notice_days` | Int | 30 | BR-031a |
| `self_cancel_limit` | Int | 3 | BR-080a |
| `webhook_log_retention_months` | Int | 13 | BR-056a |
| `license_grace_period_days` | Int | 7 | CFG-010 |
| `date_display_format` | Select: Gregorian, Hijri | Gregorian | §5 |
| `flat_inspection_reminder_months` | Int | 11 | §5 |
| `b2b_invoice_template` | Link → Print Format | | CFG-003 |
| `b2c_invoice_template` | Link → Print Format | | CFG-003 |
| `default_lead_assignee` | Link → User | | BR-005 |
| `kyc_s3_bucket` | Data | | BR-012 |
| `kyc_s3_region` | Data | | BR-012 |
| `whatsapp_enabled` | Check | 0 | BR-073 |
| `whatsapp_provider` | Select: Twilio, WhatsApp Business | | |
| `whatsapp_api_key` | Password | | |
| `esignature_advisory_shown` | Check | 0 | BR-033 |

> [!IMPORTANT]
> **Secret field access control**: All `Password` fields must be restricted to the `Administrator` role only.

**Acceptance Criteria**:
- [ ] `Rental Configuration` is accessible in Frappe Desk as a Settings page (singleton)
- [ ] `frappe.get_single("Rental Configuration")` returns the singleton
- [ ] All fields listed above exist with correct types
- [ ] `grace_period_days` defaults to 5 when not explicitly set
- [ ] `draft_expiry_hours` defaults to 48 when not explicitly set
- [ ] `Password` fields are hidden from all roles except Administrator
- [ ] Saving with an invalid `Link → Currency` raises a validation error
- [ ] `KYC ID Type` child table allows add/remove/reorder of rows
- [ ] `b2b_invoice_template` and `b2c_invoice_template` links resolve to valid Print Formats
- [ ] `renewal_alert_days` accepts comma-separated string (e.g., "90,60,30")

---

## 4. Frappe — License Enforcement

### 4.1 License Validator (`licensing/license_validator.py`)

> **Requires**: 3.1 (reads `license_key`, `license_grace_period_days` from Rental Configuration)

```python
def validate_license(login_manager=None):
    lic = frappe.get_single("Rental Configuration")
    if is_locally_expired(lic.license_key):
        grace_days = lic.license_grace_period_days or 7
        expiry_date = get_expiry_date(lic.license_key)
        grace_end = add_days(expiry_date, grace_days)
        if today() > grace_end:
            frappe.local.flags.redirect_location = "/suspended"
            raise frappe.Redirect
    if needs_remote_check():
        validate_remote(lic.license_key)
```

**Acceptance Criteria**:
- [ ] Valid license key → login proceeds normally, no redirect
- [ ] Expired license within grace period → login proceeds, `is_in_grace_mode()` returns `True`
- [ ] Expired license past grace → login redirects to `/suspended`
- [ ] Remote validation fires at most once per 24h (not on every login)
- [ ] Network failure during remote check → offline tolerance of 7 days before hard block
- [ ] `validate_license` runs on every `on_session_creation` event

---

### 4.2 Grace Mode Webhook Branching

> **Requires**: 4.1 (`is_in_grace_mode()` function must exist)

In `payment_routing/webhook_handler.py`, at the top of `payment_webhook()`:
```python
if is_in_grace_mode():
    log = create_webhook_log(gateway, event_id, payload, processed=0)
    return {"status": "ok", "grace_mode": True}
```

**Acceptance Criteria**:
- [ ] During grace mode: inbound webhook returns `{"status": "ok", "grace_mode": true}`
- [ ] During grace mode: webhook payload is stored in `Payment Webhook Log` with `processed=0`
- [ ] Outside grace mode: webhooks are processed normally (grace branching is skipped)
- [ ] Webhook log entry during grace mode has `gateway` and `event_id` populated

---

### 4.3 Post-Renewal Reconciliation Job

> **Requires**: 4.2 (grace mode must have created unprocessed webhook logs to reconcile)

```python
def reconcile_grace_period_webhooks():
    unprocessed = frappe.get_all("Payment Webhook Log",
        filters={"processed": 0, "gateway": ["!=", ""]},
        fields=["name", "gateway", "payload", "event_id"])
    for log in unprocessed:
        frappe.enqueue(
            "rental_core.payment_routing.webhook_handler.process_single_webhook",
            log_name=log.name, queue="default"
        )
```

**Acceptance Criteria**:
- [ ] After license renewal, calling `reconcile_grace_period_webhooks()` enqueues all unprocessed logs
- [ ] Each unprocessed webhook is submitted to `process_single_webhook` via background queue
- [ ] After reconciliation, `Payment Webhook Log` entries that succeed have `processed=1`
- [ ] Webhooks that fail during reconciliation remain `processed=0` with `processing_error` set

---

### 4.4 Suspended Portal Template

> **Requires**: 3.1 (reads `business_contact_email`, `business_contact_phone` from config)

New file `www/suspended.html`:
```html
{% extends "templates/web.html" %}
{% block page_content %}
<div class="text-center py-5">
    <h2>{{ _("Service Suspended") }}</h2>
    <p>{{ _("Your rental platform license has expired. Please contact support.") }}</p>
    {% if config.business_contact_email %}
    <p>{{ config.business_contact_email }} · {{ config.business_contact_phone }}</p>
    {% endif %}
</div>
{% endblock %}
```

**Acceptance Criteria**:
- [ ] `/suspended` renders the template without error
- [ ] When `business_contact_email` is configured, it displays on the page
- [ ] When `business_contact_email` is empty, only the generic message is shown (no empty `<p>`)
- [ ] Page text is wrapped in `_()` for translation support
- [ ] All portal routes redirect here when license is expired past grace

---

## 5. Frappe — Role Permission Matrix

### 5.1 Role Creation (`setup.py` → `setup_roles()`)

> **Requires**: 2.2 (`setup.py` stub must exist)

**Acceptance Criteria**:
- [ ] `setup_roles()` creates four custom roles: `Rental Manager`, `Rental Agent`, `Accountant (Rental)`, `Customer`
- [ ] Roles persist across `bench migrate` — they are not deleted on re-run
- [ ] Each role has a descriptive `role_name` (not code-only)

---

### 5.2 Permission Rules

> **Requires**: 5.1 (roles must exist), 3.1 (Rental Configuration DocType must exist)

| DocType | System Manager | Rental Manager | Rental Agent | Accountant | Customer |
|---|---|---|---|---|---|
| Rental Configuration | RW | R | — | — | — |
| Rental Asset | RW | RW | R | R | R (portal) |
| Rental Lead | RW | RW | RW | — | — |
| Rental Quotation | RW | RW | RW | — | — |
| Rental Agreement | RW | RW | RC | R | R (own) |
| Deposit Ledger | RW | RW | — | RW | R (own) |
| Asset Inspection | RW | RW | RC | — | — |
| Rental Notification Log | R | R | R | R | — |
| Payment Webhook Log | R | — | — | — | — |
| Customer KYC Submission | RW | RW | RW | — | R (own) |
| Legal Case | RW | RW | — | — | — |

**Acceptance Criteria**:
- [ ] Customer role can read only their own `Rental Agreement` records (filter by `frappe.session.user`)
- [ ] Customer role can read only their own `Deposit Ledger` records
- [ ] Accountant cannot access `Rental Lead` or `Rental Quotation` (returns `frappe.PermissionError`)
- [ ] Rental Agent can create (`C`) but not update Rental Agreement after submission
- [ ] System Manager has full read-write on all listed DocTypes
- [ ] Payment Webhook Log is read-only for System Manager (no write/delete)
- [ ] A user with no rental role gets `frappe.PermissionError` on all rental DocTypes

---

## 6. Frappe — API Error Contract

### 6.1 Error Envelope Standard

> **Requires**: 2.2 (API stub files in `api/` must exist)

**HTTP Status Codes**: `200` Success · `400` Validation · `401` Unauthenticated · `403` Forbidden · `404` Not Found · `409` Conflict · `429` Rate Limited

**Error Response Body**:
```json
{
  "message": null,
  "exc_type": "ValidationError",
  "errors": [
    {"field": "start_date", "message": "Start date must be in the future"}
  ],
  "_server_messages": ["[\"Asset is no longer available\"]"]
}
```

**Acceptance Criteria**:
- [ ] Validation errors return HTTP 400 with `exc_type: "ValidationError"` and per-field `errors[]`
- [ ] Authentication failures return HTTP 401
- [ ] Permission errors return HTTP 403
- [ ] Conflict (e.g., double-booking race) returns HTTP 409
- [ ] Rate-limited calls return HTTP 429 with `Retry-After` header
- [ ] Missing resources return HTTP 404
- [ ] All API endpoints produce errors matching this structure (no raw exception tracebacks to client)

---

### 6.2 Pagination Standard

> **Requires**: 6.1

**Pagination Response** (all list endpoints):
```json
{
  "assets": [ ... ],
  "total": 142,
  "page": 2,
  "page_size": 12,
  "has_next": true
}
```

**Acceptance Criteria**:
- [ ] All list endpoints include `total`, `page`, `page_size`, `has_next` in response
- [ ] `page=1` with `page_size=12` returns at most 12 items
- [ ] `has_next=false` when `(page * page_size) >= total`
- [ ] `page=0` or negative values return HTTP 400
- [ ] `page_size` capped at 100 to prevent abuse

---

## 7. Web — Design System & Localisation

### 7.1 CSS Design System (`rental_web.css`)

> **Requires**: 2.2 (`public/css/` directory must exist)

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
.rental-card:hover { transform: translateY(-4px); box-shadow: 0 12px 40px rgba(0,0,0,.14); }
```

**Acceptance Criteria**:
- [ ] `rental_web.css` is served at `/assets/rental_core/css/rental_web.css`
- [ ] All CSS variables listed above are defined in `:root`
- [ ] `.rental-card:hover` applies the transform and shadow transition
- [ ] Stylesheet loads on all `www/` portal pages
- [ ] No browser console errors about missing font or undefined variables

---

### 7.2 RTL Support (`rental_rtl.css`)

> **Requires**: 7.1 (base stylesheet must exist)

```css
[dir="rtl"] .booking-steps      { flex-direction: row-reverse; }
[dir="rtl"] .catalog-filters    { border-right: none; border-left: 1px solid var(--rental-border); }
```

Conditional load:
```html
{% if frappe.lang in ("ar", "fa", "ur", "he") %}
<link rel="stylesheet" href="/assets/rental_core/css/rental_rtl.css">
{% endif %}
```

**Acceptance Criteria**:
- [ ] RTL stylesheet loads only when `frappe.lang` is `ar`, `fa`, `ur`, or `he`
- [ ] RTL stylesheet does NOT load for `en`, `fr`, `de`, or any LTR language
- [ ] Booking steps reverse direction in RTL mode
- [ ] Catalog filter border flips to left side in RTL mode

---

### 7.3 Web File Structure (Stubs)

> **Requires**: 2.2 (`www/`, `templates/`, `public/` directories must exist)

```
rental_core/
├── www/
│   ├── rentals.html / .py
│   ├── rentals/{asset}.html / .py
│   ├── rentals/{asset}/book.html / .py
│   ├── my-rentals.html / .py
│   ├── my-invoices.html / .py
│   ├── my-documents.html / .py
│   ├── my-kyc.html / .py
│   ├── guarantor-portal.html / .py
│   ├── pay.html / .py
│   ├── rental-signup.html / .py
│   └── suspended.html
├── templates/includes/
│   ├── asset_card.html
│   ├── catalog_filters.html
│   ├── availability_calendar.html
│   ├── booking_steps.html
│   ├── signature_pad.html
│   └── portal_header.html
├── public/js/
│   ├── catalog.js
│   ├── asset_detail.js
│   ├── booking.js
│   ├── signature_pad.js
│   └── portal.js
```

**Acceptance Criteria**:
- [ ] Every file above exists as a stub (HTML: empty block template; Python: `get_context` returning `{}`)
- [ ] Navigating to `/rentals` renders the stub page without 404 or 500
- [ ] Navigating to `/my-rentals` as Guest redirects to `/login?redirect-to=/my-rentals`
- [ ] All JS stub files contain no syntax errors

---

### 7.4 `robots.txt`

> **Requires**: 7.3 (portal routes must exist)

```
User-agent: *
Allow: /rentals/
Disallow: /my-rentals
Disallow: /my-invoices
Disallow: /my-documents
Disallow: /my-kyc
Disallow: /guarantor-portal
Disallow: /pay/
Disallow: /app/
Sitemap: https://CLIENT_DOMAIN/sitemap.xml
```

**Acceptance Criteria**:
- [ ] `robots.txt` is served at the site root
- [ ] `/rentals/` is allowed for crawling
- [ ] All authenticated portal routes are disallowed
- [ ] `/app/` (Frappe Desk) is disallowed

---

### 7.5 Security Requirements (Web)

> **Requires**: 7.3 (all portal pages must exist for security checks)

| Requirement | Implementation |
|---|---|
| **CSRF protection** | All AJAX calls MUST use `frappe.call()` (auto-includes `X-Frappe-CSRF-Token`). |
| **Guest redirect** | All portal pages check `frappe.session.user != "Guest"` and redirect to `/login?redirect-to=...` |
| **Customer isolation** | All portal queries filter by `frappe.session.user` |
| **TLS enforcement** | HTTPS only. HTTP → HTTPS redirect via server config. |
| **Input sanitization** | Location filter sanitized (SQL wildcard stripping) in `AssetCatalogQuery` |

**Acceptance Criteria**:
- [ ] Direct `fetch()` to API without CSRF token returns HTTP 403
- [ ] `frappe.call()` succeeds (auto-includes `X-Frappe-CSRF-Token`)
- [ ] Guest visiting `/my-rentals` is redirected to `/login?redirect-to=/my-rentals`
- [ ] Customer A cannot see Customer B's agreements (portal query filters by session user)
- [ ] Location filter input `%OR 1=1--` is sanitized (wildcards stripped)

---

## 8. Flutter — Project Setup & Foundation

### 8.1 Create the App

> **Requires**: Nothing (Flutter work starts independently from Frappe)

```bash
flutter create --org com.yourorg --platforms android,ios rental_app
cd rental_app
```

**Acceptance Criteria**:
- [ ] `flutter create` completes without error
- [ ] `flutter run` launches on Android emulator
- [ ] `flutter run` launches on iOS simulator
- [ ] Project compiles for both platforms without warnings

---

### 8.2 `pubspec.yaml` — Key Dependencies

> **Requires**: 8.1

```yaml
dependencies:
  flutter: { sdk: flutter }
  dio: ^5.4.0
  go_router: ^13.0.0
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0
  flutter_secure_storage: ^9.0.0
  firebase_core: ^2.27.0
  firebase_messaging: ^14.7.0
  signature: ^5.3.0
  cached_network_image: ^3.3.0
  intl: ^0.19.0
  flutter_pdfview: ^1.3.2
  webview_flutter: ^4.7.0
  image_picker: ^1.0.7
  table_calendar: ^3.1.1
  shimmer: ^3.0.0
  freezed_annotation: ^2.4.0
  fl_chart: ^0.67.0
  connectivity_plus: ^6.0.0

dev_dependencies:
  build_runner: ^2.4.0
  freezed: ^2.4.0
  riverpod_generator: ^2.3.0
  mocktail: ^1.0.0
```

**Acceptance Criteria**:
- [ ] `flutter pub get` resolves all dependencies without version conflicts
- [ ] `dart run build_runner build` generates code without errors
- [ ] No deprecated dependency warnings for the listed versions

---

### 8.3 Project Structure & Stub Files

> **Requires**: 8.2

```
lib/
├── main.dart
├── app/ (app.dart, config.dart, theme/, router/)
├── core/ (api/, models/, services/, formatting/)
├── features/ (auth/, home/, catalog/, asset_detail/, booking/, kyc/, my_rentals/, payments/, notifications/, profile/)
└── widgets/ (app_button, app_card, status_badge, loading_overlay, offline_banner, suspended_banner, error_view)
```

**Acceptance Criteria**:
- [ ] All directories listed above exist
- [ ] All stub `.dart` files contain valid Dart (at minimum an empty widget or class)
- [ ] `flutter analyze` reports no errors (warnings acceptable at stub stage)
- [ ] `StatusBadge` widget accepts a `status` string and returns a colored container

---

### 8.4 Per-Client Build Config (`app/config.dart`)

> **Requires**: 8.3

```dart
class AppConfig {
  static const baseUrl     = String.fromEnvironment('BASE_URL', defaultValue: 'https://demo.rentalplatform.com');
  static const brandColor  = Color(int.fromEnvironment('BRAND_COLOR', defaultValue: 0xFF2563EB));
  static const appName     = String.fromEnvironment('APP_NAME', defaultValue: 'Rental Platform');
  static const logoAsset   = String.fromEnvironment('LOGO_ASSET', defaultValue: 'assets/logo.png');
  static const hasFlats    = bool.fromEnvironment('HAS_FLATS', defaultValue: true);
  static const hasVehicles = bool.fromEnvironment('HAS_VEHICLES', defaultValue: true);
}
```

```bash
flutter build apk \
  --dart-define=BASE_URL=https://client1.example.com \
  --dart-define=BRAND_COLOR=0xFF1A73E8 \
  --dart-define=APP_NAME=ClientOne+Rentals \
  --dart-define=HAS_FLATS=true \
  --dart-define=HAS_VEHICLES=false
```

**Acceptance Criteria**:
- [ ] `--dart-define=APP_NAME=TestApp` → app title bar shows "TestApp"
- [ ] `--dart-define=BRAND_COLOR=0xFFFF0000` → primary color is red
- [ ] No `--dart-define` flags → defaults compile and render correctly
- [ ] `hasFlats=false` → flat-related catalog tab is hidden
- [ ] `hasVehicles=false` → vehicle-related catalog tab is hidden

---

### 8.5 Secure Storage Provider

> **Requires**: 8.2 (`flutter_secure_storage` dependency must be resolved)

```dart
@riverpod
FlutterSecureStorage secureStorage(Ref ref) {
  return const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock),
  );
}
```

**Acceptance Criteria**:
- [ ] `secureStorageProvider` is a Riverpod provider (not a global singleton)
- [ ] Provider can be overridden in tests via `ProviderScope(overrides: [...])`
- [ ] Android uses `encryptedSharedPreferences: true`
- [ ] iOS uses `KeychainAccessibility.first_unlock`
- [ ] `await storage.write(key: 'test', value: 'val')` → `await storage.read(key: 'test')` returns `'val'`

---

### 8.6 FrappeClient — Dio Provider

> **Requires**: 8.5 (reads API key/secret from secure storage), 8.4 (`AppConfig.baseUrl`)

```dart
@riverpod
FrappeClient frappeClient(Ref ref) {
  final storage = ref.read(secureStorageProvider);
  final client = FrappeClient(storage);
  client.init(AppConfig.baseUrl);
  return client;
}

class FrappeClient {
  final FlutterSecureStorage _storage;
  FrappeClient(this._storage);
  late final Dio _dio;

  void init(String baseUrl) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
      headers: {'Accept': 'application/json'},
    ));
    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (opts, handler) async {
        final key    = await _storage.read(key: 'api_key');
        final secret = await _storage.read(key: 'api_secret');
        if (key != null) opts.headers['Authorization'] = 'token $key:$secret';
        handler.next(opts);
      },
      onError: (err, handler) {
        if (err.response?.statusCode == 401) {
          authStateController.add(AuthState.unauthenticated);
        }
        handler.next(err);
      },
    ));
  }

  Future<dynamic> get(String method, {Map<String, dynamic>? params}) async {
    final r = await _dio.get('/api/method/$method', queryParameters: params);
    return r.data['message'];
  }

  Future<dynamic> post(String method, {Map<String, dynamic>? body}) async {
    final r = await _dio.post('/api/method/$method', data: body);
    return r.data['message'];
  }
}
```

**Acceptance Criteria**:
- [ ] `frappeClientProvider` is a Riverpod provider — overridable in tests
- [ ] When `api_key` is stored, every request includes `Authorization: token key:secret`
- [ ] When `api_key` is absent, request proceeds without `Authorization` header
- [ ] HTTP 401 response triggers `AuthState.unauthenticated` event
- [ ] `BaseOptions.baseUrl` starts with `https://`
- [ ] Connect timeout is 10s; receive timeout is 20s

---

### 8.7 TLS & Transport Security

> **Requires**: 8.6

> [!IMPORTANT]
> - App must **only connect over HTTPS**.
> - Consider **certificate pinning** using `dio_http2_adapter` for production builds.
> - Future hardening: migrate to OAuth2 with refresh tokens.

**Acceptance Criteria**:
- [ ] Attempting to set `BASE_URL` to `http://` (non-TLS) causes a visible error or assertion
- [ ] Production builds include certificate pinning configuration (can be a documented TODO for post-MVP)

---

### 8.8 Auth Notifier

> **Requires**: 8.6 (FrappeClient for login API call), 8.5 (SecureStorage for credential persistence)

```dart
enum AuthState { authenticated, unauthenticated, loading }

@riverpod
class AuthNotifier extends _$AuthNotifier {
  @override
  Future<AuthState> build() async {
    final storage = ref.read(secureStorageProvider);
    final hasKey = await storage.read(key: 'api_key') != null;
    return hasKey ? AuthState.authenticated : AuthState.unauthenticated;
  }

  Future<bool> login(String email, String password) async {
    state = const AsyncLoading();
    try {
      final client = ref.read(frappeClientProvider);
      final resp = await client.post('frappe.core.doctype.user.user.login',
        body: {'usr': email, 'pwd': password});
      final storage = ref.read(secureStorageProvider);
      await storage.write(key: 'api_key', value: resp['api_key']);
      await storage.write(key: 'api_secret', value: resp['api_secret']);
      await storage.write(key: 'user_email', value: email);
      await FcmService(ref).registerToken();
      state = const AsyncData(AuthState.authenticated);
      return true;
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
      return false;
    }
  }

  Future<void> logout() async {
    await FcmService(ref).deregisterToken();
    await ref.read(frappeClientProvider).post('logout');
    await ref.read(secureStorageProvider).deleteAll();
    state = const AsyncData(AuthState.unauthenticated);
  }
}
```

**Acceptance Criteria**:
- [ ] Fresh install (no stored key) → `build()` returns `AuthState.unauthenticated`
- [ ] After successful `login()` → state transitions to `AuthState.authenticated`
- [ ] After successful `login()` → `api_key`, `api_secret`, `user_email` are in secure storage
- [ ] Invalid credentials → state transitions to `AsyncError`, `login()` returns `false`
- [ ] `logout()` → `deleteAll()` clears secure storage, state becomes `unauthenticated`
- [ ] `logout()` → FCM token is deregistered before clearing storage

---

### 8.9 GoRouter Configuration

> **Requires**: 8.8 (auth state drives redirect logic), 8.3 (all screen stubs must exist)

```dart
final router = GoRouter(
  redirect: (context, state) async {
    final auth = ref.read(authNotifierProvider);
    final isLoggedIn = auth.valueOrNull == AuthState.authenticated;
    final guarded = ['/book', '/my-rentals', '/invoices', '/pay', '/documents', '/kyc'];
    final isGuarded = guarded.any((p) => state.uri.path.startsWith(p));
    if (!isLoggedIn && isGuarded) return '/login?from=${state.uri.path}';
    return null;
  },
  routes: [ /* all routes */ ],
);
```

**Acceptance Criteria**:
- [ ] Unauthenticated user navigating to `/my-rentals` → redirected to `/login?from=/my-rentals`
- [ ] After login, user returns to `/my-rentals` (the `from` param is respected)
- [ ] Unauthenticated user navigating to `/catalog` → no redirect (non-guarded)
- [ ] Unauthenticated user navigating to `/asset/ABC` → no redirect (non-guarded)
- [ ] All routes in the route table resolve to their screen widgets without error

---

### 8.10 API Error Model

> **Requires**: 6.1 (error envelope structure), 8.6 (FrappeClient)

```dart
@freezed
class ApiError with _$ApiError {
  const factory ApiError({
    required String excType,
    required List<FieldError> errors,
    @Default([]) List<String> serverMessages,
  }) = _ApiError;

  factory ApiError.fromResponse(Response response) { /* ... */ }

  String get displayMessage =>
      errors.isNotEmpty ? errors.first.message : 'An unexpected error occurred';
}
```

**Acceptance Criteria**:
- [ ] `ApiError.fromResponse()` parses HTTP 400 body with `exc_type` and `errors[]`
- [ ] `ApiError.fromResponse()` parses HTTP 409 body correctly
- [ ] `displayMessage` returns first field error when `errors` is non-empty
- [ ] `displayMessage` returns `"An unexpected error occurred"` when `errors` is empty
- [ ] Null `exc_type` in response defaults to `"UnknownError"`
- [ ] Empty `_server_messages` does not cause a crash

---

### 8.11 Offline Caching Strategy

> **Requires**: 8.6 (all caching wraps FrappeClient calls), 8.2 (`connectivity_plus` dependency)

| Data | Strategy |
|---|---|
| Asset catalog | `keepAlive: true` on provider; stale-while-revalidate |
| Asset detail | Cached by `assetId`; invalidated on pull-to-refresh |
| Agreements | Cached; `ref.invalidate()` on screen focus |
| Invoices | Always fresh; no caching |
| Notifications | Stored locally (SharedPreferences) on receive |
| Booking submit | **Outbox pattern**: serialized to local storage, retried on reconnect |

**Acceptance Criteria**:
- [ ] `OfflineBanner` widget appears when `ConnectivityResult.none` is detected
- [ ] `OfflineBanner` disappears when connectivity is restored
- [ ] Catalog data persists when app is backgrounded and re-opened (no re-fetch until pull-to-refresh)
- [ ] Pull-to-refresh on asset detail clears cached data and re-fetches
- [ ] Invoice screen always fetches fresh data (no stale reads)

---

## 9. Domain-Level Acceptance Criteria

> Cross-task integration checks.

- [ ] `bench new-app rental_core` → install → `bench start` → all working end-to-end
- [ ] `Rental Configuration` populated → license valid → login → portal menu shows
- [ ] License expired → grace mode → webhooks logged → renewal → reconciliation
- [ ] License expired past grace → `/suspended` page shown
- [ ] Flutter app builds → `--dart-define` overrides → login → guarded routes → error parsing
- [ ] Web portal: RTL renders → guest redirect → CSRF enforced → robots.txt correct
- [ ] All user-facing strings wrapped in `_()` / `__()`

---

## 10. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (scaffold + config + licensing + roles) | 5 days |
| Web (design system + RTL + robots + security) | 1 day |
| Flutter (setup + config + auth + router + error model) | 3 days |
| **Total** | **9 days** |
