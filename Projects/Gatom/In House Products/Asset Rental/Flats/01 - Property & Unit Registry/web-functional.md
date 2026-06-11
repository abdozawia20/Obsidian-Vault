# Property & Unit Registry — Web: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Property & Unit Registry
> **Module**: Customer-Facing Website — Flat Catalog & Detail
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

This document defines the flat-specific catalog filters and asset detail content on the public web portal. Property hierarchy management (Properties, Buildings) is Desk-only — the web layer exposes flat attributes for customer discovery.

---

## 2. Page Requirements

### 2.1 Flat Catalog (`/rentals/flats`)

| # | Requirement |
|---|---|
| FW-001 | The flat catalog must be filterable by: **Bedrooms** (Studio, 1, 2, 3, 4, 5+) |
| FW-002 | Filter by **Furnishing**: Unfurnished, Semi-Furnished, Fully Furnished |
| FW-003 | Filter by **Area range**: minimum and maximum m² |
| FW-004 | Filter by **View type**: Street, Garden, Sea, City |
| FW-005 | Filter by **Building Amenities**: Pool, Gym, Parking, Security, Elevator (checkbox multi-select) |
| FW-006 | Filter by **Parking Included**: toggle |
| FW-007 | Filter by **Pets Allowed**: toggle |
| FW-008 | Amenity filtering must join through the Building table — a flat passes the filter if its building has the selected amenity |
| FW-009 | Each flat card must display: cover photo, bedrooms, bathrooms, area, furnishing level, monthly rate |
| FW-010 | All filters must apply via AJAX without a full page reload |

### 2.2 Flat Detail (`/rentals/{flat}`)

| # | Requirement |
|---|---|
| FW-020 | The detail page must show a spec grid: bedrooms, bathrooms, area, floor, furnishing, view, direction, parking |
| FW-021 | **Building amenities** must be displayed as chips/badges (pulled from the Rental Building linked to the flat) |
| FW-022 | If an appliance inventory exists, a **collapsible section** must show appliances with name, brand, and condition badge |
| FW-023 | If a floor plan document is attached, a **"View Floor Plan"** button must be shown that opens the document in a new browser tab |
| FW-024 | If utilities are included in rent, a green badge "Utilities included" must be shown |
| FW-025 | If utilities are metered, no indication of current rates needs to be shown on the public page |

---

## 3. Booking Form Extension

| # | Requirement |
|---|---|
| FW-030 | For **Individual tenants**, no additional fields are required beyond the base booking steps |
| FW-031 | For **Company tenants**, the trade license is handled as a **configurable KYC document type** in the standalone KYC workflow (base BR-011/BR-015). It is **not** embedded as a step in the booking form. |
| FW-032 | The deposit amount must be clearly shown in Step 4 (Confirmation) |

---

## 4. SEO Requirements

| Element | Content |
|---|---|
| `<title>` | `{bedrooms}-bedroom flat in {location} for rent – {site_name}` |
| `<meta description>` | `{area}m² {furnished} flat on floor {floor}, {location}. {monthly_rate}/month.` |
| Structured data | `schema.org/Apartment` with `numberOfRooms`, `floorSize`, `address` |

---

## 5. Business Rules

1. The amenity filter requires a SQL join through the Building table — flats without a linked building are invisible if an amenity filter is active.
2. The appliance section is collapsed by default to keep the page clean.
3. The floor plan button only renders if `custom_floor_plan` is set on the asset — no broken link.
