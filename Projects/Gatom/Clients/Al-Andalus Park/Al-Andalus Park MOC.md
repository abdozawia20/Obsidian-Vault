---
tags: [moc, client, erpnext, frappe, gatom, al-andalus-park, hospitality, park, ticketing, nfc]
---

# 🗺 Al-Andalus Park — Map of Content

> **Client**: Al-Andalus Park
> **Agency**: [[../../Gatom MOC|Gatom]]
> **Project**: Park management platform — ticketing, exclusive areas, accommodation & retail
> **Stack**: ERPNext (backend data), Mobile App, NFC Wristbands (TBD)
> **Status**: 🟢 Active

---

## 🏞 Project Overview

Al-Andalus Park is a nature park offering a layered guest experience:

| Domain | Description |
|---|---|
| 🎟 **Gate & Ticketing** | General admission — customers purchase tickets to enter the park and enjoy nature |
| 🏊 **Exclusive Areas** | Premium zones (swimming pools, soccer fields, etc.) requiring separate access passes |
| 🏨 **Accommodation** | Residential area with rooms available for short-term rental |
| 🛍 **Retail & F&B** | Internal shops, restaurants, and cafes |
| 📱 **Customer Interaction** | Mobile app + NFC wristbands for purchases and area access *(analysis pending)* |

---

## 🧩 Business Domains

### 🎟 Gate & Ticketing
- General park entry tickets
- Ticket types, pricing tiers, seasonal rates
- Capacity management & visitor tracking

### 🏊 Exclusive Areas
- Swimming pools, soccer fields, and other premium zones
- Exclusive access passes / add-on tickets
- Scheduling, availability, and capacity per zone

### 🏨 Accommodation *(powered by [Asset Rental — Flat Module](../../In%20House%20Products/Asset%20Rental/Flats/Flats%20MOC))*
- Room inventory & types — modelled as Rental Assets (Flat variant) via `rental_flats`
- Reservation lifecycle (booking → check-in → check-out) — uses Rental Agreement workflow
- Pricing, availability calendar — uses Base + Flat pricing engine
- Utility billing, appliance management, and insurance from the Flat module apply to rooms

### 🛍 Retail & F&B
- Shops, restaurants, cafes (internal POS)
- Menu / product catalog management
- Order processing & payment

### 📱 Customer Interaction Layer
- Mobile app for ticket purchase, area booking, orders
- NFC wristband integration for cashless payments & area access
- ⚠️ *NFC architecture not yet analyzed*

---

## 📄 Documents

| Document | Purpose |
|---|---|
| [[Ticketing/customer-interaction-analysis\|Customer Interaction Analysis]] | App vs NFC vs Hybrid — architecture decision (✅ Hybrid chosen) |
| [[Ticketing/frappe-functional\|Frappe Functional]] | ERPNext data model: 13 DocTypes, roles, wallet, tickets, areas, API surface |
| [[Ticketing/flutter-functional\|Flutter Functional]] | Customer app: ticket purchase, wallet, area availability, wristband linking |
| [[Ticketing/nfc-gateway-functional\|NFC Gateway Functional]] | Wristband spec, HMAC protocol, reader types, tap routing, offline queue |
| [[Ticketing/staff-pos-functional\|Staff POS Functional]] | Gate agent & POS operator app: ticket sales, top-ups, wristband management |

---

## 🔗 Related

- [[../../Gatom MOC|↑ Gatom]] — the agency managing this project
- [[../../In House Products/Asset Rental/Flats/Flats MOC|Asset Rental — Flat Module]] — powers the accommodation domain (rooms = flats)
- [[../../../../../Home|🏠 Home]]
