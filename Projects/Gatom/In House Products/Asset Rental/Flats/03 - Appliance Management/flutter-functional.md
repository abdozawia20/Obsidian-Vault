# Appliance Management — Flutter: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Appliance Management
> **Module**: Customer Mobile App — Appliance List Screen
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

The Flutter app provides a dedicated Appliances screen accessible from the flat detail page. Customers can see what's included. Warranty and condition management is Desk-only.

---

## 2. Screen Requirements

| # | Requirement |
|---|---|
| FF-012 | If an appliance inventory exists, an **"Appliances" button** on the flat detail screen must navigate to the appliance list |
| FF-030 | Each appliance must be listed with: name, brand, model, condition badge, and warranty countdown |
| FF-031 | Warranty countdown must change colour: green (>30 days), orange (≤30 days), red (expired) |
| FF-032 | The appliance screen is read-only for customers |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FFS-004 | Customer | See the appliance list before booking | I know exactly what a fully furnished flat includes |

---

## 4. Business Rules

1. The Appliances screen shows warranty countdown only if `warranty_expiry` is set; otherwise the field is omitted.
2. Serial numbers are **not** shown to customers.
