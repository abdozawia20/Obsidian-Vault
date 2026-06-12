---
tags: [moc, asset-rental, flats]
---

# 🏠 Flats — Map of Content

> The **Flats** variant extends `rental_core` with property hierarchy, utility billing, appliance management, insurance validation, and flat inspections — organised by business domain.

---

## 📋 Overview

- [[Flats Overview|🏗️ Flats Variant Overview]]

---

## 📁 Domains

### 01 — Property & Unit Registry
> Property → Building → Flat Unit hierarchy, flat attributes, floor plans, SEO structured data

| Frappe | Web | Flutter |
|---|---|---|
| [[01 - Property & Unit Registry/frappe-functional\|⚙️ Frappe]] | [[01 - Property & Unit Registry/web-functional\|🌐 Web]] | [[01 - Property & Unit Registry/flutter-functional\|📱 Flutter]] |

---

### 02 — Utility Billing
> Meter readings, consumption calculation, invoice injection, tenant history (read-only)

| Frappe | Web | Flutter |
|---|---|---|
| [[02 - Utility Billing/frappe-functional\|⚙️ Frappe]] | [[02 - Utility Billing/web-functional\|🌐 Web]] | [[02 - Utility Billing/flutter-functional\|📱 Flutter]] |

---

### 03 — Appliance Management
> Inventory per flat, warranty countdown, condition tracking during inspections

| Frappe | Web | Flutter |
|---|---|---|
| [[03 - Appliance Management/frappe-functional\|⚙️ Frappe]] | [[03 - Appliance Management/web-functional\|🌐 Web]] | [[03 - Appliance Management/flutter-functional\|📱 Flutter]] |

---

### 04 — Insurance
> Country-specific mandatory coverage, agreement gating, policy expiry alerts (Desk-only)

| Frappe | Web | Flutter |
|---|---|---|
| [[04 - Insurance/frappe-functional\|⚙️ Frappe]] | [[04 - Insurance/web-functional\|🌐 Web]] | [[04 - Insurance/flutter-functional\|📱 Flutter]] |

---

### 05 — Flat Inspection
> Room-by-room checklists, photo evidence, damage → deposit deduction, periodic reminders

| Frappe | Web | Flutter |
|---|---|---|
| [[05 - Flat Inspection/frappe-functional\|⚙️ Frappe]] | [[05 - Flat Inspection/web-functional\|🌐 Web]] | [[05 - Flat Inspection/flutter-functional\|📱 Flutter]] |

---

## 🔌 Technical Docs

- [[Endpoint Registry|🔌 Endpoint Registry]] — All APIs, scheduler jobs, portal routes, and Flutter routes

---

## 🛠️ Implementation Plans

| # | Domain | Plan | Effort |
|---|---|---|---|
| F01 | Property & Unit Registry | [[01 - Property & Unit Registry/implementation-plan\|📋 Plan]] | 8d |
| F02 | Utility Billing | [[02 - Utility Billing/implementation-plan\|📋 Plan]] | 7d |
| F03 | Appliance Management | [[03 - Appliance Management/implementation-plan\|📋 Plan]] | 2.5d |
| F04 | Insurance | [[04 - Insurance/implementation-plan\|📋 Plan]] | 2d |
| F05 | Flat Inspection | [[05 - Flat Inspection/implementation-plan\|📋 Plan]] | 3.5d |
| | | **Total** | **23d** |

---

## 📊 Effort Summary

| # | Domain | Frappe | Web | Flutter | Total |
|---|---|---|---|---|---|
| F01 | Property & Unit Registry | 3d | 2d | 3d | **8d** |
| F02 | Utility Billing | 3d | 1.5d | 2.5d | **7d** |
| F03 | Appliance Management | 1d | 0.5d | 1d | **2.5d** |
| F04 | Insurance | 2d | — | — | **2d** |
| F05 | Flat Inspection | 2.5d | 0.5d | 0.5d | **3.5d** |
| | **Total** | **11.5d** | **4.5d** | **7d** | **23d** |

---

## 🔗 Related

- [[../Base/Base Overview|🏗️ Base Platform Overview]]
- [[../Asset Rental MOC|🏢 Asset Rental MOC]]
