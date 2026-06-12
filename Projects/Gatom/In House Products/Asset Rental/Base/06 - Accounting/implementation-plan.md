# Domain 06 — Accounting: Implementation Plan

> **Variant**: Base
> **Domain**: Accounting
> **Sequence**: 6 of 8
> **Depends on**: Domain 01 (config + gateway keys), Domain 05 (agreements + subscriptions)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

This domain handles **all the money**: invoice generation, payment processing, late fees, deposit management, and webhook handling. Invoices are generated automatically via ERPNext's Subscription engine (linked to each Rental Agreement). Payments are routed through a configurable gateway (Stripe, Tap, or manual bank transfer). Late fees are applied after a configurable grace period. The deposit lifecycle tracks the tenant's security deposit from collection through potential deductions (for damage) to final refund.

The domain also includes the **webhook handler** that receives payment confirmations from external gateways and creates Payment Entries in ERPNext, ensuring the books stay reconciled.

---

## 2. Frappe — Billing Engine

### 2.1 Subscription Factory (`billing/subscription_factory.py`)

> **Requires**: D05-2.1 (Rental Agreement with `billing_cycle`, `monthly_rate`), D01-3.1 (config with `tax_template`)

The **subscription factory** bridges the rental agreement to ERPNext's billing engine. When a new agreement is submitted (D05-2.2), this function creates: (1) a non-stock `Item` representing the rent charge for this specific asset, and (2) an ERPNext `Subscription` that auto-generates Sales Invoices on the configured billing cycle (monthly, weekly, or daily). The Subscription is the billing clock — it fires automatically and creates invoices without manual intervention.

```python
def create_subscription(agreement):
    item = frappe.get_doc({
        "doctype": "Item",
        "item_name": f"Rent – {agreement.asset}",
        "item_group": "Rental Services",
        "is_stock_item": 0,
    }).insert(ignore_if_duplicate=True)
    sub = frappe.get_doc({
        "doctype": "Subscription",
        "party_type": "Customer",
        "party": agreement.customer,
        "plans": [{"plan": item.name, "qty": 1, "rate": agreement.monthly_rate}],
        "start_date": agreement.start_date,
        "billing_interval": agreement.billing_cycle.lower(),
    })
    sub.insert()
    sub.submit()
    return sub.name
```

**Acceptance Criteria**:
- [ ] `create_subscription()` creates a non-stock Item + Subscription
- [ ] Subscription `party` matches the agreement's customer
- [ ] Subscription `rate` matches the agreement's `monthly_rate`
- [ ] `billing_interval` maps correctly: `Monthly` → `monthly`, `Weekly` → `weekly`, `Daily` → `daily`
- [ ] Subscription is submitted (not left in Draft)
- [ ] Duplicate Item for same asset doesn't crash (`ignore_if_duplicate`)

---

### 2.2 `on_invoice_submit` Hook

> **Requires**: 2.1, D01-2.3 (hooks.py registers this event)

A **doc_events hook** that fires whenever a Sales Invoice is submitted in ERPNext. It checks whether the invoice is linked to a rental subscription; if so, it sends the tenant a notification (push + email) with the invoice amount and due date. Non-rental invoices (e.g., a one-off sales invoice) are silently ignored. This ensures tenants are immediately aware of new charges without manual communication.

```python
def on_invoice_submit(doc, method):
    agreement = get_agreement_from_subscription(doc.subscription)
    if not agreement:
        return
    send_invoice_notification(agreement, doc)
    log_to_notification_log(agreement, "Invoice Created", doc.name)
```

**Acceptance Criteria**:
- [ ] When Subscription generates a Sales Invoice and it's submitted, hook fires
- [ ] Customer receives push + email notification with invoice amount and due date
- [ ] Notification logged in `Rental Notification Log`
- [ ] Invoices not linked to a rental agreement are ignored (hook returns early)

---

### 2.3 `on_payment_submit` Hook

> **Requires**: 2.2, D01-2.3 (hooks.py registers this event)

Fires when a **Payment Entry** (the ERPNext record of a payment received) is submitted. If the payment is against a rental invoice, a receipt email is sent to the customer. This provides instant payment confirmation and audit logging. Non-rental Payment Entries are ignored.

**Acceptance Criteria**:
- [ ] When Payment Entry is submitted against a rental invoice, hook fires
- [ ] Payment receipt email sent to customer
- [ ] `Rental Notification Log` entry created with `notification_type = Payment Received`
- [ ] Non-rental Payment Entries are ignored

---

### 2.4 First-Invoice Pro-Ration

> **Requires**: 2.1 (subscription factory), D05-2.1 (agreement with start_date)

Functional requirement BR-041 states: "The first invoice in a billing period must be pro-rated if the agreement starts mid-period." ERPNext Subscriptions generate invoices based on a fixed calendar cycle (e.g., 1st of every month). If an agreement starts on the 15th, the first invoice should only cover 15 days, not the full month.

ERPNext Subscriptions do NOT automatically pro-rate the first invoice. Custom logic is required in the `on_invoice_created` hook (2.5) to detect the first invoice and adjust its amount.

The pro-ration formula is:
```
pro_rated_amount = (monthly_rate / days_in_period) * remaining_days
```

For example, if monthly rent is 3,000 AED and the agreement starts on June 15th (30-day month):
```
pro_rated_amount = (3000 / 30) * 16 = 1,600 AED
```

The pro-ration applies to the **base rent** and all `Per Invoice` additional charges (D05-2.5). One-time charges are NOT pro-rated — they appear in full on the first invoice.

Detection logic: an invoice is the "first" if the agreement's `start_date` is within the invoice's billing period and it's the earliest invoice for that subscription.

**Acceptance Criteria**:
- [ ] Agreement starting mid-month → first invoice pro-rated to remaining days
- [ ] Pro-ration formula: `(rate / days_in_period) * remaining_days`
- [ ] Additional charges with `Per Invoice` frequency are also pro-rated
- [ ] Additional charges with `One-Time` frequency are NOT pro-rated
- [ ] Agreement starting on the 1st → no pro-ration (full amount)
- [ ] Pro-rated amount is rounded to 2 decimal places
- [ ] Invoice line item shows "Pro-rated: X days" in the description

---

### 2.5 `on_invoice_created` Custom Event

> **Requires**: 2.1, D01-2.3 (hooks.py)

This is a **custom event** (not a standard Frappe doc_event) that the subscription factory fires whenever a new Sales Invoice is generated by the Subscription engine. It serves as the **extension point** for child apps to inject variant-specific line items onto invoices.

The standard Frappe `doc_events` system only supports events on DocType CRUD operations (validate, on_submit, etc.). But the rental platform needs a hook that fires specifically when a **subscription generates** an invoice — not when any Sales Invoice is created. This custom event is dispatched from within the `on_invoice_submit` hook (2.2), after verifying the invoice is rental-linked.

Child apps register handlers in their `hooks.py`:
```python
# In rental_flats/hooks.py
rental_hooks = {
    "on_invoice_created": "rental_flats.billing.inject_utility_charges"
}
```

The base module's dispatcher iterates over all registered handlers:
```python
def dispatch_on_invoice_created(invoice, agreement):
    from frappe import get_hooks
    handlers = get_hooks("rental_hooks", {}).get("on_invoice_created", [])
    for handler in handlers:
        frappe.call(handler, invoice=invoice, agreement=agreement)
```

This allows `rental_flats` to inject utility meter readings as line items, and `rental_vehicles` to inject mileage overage charges — all without the base module knowing about flats or vehicles.

**Acceptance Criteria**:
- [ ] Custom event `on_invoice_created` fires when Subscription generates an invoice
- [ ] Handler receives both the `invoice` and `agreement` objects
- [ ] Child apps can register handlers via `rental_hooks.on_invoice_created` in their hooks.py
- [ ] Multiple handlers from different child apps execute in registration order
- [ ] If no handlers are registered, the event fires without error (empty list)
- [ ] Handler errors are logged but do NOT prevent invoice submission

---

### 2.6 B2B / B2C Invoice Template Routing

> **Requires**: 2.2 (on_invoice_submit hook), D01-3.1 (`b2b_invoice_template`, `b2c_invoice_template` config fields)

The Rental Configuration includes separate print format templates for B2B and B2C invoices (D01-3.1). B2B invoices (Company customers) typically show the company's trade license number, tax registration ID, and a formal legal address. B2C invoices (Individual customers) show the individual's name and a simplified layout.

The template routing happens in the `on_invoice_submit` hook (2.2). After sending the notification, the hook checks the customer's `customer_type` field (Individual vs. Company) and sets the invoice's `print_format` field accordingly.

```python
def _apply_print_format(doc, agreement):
    config = frappe.get_single("Rental Configuration")
    customer_type = frappe.db.get_value("Customer", agreement.customer, "customer_type")
    if customer_type == "Company":
        doc.db_set("print_format", config.b2b_invoice_template)
    else:
        doc.db_set("print_format", config.b2c_invoice_template)
```

**Acceptance Criteria**:
- [ ] Company customer → invoice uses `b2b_invoice_template` print format
- [ ] Individual customer → invoice uses `b2c_invoice_template` print format
- [ ] If templates are not configured → default ERPNext print format is used (no error)
- [ ] Template routing happens automatically (no manual selection by accountant)

---

### 2.7 Deferred Revenue Accounting — Documentation

> **Requires**: 2.1 (subscription factory), D01-2.2 (app scaffold)

Functional requirement BR-045 states: "Deferred revenue accounting must be supportable for prepaid agreements." Some tenants pay quarterly or annually upfront. Under accrual accounting, this upfront payment must be recognized as revenue over the rental period, not all at once.

ERPNext supports deferred revenue natively via the "Enable Deferred Revenue" checkbox on Sales Invoice Items and a linked Deferred Revenue Account. The platform does NOT implement custom deferred revenue logic — it **documents** how the operator's accountant should configure ERPNext's built-in feature.

This subtask creates a **documentation page** (stored as a markdown file in the app's `docs/` directory and accessible from Frappe Desk's Help menu) covering:
1. When to enable deferred revenue (prepaid agreements only)
2. Which ERPNext account to use as the Deferred Revenue Account
3. How the Subscription auto-handles the monthly recognition journal entries
4. How to verify the deferred balance via the General Ledger report

> [!IMPORTANT]
> The platform does NOT automate deferred revenue setup — it provides documentation. Correct account configuration is the client accountant's responsibility.

**Acceptance Criteria**:
- [ ] Documentation file exists at `rental_core/docs/deferred-revenue-guide.md`
- [ ] Covers: when to enable, account setup, verification steps
- [ ] Accessible from Frappe Desk Help menu
- [ ] Explicitly states this is the accountant's responsibility (not automated)

---

### 2.8 PDF Payment Receipt Generation

> **Requires**: 2.3 (on_payment_submit hook)

Functional requirement BR-055 states: "PDF receipts must be auto-generated on payment confirmation." When a Payment Entry is submitted against a rental invoice, the system generates a PDF receipt using ERPNext's built-in print format system. The PDF is: (1) attached to the Payment Entry record (for back-office access), (2) emailed to the customer as an attachment alongside the payment confirmation notification (D07), and (3) downloadable from the customer's My Invoices portal page.

The receipt includes: tenant name, invoice number, payment date, amount paid, payment method, remaining balance (if partial payment), and the operator's business details.

```python
def _generate_receipt_pdf(payment_entry):
    pdf = frappe.get_print("Payment Entry", payment_entry.name, 
                           print_format="Rental Payment Receipt")
    file_doc = save_file(f"receipt-{payment_entry.name}.pdf", pdf, 
                          "Payment Entry", payment_entry.name, is_private=0)
    return file_doc.file_url
```

**Acceptance Criteria**:
- [ ] PDF receipt generated automatically on Payment Entry submission
- [ ] PDF attached to the Payment Entry record in Desk
- [ ] PDF emailed to customer alongside payment confirmation
- [ ] Receipt includes: tenant name, invoice #, payment date, amount, payment method
- [ ] Partial payment receipt shows remaining balance
- [ ] Receipt downloadable from My Invoices portal page
- [ ] Print format "Rental Payment Receipt" is created as a custom print format

---

## 3. Frappe — Late Fee Engine

### 3.1 `auto_apply_late_fees` Scheduler Job

> **Requires**: D01-3.1 (`grace_period_days`, `late_fee_type`, `late_fee_value`), D01-2.3 (hooks.py)

The **late fee engine** runs daily and identifies invoices that are unpaid past the grace period (default 5 days after due date). For each overdue invoice, it calculates the fee (either a fixed amount or a percentage of the outstanding balance) and creates a **separate Sales Invoice** for the late fee. This keeps the original invoice clean and the late fee clearly visible as a distinct charge.

The `custom_late_fee_applied` flag on the original invoice prevents duplicate late fees — each invoice gets charged at most once.

```python
def auto_apply_late_fees():
    config = frappe.get_single("Rental Configuration")
    grace_days = config.grace_period_days or 5
    cutoff = add_days(today(), -grace_days)
    overdue = frappe.get_all("Sales Invoice", filters={
        "docstatus": 1,
        "outstanding_amount": [">", 0],
        "due_date": ["<", cutoff],
        "custom_late_fee_applied": 0,
    }, fields=["name", "outstanding_amount"])
    for inv in overdue:
        fee = calc_late_fee(config, inv.outstanding_amount)
        # Create additional Sales Invoice for the late fee
        late_inv = frappe.get_doc({
            "doctype": "Sales Invoice",
            "customer": inv.customer,
            "items": [{"item_code": "Late Fee", "qty": 1, "rate": fee}],
        })
        late_inv.insert()
        late_inv.submit()
        frappe.db.set_value("Sales Invoice", inv.name, "custom_late_fee_applied", 1)
```

**Acceptance Criteria**:
- [ ] Invoice unpaid 6+ days past due (with `grace_period_days=5`) → late fee applied
- [ ] Invoice unpaid 4 days past due → NO late fee
- [ ] `late_fee_type = Fixed`: fee = `late_fee_value` (e.g., 100 AED)
- [ ] `late_fee_type = Percentage`: fee = `late_fee_value / 100 * outstanding_amount`
- [ ] Late fee creates a separate Sales Invoice (not added to the original)
- [ ] `custom_late_fee_applied = 1` prevents duplicate late fees
- [ ] Scheduler runs daily without error when no overdue invoices exist

---

### 3.2 Custom Field on Sales Invoice

> **Requires**: D01-2.2 (app scaffold)

A single custom field added to ERPNext's `Sales Invoice` DocType to track whether a late fee has already been generated for this invoice. Without this flag, the daily scheduler would create duplicate late fees every day an invoice remains overdue. The field is read-only (set programmatically) and defaults to 0.

| Field | Type | Notes |
|---|---|---|
| `custom_late_fee_applied` | Check | Default 0. Set to 1 after late fee is generated. |

**Acceptance Criteria**:
- [ ] Custom field visible in Sales Invoice form
- [ ] Default is 0 (unchecked)
- [ ] Read-only for all roles (set programmatically)

---

## 4. Frappe — Deposit Ledger

### 4.1 `Deposit Ledger` Schema

> **Requires**: D01-2.2 (DocType directory), D05-2.1 (Rental Agreement for link)

The **Deposit Ledger** tracks the security deposit for each rental agreement. When an agreement is submitted, a ledger is created with `original_amount` matching the agreement's deposit. The `current_balance` is computed as `original_amount` minus the sum of all **committed** deductions. Deductions happen when damage is found during exit inspection (D04-3.2). The status tracks the lifecycle: `Held` (full deposit held) → `Partially Released` (some deducted) → `Refunded` (all returned after lease ends).

Critical constraint: `current_balance` can never go negative — if a deduction would exceed the remaining balance, it's rejected.

| Field | Type | Notes |
|---|---|---|
| `agreement` | Link → Rental Agreement | ✅ |
| `customer` | Link → Customer | ✅ |
| `original_amount` | Currency | Original deposit paid |
| `current_balance` | Currency | Computed: original - sum(committed deductions) |
| `deductions` | Table → `Deposit Deduction` | |
| `status` | Select | `Held`, `Partially Released`, `Refunded` |

**Acceptance Criteria**:
- [ ] One Deposit Ledger per Rental Agreement
- [ ] `current_balance` = `original_amount` - sum of committed `Deposit Deduction` amounts
- [ ] `status` transitions: `Held` → `Partially Released` (when any deduction committed) → `Refunded` (all returned)
- [ ] `current_balance` never goes negative (validation error if deduction exceeds balance)
- [ ] Customer can view their own ledger (portal permission)

---

### 4.2 `Deposit Deduction` Child Table

> **Requires**: 4.1

Each deduction represents a specific charge against the tenant's deposit (e.g., "Wall damage in bedroom — 500 AED"). Deductions start as `Pending` to give the tenant a **dispute window** (configured in D01, default 5 days). During this window, the tenant can challenge the deduction through the portal or app. If disputed, the Rental Manager reviews and either commits or dismisses it. Only `Committed` deductions reduce the balance. `Pending` deductions are visible but don't affect the balance yet.

| Field | Type | Notes |
|---|---|---|
| `reason` | Data | ✅ |
| `amount` | Currency | ✅ |
| `deduction_date` | Date | ✅ |
| `deduction_status` | Select | `Pending`, `Disputed`, `Committed` |
| `photo_evidence` | Attach | |
| `disputed_by_tenant` | Check | |

**Acceptance Criteria**:
- [ ] Deduction starts as `Pending` (not auto-committed)
- [ ] Customer can dispute a `Pending` deduction within `deposit_dispute_window_days`
- [ ] Disputed deduction sets `deduction_status = Disputed` and `disputed_by_tenant = 1`
- [ ] Rental Manager can commit or dismiss a disputed deduction
- [ ] `Committed` deductions reduce `current_balance` immediately
- [ ] `Pending` deductions do NOT reduce `current_balance`

---

### 4.3 Auto-Commit Scheduler

> **Requires**: 4.2, D01-3.1 (`deposit_dispute_window_days`)

If the tenant doesn't dispute a deduction within the configured window (default 5 days), the system **auto-commits** it — the deduction becomes permanent and reduces the deposit balance. This prevents deductions from sitting in `Pending` limbo indefinitely. Only `Pending` deductions are auto-committed; `Disputed` ones remain for manual resolution by the Rental Manager.

```python
def auto_commit_deposit_deductions():
    config = frappe.get_single("Rental Configuration")
    window = config.deposit_dispute_window_days or 5
    cutoff = add_days(today(), -window)
    # Find pending deductions past the dispute window
    deductions = frappe.db.sql("""
        SELECT dd.name, dd.parent, dd.amount
        FROM `tabDeposit Deduction` dd
        JOIN `tabDeposit Ledger` dl ON dl.name = dd.parent
        WHERE dd.deduction_status = 'Pending'
          AND dd.deduction_date < %(cutoff)s
    """, {"cutoff": cutoff}, as_dict=True)
    for d in deductions:
        frappe.db.set_value("Deposit Deduction", d.name, "deduction_status", "Committed")
        recalculate_balance(d.parent)
```

**Acceptance Criteria**:
- [ ] Deduction created 6 days ago (with `dispute_window=5`) → auto-committed
- [ ] Deduction created 4 days ago → remains Pending
- [ ] Disputed deductions are NOT auto-committed (only Pending ones)
- [ ] `current_balance` is recalculated after each commit
- [ ] Scheduler runs daily without error when no pending deductions exist

---

### 4.4 Exit Inspection Event Handler

> **Requires**: 4.1 (Deposit Ledger), 4.2 (Deposit Deduction schema), D04-3.2 (fires `exit_inspection_completed` event)

This is the **D06 side** of the bounded context bridge between Asset Management and Accounting. When D04's `Asset Inspection` controller submits an Exit inspection with damage, it fires an `exit_inspection_completed` domain event (D04-3.2). This handler listens for that event and creates the `Deposit Deduction` row in the appropriate `Deposit Ledger`.

The handler is registered in `hooks.py`:
```python
rental_hooks = {
    "exit_inspection_completed": "rental_core.accounting.deposits.handle_exit_inspection"
}
```

The handler receives the event payload (inspection name, agreement, cost, damage notes, photo) and creates the deduction internally. D06 owns all deduction creation logic — D04 never touches the `Deposit Ledger` directly.

```python
def handle_exit_inspection(inspection, agreement, estimated_repair_cost, **kwargs):
    ledger = frappe.get_doc("Deposit Ledger", {"agreement": agreement})
    if estimated_repair_cost > ledger.current_balance:
        frappe.log_error(
            f"Inspection {inspection}: repair cost {estimated_repair_cost} exceeds "
            f"deposit balance {ledger.current_balance}. Capping deduction to balance.",
            "Deposit Deduction Warning"
        )
        estimated_repair_cost = ledger.current_balance
    ledger.append("deductions", {
        "reason": f"Damage per inspection {inspection}: {kwargs.get('damage_notes', '')}",
        "amount": estimated_repair_cost,
        "deduction_date": frappe.utils.today(),
        "deduction_status": "Pending",
        "photo_evidence": kwargs.get("photo_evidence"),
    })
    ledger.save(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Handler creates `Deposit Deduction` row when `exit_inspection_completed` event fires
- [ ] Deduction amount is capped to `current_balance` (never goes negative)
- [ ] If deduction would exceed balance, a warning is logged
- [ ] Deduction `reason` includes both inspection name and damage notes
- [ ] Handler registered in `hooks.py` via `rental_hooks` pattern
- [ ] Handler does not throw on empty event payload (defensive)

---

## 5. Frappe — Payment Gateway Router

### 5.1 Gateway Router (`payment_routing/gateway_router.py`)

> **Requires**: D01-3.1 (`payment_gateway` config field), D01-2.2 (gateway stub files)

The **payment gateway router** is a strategy pattern that routes payment requests to the correct payment provider. The operator configures which gateway to use in Rental Configuration (Stripe, Tap, PayMob, or Bank Transfer). When an invoice needs a payment link, the router instantiates the correct gateway class and calls `create_payment_link()`. All gateways implement the same interface, so switching providers requires only a config change — no code changes.

This design supports multi-region deployment: GCC operators use Tap (supports AED/SAR), EU operators use Stripe, operators without online payments use Bank Transfer.

```python
class GatewayRouter:
    def route(self, invoice: SalesInvoice):
        config = frappe.get_single("Rental Configuration")
        gateway_name = config.payment_gateway
        gateways = {
            "Stripe": StripeGateway,
            "Tap": TapGateway,
            "PayMob": PayMobGateway,
            "Bank Transfer": ManualGateway,
        }
        cls = gateways.get(gateway_name)
        if not cls:
            frappe.throw(f"Unknown payment gateway: {gateway_name}")
        return cls(config).create_payment_link(invoice)
```

**Acceptance Criteria**:
- [ ] When config says `Stripe` → `StripeGateway.create_payment_link()` is called
- [ ] When config says `Tap` → `TapGateway.create_payment_link()` is called
- [ ] When config says `Bank Transfer` → `ManualGateway.create_payment_link()` returns upload form URL
- [ ] Unknown gateway name → `frappe.throw` with descriptive error
- [ ] All gateways implement the same interface: `create_payment_link(invoice) → url`
- [ ] Gateway switch requires only config change (no code change)

---

### 5.2 Stripe Gateway (`gateways/stripe_gateway.py`)

> **Requires**: 5.1, D01-3.1 (API keys in config)

The **Stripe integration** creates a Checkout Session with the invoice amount, currency, and customer email. The customer is redirected to Stripe's hosted checkout page. On successful payment, Stripe sends a webhook to the `payment_webhook` endpoint (6.1). Success and cancel URLs point back to `/my-invoices` with query parameters so the web portal can show appropriate feedback.

**Acceptance Criteria**:
- [ ] Creates a Stripe Checkout Session with invoice amount, currency, and customer email
- [ ] Returns Stripe checkout URL
- [ ] `success_url` points to `/my-invoices?success=1`
- [ ] `cancel_url` points to `/my-invoices?cancelled=1`
- [ ] Missing `payment_gateway_api_key` raises informative error

---

### 5.3 Tap Gateway (`gateways/tap_gateway.py`)

> **Requires**: 5.1, D01-3.1 (API keys)

The **Tap integration** is for GCC markets (UAE, Saudi Arabia, Kuwait, etc.) where Stripe may not be available. Tap supports AED, SAR, KWD, and other regional currencies. The integration creates a Tap Charge and returns the payment URL. Webhook handling follows the same pattern as Stripe.

**Acceptance Criteria**:
- [ ] Creates a Tap Charge with correct amount and redirect URL
- [ ] Returns Tap payment URL
- [ ] Works for AED currency (common in GCC)

---

### 5.4 Manual Gateway (`gateways/manual_gateway.py`)

> **Requires**: 5.1

For operators without online payment infrastructure, the **manual gateway** provides a bank transfer workflow. Instead of redirecting to a payment processor, it returns a URL to `/pay/{invoice}` where the tenant sees bank account details and can upload proof of payment (a bank receipt screenshot or PDF). The accountant then manually reconciles the payment.

**Acceptance Criteria**:
- [ ] Returns URL to `/pay/{invoice}` with bank transfer upload form
- [ ] Does NOT call any external API
- [ ] Upload form accepts proof-of-payment file attachment

---

### 5.5 PayMob Gateway (`gateways/paymob_gateway.py`)

> **Requires**: 5.1 (gateway router), D01-3.1 (API keys)

The **PayMob integration** is for the Egyptian market, where Stripe and Tap are not available. PayMob's API differs significantly from Stripe/Tap: it uses a multi-step flow (authentication → order registration → payment key generation → iframe redirect) rather than a single "create session" call.

The integration flow:
1. **Authenticate**: POST to `/api/auth/tokens` with API key → receive an auth token
2. **Register Order**: POST to `/api/ecommerce/orders` with amount, currency (EGP), and merchant order ID → receive an order ID
3. **Generate Payment Key**: POST to `/api/acceptance/payment_keys` with order ID, amount, billing data → receive a payment key token
4. **Redirect**: Send the customer to `https://accept.paymob.com/api/acceptance/iframes/{iframe_id}?payment_token={token}`

PayMob supports multiple payment methods within the same integration: Visa/Mastercard via iframe, mobile wallets (Vodafone Cash, Orange Money, Etisalat Cash), and kiosk payments (Aman, Masary). The gateway configuration includes an `iframe_id` field specific to the operator's PayMob dashboard.

Webhook handling: PayMob sends a transaction callback with an HMAC signature. The webhook handler must verify the HMAC using the HMAC secret from the config before processing. The transaction status field uses PayMob-specific values (`success`, `declined`, `voided`) that must be mapped to the platform's generic status.

```python
class PayMobGateway:
    def create_payment_link(self, invoice):
        auth_token = self._authenticate()
        order_id = self._register_order(auth_token, invoice)
        payment_key = self._generate_payment_key(auth_token, order_id, invoice)
        iframe_id = frappe.get_single("Rental Configuration").paymob_iframe_id
        return f"https://accept.paymob.com/api/acceptance/iframes/{iframe_id}?payment_token={payment_key}"

    def verify_webhook(self, data, hmac_signature):
        # Verify HMAC against config's paymob_hmac_secret
        ...
```

**Acceptance Criteria**:
- [ ] PayMob auth token retrieval succeeds with valid API key
- [ ] Order registration creates a PayMob order with correct EGP amount
- [ ] Payment key generation produces a valid payment token
- [ ] Returned URL points to PayMob iframe with correct payment token
- [ ] Webhook HMAC verification passes for valid callbacks
- [ ] Webhook HMAC verification rejects tampered callbacks (HTTP 400)
- [ ] PayMob transaction statuses mapped correctly: `success` → Payment Entry, `declined` → logged as failure
- [ ] Missing `paymob_iframe_id` or `paymob_hmac_secret` raises informative error

---

## 6. Frappe — Webhook Handler

### 6.1 `payment_webhook` Endpoint

> **Requires**: 5.1 (gateway router), D01-4.2 (grace mode branching)

The **webhook endpoint** receives payment confirmations from external gateways (Stripe, Tap). It's publicly accessible (webhooks come from the gateway, not the user) and follows a strict processing pipeline: (1) check if the system is in license grace mode, (2) verify the gateway's signature/secret, (3) check idempotency (duplicate `event_id` returns 200 OK without re-processing), (4) create a `Payment Entry` in ERPNext. All webhooks are logged regardless of outcome.

```python
@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_webhook():
    # 1. Grace mode check (D01-4.2)
    # 2. Verify signature (per gateway)
    # 3. Idempotency check
    # 4. Process payment
```

**Acceptance Criteria**:
- [ ] Endpoint is publicly accessible (no auth — webhooks come from gateways)
- [ ] Each gateway's signature/secret is verified before processing
- [ ] Duplicate `event_id` → idempotent (returns 200 OK, no re-processing)
- [ ] Valid payment → `Payment Entry` created and submitted in ERPNext
- [ ] Invalid signature → HTTP 403, logged in `Payment Webhook Log`
- [ ] All webhooks logged with `gateway`, `event_id`, `payload`, `processed` flag

---

### 6.2 `Payment Webhook Log` DocType

> **Requires**: D01-2.2 (DocType directory)

An **audit trail** for every webhook the system receives. Every webhook creates a log entry with the gateway name, event ID, raw JSON payload, and processing status. The `event_id` is indexed for fast idempotency lookups. Logs are immutable (read-only) and purged after a configurable retention period (monthly scheduler) to prevent unbounded storage growth.

| Field | Type | Notes |
|---|---|---|
| `gateway` | Data | |
| `event_id` | Data | Gateway's unique event identifier |
| `payload` | Long Text | Raw JSON payload |
| `processed` | Check | 0 = pending, 1 = processed |
| `processing_error` | Text | Error message if processing failed |
| `created_at` | Datetime | Auto |

**Acceptance Criteria**:
- [ ] Every webhook received (valid or invalid) creates a log entry
- [ ] `event_id` is indexed for idempotency lookup
- [ ] Logs older than `webhook_log_retention_months` are purged by monthly scheduler
- [ ] Read-only for all roles (no manual edits)

---

## 7. Frappe — Accounting API Endpoints

### 7.1 `get_customer_invoices`

> **Requires**: D05-2.1 (Rental Agreement), ERPNext Sales Invoice

Returns the current customer's **invoice history**: all Sales Invoices linked to their rental agreements. Each entry includes the amount, due date, outstanding balance, and payment status (Paid, Unpaid, Overdue). Sorted by due date descending so the most recent/urgent invoices appear first.

**Acceptance Criteria**:
- [ ] Returns only invoices for the current customer
- [ ] Each invoice includes: `invoice_name`, `due_date`, `grand_total`, `outstanding_amount`, `status`
- [ ] Sorted by `due_date` descending
- [ ] Paginated per D01-6.2 standard

---

### 7.2 `get_invoice_payment_url`

> **Requires**: 5.1 (gateway router)

Generates a **payment URL** for a specific unpaid invoice. The gateway router (5.1) selects the correct payment provider and returns the checkout URL. Only the owning customer can request a payment URL for their invoice. Already-paid or cancelled invoices return an error.

**Acceptance Criteria**:
- [ ] Returns payment URL for the specified invoice
- [ ] Only the owning customer can request the URL
- [ ] Already-paid invoices return error "Invoice already paid"
- [ ] Cancelled invoices return error

---

### 7.3 `get_deposit_status`

> **Requires**: 4.1 (Deposit Ledger)

Returns the tenant's **deposit status**: original amount, current balance, all deductions (with reason, amount, status, date), and photo evidence URLs. This powers the deposit section on both the web agreement detail page and the Flutter deposit widget.

**Acceptance Criteria**:
- [ ] Returns `original_amount`, `current_balance`, `deductions[]`, `status`
- [ ] Each deduction includes `reason`, `amount`, `deduction_status`, `deduction_date`
- [ ] Only the owning customer can view their deposit
- [ ] `photo_evidence` URL is included when available

---

### 7.4 `dispute_deposit_deduction`

> **Requires**: 4.2 (Deposit Deduction with `disputed_by_tenant`)

Allows the tenant to **challenge a deposit deduction** they believe is unfair. The dispute must happen within the configured window (default 5 days after the deduction is created). Disputing changes the status to `Disputed` and notifies the Rental Manager for manual review. Past the window, the deduction is either already auto-committed or about to be, and disputes are rejected.

**Acceptance Criteria**:
- [ ] Customer can dispute a `Pending` deduction within `deposit_dispute_window_days`
- [ ] Disputing past the window returns error "Dispute window has expired"
- [ ] Disputing a `Committed` deduction returns error
- [ ] Disputing sets `deduction_status = Disputed` and `disputed_by_tenant = 1`
- [ ] Rental Manager receives notification about the dispute

---

### 7.5 `upload_payment_proof`

> **Requires**: 8.3 (Bank Transfer Upload form), D01-6.4 (API security checklist — MIME validation)

A dedicated API endpoint for uploading bank transfer proof-of-payment files. The web form (§8.3) uses a standard `<form>` submission, but the **Flutter app** needs an API endpoint to upload the receipt programmatically. This endpoint accepts a file attachment and links it to the relevant Sales Invoice. It also creates a `ToDo` for the Accountant to manually reconcile the payment.

The endpoint enforces the security checklist (D01-6.4):
- MIME type must be one of: `image/jpeg`, `image/png`, `application/pdf`
- File size must not exceed 10 MB
- The requesting user must be the customer on the linked agreement (IDOR prevention)

```python
@frappe.whitelist()
def upload_payment_proof(invoice_name, file):
    # 1. Verify ownership
    invoice = frappe.get_doc("Sales Invoice", invoice_name)
    if invoice.customer != frappe.session.user:
        frappe.throw(_("Access denied"), exc=frappe.PermissionError)
    # 2. Validate file
    validate_file_upload(file, allowed_mimes=["image/jpeg", "image/png", "application/pdf"], max_size_mb=10)
    # 3. Attach to invoice
    frappe.get_doc({"doctype": "File", "file_url": file, "attached_to_doctype": "Sales Invoice",
                    "attached_to_name": invoice_name}).insert(ignore_permissions=True)
    # 4. Create Accountant ToDo
    frappe.get_doc({"doctype": "ToDo", "allocated_to": get_accountant_user(),
                    "description": f"Reconcile bank transfer for {invoice_name}",
                    "reference_type": "Sales Invoice", "reference_name": invoice_name}).insert()
```

**Acceptance Criteria**:
- [ ] File upload succeeds with valid JPEG/PNG/PDF under 10 MB
- [ ] File upload rejected with invalid MIME type (e.g., `.exe`) → HTTP 400
- [ ] File upload rejected when exceeding 10 MB → HTTP 400
- [ ] Non-owner customer gets HTTP 403
- [ ] Uploaded file attached to the Sales Invoice
- [ ] Accountant receives a `ToDo` notification after upload
- [ ] Rate limited: 5/min per user

---

### 7.6 `get_guarantor_invoices`

> **Requires**: D03-9.x (Guarantor portal), 7.1 (invoice query pattern)

Returns the **overdue invoices** for the tenant that the guarantor is guaranteeing. The [Base Overview](file:///home/zawiatgf/Documents/Obsidian%20Vault/Projects/Gatom/In%20House%20Products/Asset%20Rental/Base/Base%20Overview.md#L106) states that guarantors "can log in to a restricted portal to view outstanding balance and **pay**." This endpoint provides the data for that view.

The guarantor can only see **overdue** invoices (not all invoices) for the specific agreement they are guaranteeing. This is a restricted view — guarantors cannot see the tenant's full financial history, only what they are liable for.

```python
@frappe.whitelist()
def get_guarantor_invoices():
    # Find agreements where current user is the guarantor
    agreements = frappe.get_all("Rental Agreement",
        filters={"guarantor": frappe.session.user, "status": "Active"},
        fields=["name", "customer"])
    if not agreements:
        return {"data": []}
    # Get overdue invoices for those agreements
    invoices = frappe.get_all("Sales Invoice",
        filters={"custom_rental_agreement": ["in", [a.name for a in agreements]],
                 "outstanding_amount": [">", 0], "due_date": ["<", frappe.utils.today()]},
        fields=["name", "due_date", "grand_total", "outstanding_amount"],
        order_by="due_date asc")
    return {"data": invoices}
```

**Acceptance Criteria**:
- [ ] Returns only overdue invoices for agreements where the user is guarantor
- [ ] Non-guarantor user gets empty list (not error)
- [ ] Does NOT return paid invoices or invoices not yet due
- [ ] Each entry includes: `invoice_name`, `due_date`, `grand_total`, `outstanding_amount`
- [ ] Rate limited: 30/min per user

---

## 8. Web — Invoice & Payment Portal

### 8.1 My Invoices Controller `www/my-invoices.py`

> **Requires**: D01-7.3 (page stub), 7.1 (invoice API)

The **My Invoices** portal page lists all of the customer's invoices with visual status badges (Paid = green, Unpaid = yellow, Overdue = red). Each unpaid invoice has a "Pay Now" button that generates a payment URL and redirects to the gateway. Guest users are redirected to login.

**Acceptance Criteria**:
- [ ] Guest → redirected to login
- [ ] Lists all invoices: date, amount, status (Paid, Unpaid, Overdue)
- [ ] Overdue invoices highlighted with warning color
- [ ] "Pay Now" button visible for unpaid invoices

---

### 8.2 Payment Page `www/pay.py`

> **Requires**: 7.2 (payment URL API), 5.1 (gateway router)

The **payment page** routes the customer to the correct payment flow: for online gateways (Stripe/Tap), it redirects to the hosted checkout page; for manual gateways (Bank Transfer), it shows bank account details and an upload form for proof-of-payment. Already-paid invoices show an "Already paid" message.

**Acceptance Criteria**:
- [ ] Online gateway (Stripe/Tap): redirects to gateway checkout page
- [ ] Manual gateway (Bank Transfer): shows upload form for proof-of-payment
- [ ] Guest → redirected to login
- [ ] Invoice already paid → "Already paid" message

---

### 8.3 Bank Transfer Upload

> **Requires**: 8.2

For manual (bank transfer) payments, this form allows the customer to **upload proof of payment** — a screenshot or PDF of the bank transfer receipt. The upload creates a notification for the Accountant to manually reconcile the payment in ERPNext. File size is capped at 10 MB.

**Acceptance Criteria**:
- [ ] File upload field accepts image/PDF
- [ ] Submission creates a notification for Accountant
- [ ] Confirmation message shown after upload
- [ ] Maximum file size enforced (10 MB)

---

## 9. Web — Deposit Status Page

### 9.1 Deposit Section on Agreement Detail

> **Requires**: 7.3 (deposit API), D05 My Rentals portal

A section on the **agreement detail page** that shows the deposit status. The tenant can see their original deposit, current balance, and a table of all deductions with reason, amount, status, and date. For `Pending` deductions within the dispute window, a "Dispute" button is shown. Photo evidence thumbnails are displayed when available.

**Acceptance Criteria**:
- [ ] Shows `original_amount`, `current_balance`, deduction table
- [ ] Each deduction row shows: reason, amount, status badge, date
- [ ] "Dispute" button shown for `Pending` deductions within window
- [ ] "Dispute" button hidden for `Committed` or past-window deductions
- [ ] Photo evidence thumbnail shown when available

---

### 9.2 Deposit Dispute Banner (Web)

> **Requires**: 9.1 (deposit section), 7.4 (dispute API), D01-7.6 (state patterns)

Functional requirement BR-068 states: "Deposit deductions must also be displayed as a **persistent banner** on the portal `/my-rentals` page for the full duration of the dispute window."

This is a dedicated banner component — separate from the deposit section on the agreement detail page (9.1). It appears at the **top of the My Rentals page** (above the agreements list) whenever the customer has at least one `Pending` deduction within its dispute window. The banner is visually prominent (warning yellow background, outlined border) and includes:

- A summary: "You have X pending deposit deductions totalling Y AED"
- A list of each deduction: reason, amount
- A countdown: "Dispute window closes in Z days"
- A "View & Dispute" link to the agreement detail page's deposit section

The banner disappears automatically when all deductions are either `Committed` (dispute window passed) or `Disputed` (tenant already acted). The data is fetched via the same `get_deposit_status` API (7.3) with an additional filter for `Pending` deductions within window.

```html
{% if pending_deductions %}
<div class="rental-dispute-banner">
  <strong>⚠️ {{ _("Deposit Deductions Pending Your Review") }}</strong>
  <p>{{ len(pending_deductions) }} deductions totalling {{ total_pending | currency }}</p>
  <ul>
    {% for d in pending_deductions %}
    <li>{{ d.reason }} — {{ d.amount | currency }}</li>
    {% endfor %}
  </ul>
  <a href="/my-rentals/{{ agreement }}">{{ _("View & Dispute") }}</a>
</div>
{% endif %}
```

**Acceptance Criteria**:
- [ ] Banner appears at top of `/my-rentals` when pending deductions exist within dispute window
- [ ] Banner shows: count, total amount, per-deduction breakdown
- [ ] Banner includes countdown: "Dispute window closes in X days"
- [ ] "View & Dispute" link navigates to agreement detail → deposit section
- [ ] Banner disappears when all deductions are Committed or Disputed
- [ ] Banner is visually prominent (not subtle — uses warning color scheme)

---

### 9.3 Guarantor Payment Flow (Web)

> **Requires**: D03-9.1 (guarantor portal controller), 7.2 (payment URL API), 5.1 (gateway router)

The guarantor portal (D03-9.x) currently allows guarantors to **view** outstanding balances but not **pay** them. This subtask adds payment capability to the guarantor portal. When a guarantor views outstanding invoices for their guaranteed tenant, each overdue invoice shows a "Pay on Behalf" button.

The payment flow is identical to the tenant's (8.2) — the gateway router generates a payment URL, and the guarantor is redirected to the same checkout page. The key difference is that the Payment Entry is logged with `payment_source = "Guarantor"` and the guarantor's name/email for audit purposes.

This is triggered by the escalation engine (D07-4.1) at the D+7 and D+14 tiers, when the guarantor starts receiving overdue notifications. The notification email includes a direct link to the guarantor portal with the relevant invoice pre-selected.

**Acceptance Criteria**:
- [ ] Guarantor portal shows "Pay on Behalf" button on overdue invoices
- [ ] Button generates a payment URL via the same gateway router (5.1)
- [ ] Payment Entry records `payment_source = "Guarantor"` for audit
- [ ] Guarantor's email is logged on the Payment Entry (not the tenant's)
- [ ] Successful payment reduces the tenant's outstanding balance
- [ ] Tenant receives notification that guarantor made a payment
- [ ] Guarantor CANNOT see tenant's personal details (D03-9.2 restrictions still apply)

---

## 10. Flutter — Payment Screens

### 10.1 Invoices Screen

> **Requires**: D01-8.3 (screen stub), 7.1 (invoice API)

The Flutter **invoices screen** displays all of the customer's invoices in a list. Each row shows the amount, due date, and a colored status badge (Paid/Unpaid/Overdue). Overdue invoices are visually highlighted. Tapping "Pay" starts the payment flow (10.2). Pull-to-refresh reloads the invoice list from the API.

**Acceptance Criteria**:
- [ ] Lists all invoices: amount, due date, status badge
- [ ] Overdue invoices highlighted
- [ ] Tapping "Pay" navigates to payment flow
- [ ] Pull-to-refresh reloads invoice list

---

### 10.2 Payment Flow

> **Requires**: 10.1, 7.2 (payment URL API), D01-8.3 (screen stubs)

The Flutter payment flow handles both online and manual gateways. For online payments (Stripe/Tap), a **WebView** opens with the gateway checkout URL and listens for success/cancel redirect URLs. On success, the WebView closes and the user sees a confirmation toast. For manual payments (bank transfer), the app shows a camera/file upload interface for proof of payment.

**Acceptance Criteria**:
- [ ] Online gateway → opens `WebView` with gateway checkout URL
- [ ] WebView listens for success/cancel redirect URLs
- [ ] On success redirect → close WebView, navigate to invoices, show success toast
- [ ] On cancel redirect → close WebView, show cancellation message
- [ ] Manual gateway → shows camera/file upload for proof-of-payment
- [ ] Upload success → confirmation screen

---

### 10.3 Deposit Detail Widget

> **Requires**: 7.3 (deposit API)

A **reusable Flutter widget** that displays the deposit status on the agreement detail screen. It shows a progress bar (original amount vs. current balance), a list of deductions, and a "Dispute" button for eligible deductions. Successful disputes update the status badge reactively.

**Acceptance Criteria**:
- [ ] Displays `original_amount`, `current_balance`, progress bar
- [ ] Deduction list with: reason, amount, status badge, date
- [ ] "Dispute" button for eligible deductions (Pending + within window)
- [ ] Dispute submission calls `dispute_deposit_deduction` API
- [ ] Dispute success → status badge updates to "Disputed"

---

### 10.4 Deposit Dispute Banner (Flutter)

> **Requires**: 10.3 (deposit detail widget), D05-12.1 (My Rentals screen)

The Flutter counterpart to the web's deposit dispute banner (9.2). A **persistent card** displayed at the top of the My Rentals screen when the customer has pending deposit deductions within their dispute window.

The card uses a warning color scheme (`Colors.amber.shade50` background, `Colors.amber.shade800` text) and shows:
- Summary text: "You have X deposit deductions pending your review"
- Total pending amount
- A countdown chip: "X days remaining to dispute"
- A "Review Deductions" button that navigates to the agreement detail → deposit section

The banner data is fetched alongside the My Rentals data (D05-12.1 provider) and is reactively hidden when all deductions are resolved.

**Acceptance Criteria**:
- [ ] Banner card appears at top of My Rentals screen when pending deductions exist
- [ ] Shows count, total amount, and countdown
- [ ] "Review Deductions" navigates to agreement detail → deposit section
- [ ] Banner hidden when no pending deductions within window
- [ ] Warning color scheme is visually distinct from normal content

---

## 11. Domain-Level Acceptance Criteria

- [ ] Subscription generates invoices on schedule
- [ ] Late fees applied after grace period to overdue invoices
- [ ] No duplicate late fees on same invoice
- [ ] Payment via Stripe → webhook → Payment Entry reconciled
- [ ] Payment via Tap → webhook → Payment Entry reconciled
- [ ] Bank Transfer → proof uploaded → manual reconciliation
- [ ] Deposit deductions: dispute within window → auto-commit after window
- [ ] Webhook log retention purges old entries monthly

---

## 12. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (billing engine + late fees + deposit + gateways + webhooks + APIs) | 7 days |
| Web (invoices + payment + deposit portal) | 2 days |
| Flutter (invoices + payment + deposit) | 3 days |
| **Total** | **12 days** |
