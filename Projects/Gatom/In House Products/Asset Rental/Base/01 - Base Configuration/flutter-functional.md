# Base Configuration — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Base Configuration
> **Module**: Customer Mobile App — White-Label, Auth & Offline
> **Document Type**: Functional
> **Audience**: Product owners, mobile developers, QA

---

## 1. Purpose & Scope

This document defines the white-label configuration, authentication flow, onboarding experience, and offline support strategy for the Flutter mobile app. These are cross-cutting concerns that affect every screen.

---

## 2. Screen Requirements

### 2.1 Onboarding & Auth

| # | Requirement |
|---|---|
| FR-001 | Splash screen with brand logo must show on first launch |
| FR-002 | Onboarding slides (4 screens) must introduce the platform on first install. The 4 slides must cover: (1) What this app is for and who it serves, (2) Browse and book assets without an office visit, (3) Track agreements and pay invoices on the go, (4) Get notified before your payment is due. Actual copy is written by the client at onboarding. |
| FR-003 | Users must be able to register with email and password |
| FR-004 | Email confirmation must be required before first login |
| FR-005 | Existing users must be able to log in with email and password |
| FR-006 | Session must persist across app restarts using secure storage |
| FR-007 | Users must be able to log out, which clears credentials and deregisters push token |

### 2.2 Profile

| # | Requirement |
|---|---|
| FR-080 | The customer must be able to update their profile (name, phone, language) |
| FR-082 | Language selection must change the app locale |

---

## 3. White-Label Requirements

| Requirement | Description |
|---|---|
| **Base URL** | Configurable at build time via `--dart-define=BASE_URL=...` |
| **Brand colour** | Configurable at build time via `--dart-define=BRAND_COLOR=...` |
| **App name** | Configurable at build time via `--dart-define=APP_NAME=...` |
| **Logo** | Configurable via asset replacement in client-specific branch |
| **App distribution** | Two-tier model: (1) **Small clients**: PWA as the primary recommendation. (2) **TestFlight / APK sideload** as secondary. (3) **Own App Store / Google Play account** for clients who explicitly require public store presence. |
| **Feature flags** | `HAS_VEHICLES` / `HAS_FLATS` compile-time flags to show/hide product tabs |

---

## 4. Offline Support Requirements

| Data | Expected Behaviour when Offline |
|---|---|
| Asset catalog | Shows last-fetched results with a stale indicator |
| Asset detail | Shows cached asset if previously viewed |
| Agreements | Shows cached list; pull-to-refresh forces network |
| Invoices | Must always be fetched live. When offline, show a clear error message with a Retry button. The error screen must also display the **last known invoice summary** (amount and due date) from local cache with a "Last updated: [timestamp]" label. |
| Booking submission | Shows a clear "you are offline" error; does not silently fail |

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Credential storage** | API key + secret stored in `flutter_secure_storage` (OS keychain / keystore) |
| **No plaintext credentials** | Username and password are exchanged once for API key; never stored |
| **Route guards** | Booking, My Rentals, Payments, and Documents routes require authenticated state |
