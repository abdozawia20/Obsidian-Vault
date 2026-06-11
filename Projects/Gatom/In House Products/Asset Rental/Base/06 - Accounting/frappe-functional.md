# Accounting — Frappe: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Accounting
> **Module**: `rental_core` — Billing, Payments, Deposits & Tax
> **Document Type**: Functional
> **Audience**: Finance teams, accountants, QA

---

## 1. Purpose & Scope

This document covers all financial operations: recurring billing, payment collection, deposit management, tax configuration, late fees, deferred revenue, and payment gateway integration.

---

## 2. Business Requirements

### 2.1 Recurring Billing

| # | Requirement |
|---|---|
| BR-040 | Billing must be automatable on Monthly, Weekly, or Daily cycles |
| BR-041 | The first invoice in a billing period must be pro-rated if the agreement starts mid-period |
| BR-042 | Additional charges (utilities, overage, violations) must be injectable as line items on the monthly invoice |
| BR-043 | Annual rent escalation (% increase after N months) must be configurable per agreement. A **per-country maximum escalation %** must be configurable in `Rental Configuration`. If a configured escalation exceeds the country maximum, the system must log a warning and require a written justification from the Rental Manager before applying. |
| BR-044 | Tax must be automatically applied based on the regional tax template configured for the client |
| BR-045 | Deferred revenue accounting must be supportable for prepaid agreements. The platform documents the intended accounting behaviour. Correct ERPNext account configuration is the client accountant's responsibility. |
| BR-046 | The last invoice of an open-ended agreement must be pro-rated to the termination date set by the Rental Manager |

### 2.2 Payment Collection

| # | Requirement |
|---|---|
| BR-050 | The system must support multiple payment methods: bank transfer, card, mobile money, cash, payment link |
| BR-051 | Payment gateway must be configurable per deployment (Stripe for EU, Tap for Gulf, PayMob for Egypt) |
| BR-052 | Partial payments must be accepted and tracked. Outstanding balance stays on the **original invoice** — no new invoice is created for the carried balance. The next subscription cycle generates a fresh invoice for the new period only. |
| BR-053 | Late fees must be automatically applied after a configurable grace period |
| BR-054 | An aging receivables report must be available (0–30, 31–60, 61–90, 90+ days) |
| BR-055 | PDF receipts must be auto-generated on payment confirmation |
| BR-056 | **Payment webhook idempotency**: each gateway fires a unique transaction/event ID. The system must store received IDs in a `Payment Webhook Log` table. Duplicate IDs must be silently discarded before any ERPNext Payment Entry is created. The webhook endpoint must return HTTP 200 for all successfully received events (including duplicates) to prevent gateway retry storms. |
| BR-056a | `Payment Webhook Log` entries older than a configurable retention period (default: 13 months) must be archived or purged by a scheduled cleanup job. |
| BR-057 | The platform generates standard ERPNext Sales Invoices. Government e-invoicing compliance (Egypt ETA, KSA ZATCA, Turkey e-Fatura) is the **client's responsibility**. |

### 2.3 Deposit Management

| # | Requirement |
|---|---|
| BR-060 | Security deposits must be tracked in a dedicated ledger, separate from rent |
| BR-061 | Deposits must support partial deductions (damage, arrears) with documented justification |
| BR-062 | Refunds must be calculable automatically: `deposit − deductions − outstanding` |
| BR-063 | Deposit status must be visible to the tenant in the portal |
| BR-064 | When an exit inspection is submitted and deductions are proposed, the system must send the tenant a **push notification and email** listing all deducted items and their amounts |
| BR-065 | A configurable **deposit dispute window** must open (default: 5 **calendar** days, set in `Rental Configuration`). During this window, deductions are in `Pending` status and cannot be committed. |
| BR-066 | If the tenant raises a dispute during the window, a High-priority `ToDo` must be created and assigned to the Rental Manager for review. |
| BR-067 | If no dispute is raised by the end of the window, all `Pending` deductions must **auto-commit** to the deposit ledger. |
| BR-068 | Deposit deductions must also be displayed as a persistent banner on the portal `/my-rentals` page (web) and the My Rentals screen (Flutter) for the full duration of the dispute window, showing all proposed deductions and amounts with a link to raise a dispute. This is in addition to push and email notifications. |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| US-003 | Accountant | See all overdue invoices with aging | I can prioritise collections |
| US-005 | Customer | Pay my invoice online | I don't need to visit an office |
| US-007 | Rental Manager | Configure the grace period and late fee | Each client can set their own policy |
| US-008 | Accountant | Process a deposit refund with documented deductions | The settlement is transparent and auditable |

---

## 4. Business Rules

1. Late fees apply only after `grace_period_days` (client-configurable) and only once per invoice.
2. Partial payment outstanding balance stays on the original invoice — no re-invoicing. The next cycle generates a fresh invoice.
3. Deposit deductions are in `Pending` status for a configurable dispute window (default: 5 **calendar** days). If not disputed, they auto-commit. If disputed, a Rental Manager `ToDo` is created.
4. Webhook idempotency: duplicate gateway event IDs are silently discarded against the `Payment Webhook Log`.

---

## 5. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **ERPNext Accounts** | Outbound | Sales Invoice, Payment Entry, Journal Entry |
| **ERPNext Subscription** | Outbound | Recurring invoice generation |
| **Payment Gateway** (Stripe/Tap/PayMob) | Outbound | Hosted payment links, webhook reconciliation |

---

## 6. Security Requirements

| Requirement | Description |
|---|---|
| **Payment credentials** | Gateway API keys stored in `Password` field type (encrypted at rest) |
| **Deposit ledger** | Write access restricted to Accountant and Rental Manager roles |
| **Audit trail** | All payment entries logged by ERPNext core |
