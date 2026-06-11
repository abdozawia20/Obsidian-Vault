# Appliance Management — Frappe: Functional Document

> **Product**: Asset Rental Platform — Flat Variant
> **Domain**: Appliance Management
> **Module**: `rental_flats` — Inventory, Warranty & Condition Tracking
> **Document Type**: Functional
> **Audience**: Property managers, QA

---

## 1. Purpose & Scope

This document defines the appliance inventory per flat: tracking name, brand, model, warranty, and condition. Condition is updated during inspections. Warranty alerts fire before expiry.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| FR-030 | Each appliance must record: name, brand, model, serial number, purchase date, warranty expiry, and condition |
| FR-031 | An alert must fire 30 days before any appliance warranty expires |
| FR-032 | Appliance condition must be updatable after each inspection |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FS-005 | Property Manager | Get a warranty expiry alert for appliances | I arrange replacement before it fails for the tenant |

---

## 4. Business Rules

1. Appliance conditions are updated during entry and exit inspections — the flat's appliance record reflects the current state.
2. Warranty alerts are sent via email and Frappe ToDo to the Property Manager.
