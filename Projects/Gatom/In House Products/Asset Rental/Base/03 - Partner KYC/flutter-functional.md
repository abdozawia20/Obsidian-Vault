# Partner KYC — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Partner KYC
> **Module**: Customer Mobile App — KYC Verification Screen
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the KYC verification screen in the Flutter app. KYC is a standalone workflow prompted after first login and always accessible from the Profile menu. It must be completed before booking is permitted.

---

## 2. Screen Requirements

### 2.1 KYC Verification Screen

| # | Requirement |
|---|---|
| FR-036 | A KYC screen must be accessible from the Profile menu and must be prompted automatically after first login |
| FR-037 | The screen must display the customer's current KYC status: `Not Submitted`, `Pending Review`, `Verified`, or `Resubmit Required` |
| FR-038 | If status is `Not Submitted` or `Resubmit Required`, the customer must be able to upload required documents using the device camera or file picker. If `Resubmit Required`, the staff rejection reason must be displayed prominently above the upload form. |
| FR-039 | If status is `Pending Review`, the screen must show a "Your documents are under review" message with no upload option |
| FR-040 | If status is `Verified`, the screen must show a verified badge with the date of verification |

### 2.2 Documents Screen

| # | Requirement |
|---|---|
| FR-081 | KYC documents, signed agreements, and receipts must be downloadable in the Documents screen. **Document download must remain accessible even for suspended or legally flagged accounts.** |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FS-006 | Customer | Upload my ID from my phone camera | I can complete KYC instantly |
| FS-KYC1 | Customer | See why my KYC was rejected | I know exactly what to re-upload |

---

## 4. Business Rules

1. The app requires authentication for the KYC screen — it is behind a route guard.
2. **A customer must have KYC status `Verified` to access the booking flow.** The "Book Now" CTA on Asset Detail is replaced with a "Complete Verification" prompt for all other KYC statuses.
3. The KYC screen is always accessible from the Profile menu and auto-prompted after first login.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Customer isolation** | All API calls filter by the authenticated user server-side |
| **Availability opacity** | API response contains only date ranges; no reason field |
