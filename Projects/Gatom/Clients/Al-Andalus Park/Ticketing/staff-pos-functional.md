# Ticketing Domain — Staff POS App: Functional Document

> **Client**: Al-Andalus Park
> **Domain**: Ticketing & Access Control
> **Module**: Staff Mobile App — Ticket Sales, Wallet Top-Up, Wristband Management
> **Document Type**: Functional
> **Audience**: Product owners, mobile developers, park operations

---

## 1. Purpose & Scope

This document defines the staff-facing mobile/tablet app used by Gate Agents and POS Operators. Unlike the customer app (which is a companion for browsing and pre-visit purchases), this app is an **operational tool** for in-park staff. It handles: selling tickets at the gate, issuing and deactivating wristbands, topping up customer wallets (cash or card), processing POS purchases via wristband tap, and viewing real-time park/area occupancy.

> [!IMPORTANT]
> **This is NOT the Frappe Desk.** Frappe Desk handles back-office operations (reports, configuration, Park Manager tasks). The Staff POS App is a purpose-built, touch-optimized interface for frontline staff who need speed and simplicity — not a full ERP UI.

---

## 2. Screen Requirements

### 2.1 Auth & Role Selection

| # | Requirement |
|---|---|
| ST-001 | Staff login with ERPNext credentials (email + password → API key exchange) |
| ST-002 | After login, staff selects their active role for this session: `Gate Agent`, `POS Operator`, or `Area Attendant`. This filters the UI to relevant screens only |
| ST-003 | Session persists until explicit logout or 8-hour auto-expiry |
| ST-004 | Staff can switch roles without re-logging in |

### 2.2 Gate Agent — Ticket Sales

| # | Requirement |
|---|---|
| ST-010 | "Sell Ticket" screen: select ticket type, quantity, and date (default: today) |
| ST-011 | Price auto-calculates including group discounts. Total displayed prominently |
| ST-012 | Payment method selector: `Cash`, `Card` (external card terminal), `Wallet` (if customer has existing account) |
| ST-013 | For walk-in customers: system auto-creates anonymous `Park Customer` account — no data entry required from the gate agent |
| ST-014 | After sale, the screen prompts "Scan wristband to assign" — agent taps a wristband on the reader connected to their device |
| ST-015 | Confirmation screen: ticket number, customer (name or "Walk-in #XXXX"), wristband UID, balance (if wallet was loaded) |

### 2.3 Gate Agent — Wristband Management

| # | Requirement |
|---|---|
| ST-020 | "Issue Wristband" flow: (1) scan wristband NFC UID, (2) optionally scan customer QR code from their app (for registered users) or create anonymous account, (3) link wristband to customer |
| ST-021 | "Deactivate Wristband": enter NFC UID or scan wristband → confirm deactivation → if registered customer, remaining balance is preserved on account. If anonymous, forfeited |
| ST-022 | "Re-assign Wristband": deactivate current link, then assign to new customer in one flow |
| ST-023 | Wristband status lookup: scan or enter NFC UID → shows linked customer, status, balance, last tap location |

### 2.4 Gate Agent / POS Operator — Wallet Top-Up

| # | Requirement |
|---|---|
| ST-030 | "Top Up" screen: scan customer wristband → shows current balance → enter top-up amount |
| ST-031 | Amount validates against min/max from `Park Configuration` |
| ST-032 | Payment received: `Cash` or `Card` (external terminal). Staff confirms receipt |
| ST-033 | On confirm: wallet credited, `Wallet Transaction` created with source `POS Top-Up` and operator recorded |
| ST-034 | Confirmation: shows new balance, prints receipt (if thermal printer connected) |

### 2.5 POS Operator — Purchase Processing

| # | Requirement |
|---|---|
| ST-040 | "New Sale" screen: customer taps wristband → shows customer name and balance |
| ST-041 | Operator enters order total (manual entry — no item-level catalog in v1) |
| ST-042 | If balance ≥ total: debit wallet, create `Wallet Transaction` (source: `POS Purchase`), create `POS Invoice` |
| ST-043 | If balance < total: show shortfall, offer "Top Up First" flow (transitions to ST-030) |
| ST-044 | Transaction history for this POS session: list of all transactions processed by this operator today |
| ST-045 | End-of-day reconciliation: total wallet debits, total cash received for top-ups, discrepancy flag |

### 2.6 Area Attendant — Occupancy

| # | Requirement |
|---|---|
| ST-050 | "My Area" screen: shows assigned area name, status, current occupancy / max capacity with visual bar |
| ST-051 | "Manual Adjust" button: enter corrected headcount. System updates `current_occupancy`. Creates audit log |
| ST-052 | "Close Area" / "Open Area" toggle: changes area status, triggers push notification to customer app (for registered users in the park) |

### 2.7 Dashboard (All Roles)

| # | Requirement |
|---|---|
| ST-060 | Real-time park occupancy counter |
| ST-061 | Area status overview: all areas with occupancy bars |
| ST-062 | Today's stats: tickets sold, total top-ups, total wallet debits |

---

## 3. Hardware Requirements

| Feature | Requirement |
|---|---|
| **Device** | Android tablet (8–10") recommended for POS; Android phone acceptable for gate agents |
| **NFC** | Device must have built-in NFC reader for wristband scanning. If not, external USB NFC reader via OTG |
| **Printer** | Optional: Bluetooth thermal receipt printer for top-up and purchase receipts |
| **Connectivity** | WiFi to park LAN. Cellular as fallback |

---

## 4. Offline Behaviour

| Action | Offline Behaviour |
|---|---|
| Ticket sale | **Blocked** — requires server for ticket creation and wallet linking |
| Wristband scan | Can read NFC UID offline but cannot verify or process — show "Reconnecting..." |
| Wallet top-up | **Blocked** — requires server for balance update |
| POS purchase | **Blocked** — requires server for balance check |
| Occupancy view | Shows last-known values with stale warning |

> [!NOTE]
> The Staff POS App requires connectivity for all transactional operations. Offline mode is limited to read-only cached data. The NFC Gateway (separate system) handles offline gate operations — the staff app is for assisted transactions only.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Role enforcement** | Staff can only access screens matching their ERPNext role |
| **Operator audit** | Every transaction logs the operator's user ID |
| **Session timeout** | Auto-logout after 8 hours of inactivity |
| **No customer data storage** | App does not persist customer data locally — all lookups are live from server |
| **Device lock** | App should enforce device PIN/biometric before launch in production |
