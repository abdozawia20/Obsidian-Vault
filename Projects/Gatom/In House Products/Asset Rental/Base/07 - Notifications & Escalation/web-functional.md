# Notifications & Escalation — Web: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Notifications & Escalation
> **Module**: Customer-Facing Website — Status Indicators & Banners
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

This document defines how notification outcomes are displayed on the web portal: pending review indicators, approval/rejection messaging, and the suspended account banner. The web portal does not manage notifications — it displays their results.

---

## 2. Page Requirements

### 2.1 Pending Booking Status

| # | Requirement |
|---|---|
| NW-001 | The post-submission confirmation screen must display: a "Pending Review" status indicator and the maximum review window (e.g. "You will hear back within 48 hours") |
| NW-002 | Pending bookings must appear in `/my-rentals` with a distinct "Pending Review" badge |

### 2.2 Suspended Account Banner

| # | Requirement |
|---|---|
| NW-010 | If the customer's account is suspended or under legal flag, **every portal page** must display a persistent **non-blocking** "Account on hold" banner. The banner must include: a brief message, contact details for the business office, and a link to the invoice payment page. |
| NW-011 | The banner must never prevent page navigation, document download, or invoice viewing. |

---

## 3. Business Rules

1. The web portal receives notifications via email — it does not manage push or SMS.
2. Notification-driven status changes (approval, rejection, expiry) are reflected in portal data via standard Frappe API calls.
