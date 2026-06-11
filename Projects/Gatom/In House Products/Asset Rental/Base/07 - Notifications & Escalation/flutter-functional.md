# Notifications & Escalation — Flutter: Functional Document

> **Product**: Asset Rental Platform
> **Domain**: Notifications & Escalation
> **Module**: Customer Mobile App — Push Notifications & History
> **Document Type**: Functional
> **Audience**: UX designers, mobile developers, QA

---

## 1. Purpose & Scope

This document defines push notification handling in the Flutter app: FCM registration, foreground/background handling, notification history, and deep-linking from push taps.

---

## 2. Screen Requirements

### 2.1 Push Notifications

| # | Requirement |
|---|---|
| FR-070 | The app must register an FCM push token on login |
| FR-071 | The app must handle push notifications in foreground (in-app banner) and background (OS tray) |
| FR-072 | Tapping a push notification must navigate to the relevant screen (invoices, agreement, etc.) |
| FR-073 | A notification history screen must list all received push notifications |
| FR-074 | Push token must be deregistered on logout |
| FR-075 | **Known limitation**: FCM requires Google Play Services. Huawei devices (which lack Google Play Services) will **not receive push notifications**. These customers receive notifications via email and SMS only. HMS Push Kit support is planned for a Post-MVP release. This limitation must be documented in the platform release notes. |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|---|---|---|---|
| FS-007 | Active tenant | Receive a push reminder 3 days before payment | I never miss a due date |

---

## 4. Business Rules

1. Push token is registered immediately after login and deregistered on logout.
2. The customer sees booking approval, rejection, and expiry notifications via push.
3. Overdue reminders follow the D+1, D+3, D+7, D+14 schedule as push notifications.

---

## 5. Security Requirements

| Requirement | Description |
|---|---|
| **Push token** | Deregistered on logout to prevent misdirected notifications |
