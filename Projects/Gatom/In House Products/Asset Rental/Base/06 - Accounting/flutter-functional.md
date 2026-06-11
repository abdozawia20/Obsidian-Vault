# Accounting — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Accounting
> **Module**: Customer Mobile App — Payments, Invoices & Deposit
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the payment screen, invoice list, deposit visibility, and the suspended account payment access in the Flutter app.

---

## 2. Screen Requirements

### 2.1 Payments

| # | Requirement |
|---|---|
| FR-060 | Outstanding invoices must be listed sorted by due date (earliest first) |
| FR-061 | Each outstanding invoice must have a "Pay Now" action |
| FR-062 | Payment must open the gateway in a WebView (online) or show bank transfer instructions |
| FR-063 | Paid invoices must be listed separately with download receipt action |
| FR-064 | Deposit status must be visible on the agreement detail |
| FR-065 | **The invoice payment screen must remain accessible for suspended or legally flagged accounts** — customers must be able to pay outstanding balances to reinstate their account |

### 2.2 Deposit & Dispute Banner

| # | Requirement |
|---|---|
| FR-058 | During the deposit dispute window, a persistent banner must appear on the My Rentals screen listing all proposed deductions and amounts, with a button to raise a dispute. This is in addition to push and email notifications. |

### 2.3 Suspended Account UX

| # | Requirement |
|---|---|
| FR-066 | If the account is suspended or under legal flag, a persistent **non-blocking** "Account on hold" banner (implemented as a sticky top bar, not a modal or blocking overlay) must appear on every screen except the invoice payment page. The banner must show the business contact details and a link to the invoice payment screen. |
| FR-067 | For suspended/flagged accounts, the "Book Now" CTA on asset detail and catalog must be replaced by the "Account on hold" state — booking is blocked. |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FS-005 | Active tenant | See my upcoming invoice on the home screen | I'm always aware of what I owe |
| FS-006 | Active tenant | Pay my invoice from the app | Fast and convenient |

---

## 4. Business Rules

1. Suspended or legally flagged accounts may: view agreements, pay invoices, download documents, navigate all screens. They may NOT: submit new bookings.
2. An "Account on hold" **non-blocking sticky top bar** must be shown on every screen, with the booking CTA replaced.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **WebView scope** | Payment WebView is sandboxed; no access to app state |
| **Customer isolation** | All API calls filter by the authenticated user server-side |
