# Base Configuration — Web: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Base Configuration
> **Module**: Customer-Facing Website — Design System & Localisation
> **Document Type**: Functional
> **Audience**: UX designers, frontend developers, QA

---

## 1. Purpose & Scope

This document defines the design system, localisation, and global UX standards applied to the customer-facing web portal. These settings are configured per client and affect all web pages.

---

## 2. Design Requirements

| Element | Requirement |
|---|---|
| Typography | Inter (Google Fonts) via `@import` |
| Primary colour | CSS variable `--rental-primary` — overridable per client via Site Settings |
| Responsive | Mobile-first; Bootstrap 5 grid |
| RTL | CSS override file loaded automatically for Arabic/Persian users |
| Micro-animations | Card hover lift (translate-Y), button press scale — CSS transition only |
| Loading state | Spinner overlay on AJAX catalog reload |

---

## 3. Multi-Language Requirements

- All user-facing strings must be wrapped in `{{ _("...") }}` (Jinja) or `__("...")` (JS)
- RTL layout must apply automatically when user language is `ar` or `fa`
- Translation files extracted by `bench build` and stored in `rental_core/translations/`

---

## 4. Security Requirements

| Requirement | Description |
|---|---|
| **CSRF protection** | Frappe's built-in CSRF token applied to all form submissions |
| **robots.txt** | `/my-*` and `/pay/*` disallowed for search engine crawlers |
