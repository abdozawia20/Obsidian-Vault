# Traffic Violations — Flutter: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: Traffic Violations
> **Module**: Customer Mobile App — Violation Reporting & History

---

## 1. Purpose & Scope

The Flutter app lets tenants self-report violations and view their violation history with status tracking.

---

## 2. Screen Requirements

| # | Requirement |
|---|---|
| VF-040 | Tenants can report a received traffic violation |
| VF-041 | Report form: violation type, fine amount, violation date, issuing authority |
| VF-042 | Evidence upload: photo/PDF. Photos **compressed to ≤2MB** with progress indicator and retry on failure. |
| VF-043 | Violation list: open, paid, disputed — with **status badge** (`Pending Review`, `Confirmed`, `Disputed`, `Paid`) |
| VF-044 | Charge status (Tenant / Fleet) visible per violation |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| VFS-005 | Active tenant | Report a traffic violation from the app | I handle it promptly |

---

## 4. Business Rules

1. Self-reported violations default to `Pending Review` — cannot be charged until Fleet Manager confirms.
2. Guarantors do NOT see violation data.
