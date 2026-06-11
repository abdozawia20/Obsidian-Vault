# Ticketing Domain — NFC Gateway: Functional Document

> **Client**: Al-Andalus Park
> **Domain**: Ticketing & Access Control
> **Module**: NFC Gateway Service — Wristband Tap Processing & Reader Communication
> **Document Type**: Functional
> **Audience**: Hardware engineers, backend developers, park operations

---

## 1. Purpose & Scope

This document defines the NFC Gateway — a lightweight service that sits between the physical NFC readers (at gates, exclusive areas, and POS terminals) and the ERPNext backend. It receives tap events from NFC readers, verifies wristband authenticity via HMAC hash, resolves the tap to the correct business action (entry, exit, area access, purchase), and communicates the result back to the reader (green light / red light / display message). The gateway also handles **offline queuing** — if the ERPNext server is unreachable, taps are queued locally and synced when connectivity returns.

> [!IMPORTANT]
> **The wristband is a dumb passive NFC tag.** It stores: (1) a UID (factory-set, immutable), (2) an NFC counter (auto-incremented on every tap), and (3) user memory containing a hashed customer ID. All business logic runs server-side. The gateway is the bridge.

---

## 2. NFC Wristband Specification

### 2.1 Chip Requirements

| Spec | Value | Rationale |
|---|---|---|
| **NFC Type** | NTAG 213 or NTAG 215 | Passive, low-cost, widely supported, built-in counter |
| **Memory** | 144 bytes (NTAG 213) or 504 bytes (NTAG 215) | Stores hashed customer ID (32 bytes for SHA-256 + metadata) |
| **Counter** | Hardware auto-increment on each read | Used as HMAC nonce to prevent replay attacks |
| **UID** | 7-byte factory UID | Unique per chip, cannot be cloned |
| **Waterproof** | IP67+ silicone wristband enclosure | Must survive swimming pools |
| **Read Range** | 1–4 cm | Standard NFC range |

### 2.2 Wristband Data Layout

```
┌──────────────────────────────────────────────┐
│ Byte 0–6:   UID (factory, read-only)         │
│ Byte 7–10:  NFC Counter (auto-increment)     │
│ Byte 11–42: HMAC hash (32 bytes)             │
│ Byte 43:    Version byte (0x01)              │
│ Byte 44–47: Reserved                         │
└──────────────────────────────────────────────┘
```

### 2.3 HMAC Hash Cycle

When a wristband is assigned to a customer:

1. Server generates: `hash = HMAC-SHA256(key=nfc_hash_secret, message=customer_id + nfc_uid + initial_counter)`
2. Hash is written to wristband user memory (bytes 11–42)
3. On each subsequent tap, the gateway reads: `{uid, counter, stored_hash}`
4. Server verifies: recomputes the expected hash for this customer at this counter value
5. If valid → process action. If invalid → reject (cloned or tampered wristband)

> [!NOTE]
> The counter auto-increments on every read, so a captured hash from a previous tap cannot be replayed — the counter will have advanced.

---

## 3. NFC Reader Specification

### 3.1 Reader Types & Locations

| Reader Type | Location | Action on Tap | Hardware |
|---|---|---|---|
| `gate_entry` | Park entrance gates | Validate ticket, grant entry | Reader + turnstile relay + LED |
| `gate_exit` | Park exit gates | Log exit, decrement park occupancy | Reader + turnstile relay + LED |
| `area_entry` | Exclusive area entrance | Check capacity, debit fee, grant access | Reader + barrier relay + LED |
| `area_exit` | Exclusive area exit | Decrement area occupancy | Reader + LED |
| `pos` | Shop / restaurant / café | Identify customer for wallet debit | Reader + display + LED |

### 3.2 Reader Hardware Requirements

| Component | Spec |
|---|---|
| NFC reader module | ACR122U or equivalent (USB/UART), 13.56 MHz |
| Controller | Raspberry Pi 4 or ESP32 (WiFi + Ethernet) |
| Indicator | RGB LED (green = OK, red = denied, amber = processing) |
| Display (POS only) | Small LCD/OLED: shows customer name, balance, transaction result |
| Relay output | Dry-contact relay for turnstile/barrier gate control |
| Network | WiFi primary, Ethernet fallback |
| Power | PoE (preferred) or 5V DC adapter |

### 3.3 Reader Communication Protocol

Each reader runs a lightweight agent that communicates with the NFC Gateway:

```
Reader → Gateway:
POST /api/method/andalus.api.nfc.tap
{
  "nfc_uid": "04:A2:5C:B1:C3:D4:E5",
  "counter": 1247,
  "stored_hash": "a1b2c3d4...32-byte-hex",
  "reader_id": "GATE-ENTRY-01",
  "reader_type": "gate_entry",
  "timestamp": "2026-06-12T10:30:15Z"
}

Gateway → Reader:
{
  "status": "granted" | "denied" | "error",
  "message": "Welcome, Ahmed!",
  "customer_name": "Ahmed Al-Rashid",
  "balance": 350.00,
  "action": "open_gate" | "none",
  "display_seconds": 3
}
```

---

## 4. Gateway Business Logic

### 4.1 Tap Processing Pipeline

```
    Receive tap event
         │
         ▼
    ┌─────────────────┐
    │ 1. Validate hash │──── Invalid ──▶ {status: "denied", message: "Invalid wristband"}
    └────────┬────────┘
             │ Valid
             ▼
    ┌─────────────────┐
    │ 2. Lookup        │──── Not found ──▶ {status: "denied", message: "Wristband not registered"}
    │    wristband     │
    │    → customer    │
    └────────┬────────┘
             │ Found
             ▼
    ┌─────────────────┐
    │ 3. Check         │──── Deactivated/Lost ──▶ {status: "denied", message: "Wristband deactivated"}
    │    wristband     │
    │    status        │
    └────────┬────────┘
             │ Active
             ▼
    ┌─────────────────────────┐
    │ 4. Route by reader_type │
    │                         │
    │ gate_entry  → §4.2      │
    │ gate_exit   → §4.3      │
    │ area_entry  → §4.4      │
    │ area_exit   → §4.5      │
    │ pos         → §4.6      │
    └─────────────────────────┘
```

### 4.2 Gate Entry Logic

1. Check customer has a valid ticket for today (`status = Valid` or `status = Used` with `allow_reentry`)
2. Check park occupancy < max capacity
3. If first entry: update ticket `status → Used`, set `entry_time`
4. Increment park occupancy
5. Create `Gate Log` entry (direction = Entry)
6. Return `{status: "granted", action: "open_gate"}`

**Denial reasons**: No valid ticket, Park at capacity, Ticket expired

### 4.3 Gate Exit Logic

1. Create `Gate Log` entry (direction = Exit)
2. Decrement park occupancy
3. Update ticket `exit_time`
4. Return `{status: "granted", action: "open_gate"}`

### 4.4 Area Entry Logic

1. Check area `status = Open`
2. Check area operating hours (current time within open/close)
3. Check `current_occupancy < max_capacity`
4. Check if area is included in customer's ticket type (TK-005). If yes, fee = 0
5. If fee > 0: check wallet balance ≥ fee. If insufficient, deny
6. If fee > 0: debit wallet, create `Wallet Transaction`
7. Increment area `current_occupancy`
8. Create `Area Access Log` entry
9. Return `{status: "granted", action: "open_gate", balance: new_balance}`

**Denial reasons**: Area closed, Area full, Insufficient balance, Outside operating hours

### 4.5 Area Exit Logic

1. Decrement area `current_occupancy`
2. Update `Area Access Log` → set `exit_time`
3. Return `{status: "granted", action: "open_gate"}`

### 4.6 POS Identification Logic

1. Return customer name, wallet balance, and customer ID
2. POS operator uses this to process the transaction (separate POS flow)
3. Return `{status: "granted", customer_name, balance, action: "none"}`

> [!NOTE]
> The POS tap only **identifies** the customer. The actual purchase debit is a separate API call from the POS app after the operator enters the order total.

---

## 5. Offline Handling

### 5.1 Gateway Offline Queue

When the ERPNext server is unreachable:

| Scenario | Behaviour |
|---|---|
| **Gate entry** | Queue the tap locally. Open the gate (optimistic). Sync when online. If ticket turns out to be invalid, flag for review |
| **Gate exit** | Queue locally. Open the gate (always allow exit). Sync when online |
| **Area entry** | **Deny** — capacity checks require server state. Display "Service temporarily unavailable, please try again shortly" |
| **Area exit** | Queue locally. Open the gate. Sync when online |
| **POS** | **Deny** — balance checks require server state. Display "Cannot process payment offline" |

### 5.2 Batch Sync

When connectivity is restored, the gateway sends all queued taps to:

```
POST /api/method/andalus.api.nfc.batch_sync
{
  "taps": [
    {"nfc_uid": "...", "counter": ..., "reader_id": "...", "reader_type": "...", "timestamp": "..."},
    ...
  ]
}
```

The server processes each tap in chronological order and returns results. Conflicts (e.g., tap for an expired ticket that was optimistically admitted) are flagged for Park Manager review.

---

## 6. Hardware Deployment Plan

### 6.1 Reader Count Estimate

| Location | Count | Reader Type |
|---|---|---|
| Main gate (entry) | 4 | `gate_entry` |
| Main gate (exit) | 2 | `gate_exit` |
| Swimming pool (entry/exit) | 2 | `area_entry` + `area_exit` |
| Soccer field (entry/exit) | 2 | `area_entry` + `area_exit` |
| VIP lounge (entry) | 1 | `area_entry` |
| Restaurants (×3) | 3 | `pos` |
| Shops (×2) | 2 | `pos` |
| Cafés (×2) | 2 | `pos` |
| **Total** | **18** | |

> [!NOTE]
> Exact counts depend on park layout. These are minimum estimates for an initial deployment. Additional readers can be added without code changes — just register a new `reader_id` in the system.

### 6.2 Network Architecture

```
                    ┌──────────────────┐
                    │  ERPNext Server   │
                    │  (Cloud / On-Prem)│
                    └────────▲─────────┘
                             │ HTTPS
                    ┌────────┴─────────┐
                    │  NFC Gateway     │
                    │  Service (Local) │
                    └────────▲─────────┘
                             │ LAN (WiFi/Ethernet)
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────┴───┐  ┌──────┴─────┐  ┌────┴────────┐
     │ Gate       │  │ Area       │  │ POS         │
     │ Readers    │  │ Readers    │  │ Readers     │
     │ (RPi/ESP)  │  │ (RPi/ESP)  │  │ (RPi/ESP)   │
     └────────────┘  └────────────┘  └─────────────┘
```

---

## 7. Security Requirements

| Requirement | Description |
|---|---|
| **HMAC verification** | Every tap is verified server-side. Gateway never trusts the wristband's stored hash alone — the server recomputes |
| **Counter monotonicity** | Server rejects taps where counter ≤ last known counter (prevents replay attacks) |
| **Gateway authentication** | Gateway uses a dedicated API key with restricted permissions (can only call NFC and staff endpoints) |
| **TLS** | All gateway ↔ server communication over HTTPS. No plaintext |
| **Reader registration** | Only registered `reader_id` values are accepted. Unknown reader IDs are rejected and alerted |
| **Physical security** | Readers are tamper-resistant enclosures. USB ports are disabled on controller boards |
| **Offline queue encryption** | Queued taps are encrypted at rest on the gateway with a local key |
