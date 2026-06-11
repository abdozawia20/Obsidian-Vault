# Ticketing Domain — Flutter: Functional Document

> **Client**: Al-Andalus Park
> **Domain**: Ticketing & Access Control
> **Module**: Customer Mobile App — Browse, Buy, Top-Up, Link Wristband
> **Document Type**: Functional
> **Audience**: Product owners, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the Flutter customer-facing app screens for Al-Andalus Park's ticketing domain. The app serves as the **digital companion** — visitors use it to browse ticket types, purchase tickets, top up their wallet, view live area availability, link their NFC wristband, and review spending history. The app is **never required** for in-park interactions (the wristband handles that), but it enhances the experience for pre-visit planning and post-visit review.

> [!IMPORTANT]
> **Walk-in visitors do not need the app.** The app is an optional enhancement. All in-park interactions work via wristband alone. The app targets repeat visitors, families who want to plan ahead, and tech-savvy customers who value a digital experience.

---

## 2. Screen Requirements

### 2.1 Onboarding & Auth

| # | Requirement |
|---|---|
| FL-001 | Splash screen with Al-Andalus Park branding and nature-themed animation on first launch |
| FL-002 | Onboarding slides (3 screens): (1) "Welcome to Al-Andalus Park — nature, adventure, and relaxation", (2) "Buy tickets, top up your wallet, and skip the queue", (3) "Link your wristband to track your spending and explore exclusive areas" |
| FL-003 | Users can register with phone number + OTP verification (primary) or email + password (secondary) |
| FL-004 | Guest mode: users can browse ticket types, prices, and area availability **without** creating an account. Purchase and wallet features require login |
| FL-005 | Session persists across app restarts using secure storage |
| FL-006 | Logout clears credentials and deregisters push notification token |

### 2.2 Home / Dashboard

| # | Requirement |
|---|---|
| FL-010 | Home screen shows: park status (Open/Closed), current weather widget, wallet balance card, and quick-action buttons (Buy Ticket, Top Up, View Areas) |
| FL-011 | If the user has an active ticket for today, show a ticket card with entry time, ticket type, and a QR code for wristband linking |
| FL-012 | Live park occupancy indicator: "Busy / Moderate / Quiet" based on `current_occupancy / max_capacity` ratio |
| FL-013 | Promotional banner carousel (managed in Frappe as `Park Announcement` DocType — out of scope for this domain, but the UI slot must exist) |

### 2.3 Ticket Purchase

| # | Requirement |
|---|---|
| FL-020 | Ticket type selection screen listing all active ticket types with: name, price, included areas, and group discount info |
| FL-021 | Price dynamically adjusts based on selected date (weekday/weekend) and active seasonal pricing |
| FL-022 | Quantity selector with automatic group discount preview when threshold is met (e.g., "10+ tickets: save 10%!") |
| FL-023 | Date picker for ticket validity date. Default: today. Cannot select past dates or dates when park is closed |
| FL-024 | Order summary screen showing: ticket type, quantity, unit price, discount, total. Confirm button triggers payment |
| FL-025 | Payment flow: debit from wallet balance first. If wallet balance is insufficient, prompt to top up the difference via payment gateway |
| FL-026 | After purchase, show confirmation with ticket details and a QR code linking to the customer's wristband account |
| FL-027 | Purchase history: list of all past tickets with date, type, quantity, and status (Valid / Used / Expired) |

### 2.4 Wallet

| # | Requirement |
|---|---|
| FL-030 | Wallet screen shows current balance prominently (large number, branded color) |
| FL-031 | "Top Up" button opens amount selection: preset amounts (50, 100, 200, 500) + custom amount input |
| FL-032 | Custom amount validates against min/max from `Park Configuration` |
| FL-033 | Top-up payment via integrated payment gateway (Apple Pay, Google Pay, card) |
| FL-034 | Transaction history: scrollable list of all wallet transactions with type icon (↑ credit, ↓ debit), amount, source, timestamp |
| FL-035 | Filter transactions by type: All, Credits, Debits |
| FL-036 | Each transaction shows `balance_after` so the user sees a running balance |

### 2.5 Exclusive Areas

| # | Requirement |
|---|---|
| FL-040 | Areas screen shows a list/grid of all exclusive areas with: name, type icon, status badge (Open / Closed), live occupancy bar (e.g., "23/50"), and access fee |
| FL-041 | Occupancy bar is color-coded: green (< 50%), amber (50–80%), red (> 80%), grey (Closed) |
| FL-042 | Tapping an area opens detail view: description, photos (managed in Frappe), operating hours, current occupancy, and access fee |
| FL-043 | If the area is included in the user's ticket type, show a "Included in your ticket" badge. Otherwise, show the fee |
| FL-044 | No booking or reservation UI — access is FIFO via wristband tap. The app is informational only for areas |
| FL-045 | If area status is `Closed`, show the closure reason and disable the occupancy bar |

### 2.6 Wristband Linking

| # | Requirement |
|---|---|
| FL-050 | "Link Wristband" button on the home screen and profile page |
| FL-051 | Opens the device camera to scan a QR code printed on the wristband packaging or displayed at the gate kiosk |
| FL-052 | QR code contains the wristband's `nfc_uid`. The app sends this to the `/api/method/andalus.api.wristband.link` endpoint |
| FL-053 | On success, show confirmation: "Wristband linked! Your wallet balance is now accessible via wristband tap" |
| FL-054 | If the wristband is already linked to another customer, show an error: "This wristband is already in use. Please ask a gate agent for assistance" |
| FL-055 | Profile screen shows linked wristband status (linked / not linked) and a "Unlink" option |

### 2.7 Park Info

| # | Requirement |
|---|---|
| FL-060 | Park information screen: operating hours (per day of week), location map (static image or embedded map), contact information |
| FL-061 | FAQ / help section with expandable cards for common questions: "How do I top up my wristband?", "What if I lose my wristband?", "Can I get a refund?" |

### 2.8 Profile & Settings

| # | Requirement |
|---|---|
| FL-070 | Profile edit: name, phone, email |
| FL-071 | Language selection (Arabic, English at minimum) |
| FL-072 | Push notification toggle |
| FL-073 | Visit history: list of past visits with date, ticket type, total spent, areas visited |

---

## 3. Offline Support

| Screen / Data | Behaviour When Offline |
|---|---|
| Ticket types & prices | Show last-fetched data with stale indicator |
| Wallet balance | Show last-known balance with "Last updated: [time]" |
| Area availability | Show last-known occupancy with stale warning |
| Ticket purchase | Blocked — show "You are offline. Connect to purchase tickets" |
| Wallet top-up | Blocked — show "You are offline. Connect to top up" |
| Transaction history | Show cached history with pull-to-refresh when online |
| Wristband linking | Blocked — requires network for QR verification |

---

## 4. Security Requirements

| Requirement | Description |
|---|---|
| **Credential storage** | API key + secret stored in `flutter_secure_storage` (OS keychain / keystore) |
| **No plaintext credentials** | Phone/OTP or email/password exchanged once for API key; never stored |
| **Route guards** | Wallet, Purchase, Profile, and Wristband screens require authenticated state |
| **Payment security** | Payment gateway SDK handles card data — app never touches raw card numbers |
| **QR code validation** | QR scan result is sent to server for validation — no client-side trust |

---

## 5. Push Notifications

| Event | Notification |
|---|---|
| Ticket purchased | "Your ticket for [date] is confirmed! Show your QR at the gate" |
| Wallet top-up successful | "₹[amount] added. Your balance is ₹[new_balance]" |
| Area closed | "[Area Name] is now closed: [reason]" |
| Low wallet balance | "Your balance is below ₹[threshold]. Top up to keep enjoying the park!" |
| Wristband linked | "Wristband linked successfully. Tap to enter!" |
