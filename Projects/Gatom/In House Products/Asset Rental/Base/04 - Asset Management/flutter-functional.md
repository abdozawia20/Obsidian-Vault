# Asset Management — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Asset Management
> **Module**: Customer Mobile App — Catalog, Home & Asset Detail
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the home screen, asset catalog, and asset detail screens in the Flutter app — the mobile discovery channel for prospective tenants.

---

## 2. Screen Requirements

### 2.1 Home

| # | Requirement |
|---|---|
| FR-010 | A featured assets carousel must be shown (curated by the operator) |
| FR-011 | The home screen must show the customer's active rental summary (if any) |
| FR-012 | Quick filter buttons (Flats / Vehicles / By price) must be accessible from home |

### 2.2 Asset Catalog

| # | Requirement |
|---|---|
| FR-020 | All available assets must be browsable in a card grid |
| FR-021 | A filter sheet must allow filtering by type, location, and price |
| FR-022 | Each card must show: cover photo, name, location, key spec, price per month |
| FR-023 | Infinite scroll or pagination must prevent loading all assets at once |

### 2.3 Asset Detail

| # | Requirement |
|---|---|
| FR-030 | A photo gallery with swipe navigation must be shown |
| FR-031 | Key specs must be displayed in a visual grid |
| FR-032 | A read-only availability calendar must show blocked/available dates |
| FR-033 | Unavailable dates must not disclose the reason |
| FR-034 | If a 3D preview is configured, a button must open it in an in-app WebView |
| FR-035 | A "Book Now" CTA must be shown **only for customers with KYC status `Verified`**. For all other KYC statuses, the CTA is replaced with a "Complete Verification" prompt that navigates to the KYC screen. |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FS-001 | Prospective tenant | Browse available assets on my phone | I can find a rental without a computer |
| FS-002 | Prospective tenant | Filter by price and location | I only see relevant options |
| FS-003 | Prospective tenant | See which dates are blocked before booking | I choose realistic dates |

---

## 4. Business Rules

1. The app allows catalog and detail browsing without login (configurable).
2. Unavailable dates on the booking calendar do not reveal the reason.
3. The app supports offline browsing of previously fetched asset data.
