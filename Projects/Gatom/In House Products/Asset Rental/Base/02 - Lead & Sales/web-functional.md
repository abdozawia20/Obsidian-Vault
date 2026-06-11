# Lead & Sales — Web: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Lead & Sales
> **Module**: Customer-Facing Website — Inquiry Capture
> **Document Type**: Functional
> **Audience**: UX designers, QA

---

## 1. Purpose & Scope

The web layer captures inbound rental inquiries via the public catalog. Visitors can browse assets and express interest. Lead management itself happens in Frappe Desk — the web portal provides the intake funnel.

---

## 2. Page Requirements

### 2.1 Inquiry via Catalog

| # | Requirement |
|---|---|
| WR-L01 | Asset detail pages must include a "Request Info" CTA for anonymous visitors who are not ready to book |
| WR-L02 | The "Request Info" form must capture: name, email, phone (optional), and a free-text message |
| WR-L03 | Submission must create a Lead in `rental_core` with source set to `Web` |
| WR-L04 | A confirmation message must be shown after submission ("We'll get back to you within 24 hours") |

> **Note**: Lead management (assignment, follow-up, conversion) is performed entirely in Frappe Desk by Rental Agents. The web portal does not provide a lead management interface.
