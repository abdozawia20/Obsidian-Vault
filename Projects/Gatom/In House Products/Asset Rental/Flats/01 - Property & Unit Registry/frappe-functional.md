# Property & Unit Registry — Frappe: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Property & Unit Registry
> **Module**: `rental_flats` — Property Hierarchy & Flat Attributes
> **Document Type**: Functional
> **Audience**: Property managers, product owners, QA

---

## 1. Purpose & Scope

This document defines the three-level property hierarchy (Property → Building → Flat Unit) and the flat-specific attributes that extend the base `Rental Asset` DocType. These DocTypes are managed exclusively in Frappe Desk.

---

## 2. Business Requirements

### 2.1 Property Hierarchy

| # | Requirement |
|---|---|
| FR-001 | Flat units must be organizable under Buildings, and Buildings under Properties |
| FR-002 | A Property must record: name, address, city, country, GPS coordinates, managing user |
| FR-003 | A Building must record: number of floors, elevator presence, parking slots, monthly service charge |
| FR-004 | Bulk operations (mass email tenants, mass inspection scheduling) must be performable at the building level |
| FR-005 | Total units and occupancy rate must be computable per Property and per Building |

### 2.2 Flat Unit Registry

| # | Requirement |
|---|---|
| FR-010 | Each flat unit must record: unit number, floor, gross area (m²), living area (m²), bedrooms, bathrooms |
| FR-011 | Flat attributes must include: balcony, storage room, parking slot number, furnishing level, direction facing, view type |
| FR-012 | Utility meter IDs (electricity, water, gas) must be configurable per flat |
| FR-013 | A flag for "utilities included in rent" must be settable — if set, no utility billing is generated |
| FR-014 | House rules must be configurable per flat: max occupants, pets allowed, smoking allowed |
| FR-015 | An appliance inventory (child table) must be maintainable per flat |
| FR-016 | A floor plan document must be attachable to each flat |

---

## 3. User Roles

| Role | Responsibilities |
|---|---|
| **Property Manager** | Full CRUD on Properties, Buildings, and Flat Units |
| **Rental Agent** | Read access to properties and units; creates agreements |

---

## 4. Business Rules

1. A flat unit must belong to exactly one Building; a Building must belong to exactly one Property.
2. Occupancy rate = (units with status `Rented`) / (total active units) per Building or Property.
3. **Structured data for SEO**: The flat detail API response must include fields required for `schema.org/Apartment` markup (`numberOfRooms`, `floorSize`, `address`) so the web layer can render structured data without additional API calls.
