# Accounting — Web: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Accounting
> **Module**: Customer-Facing Website — Invoices, Payments & Deposit
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

This document defines the customer-facing invoice list, online payment flow, deposit visibility, and the suspended account payment access on the web portal.

---

## 2. Page Requirements

### 2.1 My Invoices (`/my-invoices`)

| # | Requirement |
|---|---|
| WR-041 | Show outstanding (sorted by due date asc) and paid invoices; each outstanding has a "Pay Now" link |

### 2.2 Payment Page (`/pay/{invoice}`)

| # | Requirement |
|---|---|
| WR-043 | Online payment page opening the gateway-specific flow. **This page must remain accessible even when the account is suspended or under legal flag, so the customer can clear outstanding balances and reinstate.** |

### 2.3 Deposit & Dispute Banner

| # | Requirement |
|---|---|
| WR-048 | During the deposit dispute window, a persistent banner must appear on `/my-rentals` listing all proposed deductions and amounts with a link to raise a dispute. This is in addition to push and email notifications. |

### 2.4 Suspended Account Access

| # | Requirement |
|---|---|
| WR-046 | If the customer's account is suspended or under legal flag, **every portal page** must display a persistent **non-blocking** "Account on hold" banner (implemented as a sticky top bar, not a modal). The banner must include: a brief message, a contact email/phone for the client business office, and a link to the outstanding invoice payment page. The banner must never prevent page navigation, document download, or invoice viewing. |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| WS-008 | Active tenant | Check my outstanding invoices online | I can pay without calling the office |
| US-004 | Customer | View my active agreement and upcoming invoices | I know what I owe and when |

---

## 4. Business Rules

1. Portal pages enforce strict customer-to-customer isolation — a customer can never see another customer's data.
2. Suspended or legally flagged accounts may still: log in, view their data, pay invoices, and download documents. They may NOT: submit new bookings.
3. The "Account on hold" banner must appear as a non-blocking sticky top bar on every page for suspended/flagged accounts.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Portal auth wall** | All `/my-*` and `/pay/*` routes redirect to `/login` for guest access |
| **Customer isolation** | All portal API endpoints filter strictly by `frappe.session.user` |
