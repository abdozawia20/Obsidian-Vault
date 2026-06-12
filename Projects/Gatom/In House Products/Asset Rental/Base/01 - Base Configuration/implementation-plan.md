# Domain 01 — Base Configuration: Implementation Plan

> **Variant**: Base
> **Domain**: Base Configuration
> **Sequence**: 1 of 8 — **Implement this first**
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

This is the **very first domain** to implement — it creates the `rental_core` Frappe app, sets up the directory structure, registers all hooks and scheduler events, and establishes the global configuration singleton (`Rental Configuration`). Every other domain in the base module (D02–D08) and every child app (Flats, Vehicles) depends on the infrastructure created here.

The domain also includes the **license enforcement** system (preventing usage after license expiry), the **role hierarchy** (who can do what), the **design system** (CSS variables and components for the web portal), and the **Flutter project scaffold** (Dart project, Riverpod setup, shared models).

---

## 2. Frappe — App Scaffold & Directory Layout

### 2.1 Create the App

> **Requires**: Nothing — first task in the project.

The `rental_core` app is the **base Frappe application** that all rental platform functionality lives in. This is the very first thing to do — creating the app scaffold using Frappe's `bench new-app` command, then installing it on the development site. Until this is done, no DocTypes, APIs, or web pages can be created.

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

This establishes the **physical file layout** of the entire application. Rather than dumping everything into generic `utils/` or `helpers/` folders, the codebase uses **domain-specific directories**: `billing/`, `payment_routing/`, `notification_pipeline/`, `licensing/`, `catalog/`, and `gateways/`. This makes it immediately obvious where code for a specific feature lives.

The directory also includes the `api/` layer (one file per resource), `templates/` for email HTML, and `doctype/` for all Frappe DocType definitions. Every file is created as a stub initially — actual logic is added in later domains.

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

Frappe's `hooks.py` is the **central wiring file** for the entire application. It registers: **7 daily scheduler events** (payment reminders, renewal checks, late fees, quotation expiry, booking expiry, deposit auto-commit, overdue escalation), **1 cron job** (booking expiry check every 5 minutes for time-sensitive expirations), **2 monthly jobs** (reporting and webhook log cleanup), **3 doc_events** (hooks on Subscription, Sales Invoice, and Payment Entry for the billing pipeline), **5 portal menu items** (customer and guarantor sidebar links), and **2 website route rules** (clean URLs for asset detail and booking pages).

This subtask creates the file with all registrations pointing to stub modules. The actual logic is implemented in subsequent domains.

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

This is an **architectural constraint**, not a feature to build. The base app (`rental_core`) must **never import** from child apps (`rental_flats`, `rental_vehicles`). Instead, child apps extend the base by registering their own `doc_events` in their `hooks.py`. This means `rental_core` works perfectly standalone — installing or uninstalling a child app doesn't break anything. This pattern is critical for the multi-variant business model where different customers may have only Flats, only Vehicles, or both.

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

`Rental Configuration` is a **Frappe singleton** — a single-record DocType that acts as the global settings page for the entire platform. It stores everything from country/currency selection and payment gateway credentials, to billing parameters (grace periods, late fee rules), KYC requirements, AWS/CDN settings for media, notification preferences, and license keys. Every domain in the system reads from this singleton.

The schema is intentionally large because it centralizes all operator-configurable values in one place, avoiding scattered settings across multiple pages. **Password fields** (API keys, secrets) are restricted to the Administrator role only.

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
> **Integration**: `gatom_agent` (Pulse Agent) handles all license communication with Pulse server. `rental_core` only reads the result from Redis.

The platform is a **licensed product** — operators need a valid license key (RSA-signed JWT issued by Gatom Pulse) to use it. License validation is a **two-layer** system:

1. **`gatom_agent`** (installed alongside `rental_core`) validates the license daily at 4 AM — both online (calling Pulse API) and offline (local JWT signature verification). The agent writes the validation result to Redis key `pulse:license_status`.
2. **`rental_core`** reads `pulse:license_status` from Redis on every user login (`on_session_creation` hook) and acts on the result.

This separation means `rental_core` has **zero dependency on network connectivity** for license checks — the agent handles all remote communication.

> [!IMPORTANT]
> The previous design referenced `validate_remote(lic.license_key)` — this function is **removed**. Remote validation is now handled entirely by `gatom_agent`. See [[../../Internal/Gatom Pulse/Agent/functional|Agent Functional Analysis]] and [[../../Internal/Gatom Pulse/P07 - Licensing/functional|P07 — Licensing Engine]] for the full specification.

```python
def validate_license(login_manager=None):
    """Called on every login via on_session_creation hook.
    Reads license status from Redis (written by gatom_agent).
    """
    # Read agent's license validation result from Redis
    status = frappe.cache().get("pulse:license_status")
    
    if status in ("VALID", "VALID_OFFLINE", None):
        # None = agent hasn't run yet (fresh install grace)
        return
    
    if status == "EXPIRING":
        # License expires within 30 days — show warning banner
        frappe.msgprint(
            "Your license is expiring soon. Contact your provider.",
            indicator="orange", alert=True
        )
        return
    
    if status == "GRACE":
        # License expired but within grace period
        frappe.msgprint(
            "Your license has expired. Operating in grace mode.",
            indicator="red", alert=True
        )
        frappe.flags.in_grace_mode = True
        return
    
    if status in ("EXPIRED", "REVOKED", "OFFLINE_EXPIRED"):
        # Hard block — redirect to suspended page
        frappe.local.flags.redirect_location = "/suspended"
        raise frappe.Redirect
    
    if status == "ASSET_LIMIT":
        frappe.msgprint(
            "Asset limit reached. Contact your provider to upgrade.",
            indicator="orange", alert=True
        )
        return
    
    if status in ("MISSING", "INVALID", "SITE_MISMATCH", "UNVERIFIED"):
        frappe.local.flags.redirect_location = "/suspended"
        raise frappe.Redirect


def is_in_grace_mode():
    """Check if the platform is currently in license grace mode."""
    return frappe.cache().get("pulse:license_status") == "GRACE"
```

**Acceptance Criteria**:
- [ ] Valid license (status = `VALID` or `VALID_OFFLINE`) → login proceeds normally
- [ ] Expiring license (status = `EXPIRING`) → login proceeds with warning banner
- [ ] Grace mode (status = `GRACE`) → login proceeds with red banner, `is_in_grace_mode()` returns `True`
- [ ] Expired/Revoked (status = `EXPIRED`, `REVOKED`, `OFFLINE_EXPIRED`) → redirect to `/suspended`
- [ ] No license status in Redis (agent hasn't run yet) → allow login (fresh install grace)
- [ ] `validate_license` runs on every `on_session_creation` event
- [ ] **No direct network calls** — all remote validation is delegated to `gatom_agent`

---

### 4.2 Grace Mode Webhook Branching

> **Requires**: 4.1 (`is_in_grace_mode()` function must exist)

Payment webhooks arrive from Stripe/Tap/PayMob even when the license is expired. During grace mode, the system **must not lose these webhooks** but also cannot fully process them (since billing logic may be degraded). This subtask logs the incoming webhook payload with `processed=0` and returns a benign `{"status": "ok"}` response so the payment gateway doesn't retry endlessly. Once the license is renewed, the reconciliation job (4.3) picks up these deferred webhooks.

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

After the operator renews the license and the platform exits grace mode, all the webhook payloads that were stored during the grace period need to be **re-processed**. This job finds all `Payment Webhook Log` entries with `processed=0` and enqueues each one for background processing. This ensures no payment confirmations are lost during the license gap — the billing state catches up automatically.

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

When the license expires past the grace period, every page in the platform (portal and Desk) redirects to this static page. It shows a "Service Suspended" message with the operator's contact information so users know who to reach. The page must work even when most of the system is degraded — it's essentially a static fallback.

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

The platform uses **four custom roles** to control access across all DocTypes. `Rental Manager` has full control, `Rental Agent` can handle leads and quotations but has limited agreement access, `Accountant (Rental)` can manage financial records but not operational ones, and `Customer` has read-only access to their own data. These roles are created during app setup and must survive `bench migrate` without being deleted.

**Acceptance Criteria**:
- [ ] `setup_roles()` creates four custom roles: `Rental Manager`, `Rental Agent`, `Accountant (Rental)`, `Customer`
- [ ] Roles persist across `bench migrate` — they are not deleted on re-run
- [ ] Each role has a descriptive `role_name` (not code-only)

---

### 5.2 Permission Rules

> **Requires**: 5.1 (roles must exist), 3.1 (Rental Configuration DocType must exist)

This matrix defines **who can do what** across every DocType in the system. The key security principle is **customer isolation**: customers can only see their own agreements, deposits, and KYC submissions. Accountants are deliberately blocked from leads and quotations (separation of concerns). The Customer role gets special `R (portal)` access on Rental Asset — meaning they can read assets through the web portal's filtered views, not through Frappe Desk.

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

All API endpoints must return errors in a **consistent format** that the Flutter app and web portal can reliably parse. Instead of raw Python tracebacks, every error returns a structured JSON body with the error type, per-field validation messages, and server messages. This is a **contract** that all developers must follow when writing API endpoints — the Flutter `ApiError` model (8.10) is built to parse this exact structure.

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

Every API endpoint that returns a list of records (assets, agreements, invoices, readings) must follow this pagination structure. The response includes `total` count, current `page`, `page_size`, and a `has_next` boolean. This lets the Flutter app show "Load More" buttons and the web portal show page numbers. `page_size` is capped at 100 to prevent a single request from dumping the entire database.

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

### 6.3 Rate Limiting Middleware

> **Requires**: 6.1 (error envelope must support HTTP 429)

Several API endpoints are vulnerable to abuse if left unthrottled — particularly the registration endpoint (brute-force account creation), the login endpoint (credential stuffing), the inquiry form (spam), and the booking submission (reservation flooding). Without rate limiting, the platform defines HTTP 429 in its error contract (6.1) but never actually produces it.

Rate limiting is implemented as a **Frappe before_request hook** that checks the caller's IP address and user session against a per-endpoint counter stored in Redis (Frappe's cache backend). Each endpoint category has its own threshold:

**Rate Limit Registry** — every endpoint in the platform and its threshold:

| Endpoint | Limit | Window | Scope | Domain |
|---|---|---|---|---|
| `register_customer` | 5 | per hour | per IP | D01-7.8 |
| `login` | 10 | per 15 min | per IP | Frappe built-in |
| `guest_inquiry` | 3 | per 10 min | per IP | D02-4.1 |
| `get_available_assets` | 60 | per minute | per IP | D04-7.1 |
| `get_asset_detail` | 60 | per minute | per IP | D04-7.2 |
| `get_asset_availability` | 60 | per minute | per IP | D04-7.3 |
| `get_featured_assets` | 60 | per minute | per IP | D04-7.4 |
| `payment_webhook` | 100 | per minute | per IP | D06-6.1 |
| `submit_kyc_documents` | 10 | per minute | per user | D03-4.2 |
| `submit_booking_request` | 5 | per minute | per user | D05-7.1 |
| `cancel_booking_request` | 3 | per minute | per user | D05-3.1 |
| `get_invoice_payment_url` | 10 | per minute | per user | D06-7.2 |
| `dispute_deposit_deduction` | 5 | per minute | per user | D06-7.4 |
| `register_fcm_token` | 10 | per minute | per user | D07-6.3 |
| All other authenticated APIs | 60 | per minute | per user | — |

When a limit is exceeded, the middleware returns HTTP 429 with the standard error envelope (6.1) and a `Retry-After` header indicating how many seconds the caller must wait.

```python
def rate_limit(endpoint, max_requests, window_seconds, scope="user"):
    key = f"rate_limit:{endpoint}:{get_scope_key(scope)}"
    current = frappe.cache().get(key) or 0
    if current >= max_requests:
        frappe.local.response.headers["Retry-After"] = str(window_seconds)
        frappe.throw(_("Too many requests. Please try again later."),
                     exc=frappe.TooManyRequestsError)
    frappe.cache().set(key, current + 1, expires_in_sec=window_seconds)
```

**Acceptance Criteria**:
- [ ] Registration endpoint returns HTTP 429 after 5 calls from the same IP within 1 hour
- [ ] Login endpoint returns HTTP 429 after 10 calls from the same IP within 15 minutes
- [ ] Inquiry form returns HTTP 429 after 3 calls from the same IP within 10 minutes
- [ ] `payment_webhook` endpoint returns HTTP 429 after 100 calls from the same IP within 1 minute
- [ ] All 429 responses include `Retry-After` header with seconds remaining
- [ ] All 429 responses match the standard error envelope (6.1)
- [ ] Rate limit counters are stored in Redis (Frappe cache), not the database
- [ ] Different users/IPs have independent counters (no cross-contamination)
- [ ] Rate limit registry table covers all 15 endpoint categories listed above

---

### 6.4 API Security Checklist

> **Requires**: 6.1 (error envelope), 6.3 (rate limiting)

A cross-cutting security standard that **every API endpoint** in the platform must satisfy. This is not a separate subtask per domain — it's a checklist that domain developers apply when implementing any `@frappe.whitelist()` endpoint. The checklist is enforced during code review.

**Mandatory for all endpoints**:

1. **Authorization check**: Every endpoint that returns or modifies a document must verify ownership via `frappe.has_permission(doctype, "read", doc=name)` or equivalent. Never trust the `name` parameter alone — an attacker could guess another customer's document name (IDOR prevention).

2. **Input sanitization**: All text inputs that are displayed back to users (rejection reasons, damage notes, chat messages, inquiry bodies) must be escaped via `frappe.utils.escape_html()` before storage. This prevents stored XSS.

3. **File upload validation**: All file upload endpoints (KYC documents D03-4.2, bank transfer receipts D06-8.3, inspection photos D04-3.1) must validate:
   - MIME type against an allowlist: `image/jpeg`, `image/png`, `application/pdf`
   - File size against a maximum: 10 MB per file (configurable in Rental Configuration)
   - File extension matches MIME type (prevent `.php` disguised as `.jpg`)

4. **SQL injection prevention**: All database queries must use Frappe's parameterized query API (`frappe.get_all()`, `frappe.db.get_value()`) — never raw SQL string concatenation. The `LIKE` operator in catalog filters (D04-4.3) must sanitize `%` and `_` in user input.

5. **Rate limiting**: Every endpoint must be listed in the rate limit registry (§6.3). Unlisted endpoints inherit the default rate (60/min/user).

**Acceptance Criteria**:
- [ ] Code review checklist document created and linked in project README
- [ ] All existing endpoints audited against the 5 rules above
- [ ] D06-7.3 (`get_deposit_status`) includes explicit ownership check: requesting user must be the `customer` on the linked agreement
- [ ] D03-4.2 (`submit_kyc_documents`) validates MIME type: only `image/jpeg`, `image/png`, `application/pdf` accepted
- [ ] D06-8.3 (bank transfer upload) validates MIME type: same allowlist
- [ ] D04-4.3 catalog filter sanitizes `%` and `_` in location search input

---

### 6.5 API Endpoint Registry

> **Requires**: All domains (D01–D08)

A centralized reference of **every API endpoint** exposed by the `rental_core` app. This registry ensures no endpoint is undocumented, unprotected, or missing from the rate limit table. It is maintained as a living document — when a new endpoint is added in any domain, a corresponding row is added here.

#### Public Endpoints (No Authentication Required)

| # | Method | Endpoint | Domain | Description |
|---|---|---|---|---|
| P1 | GET | `get_available_assets` | D04-7.1 | Catalog listing with filters |
| P2 | GET | `get_asset_detail` | D04-7.2 | Single asset detail page data |
| P3 | GET | `get_asset_availability` | D04-7.3 | Calendar availability for an asset |
| P4 | GET | `get_featured_assets` | D04-7.4 | Featured assets for home screen |
| P5 | POST | `guest_inquiry` | D02-4.1 | Anonymous inquiry form submission |
| P6 | POST | `payment_webhook` | D06-6.1 | Payment gateway callback (signature-verified) |
| P7 | POST | `register_customer` | D01-7.8 | New customer registration |
| P8 | GET | `verify_email` | D01-7.8 | Email verification link handler |

#### Authenticated Customer Endpoints

| # | Method | Endpoint | Domain | Description |
|---|---|---|---|---|
| C1 | GET | `get_kyc_status` | D03-4.1 | Current KYC verification status |
| C2 | POST | `submit_kyc_documents` | D03-4.2 | Upload KYC documents |
| C3 | GET | `get_required_document_types` | D03-4.4 | KYC document type list for region |
| C4 | POST | `submit_booking_request` | D05-7.1 | Create a new booking |
| C5 | POST | `cancel_booking_request` | D05-3.1 | Self-cancel a pending booking |
| C6 | GET | `get_my_agreements` | D05-7.2 | List customer's agreements |
| C7 | GET | `get_customer_invoices` | D06-7.1 | List customer's invoices |
| C8 | GET | `get_invoice_payment_url` | D06-7.2 | Generate payment gateway URL |
| C9 | GET | `get_deposit_status` | D06-7.3 | Deposit ledger for an agreement |
| C10 | POST | `dispute_deposit_deduction` | D06-7.4 | Dispute a pending deduction |
| C11 | GET | `get_customer_notifications` | D07-6.1 | Notification inbox |
| C12 | POST | `mark_notification_read` | D07-6.2 | Mark notification as read |
| C13 | POST | `register_fcm_token` | D07-6.3 | Register FCM push token |
| C14 | POST | `deregister_fcm_token` | D07-6.3 | Deregister FCM push token |
| C15 | GET | `get_active_rental_summary` | D04-7.5 | Home screen rental summary |
| C16 | GET | `get_booking_steps` | D05-8.6 | Dynamic booking step list |
| C17 | POST | `upload_payment_proof` | D06-7.5 | Bank transfer receipt upload |

#### Guarantor Endpoints

| # | Method | Endpoint | Domain | Description |
|---|---|---|---|---|
| G1 | GET | `get_guarantor_invoices` | D06-7.6 | View guaranteed tenant's overdue invoices |

#### Staff Endpoints (Rental Manager / Accountant)

| # | Method | Endpoint | Domain | Description |
|---|---|---|---|---|
| S1 | GET | `get_dashboard_metrics` | D08-7.1 | Dashboard summary data for Flutter |

#### Scheduler Jobs (Background)

| # | Schedule | Job | Domain | Description |
|---|---|---|---|---|
| J1 | Daily | `send_payment_reminders` | D07-3.1 | 3-day-before-due reminders |
| J2 | Hourly | `run_overdue_escalation` | D07-4.1 | Escalation ladder |
| J3 | Daily | `auto_apply_late_fees` | D06-3.1 | Apply late fees after grace |
| J4 | Hourly | `auto_expire_draft_agreements` | D04-5.1 | Expire unreviewed bookings |
| J5 | Daily | `auto_commit_deposit_deductions` | D06-4.3 | Commit undisputed deductions |
| J6 | Monthly | `generate_monthly_report` | D08-4.1 | Email monthly metrics |
| J7 | Monthly | `purge_old_webhook_logs` | D08-5.1 | Clean old webhook logs |

**Acceptance Criteria**:
- [ ] Every `@frappe.whitelist()` function in `rental_core` has a corresponding row in this registry
- [ ] Registry is updated whenever a new endpoint is added in any domain
- [ ] All public endpoints (P1–P8) are accessible without login
- [ ] All customer endpoints (C1–C17) return 403 for unauthenticated requests
- [ ] Guarantor endpoint (G1) restricts access to users with guarantor link only
- [ ] Staff endpoint (S1) restricts access to Rental Manager / System Manager roles

---

## 7. Web — Design System & Localisation

### 7.1 CSS Design System (`rental_web.css`)

> **Requires**: 2.2 (`public/css/` directory must exist)

The **design system** defines all visual constants (colors, typography, spacing, shadows, radii) as CSS custom properties. Every web portal page uses these variables instead of hardcoded values, ensuring visual consistency and making it easy to re-theme for different clients. The system uses a modern neutral palette with `Inter` as the primary font. The `.rental-card:hover` rule adds a subtle lift animation that makes the catalog feel interactive.

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

The platform supports **right-to-left languages** (Arabic, Farsi, Urdu, Hebrew). This conditional stylesheet overrides layout-direction-sensitive rules: booking step indicators reverse their flow, catalog filter sidebars flip to the left side, and text alignment adjusts. The stylesheet is **only loaded** when the user's language is RTL — LTR users never download it.

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

This creates all the web portal page files as **stubs** — each `.html` file has an empty template block, and each `.py` file has a `get_context()` that returns `{}`. The actual page logic is built in later domains (D02 builds the catalog, D05 builds booking, etc.). Creating stubs now ensures all `hooks.py` route rules resolve without 404s, and the portal menu links don't break during development.

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

The `robots.txt` file tells search engines which pages they can crawl. The **public catalog** (`/rentals/`) is allowed for SEO visibility, but all authenticated portal pages (My Rentals, My Invoices, My Documents, My KYC, Guarantor Portal, Pay) and Frappe Desk (`/app/`) are disallowed to prevent indexing of private user data.

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

These are **cross-cutting security rules** that every web developer must follow. All AJAX calls must use `frappe.call()` (which auto-includes the CSRF token), every portal page must redirect guests to `/login`, every database query must filter by the current user's session, and all user inputs must be sanitized against SQL injection. These are not single-feature subtasks — they're constraints that must be verified across every page.

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

### 7.6 Error, Empty & Loading State Patterns

> **Requires**: 7.1 (CSS design system must exist)

The Flutter plan defines reusable `error_view`, `loading_overlay`, and `offline_banner` widgets (8.3), but the web portal has **no equivalent patterns**. Without shared patterns, each domain will independently invent its own "empty catalog" or "payment failed" page, leading to visual inconsistency and duplicated markup. This subtask defines the HTML/CSS patterns that every web portal page must use.

Three patterns are needed:

**Error State** — shown when an API call fails or a page can't load its data. Includes an icon (⚠️), a translated error message, and a "Try Again" button that reloads the current page. Used on: catalog (API failure), My Rentals (permission error), payment page (gateway timeout).

**Empty State** — shown when a query returns zero results. Includes an icon (📭), a translated message ("No results found" / "You have no active rentals"), and an optional CTA ("Browse Rentals"). Used on: catalog (no matching assets), My Invoices (no invoices yet), notifications (no notifications).

**Loading State** — shown while data is being fetched. A centered spinner with a pulsing animation using the design system's `--rental-primary` color. Applied as an overlay on the content area, not the full page (so the header/nav remain visible).

```css
.rental-error-state, .rental-empty-state {
  display: flex; flex-direction: column; align-items: center;
  padding: 3rem 1rem; text-align: center; color: var(--rental-muted);
}
.rental-error-state .retry-btn { margin-top: 1rem; }
.rental-loading { display: flex; justify-content: center; padding: 3rem; }
.rental-loading .spinner {
  width: 40px; height: 40px; border: 3px solid var(--rental-border);
  border-top-color: var(--rental-primary); border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
```

**Acceptance Criteria**:
- [ ] `.rental-error-state` pattern defined in the design system CSS
- [ ] `.rental-empty-state` pattern defined in the design system CSS
- [ ] `.rental-loading` spinner pattern defined in the design system CSS
- [ ] All messages within state patterns are wrapped in `_()` for translation
- [ ] At least one Jinja2 include template exists for each pattern (`templates/includes/error_state.html`, `empty_state.html`, `loading_state.html`)
- [ ] Error state includes a "Try Again" button
- [ ] Empty state supports an optional CTA button (passed as template parameter)

---

### 7.7 Accessibility Requirements (Web)

> **Requires**: 7.1 (CSS design system), 7.3 (all portal page stubs)

This is a **cross-cutting constraint** that applies to every web portal page, similar to the security requirements in 7.5. The platform targets multi-region deployment including the EU (where WCAG 2.1 AA compliance is increasingly expected) and government-adjacent clients in the Gulf (who may have accessibility mandates). These rules ensure the portal is usable by people with visual, motor, or cognitive disabilities.

The requirements cover four areas:

**Keyboard Navigation** — Every interactive element (buttons, links, form inputs, calendar dates, filter toggles) must be reachable via Tab key and activatable via Enter/Space. Focus order must follow the visual reading order (LTR or RTL depending on locale). The booking form's 5-step wizard must be navigable without a mouse.

**ARIA Labels** — All icon-only buttons (e.g., the notification bell, calendar navigation arrows, photo carousel arrows) must have `aria-label` attributes describing their function. Form inputs must have associated `<label>` elements or `aria-label` (not just placeholder text). Status badges must use `role="status"` and `aria-live="polite"`.

**Color Contrast** — The design system's color palette (7.1) must meet WCAG 2.1 AA contrast ratios: at least 4.5:1 for normal text and 3:1 for large text. The current `--rental-muted: #64748B` on `--rental-bg: #F8FAFC` must be verified (it's borderline at ~4.6:1).

**Screen Reader Support** — The portal header must use `<nav aria-label="Main navigation">`. Page content areas must use `<main>`. Form validation errors must be announced via `aria-live="assertive"`. The availability calendar must announce selected dates.

**Acceptance Criteria**:
- [ ] All interactive elements are reachable via Tab key
- [ ] Focus order follows visual reading order (LTR and RTL)
- [ ] All icon-only buttons have descriptive `aria-label`
- [ ] All form inputs have associated `<label>` elements
- [ ] Color contrast meets WCAG 2.1 AA (4.5:1 for text, 3:1 for large text)
- [ ] Portal header uses `<nav aria-label="Main navigation">`
- [ ] Validation errors are announced via `aria-live="assertive"`
- [ ] Booking form wizard is navigable via keyboard only

---

### 7.8 Registration Page (`www/rental-signup.html`)

> **Requires**: 7.3 (stub file exists), 7.1 (design system), 6.3 (rate limiting on registration endpoint)

The platform assumes customers exist before they can complete KYC (D03) and book assets (D05), but **no domain defines how a customer account is created**. The `rental-signup.html` stub exists in the file structure (7.3) but has no implementation. This subtask builds the actual registration form and its server-side handler.

The registration form collects the minimum needed to create a Frappe user + ERPNext Customer record: `full_name`, `email`, `phone`, and `password`. No KYC documents are collected at this stage — that's handled separately in D03 after registration. This separation is intentional: casual browsers can create an account and explore the portal (My Rentals, invoices, etc.) before committing to the KYC process.

The server-side API creates a Frappe User with role `Customer`, creates a linked ERPNext Customer record, sends a **verification email** with a confirmation link, and returns a success response. The account is **inactive** until the email link is clicked — this prevents bot registrations from cluttering the customer database.

After successful email verification, the user is redirected to `/my-kyc` with a flash message: "Account verified! Complete your identity verification to start booking." This is the bridge to D03.

```python
@frappe.whitelist(allow_guest=True)
def register_customer(full_name, email, phone, password):
    rate_limit("register_customer", max_requests=5, window_seconds=3600, scope="ip")
    if frappe.db.exists("User", email):
        frappe.throw(_("An account with this email already exists"))
    user = frappe.get_doc({
        "doctype": "User", "email": email, "first_name": full_name,
        "phone": phone, "new_password": password,
        "roles": [{"role": "Customer"}], "enabled": 0,
    })
    user.insert(ignore_permissions=True)
    customer = frappe.get_doc({
        "doctype": "Customer", "customer_name": full_name,
        "customer_type": "Individual", "email_id": email,
    })
    customer.insert(ignore_permissions=True)
    send_verification_email(user)
    return {"status": "ok", "message": _("Please check your email to verify your account")}
```

The web form includes:
- Full name (required, min 2 characters)
- Email (required, email format validation)
- Phone (required, used for SMS notifications later)
- Password (required, min 8 characters, strength indicator)
- "Already have an account? Log in" link

**Acceptance Criteria**:
- [ ] Registration form renders at `/rental-signup`
- [ ] Successful submission creates a Frappe User with role `Customer` and `enabled=0`
- [ ] Successful submission creates a linked ERPNext Customer record
- [ ] Verification email is sent with a confirmation link
- [ ] Clicking the confirmation link sets `enabled=1` on the User
- [ ] After verification, user is redirected to `/my-kyc`
- [ ] Duplicate email returns HTTP 400 with "An account with this email already exists"
- [ ] Rate-limited to 5 registrations per IP per hour (via 6.3)
- [ ] Password must be at least 8 characters (client-side + server-side validation)
- [ ] All form labels and messages are wrapped in `_()` for translation

---

### 7.9 Hijri Date Display

> **Requires**: 3.1 (`date_display_format` field in Rental Configuration), 7.1 (design system)

The platform targets Gulf region deployments (UAE, KSA, Bahrain, Oman, Kuwait, Qatar) where the **Hijri (Islamic) calendar** is used alongside the Gregorian calendar for official and business purposes. When the operator configures `date_display_format = Hijri` in Rental Configuration, all customer-facing dates in the web portal must display in **dual format**: the Hijri date as the primary display with the Gregorian date in parentheses (e.g., "15 Dhul Hijjah 1447 (12 Jun 2026)").

This does NOT change how dates are stored internally — all database fields remain Gregorian ISO format. The conversion happens only at the **display layer** in Jinja2 templates.

The conversion uses the `hijri-converter` Python library (which must be added to `pyproject.toml` dependencies). A custom Jinja2 filter `|hijri` is registered in `hooks.py` under `jinja.filters` to make it available in all templates.

```python
from hijri_converter import Gregorian

def hijri_filter(date_value):
    config = frappe.get_single("Rental Configuration")
    if config.date_display_format != "Hijri":
        return frappe.format_date(date_value)
    hijri = Gregorian(date_value.year, date_value.month, date_value.day).to_hijri()
    return f"{hijri.day} {hijri.month_name()} {hijri.year} ({frappe.format_date(date_value)})"
```

For the Flutter app, the equivalent conversion uses the `hijri` Dart package (added to `pubspec.yaml`). A `DateFormatter` utility in `core/formatting/date_formatter.dart` checks `AppConfig.dateFormat` and returns the appropriate string.

**Acceptance Criteria**:
- [ ] `hijri-converter` added to `pyproject.toml` dependencies
- [ ] Custom Jinja2 filter `|hijri` registered in `hooks.py`
- [ ] When `date_display_format = Hijri`: dates display as "15 Dhul Hijjah 1447 (12 Jun 2026)"
- [ ] When `date_display_format = Gregorian`: dates display in the standard Frappe format
- [ ] All Jinja2 templates that display dates use `{{ date_value | hijri }}` instead of raw `{{ date_value }}`
- [ ] Flutter: `hijri` package added to `pubspec.yaml`
- [ ] Flutter: `DateFormatter.format(date)` returns dual format when Hijri is configured
- [ ] Date storage remains Gregorian ISO in all database fields (no conversion at storage layer)

---

> ⚙️ **FLUTTER FOUNDATION** — The following section (§8) covers the Dart/Flutter project scaffold.
> This section can be assigned to a Flutter-specialist developer independently of §2-§7 (Frappe backend).
> Future refactoring may split this into a separate `D01-F` sub-domain document.

## 8. Flutter — Project Setup & Foundation

### 8.1 Create the App

> **Requires**: Nothing (Flutter work starts independently from Frappe)

The Flutter mobile app is a **separate project** from the Frappe backend. It communicates with the backend exclusively through the API layer (D01-6.x). This subtask creates the Flutter project scaffold targeting both Android and iOS. The app will serve as the customer-facing mobile experience for browsing assets, booking, managing agreements, and making payments.

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

The app uses a curated set of dependencies: **Dio** for HTTP requests, **GoRouter** for declarative routing, **Flutter Riverpod** for state management, **flutter_secure_storage** for credential persistence, **Firebase** for push notifications, **Freezed** for immutable data models, **fl_chart** for utility usage charts, and **connectivity_plus** for offline detection. All versions are pinned to avoid breaking changes.

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

The Dart codebase is organized into four top-level directories: `app/` (configuration, theming, routing), `core/` (shared API client, data models, formatting utilities), `features/` (one folder per user-facing feature: auth, catalog, booking, etc.), and `widgets/` (reusable UI components like buttons, cards, badges). Every file starts as a stub with a valid Dart class or widget — actual logic is added in later domains.

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

The platform is a **white-label product** — each client gets a custom-branded app. Instead of forking the codebase per client, all client-specific values (API URL, brand color, app name, logo, which asset types to show) are injected at build time via `--dart-define` flags. The same source code produces apps for "ClientOne Rentals" (blue, flats only) and "ClientTwo Mobility" (green, vehicles only) just by changing build parameters.

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

User credentials (API key + secret) are stored in the device's **encrypted keychain** (iOS Keychain / Android EncryptedSharedPreferences). This provider exposes `FlutterSecureStorage` as a Riverpod provider so it can be easily overridden in tests with a mock implementation. The storage is the **only place** credentials live on the device — they're never written to plain SharedPreferences or logged.

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

The **FrappeClient** is the app's HTTP layer — every API call goes through it. It wraps Dio with two important behaviors: (1) an **auth interceptor** that reads the API key from secure storage and adds the `Authorization: token key:secret` header to every request, and (2) an **error interceptor** that detects HTTP 401 responses and triggers a global logout (the token might have been revoked server-side). All `get()` and `post()` methods route through Frappe's `/api/method/` convention.

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

The app must **only communicate over HTTPS** — setting `BASE_URL` to `http://` should cause an assertion error in debug mode. For production builds, certificate pinning is recommended to prevent man-in-the-middle attacks (documented as a post-MVP hardening step). The long-term plan is to migrate from API key authentication to OAuth2 with refresh tokens, but API keys are sufficient for the initial release.

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

The **AuthNotifier** is the central authentication state manager for the app. On app startup, it checks secure storage for an existing API key — if found, the user is `authenticated`; otherwise, `unauthenticated`. The `login()` method calls Frappe's login API, stores the returned credentials, registers the device's FCM token for push notifications, and transitions to `authenticated`. The `logout()` method reverses everything: deregisters FCM, calls the server-side logout endpoint, clears all stored credentials, and transitions to `unauthenticated`.

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

The app uses **GoRouter** for declarative, URL-based navigation. The key feature is the `redirect` guard: certain routes (booking, my-rentals, invoices, payments, documents, KYC) require authentication. If an unauthenticated user tries to access them, they're redirected to `/login?from=...` and returned to the original page after successful login. Public routes (catalog, asset detail) are accessible without login.

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

The Dart counterpart to the server-side error envelope (6.1). This Freezed model parses HTTP error responses into typed objects that the UI layer can display meaningfully. `displayMessage` provides a single string for SnackBars and dialogs, while the full `errors` list gives per-field validation messages for form-level error highlighting. The model handles edge cases like null `exc_type` and empty `_server_messages` without crashing.

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

The app must remain **usable when offline** for read-heavy screens. The strategy varies by data type: the asset catalog uses `keepAlive` with stale-while-revalidate (show cached data immediately, refresh in background), asset details are cached per ID and refreshed on pull, agreements are cached but invalidated on screen focus, and invoices are always fetched fresh (financial data must never be stale). The most critical offline behavior is the **booking outbox**: if a user submits a booking while offline, it's serialized to local storage and automatically retried when connectivity returns.

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

### 8.12 Registration Screen (Flutter)

> **Requires**: 7.8 (registration API must exist), 8.6 (FrappeClient), 8.8 (AuthNotifier)

The Flutter counterpart to the web registration page (7.8). The app's login screen includes a "Don't have an account? Sign up" link that navigates to the registration screen. The registration form mirrors the web form: full name, email, phone, password, and a confirm password field.

On successful submission, the screen shows a **success overlay**: "Check your email to verify your account" with an illustration and a "Go to Login" button. The user must verify via email before logging in — this is the same flow as the web, ensuring consistency regardless of which platform the customer uses to register.

The registration screen is an **unauthenticated route** — it's accessible without login (obviously, since the user doesn't have an account yet). It's also excluded from the GoRouter guard list (8.9).

Form validation is done **inline** as the user types: email format check (shows "Invalid email" under the field), password strength indicator (weak/medium/strong with color coding), and confirm password match check. The submit button is disabled until all validations pass.

**Acceptance Criteria**:
- [ ] Registration screen accessible from the login screen via "Sign up" link
- [ ] Form includes: full name, email, phone, password, confirm password
- [ ] Inline validation: email format, password min 8 chars, confirm password match
- [ ] Successful registration shows success overlay with "Go to Login" button
- [ ] Registration calls the same `register_customer` API endpoint (7.8)
- [ ] Rate-limited registration returns a user-friendly error via `ApiError` model (8.10)
- [ ] Duplicate email error displays "An account with this email already exists"
- [ ] Registration screen is excluded from GoRouter auth guard (no redirect to login)

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
