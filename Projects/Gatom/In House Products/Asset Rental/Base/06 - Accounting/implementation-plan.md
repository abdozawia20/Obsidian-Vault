# Domain 06 — Accounting: Implementation Plan

> **Variant**: Base
> **Domain**: Accounting
> **Sequence**: 6 of 8
> **Depends on**: Domain 01 (config + gateway keys), Domain 05 (agreements + subscriptions)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Invoice generation via ERPNext Subscription, multi-gateway payment routing, late fee engine, deposit lifecycle, webhook processing, and customer payment portal (web + Flutter).

---

## 2. Frappe — Billing Engine

### 2.1 Subscription Factory (`billing/subscription_factory.py`)

> **Requires**: D05-2.1 (Rental Agreement with `billing_cycle`, `monthly_rate`), D01-3.1 (config with `tax_template`)

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

**Acceptance Criteria**:
- [ ] When Payment Entry is submitted against a rental invoice, hook fires
- [ ] Payment receipt email sent to customer
- [ ] `Rental Notification Log` entry created with `notification_type = Payment Received`
- [ ] Non-rental Payment Entries are ignored

---

## 3. Frappe — Late Fee Engine

### 3.1 `auto_apply_late_fees` Scheduler Job

> **Requires**: D01-3.1 (`grace_period_days`, `late_fee_type`, `late_fee_value`), D01-2.3 (hooks.py)

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

## 5. Frappe — Payment Gateway Router

### 5.1 Gateway Router (`payment_routing/gateway_router.py`)

> **Requires**: D01-3.1 (`payment_gateway` config field), D01-2.2 (gateway stub files)

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

**Acceptance Criteria**:
- [ ] Creates a Stripe Checkout Session with invoice amount, currency, and customer email
- [ ] Returns Stripe checkout URL
- [ ] `success_url` points to `/my-invoices?success=1`
- [ ] `cancel_url` points to `/my-invoices?cancelled=1`
- [ ] Missing `payment_gateway_api_key` raises informative error

---

### 5.3 Tap Gateway (`gateways/tap_gateway.py`)

> **Requires**: 5.1, D01-3.1 (API keys)

**Acceptance Criteria**:
- [ ] Creates a Tap Charge with correct amount and redirect URL
- [ ] Returns Tap payment URL
- [ ] Works for AED currency (common in GCC)

---

### 5.4 Manual Gateway (`gateways/manual_gateway.py`)

> **Requires**: 5.1

**Acceptance Criteria**:
- [ ] Returns URL to `/pay/{invoice}` with bank transfer upload form
- [ ] Does NOT call any external API
- [ ] Upload form accepts proof-of-payment file attachment

---

## 6. Frappe — Webhook Handler

### 6.1 `payment_webhook` Endpoint

> **Requires**: 5.1 (gateway router), D01-4.2 (grace mode branching)

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

**Acceptance Criteria**:
- [ ] Returns only invoices for the current customer
- [ ] Each invoice includes: `invoice_name`, `due_date`, `grand_total`, `outstanding_amount`, `status`
- [ ] Sorted by `due_date` descending
- [ ] Paginated per D01-6.2 standard

---

### 7.2 `get_invoice_payment_url`

> **Requires**: 5.1 (gateway router)

**Acceptance Criteria**:
- [ ] Returns payment URL for the specified invoice
- [ ] Only the owning customer can request the URL
- [ ] Already-paid invoices return error "Invoice already paid"
- [ ] Cancelled invoices return error

---

### 7.3 `get_deposit_status`

> **Requires**: 4.1 (Deposit Ledger)

**Acceptance Criteria**:
- [ ] Returns `original_amount`, `current_balance`, `deductions[]`, `status`
- [ ] Each deduction includes `reason`, `amount`, `deduction_status`, `deduction_date`
- [ ] Only the owning customer can view their deposit
- [ ] `photo_evidence` URL is included when available

---

### 7.4 `dispute_deposit_deduction`

> **Requires**: 4.2 (Deposit Deduction with `disputed_by_tenant`)

**Acceptance Criteria**:
- [ ] Customer can dispute a `Pending` deduction within `deposit_dispute_window_days`
- [ ] Disputing past the window returns error "Dispute window has expired"
- [ ] Disputing a `Committed` deduction returns error
- [ ] Disputing sets `deduction_status = Disputed` and `disputed_by_tenant = 1`
- [ ] Rental Manager receives notification about the dispute

---

## 8. Web — Invoice & Payment Portal

### 8.1 My Invoices Controller `www/my-invoices.py`

> **Requires**: D01-7.3 (page stub), 7.1 (invoice API)

**Acceptance Criteria**:
- [ ] Guest → redirected to login
- [ ] Lists all invoices: date, amount, status (Paid, Unpaid, Overdue)
- [ ] Overdue invoices highlighted with warning color
- [ ] "Pay Now" button visible for unpaid invoices

---

### 8.2 Payment Page `www/pay.py`

> **Requires**: 7.2 (payment URL API), 5.1 (gateway router)

**Acceptance Criteria**:
- [ ] Online gateway (Stripe/Tap): redirects to gateway checkout page
- [ ] Manual gateway (Bank Transfer): shows upload form for proof-of-payment
- [ ] Guest → redirected to login
- [ ] Invoice already paid → "Already paid" message

---

### 8.3 Bank Transfer Upload

> **Requires**: 8.2

**Acceptance Criteria**:
- [ ] File upload field accepts image/PDF
- [ ] Submission creates a notification for Accountant
- [ ] Confirmation message shown after upload
- [ ] Maximum file size enforced (10 MB)

---

## 9. Web — Deposit Status Page

### 9.1 Deposit Section on Agreement Detail

> **Requires**: 7.3 (deposit API), D05 My Rentals portal

**Acceptance Criteria**:
- [ ] Shows `original_amount`, `current_balance`, deduction table
- [ ] Each deduction row shows: reason, amount, status badge, date
- [ ] "Dispute" button shown for `Pending` deductions within window
- [ ] "Dispute" button hidden for `Committed` or past-window deductions
- [ ] Photo evidence thumbnail shown when available

---

## 10. Flutter — Payment Screens

### 10.1 Invoices Screen

> **Requires**: D01-8.3 (screen stub), 7.1 (invoice API)

**Acceptance Criteria**:
- [ ] Lists all invoices: amount, due date, status badge
- [ ] Overdue invoices highlighted
- [ ] Tapping "Pay" navigates to payment flow
- [ ] Pull-to-refresh reloads invoice list

---

### 10.2 Payment Flow

> **Requires**: 10.1, 7.2 (payment URL API), D01-8.3 (screen stubs)

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

**Acceptance Criteria**:
- [ ] Displays `original_amount`, `current_balance`, progress bar
- [ ] Deduction list with: reason, amount, status badge, date
- [ ] "Dispute" button for eligible deductions (Pending + within window)
- [ ] Dispute submission calls `dispute_deposit_deduction` API
- [ ] Dispute success → status badge updates to "Disputed"

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
