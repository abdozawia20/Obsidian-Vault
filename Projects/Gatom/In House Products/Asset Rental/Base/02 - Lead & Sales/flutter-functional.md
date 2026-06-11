# Lead & Sales — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Lead & Sales
> **Module**: Customer Mobile App — Inquiry Capture
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

The Flutter app captures inbound rental inquiries from mobile users. Like the web portal, lead management is performed in Frappe Desk — the app provides the intake funnel only.

---

## 2. Screen Requirements

### 2.1 Inquiry via Asset Detail

| # | Requirement |
|---|---|
| FR-L01 | Asset detail screens must include a "Request Info" CTA for users who are not ready to book |
| FR-L02 | The inquiry form must capture: name, email, phone (optional), and a free-text message. Fields must be pre-filled from the user's profile if logged in. |
| FR-L03 | Submission must create a Lead in `rental_core` with source set to `Mobile App` |
| FR-L04 | A confirmation toast must be shown after submission |

> **Note**: Lead management (assignment, follow-up, conversion) is performed entirely in Frappe Desk by Rental Agents. The mobile app does not provide a lead management interface.
