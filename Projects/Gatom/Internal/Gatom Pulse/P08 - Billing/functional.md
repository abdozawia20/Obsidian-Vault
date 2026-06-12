---
tags: [gatom, pulse, p08, billing, subscriptions, revenue, functional]
---

# P08 — Billing & Subscriptions: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P08 — Billing & Subscriptions
> **Module**: `gatom_pulse`
> **Audience**: Gatom operations staff

---

## 1. Purpose & Scope

This domain tracks the financial relationship with each client: subscription plans, payment history, revenue metrics, and overdue escalation. It reuses ERPNext's built-in **Subscription**, **Sales Invoice**, and **Payment Entry** DocTypes — Pulse adds custom fields for linking to Pulse Clients and automation for overdue escalation.

> **Scope boundary**: Pulse tracks billing lifecycle and generates invoices. It does NOT process payments online. Gatom collects payments manually (bank transfer) and logs them in Pulse.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P08-001 | Each client must have a subscription record linking plan tier, billing cycle, amount, and renewal dates |
| P08-002 | Invoices must be auto-generated based on billing cycle (monthly/annual) via ERPNext Subscription |
| P08-003 | Payment recording is manual — Gatom admin marks payment received against an invoice |
| P08-004 | Payment overdue > 7 days → alert (P05) + suspend license (P07) |
| P08-005 | Payment overdue > 30 days → escalation ticket (P06) |
| P08-006 | Dashboard must show MRR, ARR, upcoming renewals, overdue payments |
| P08-007 | Client lifetime value (LTV) must be calculable from payment history |
| P08-008 | Churn tracking: clients who stop paying must be flagged |

---

## 3. Pricing Tiers

| Tier | Monthly | Annual (2 months free) | Max Assets | Support Level |
|---|---|---|---|---|
| Starter | $150/mo | $1,500/yr | 50 | Email only |
| Professional | $350/mo | $3,500/yr | 500 | Email + WhatsApp |
| Enterprise | Custom | Custom | Unlimited | Priority + custom dev |

> [!NOTE]
> Prices are illustrative — actual pricing will be determined by Gatom's business strategy. The system must support custom pricing per client (Enterprise tier and negotiated discounts).

---

## 4. ERPNext Integration

### 4.1 Customer Mapping

Each `Pulse Client` maps to an ERPNext `Customer`:
- `Customer.customer_name` = `Pulse Client.client_name`
- `Customer.customer_group` = `"Pulse Clients"` (dedicated group)
- `Customer.territory` = derived from `Pulse Client.country`
- Custom field: `Customer.custom_pulse_client` = Link → Pulse Client

### 4.2 Subscription

ERPNext's built-in `Subscription` DocType handles recurring invoicing:
- `party_type` = Customer
- `party` = mapped Customer name
- `plans` = Subscription Plan for the client's tier
- `billing_interval` = Monthly or Yearly
- `start_date` = contract start date

When Subscription triggers, it auto-creates a `Sales Invoice` → Gatom admin records payment manually via `Payment Entry`.

> [!IMPORTANT]
> **Audit Requirement (LOG-06)**: Every `Payment Entry` for a Pulse client must create a Pulse Audit Log entry: `PAYMENT_RECORDED` with details:
> ```json
> {
>     "payment_entry": "PE-001",
>     "sales_invoice": "SINV-001",
>     "pulse_client": "Al-Andalus Park",
>     "amount": 350.00,
>     "recorded_by": "admin@gatom.com",
>     "triggered_license_reinstatement": true
> }
> ```
> This is implemented via the `on_payment_submit` hook (see §5).

### 4.3 Custom Fields on Sales Invoice

| Field | Type | Section | Notes |
|---|---|---|---|
| `custom_pulse_client` | Link → Pulse Client | Pulse Context | For cross-reference |
| `custom_billing_period` | Data | Pulse Context | e.g., "June 2026" |

---

## 5. Overdue Escalation Pipeline

```
Day 0: Invoice generated, payment_status = "Unpaid"
Day 1-6: Normal — client has time to pay
Day 7: WARNING alert to Gatom admin
Day 8: License status → Grace (agent shows warning banner)
Day 14: HIGH alert to Gatom admin
Day 30: CRITICAL — create escalation ticket, license → Expired
Day 60: Gatom contacts client directly (manual process)
```

### Scheduler Job: `check_overdue_payments` (Daily at 2:00 AM UTC)

> ⚠️ **Scheduler timeline**: [[../API Contract#4. Pulse Scheduler Timeline|API Contract §4]]

```python
def check_overdue_payments():
    overdue = frappe.get_all("Sales Invoice",
        filters={"status": "Unpaid", "due_date": ["<", today()], "custom_pulse_client": ["!=", ""]},
        fields=["name", "custom_pulse_client", "due_date", "grand_total"])
    
    for inv in overdue:
        days_overdue = date_diff(today(), inv.due_date)
        client = inv.custom_pulse_client
        
        if days_overdue == 7:
            create_alert(client, "Payment", "Warning", f"Invoice {inv.name} overdue by 7 days")
        elif days_overdue == 8:
            create_alert(client, "Payment", "High", f"Invoice {inv.name} overdue by 8 days")
            suspend_license_for_payment(client)  # P07: License → Grace
        elif days_overdue >= 30:
            create_alert(client, "Payment", "Critical", f"Invoice {inv.name} overdue by {days_overdue} days")
            expire_license_for_payment(client)  # P07: License → Expired
            create_escalation_ticket(client, inv)
```

### Payment Reinstatement

When a Gatom admin records a `Payment Entry` against an overdue `Sales Invoice`:

```python
# Hook on Payment Entry on_submit (in hooks.py)
def on_payment_submit(doc, method):
    """If payment is for an overdue Pulse client, reinstate license."""
    for ref in doc.references:
        inv = frappe.get_doc("Sales Invoice", ref.reference_name)
        if inv.custom_pulse_client and inv.outstanding_amount <= 0:
            reinstate_license_on_payment(inv.custom_pulse_client)  # P07: License → Active
```

> ⚠️ **Full license integration**: [[../API Contract#7.2 P07 ↔ P08 Payment-Driven License Suspension|API Contract §7.2]]

---

## 6. Dashboard Views (React)

### 6.1 Revenue Overview

- **MRR**: Sum of all active monthly subscriptions (annual converted to monthly equivalent)
- **ARR**: MRR × 12
- **MRR trend chart**: Line chart, last 12 months
- **Revenue by tier**: Pie chart (Starter / Professional / Enterprise)
- **Revenue by client**: Bar chart, top 10 clients

### 6.2 Renewals Calendar

- Timeline view: upcoming renewals in next 30/60/90 days
- Color-coded: green (paid), yellow (upcoming), red (overdue)
- Click → client detail with payment history

### 6.3 Client Financial Detail

- Subscription info: plan, amount, cycle, next due
- Payment history: table of all invoices + payment status
- LTV calculation: total payments from first invoice to today
- Balance: outstanding unpaid invoices
