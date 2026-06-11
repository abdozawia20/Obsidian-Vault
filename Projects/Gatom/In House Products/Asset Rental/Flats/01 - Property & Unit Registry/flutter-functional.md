# Property & Unit Registry — Flutter: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Property & Unit Registry
> **Module**: Customer Mobile App — Flat Catalog & Detail
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the flat-specific catalog filtering and asset detail screens in the Flutter app. Property hierarchy management is Desk-only — the app exposes flat attributes for customer discovery.

---

## 2. Screen Requirements

### 2.1 Flat Catalog

| # | Requirement |
|---|---|
| FF-001 | A filter sheet must allow filtering by: Bedrooms (Studio, 1, 2, 3, 4, 5+), Furnishing, Area range (min/max m²), Parking Included, Pets Allowed |
| FF-002 | Each flat card must display: cover photo, bedrooms, bathrooms, area, furnishing, monthly rate |
| FF-003 | Active filters must be shown as dismissible chips above the grid |

### 2.2 Flat Detail

| # | Requirement |
|---|---|
| FF-010 | A spec grid must show: bedrooms, bathrooms, area, floor, furnishing, view type, direction, parking status |
| FF-011 | **Building amenities** must be displayed as a horizontally scrollable chip row |
| FF-012 | If an appliance inventory exists, an **"Appliances" button** must navigate to the appliance list screen |
| FF-013 | If a floor plan is attached, a **"View Floor Plan"** button must open the document in an in-app PDF viewer or the device's native viewer |
| FF-014 | If a 3D preview is configured, a **"View 3D Model"** button must open a WebView |
| FF-015 | If utilities are included in rent, a green badge must be shown; if metered, no rate details shown on the detail screen |
| FF-016 | The availability calendar must show blocked dates without disclosing the reason |

### 2.3 Booking Flow Extension

| # | Requirement |
|---|---|
| FF-020 | No additional fields are required for Individual tenant bookings beyond the base booking steps |
| FF-021 | For **Company tenants**, the trade license is handled as a **configurable KYC document type** in the standalone KYC workflow (base BR-011/BR-015). It is **not** embedded as a step in the booking flow. |

---

## 3. Business Rules

1. Building amenities are part of the flat detail API response — no separate API call needed.
2. The Floor Plan viewer opens the attached file URL — if PDF, opens in `flutter_pdfview`; if image, full-screen viewer.
