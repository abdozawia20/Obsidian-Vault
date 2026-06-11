# Base — Frappe: Technical Document

> **Product**: Asset Rental Platform
> **Module**: `rental_core` — Shared Backend Foundation
> **Document Type**: Technical
> **Audience**: Backend developers (Python/Frappe)
> **Companion**: [[../Base Overview|Base Platform Overview]]

---

## 1. App Scaffold

```bash
bench new-app rental_core
# App name: rental_core | Title: Rental Core | Publisher: Your Org
bench --site rental.localhost install-app rental_core
```

---

## 2. Directory Layout

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
│   │   └── asset_catalog_query.py        ← shared SSR + API query logic
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

---

## 3. DocType Schemas

### 3.1 `Rental Asset`

| Field | Type | Required | Notes |
|---|---|---|---|
| `asset_name` | Data | ✅ | |
| `asset_code` | Data | ✅ | Auto: `FL-XXXXXXXX` / `VH-XXXXXXXX` |
| `asset_type` | Select | ✅ | `Flat`, `Vehicle` |
| `status` | Select | ✅ | `Available`, `Reserved`, `Rented`, `Maintenance`, `Retired` |
| `location` | Data | | City/region |
| `geo_lat` | Float | | |
| `geo_lng` | Float | | |
| `monthly_rate` | Currency | ✅ | |
| `deposit_amount` | Currency | ✅ | |
| `description` | Text Editor | | |
| `images` | Table | | Child: `Asset Image` |
| `is_active` | Check | | Default 1 |
| `custom_preview_mode` | Select | | `None`, `Embed URL`, `3D Model (GLB)`, `360° Photo Sphere` |
| `custom_preview_embed_url` | Data | | |
| `custom_preview_model_file` | Attach | | |
| `custom_preview_sphere_file` | Attach | | |

**Naming series**: `{FL|VH}-{8-char hash}` set in `autoname()`.
**Controller**: `set_status(status)` — atomic DB write, validates allowed transitions.

### 3.2 `Rental Lead`

| Field | Type | Required | Notes |
|---|---|---|---|
| `lead_name` | Data | auto | Series: `RL-.YYYY.-.####` |
| `customer_name` | Data | ✅ | Full name of the inquirer |
| `email` | Data | ✅ | |
| `phone` | Data | | |
| `source` | Select | ✅ | `Web Form`, `Mobile App`, `Walk-In`, `Phone`, `Referral` |
| `asset_type` | Select | | `Flat`, `Vehicle` |
| `preferred_asset` | Link → Rental Asset | | If the customer inquired about a specific asset |
| `preferred_location` | Data | | |
| `budget_range` | Data | | Free text: "2000–3000 AED/month" |
| `notes` | Text | | Internal notes by agent |
| `status` | Select | ✅ | `New`, `Contacted`, `Qualified`, `Converted`, `Lost` |
| `assigned_to` | Link → User | | The Rental Agent working this lead |
| `follow_up_date` | Date | | Next follow-up reminder |
| `converted_to` | Link → Rental Quotation | | Set on conversion |

**Controller**:
- `validate` → ensure `email` format, prevent duplicate active leads for same email + asset
- `on_update` → if `status` changes to `Converted`, create `Rental Quotation` and link it

### 3.3 `Rental Quotation`

| Field | Type | Required | Notes |
|---|---|---|---|
| `quotation_number` | Data | auto | Series: `RQ-.YYYY.-.####` |
| `lead` | Link → Rental Lead | | Source lead (nullable for direct quotations) |
| `customer_name` | Data | ✅ | |
| `email` | Data | ✅ | |
| `asset` | Link → Rental Asset | ✅ | |
| `proposed_start_date` | Date | ✅ | |
| `proposed_end_date` | Date | | Null = open-ended |
| `proposed_rate` | Currency | ✅ | Can differ from asset's listed rate (negotiated) |
| `deposit_amount` | Currency | ✅ | |
| `billing_cycle` | Select | ✅ | `Monthly`, `Weekly`, `Daily` |
| `valid_until` | Date | ✅ | Quotation expiry |
| `notes` | Text | | Terms, special conditions |
| `status` | Select | ✅ | `Draft`, `Sent`, `Accepted`, `Rejected`, `Expired` |
| `quotation_pdf` | Attach | | Generated PDF sent to customer |

**Controller**:
- `validate` → check asset availability for proposed dates, ensure `valid_until` ≥ today
- `on_submit` → email the quotation PDF to the customer
- Scheduled: daily job marks `Sent` quotations past `valid_until` as `Expired`

### 3.4 `Rental Agreement`

| Field | Type | Required | Notes |
|---|---|---|---|
| `agreement_number` | Data | auto | Series: `RNT-.YYYY.-.####` |
| `asset` | Link → Rental Asset | ✅ | |
| `tenant_type` | Select | ✅ | `Individual`, `Company` |
| `customer` | Link → Customer | ✅ | ERPNext Customer |
| `start_date` | Date | ✅ | |
| `end_date` | Date | | Null = open-ended |
| `billing_cycle` | Select | ✅ | `Monthly`, `Weekly`, `Daily` |
| `monthly_rate` | Currency | ✅ | Editable copy from asset |
| `deposit_amount` | Currency | ✅ | |
| `deposit_status` | Select | | `Held`, `Partially Released`, `Refunded` |
| `status` | Select | ✅ | `Draft`, `Active`, `Expired`, `Terminated` |
| `signed_agreement` | Attach | | Generated PDF |
| `signature_data` | Long Text | | Base64 canvas |
| `additional_charges` | Table | | Child: `Additional Charge` |
| `erpnext_subscription` | Link → Subscription | | Set on submit |
| `notes` | Text | | Internal only |

**Key controller events**:
- `validate` → check asset availability + date logic. Child apps hook additional validations via `doc_events` (e.g., insurance check from `rental_flats`)
- `on_submit` → `asset.set_status("Rented")` + `create_subscription()` + create `Deposit Ledger`
- `on_cancel` → `asset.set_status("Available")` + cancel subscription
- `on_invoice_created(invoice_name)` → **hook point** for child apps to inject variant-specific charges (utility billing, overage, etc.)

### 3.5 `Deposit Ledger`

| Field | Type |
|---|---|
| `agreement` | Link → Rental Agreement |
| `customer` | Link → Customer |
| `original_amount` | Currency |
| `deductions` | Table → `Deposit Deduction` (reason, amount, reference, date) |
| `refunded_amount` | Currency |
| `balance` | Currency (computed: original − Σdeductions − refunded) |
| `status` | Select: `Held`, `Partially Released`, `Fully Refunded` |

### 3.6 `Asset Inspection`

| Field | Type |
|---|---|
| `agreement` | Link → Rental Agreement |
| `asset` | Link → Rental Asset |
| `inspection_type` | Select: `Entry`, `Exit` |
| `inspection_date` | Date |
| `inspector` | Link → User |
| `checklist` | Table (child app provides rows) |
| `photos` | Table → `Inspection Photo` |
| `damage_notes` | Text |
| `estimated_repair_cost` | Currency |
| `signed_by_tenant` | Check |

**On submit (Exit type)**: compute total damage → append to `Deposit Ledger.deductions`.

### 3.7 `Rental Notification Log`

| Field | Type |
|---|---|
| `agreement` | Link → Rental Agreement |
| `customer` | Link → Customer |
| `channel` | Select: Email, SMS, WhatsApp, Push |
| `notification_type` | Select: Payment Due, Overdue, Renewal, Maintenance, General |
| `sent_at` | Datetime |
| `status` | Select: Sent, Failed, Bounced |
| `message_preview` | Small Text |
| `error_log` | Text |

### 3.8 `Payment Webhook Log`

| Field | Type | Notes |
|---|---|---|
| `gateway` | Select | `Stripe`, `Tap`, `PayMob` |
| `event_id` | Data (unique) | Gateway's unique event identifier — used for idempotency |
| `event_type` | Data | e.g., `payment_intent.succeeded`, `charge.completed` |
| `payload` | JSON | Full raw webhook body |
| `invoice` | Link → Sales Invoice | Resolved after processing |
| `processed` | Check | Set to 1 after successful handling |
| `processing_error` | Text | Error details if processing failed |
| `received_at` | Datetime | Timestamp of receipt |

**Idempotency**: Before processing, check `frappe.db.exists("Payment Webhook Log", {"event_id": event_id})`. If exists and `processed = 1`, return `{"status": "duplicate"}` with HTTP 200.

### 3.9 `Rental Configuration` (Singleton)

| Field | Type |
|---|---|
| `country` | Link → Country |
| `default_currency` | Link → Currency |
| `tax_template` | Link → Sales Taxes and Charges Template |
| `payment_gateway` | Select: Stripe, Tap, PayMob, Bank Transfer |
| `payment_gateway_api_key` | Password |
| `payment_gateway_secret` | Password |
| `kyc_id_types` | Table → `KYC ID Type` |
| `contract_language` | Select |
| `grace_period_days` | Int (default 5) |
| `late_fee_type` | Select: Fixed, Percentage |
| `late_fee_value` | Float |
| `renewal_alert_days` | Int (default 30) |
| `electricity_rate_per_unit` | Currency |
| `water_rate_per_unit` | Currency |
| `gas_rate_per_unit` | Currency |
| `aws_access_key` / `aws_secret_key` | Password |
| `aws_region` / `s3_media_bucket` / `cdn_base_url` | Data |
| `license_key` | Data |

> [!IMPORTANT]
> **Secret field access control**: All `Password` fields (`payment_gateway_api_key`, `payment_gateway_secret`, `aws_access_key`, `aws_secret_key`) must be restricted to the `Administrator` role only. Regular `System Manager` users should not see these values. For maximum security, consider moving gateway secrets to `site_config.json` so they are never stored in the database.

---

## 4. `hooks.py`

```python
app_name = "rental_core"
required_apps = ["frappe", "erpnext"]

scheduler_events = {
    "daily": [
        "rental_core.scheduler_events.send_payment_reminders",
        "rental_core.scheduler_events.check_contract_renewals",
        "rental_core.scheduler_events.auto_apply_late_fees",
        "rental_core.scheduler_events.expire_stale_quotations",
    ],
    "monthly": ["rental_core.scheduler_events.generate_monthly_report"],
}

on_session_creation = "rental_core.licensing.license_validator.validate_license"

doc_events = {
    "Subscription": {"on_submit": "rental_core.billing.subscription_factory.on_subscription_submit"},
    "Sales Invoice": {"on_submit": "rental_core.billing.subscription_factory.on_invoice_submit"},
    "Payment Entry": {"on_submit": "rental_core.billing.subscription_factory.on_payment_submit"},
}

# Child apps (rental_flats, rental_vehicles) register their own doc_events
# to extend Rental Agreement validation and invoice enrichment.
# Example in rental_flats/hooks.py:
#   doc_events = {
#       "Rental Agreement": {
#           "on_invoice_created": "rental_flats.billing.utility_injector.attach_unbilled_utilities"
#       }
#   }

portal_menu_items = [
    {"title": "My Rentals",   "route": "/my-rentals",   "role": "Customer"},
    {"title": "My Invoices",  "route": "/my-invoices",  "role": "Customer"},
    {"title": "My Documents", "route": "/my-documents", "role": "Customer"},
]

website_route_rules = [
    {"from_route": "/rentals/<asset>",      "to_route": "rentals/{asset}"},
    {"from_route": "/rentals/<asset>/book", "to_route": "rentals/{asset}/book"},
]
```

---

## 5. Billing Engine (`billing/subscription_factory.py`)

> [!NOTE]
> The billing engine has **zero knowledge of child apps**. Variant-specific charge injection (utility billing for flats, overage for vehicles) is handled via Frappe `doc_events` hooks registered by each child app in their own `hooks.py`.

```python
def create_subscription(agreement) -> str:
    config = frappe.get_single("Rental Configuration")
    plan = frappe.get_doc({
        "doctype": "Subscription Plan",
        "plan_name": f"Plan for {agreement.name}",
        "item": get_or_create_rental_item(agreement),
        "price": agreement.monthly_rate,
        "billing_interval": "Month" if agreement.billing_cycle == "Monthly" else "Day",
        "billing_interval_count": 1,
        "currency": config.default_currency,
    }).insert(ignore_permissions=True)

    sub = frappe.get_doc({
        "doctype": "Subscription",
        "party_type": "Customer", "party": agreement.customer,
        "plans": [{"plan": plan.name, "qty": 1}],
        "start": agreement.start_date, "end": agreement.end_date,
        "generate_invoice_at_period_start": 1,
        "taxes_and_charges": config.tax_template,
        "days_until_due": 7,
        "custom_rental_agreement": agreement.name,
    }).insert(ignore_permissions=True)
    sub.submit()
    return sub.name

def on_subscription_submit(doc, method):
    """Called by ERPNext when a new invoice is auto-generated by Subscription.
    
    This method fires the `on_invoice_created` hook on the Rental Agreement,
    allowing child apps to inject variant-specific charges (e.g., utility
    billing from rental_flats, overage from rental_vehicles).
    """
    agreement_name = doc.get("custom_rental_agreement")
    if not agreement_name:
        return
    agreement = frappe.get_doc("Rental Agreement", agreement_name)
    agreement.run_method("on_invoice_created", doc.name)
```

---

## 6. Scheduler Events (`scheduler_events.py`)

```python
def send_payment_reminders():
    # Upcoming invoices (due in next 3 days)
    upcoming = frappe.db.get_all("Sales Invoice", filters={
        "status": "Unpaid",
        "due_date": ["between", [today(), add_days(today(), 3)]],
        "custom_rental_agreement": ["!=", ""],
    }, fields=["name", "customer", "due_date", "grand_total", "custom_rental_agreement"])
    for inv in upcoming:
        send_reminder(inv, "Payment Due")

def check_contract_renewals():
    config = frappe.get_single("Rental Configuration")
    target = add_days(today(), config.renewal_alert_days or 30)
    expiring = frappe.db.get_all("Rental Agreement", filters={
        "status": "Active", "end_date": ["between", [today(), target]],
    }, fields=["name", "customer", "end_date", "asset"])
    for agr in expiring:
        send_reminder(agr, "Renewal")

def auto_apply_late_fees():
    config = frappe.get_single("Rental Configuration")
    overdue = frappe.db.get_all("Sales Invoice", filters={
        "status": ["in", ["Unpaid", "Overdue"]],
        "due_date": ["<", add_days(today(), -(config.grace_period_days or 5))],
        "custom_late_fee_applied": 0,
        "custom_rental_agreement": ["!=", ""],
    }, fields=["name", "grand_total", "customer"])
    for inv in overdue:
        apply_late_fee(inv, config)

def expire_stale_quotations():
    """Mark quotations past their valid_until date as Expired."""
    stale = frappe.db.get_all("Rental Quotation", filters={
        "status": "Sent",
        "valid_until": ["<", today()],
    }, fields=["name"])
    for q in stale:
        frappe.db.set_value("Rental Quotation", q.name, "status", "Expired")
```

---

## 7. Notification Pipeline (`notification_pipeline/reminder_dispatcher.py`)

```python
CHANNELS = ["Email", "SMS", "Push"]

def send_reminder(doc, notification_type: str):
    customer = frappe.get_doc("Customer", doc.customer)
    context = build_context(doc, customer, notification_type)
    for channel in CHANNELS:
        try:
            dispatch(channel, customer, context, notification_type)
            log_notification(doc, customer, channel, notification_type, "Sent", context)
        except Exception as e:
            log_notification(doc, customer, channel, notification_type, "Failed", context, error=str(e))
```

---

## 8. Payment Gateway Routing (`payment_routing/gateway_router.py`)

```python
GATEWAY_MAP = {
    "Stripe":        "rental_core.gateways.stripe_gateway",
    "Tap":           "rental_core.gateways.tap_gateway",
    "PayMob":        "rental_core.gateways.paymob_gateway",
    "Bank Transfer": "rental_core.gateways.manual_gateway",
}

def get_payment_link(invoice_name: str) -> str:
    config = frappe.get_single("Rental Configuration")
    gateway = frappe.get_attr(GATEWAY_MAP[config.payment_gateway])
    return gateway.create_payment_link(invoice_name)
```

Each gateway module exposes `create_payment_link(invoice_name) -> str`.

---

## 9. Webhook Handler (`payment_routing/webhook_handler.py`)

> [!IMPORTANT]
> All inbound payment webhooks must pass HMAC signature validation and idempotency checks before processing.

```python
import hashlib, hmac, json

HMAC_HEADER_MAP = {
    "Stripe": "Stripe-Signature",
    "Tap":    "X-Tap-Signature",
    "PayMob": "X-PayMob-Signature",
}

@frappe.whitelist(allow_guest=True, methods=["POST"])
@frappe.rate_limiter(limit=30, seconds=60)
def payment_webhook():
    """Receives payment gateway callbacks. Validates HMAC, checks idempotency,
    processes payment, and logs the event."""
    config = frappe.get_single("Rental Configuration")
    gateway = identify_gateway(frappe.request.headers)
    payload = frappe.request.get_data(as_text=True)

    # 1. HMAC validation
    expected_sig = frappe.request.headers.get(HMAC_HEADER_MAP.get(gateway, ""))
    secret = config.get_password("payment_gateway_secret")
    computed_sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_sig, expected_sig or ""):
        frappe.throw("Invalid webhook signature", frappe.AuthenticationError)

    # 2. Idempotency check
    event_id = extract_event_id(gateway, json.loads(payload))
    if frappe.db.exists("Payment Webhook Log", {"event_id": event_id, "processed": 1}):
        return {"status": "duplicate"}

    # 3. Log the event
    log = frappe.get_doc({
        "doctype": "Payment Webhook Log",
        "gateway": gateway,
        "event_id": event_id,
        "event_type": extract_event_type(gateway, json.loads(payload)),
        "payload": payload,
        "received_at": frappe.utils.now_datetime(),
    }).insert(ignore_permissions=True)

    # 4. Process payment
    try:
        invoice_name = resolve_invoice(gateway, json.loads(payload))
        process_payment(invoice_name, json.loads(payload))
        log.invoice = invoice_name
        log.processed = 1
        log.save(ignore_permissions=True)
    except Exception as e:
        log.processing_error = str(e)
        log.save(ignore_permissions=True)
        frappe.log_error(title=f"Webhook processing failed: {event_id}")

    return {"status": "ok"}
```

---

## 10. License Enforcement (`licensing/license_validator.py`)

```python
def validate_license(login_manager=None):
    lic = frappe.get_single("Rental Configuration")
    # 1. Check local expiry (fast, no network)
    if is_locally_expired(lic.license_key):
        frappe.throw("Your rental platform license has expired. Contact support.")
    # 2. Remote validation once per 24h (store last validated timestamp)
    if needs_remote_check():
        validate_remote(lic.license_key)   # POST to central license server
    # 3. On network failure: allow gracefully (offline tolerance window: 7 days)
```

---

## 11. Catalog Query Service (`catalog/asset_catalog_query.py`)

> [!NOTE]
> **Single source of truth** for asset filtering — used by both the SSR web controller (`www/rentals.py`) and the REST API (`api/assets.py`). This prevents filter logic divergence between the two code paths.

```python
import re

def query_available_assets(
    asset_type: str = "",
    location: str = "",
    max_price: float = None,
    page: int = 1,
    page_size: int = 12,
    extra_filters: dict = None,
) -> dict:
    """Returns {"assets": [...], "total": int, "page": int, "page_size": int, "has_next": bool}"""
    filters = {"status": "Available", "is_active": 1}
    if asset_type in ("Flat", "Vehicle"):
        filters["asset_type"] = asset_type
    if max_price:
        filters["monthly_rate"] = ["<=", float(max_price)]
    if location:
        # Sanitize: strip SQL wildcards, cap length to prevent pattern abuse
        safe_location = re.sub(r'[%_]', '', location)[:50]
        if safe_location:
            filters["location"] = ["like", f"%{safe_location}%"]
    if extra_filters:
        filters.update(extra_filters)

    total = frappe.db.count("Rental Asset", filters)
    offset = (page - 1) * page_size

    assets = frappe.get_all("Rental Asset",
        filters=filters,
        fields=["name", "asset_name", "asset_type", "location",
                "monthly_rate", "deposit_amount",
                "custom_bedrooms", "custom_seats", "status"],
        limit_start=offset, limit_page_length=page_size,
        order_by="monthly_rate asc",
    )

    # Batch cover image query — single SQL instead of N+1
    if assets:
        asset_names = [a.name for a in assets]
        images = frappe.db.sql("""
            SELECT parent, image FROM `tabAsset Image`
            WHERE parent IN %(assets)s AND idx = 1
        """, {"assets": asset_names}, as_dict=True)
        image_map = {i.parent: i.image for i in images}
        for a in assets:
            a.cover_image = image_map.get(a.name, "/assets/rental_core/images/placeholder.jpg")

    return {
        "assets": assets,
        "total": total,
        "page": page,
        "page_size": page_size,
        "has_next": (offset + page_size) < total,
    }
```

---

## 12. REST API Endpoints

### 12.1 Endpoint Table

| Method | Auth | Rate Limit | Description |
|---|---|---|---|
| `get_available_assets(asset_type, location, max_price, page, page_size)` | Token | 60/min | Browse/filter catalog |
| `get_asset_detail(asset_name)` | Token | 60/min | Full asset + type-specific custom fields |
| `get_asset_availability(asset_name, year, month)` | Token | 60/min | Blocked date ranges (opaque) |
| `submit_booking_request(...)` | Token | 10/min | Create Draft Agreement |
| `get_my_agreements()` | Token | 30/min | Customer's own agreements |
| `sign_agreement(agreement_name, signature_data)` | Token | 10/min | Store e-signature |
| `get_outstanding_invoices()` | Token | 30/min | Unpaid/overdue invoices |
| `get_payment_link(invoice_name)` | Token | 10/min | Gateway-specific payment URL |
| `register_push_token(token)` | Token | 10/min | Save FCM token |
| `payment_webhook()` | Guest (HMAC) | 30/min | Inbound payment callback |

### 12.2 Error Response Contract

> [!IMPORTANT]
> All API endpoints return errors in a consistent envelope format. Both Web (JS) and Flutter clients must handle this structure.

**HTTP Status Codes**:

| Code | Meaning | When |
|---|---|---|
| `200` | Success | Request processed successfully |
| `400` | Validation Error | Missing/invalid fields, business rule violation |
| `401` | Unauthenticated | Missing or invalid API token |
| `403` | Forbidden | User doesn't have permission (e.g., cross-customer access) |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Concurrency conflict (e.g., asset already reserved) |
| `429` | Rate Limited | Too many requests |

**Error Response Body**:

```json
{
  "message": null,
  "exc_type": "ValidationError",
  "errors": [
    {"field": "start_date", "message": "Start date must be in the future"},
    {"field": "end_date", "message": "End date must be after start date"}
  ],
  "_server_messages": ["[\"Asset is no longer available\"]"]
}
```

### 12.3 Pagination Response Format

All list endpoints return:

```json
{
  "assets": [ ... ],
  "total": 142,
  "page": 2,
  "page_size": 12,
  "has_next": true
}
```

---

## 13. Child App Extension Pattern

> [!IMPORTANT]
> `rental_core` has **zero imports** from child apps (`rental_flats`, `rental_vehicles`). All extension points use Frappe's native `doc_events` hook system. This means adding a new variant (e.g., `rental_equipment`) requires zero changes to core.

### Extension Points

| Hook | Fired When | Purpose |
|---|---|---|
| `Rental Agreement.validate` | Agreement is being validated | Child app adds variant-specific checks (e.g., insurance validation for flats, license validation for vehicles) |
| `Rental Agreement.on_invoice_created` | New subscription invoice is generated | Child app injects variant-specific line items (e.g., utility charges for flats) |
| `Rental Asset.before_save` | Asset is saved | Child app can enrich custom fields |

### Example: `rental_flats/hooks.py`

```python
doc_events = {
    "Rental Agreement": {
        "validate": "rental_flats.validation.insurance_gate.check_mandatory_coverage",
        "on_invoice_created": "rental_flats.billing.utility_injector.attach_unbilled_utilities",
    }
}
```

### Example: `rental_vehicles/hooks.py`

```python
doc_events = {
    "Rental Agreement": {
        "validate": "rental_vehicles.validation.document_gate.check_registration_expiry",
    }
}
```

---

## 14. Testing Checklist

- [ ] Agreement submit → asset status `Rented` + Subscription created + Deposit Ledger created
- [ ] Agreement cancel → asset status `Available` + Subscription cancelled
- [ ] Late fee fires only after grace period; `custom_late_fee_applied` prevents duplicates
- [ ] Notification log captures all channels including failure reason
- [ ] License validation blocks login on expired key; tolerates network outage for 7 days
- [ ] `get_asset_availability` merges all blocking sources (agreements + maintenance + inspections)
- [ ] Payment link resolves to correct gateway per `Rental Configuration`
- [ ] Each API endpoint returns HTTP 403 for unauthenticated / cross-customer requests
- [ ] Webhook HMAC validation rejects invalid signatures with 401
- [ ] Duplicate webhook `event_id` returns `{"status": "duplicate"}` without re-processing
- [ ] Catalog query returns correct pagination metadata (`total`, `has_next`)
- [ ] Lead → Quotation conversion sets `converted_to` link
- [ ] Stale quotations are expired daily by scheduler
- [ ] Rate limiter triggers 429 on excessive API calls
- [ ] Child app hooks fire correctly during agreement validation and invoice creation
- [ ] `on_invoice_created` hook is called for each new subscription-generated invoice
