# Base Configuration — Frappe: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Base Configuration
> **Module**: `rental_core` — System Settings & Multi-Region Configuration
> **Document Type**: Functional
> **Audience**: Platform owners, IT administrators, project managers

---

## 1. Purpose & Scope

This document defines the system-level configuration, user roles, license enforcement, and multi-region settings that underpin the entire rental platform. These settings are configured once per client site and affect all other domains.

---

## 2. User Roles

| Role | Who | Responsibilities |
|---|---|---|
| **System Manager** | Platform owner / IT | Full system access, configuration |
| **Rental Manager** | Client operations lead | All rental DocTypes; configuration read-only |
| **Rental Agent** | Sales / customer service | Create leads, quotations, agreements |
| **Accountant** | Finance | Invoices, payments, deposit ledger |
| **Customer** | End tenant (individual or company) | Portal access: own data only |

---

## 3. Business Requirements

### 3.1 System Configuration

| # | Requirement |
|---|---|
| CFG-001 | Each client site must be independently configurable via a `Rental Configuration` singleton DocType |
| CFG-002 | Multi-currency is supported — each site is configured for one default currency with a tax template (one site = one country) |
| CFG-003 | Individual and Company tenants must receive different invoice formats (B2C receipt vs. B2B tax invoice) |
| CFG-004 | Rental Configuration must validate that business contact details (email and phone) are non-empty before the suspended-account banner feature activates. If contact details are not configured, the banner must fall back to a generic "Contact your property manager" message. |

### 3.2 License Enforcement

| # | Requirement |
|---|---|
| CFG-010 | License expiry triggers a grace mode: portal and automated jobs continue for a configurable period (default: 7 days) |
| CFG-011 | During grace, payment webhooks are **logged but not reconciled** against invoices |
| CFG-012 | On license renewal, a reconciliation job is **queued as a background Frappe job** — not run synchronously on first login. The reconciliation job inherits webhook idempotency rules from BR-056 — duplicate gateway event IDs are silently discarded. |
| CFG-013 | After the grace period without renewal: all jobs halt, portal shows "Service Suspended". Data is never deleted. |

---

## 4. Security Requirements

| Requirement | Description |
|---|---|
| **Role-based access** | Each DocType has explicit `has_permission` rules per role |
| **License enforcement** | Boot-session hook disables DocType access on expired license |
| **CSRF** | Frappe's built-in CSRF protection applies to all web form submissions |
| **API authentication** | Flutter uses `token <api_key>:<api_secret>` — never username/password in headers |

---

## 5. Multi-Region Configuration Requirements

Each client site must be independently configurable for:

| Configuration | Examples / Notes |
|---|---|
| Tax template | EU VAT 20%, Egypt VAT 14%, UAE VAT 5%, KSA VAT 15%, Libya 0% |
| Payment gateway | Stripe (EU), Tap (KSA/UAE), PayMob (Egypt), Bank Transfer (Libya) |
| KYC document types | Passport + residency (EU), National ID (MENA), Driving license (vehicles) |
| Contract language | English, Arabic (RTL), Turkish, French |
| Currency | EUR, USD, TRY, EGP, LYD, AED, SAR |
| Date format | Gregorian vs. Hijri display |
| Grace period | Number of days before late fee applies |
| Renewal alert | Days before contract expiry to send renewal notice |
| Draft expiry window | Hours before an unreviewed booking auto-expires (default: 48h) |
| Deposit dispute window | Calendar days before unchallenged deposit deductions auto-commit (default: 5). Clients in markets with non-standard weekends (e.g., Fri/Sat) should adjust the window accordingly |
| License grace period | Days after license expiry before portal and jobs are suspended (default: 7) |
| Rent escalation cap | Maximum % rent increase per year, per country |
| Open-ended notice period | Default minimum days before open-ended agreement can be terminated (default: 30) |
| Flat inspection reminder | Months between mandatory periodic inspection reminders (default: 11) |
| Self-cancel limit | Maximum booking cancellations per customer per rolling 30-day window (default: 3) |
| Webhook log retention | Months before Payment Webhook Log entries are archived/purged (default: 13) |

> **⚠️ E-Invoicing Compliance Notice**
> This platform generates standard ERPNext Sales Invoices. These are **not pre-configured** for ZATCA (KSA), ETA (Egypt), or e-Fatura (Turkey) compliance. Clients must install a certified ERPNext e-invoicing integration app before going live in these markets. Compliance is entirely the client's responsibility.

---

## 6. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **License server** | Outbound (read) | License key validation |
