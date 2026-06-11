# Ticketing Domain — Frappe: Functional Document

> **Client**: Al-Andalus Park
> **Domain**: Ticketing & Access Control
> **Module**: `andalus_park` — Ticketing, Wallet, NFC, Exclusive Areas
> **Document Type**: Functional
> **Audience**: Park operations, IT administrators, project managers

---

## 1. Purpose & Scope

This document defines the ERPNext/Frappe backend for Al-Andalus Park's ticketing system. It covers: general admission tickets, pre-loaded customer wallets, NFC wristband provisioning, exclusive area access (FIFO with capacity caps), staff-side balance management, and the POS top-up flow. The data model lives entirely in ERPNext; the Flutter customer app and NFC Gateway are thin clients consuming the Frappe REST API.

> [!IMPORTANT]
> **Design philosophy**: The wristband is a **dumb credential** — it stores only a hashed customer ID cycled by the NFC counter. All business logic (balance checks, access authorization, capacity enforcement) runs server-side in ERPNext. The wristband never stores balance or ticket data.

---

## 2. User Roles

| Role | Who | Responsibilities |
|---|---|---|
| **System Manager** | Gatom / IT | Full system access, configuration, ERPNext admin |
| **Park Manager** | Park operations lead | All park DocTypes; configuration; reporting |
| **Gate Agent** | Entry/exit booth staff | Sell tickets, issue wristbands, top up wallets |
| **Area Attendant** | Pool, field, zone staff | Validate area access, monitor capacity |
| **POS Operator** | Shop/restaurant/café cashier | Process purchases, top up customer wallets |
| **Customer** | Park visitor (registered) | App access: buy tickets, view balance, link wristband |
| **Walk-in** | Park visitor (anonymous) | No app — wristband-only, anonymous account |

---

## 3. Business Requirements

### 3.1 Park Configuration

| # | Requirement |
|---|---|
| PK-001 | A `Park Configuration` singleton stores all site-wide settings: park name, currency, timezone, operating hours, max park capacity, and NFC settings |
| PK-002 | Operating hours define gate open/close times per day of week. Gates reject ticket scans outside operating hours |
| PK-003 | Maximum park capacity is enforced — when reached, gate agents see a "CAPACITY FULL" warning and new entries are blocked until visitors exit |
| PK-004 | Currency is pre-configured (e.g., SAR, AED, EGP). All wallet balances and prices use this currency |

### 3.2 Ticket Types & Pricing

| # | Requirement |
|---|---|
| TK-001 | Multiple ticket types must be configurable: e.g., `General Admission`, `VIP`, `Child`, `Group (10+)` |
| TK-002 | Each ticket type has a base price. Prices can vary by day-of-week (weekend vs. weekday) and by season (configured date ranges) |
| TK-003 | Ticket types can be marked as `Active` or `Disabled`. Disabled types are hidden from the app and POS |
| TK-004 | Group tickets auto-apply a configurable discount percentage when quantity ≥ threshold (e.g., 10% off for 10+) |
| TK-005 | Each ticket type defines which areas are included in the base price and which require an exclusive access add-on |

### 3.3 Customer & Wristband

| # | Requirement |
|---|---|
| CW-001 | A `Park Customer` DocType represents every visitor — both registered (app users) and anonymous (walk-ins) |
| CW-002 | Walk-in customers get an auto-generated anonymous account at the gate POS. No personal data is required. The account exists only to link the wristband and wallet |
| CW-003 | Registered customers (via app) can optionally link a profile with name, phone, and email for receipts and loyalty |
| CW-004 | Each `Park Customer` has exactly one `Wallet` with a pre-loaded balance. All in-park spending deducts from this wallet |
| CW-005 | A `Wristband` record tracks each physical wristband: its NFC UID, linked customer, hash seed, activation time, and status |
| CW-006 | The wristband is **kept by the customer** after their visit. It stores a hashed customer ID cycled by the NFC chip's counter. The hash algorithm and seed are server-side — the wristband is a passive credential |
| CW-007 | A wristband can be **re-linked** to a new customer on a subsequent visit. The old link is deactivated and a new wallet is created (or the existing registered customer's wallet is reused) |
| CW-008 | Lost wristband: the gate agent can deactivate a wristband by customer lookup. Any remaining balance transfers to the customer's account (for registered customers) or is forfeited (for anonymous walk-ins) |

### 3.4 Wallet & Balance

| # | Requirement |
|---|---|
| WL-001 | Every `Park Customer` has a `Customer Wallet` with a `balance` field (Currency). Balance starts at 0 and is always ≥ 0 |
| WL-002 | Balance is topped up via: (a) app purchase (payment gateway), (b) gate POS (cash/card), (c) staff manual top-up in Frappe Desk |
| WL-003 | Every balance change (top-up, purchase, refund, transfer) creates a `Wallet Transaction` log entry with: amount, type (`Credit` / `Debit`), source, timestamp, and operator |
| WL-004 | A purchase is rejected if wallet balance is insufficient. The POS/NFC gateway returns "Insufficient balance" and suggests the nearest recharge point |
| WL-005 | Minimum top-up amount is configurable in `Park Configuration` (e.g., 50 SAR) |
| WL-006 | Maximum wallet balance is configurable (anti-money-laundering cap, e.g., 5,000 SAR) |
| WL-007 | Staff manual top-up requires the `Park Manager` or `Gate Agent` role and creates an auditable log entry with the operator's user ID |
| WL-008 | Refunds (e.g., area closed due to weather) credit the customer's wallet. Cash refunds are not supported through the system — they are handled offline |

### 3.5 Gate Operations

| # | Requirement |
|---|---|
| GT-001 | Gate entry requires a valid ticket (purchased via app or gate POS) and an active wristband |
| GT-002 | The gate flow for **walk-ins**: (1) customer buys ticket at gate POS, (2) gate agent assigns a wristband (scans NFC UID), (3) system creates anonymous `Park Customer`, links wristband, creates wallet, (4) customer tops up wallet if desired, (5) wristband tap grants entry |
| GT-003 | The gate flow for **app users**: (1) customer buys ticket in the app and pre-loads wallet, (2) at the gate, agent scans wristband and links to existing customer account via QR code from the app, (3) wristband tap grants entry |
| GT-004 | Gate exit logs the exit time. No balance check is needed at exit |
| GT-005 | Re-entry: a customer who exits can re-enter the same day if their ticket allows it. The system checks the ticket's `allow_reentry` flag |
| GT-006 | The system tracks **current park occupancy** in real-time: `occupancy = entries_today - exits_today`. When occupancy ≥ `max_park_capacity`, new entries are blocked |
| GT-007 | Tickets are valid for the **date of purchase** only (single-day). Multi-day visitors use the Flat module (`rental_flats`) for room check-in, which grants daily gate re-entry |

### 3.6 Exclusive Areas

| # | Requirement |
|---|---|
| EA-001 | An `Exclusive Area` DocType represents each premium zone: swimming pool, soccer field, VIP lounge, etc. |
| EA-002 | Each area has: name, type (select), max capacity, current occupancy, status (`Open`, `Closed`, `Maintenance`), and an access fee (can be 0 for VIP-ticket holders) |
| EA-003 | Access is **FIFO**: when a customer taps their wristband at an area gate, the system checks capacity. If `current_occupancy < max_capacity`, access is granted and occupancy increments. Otherwise, access is denied with "Area Full" |
| EA-004 | Exit from an area decrements occupancy. Area attendants can also manually adjust occupancy (e.g., headcount reconciliation) |
| EA-005 | Access fee is deducted from the customer's wallet at entry. If the area is included in the customer's ticket type (per TK-005), the fee is waived |
| EA-006 | Closing an area (e.g., weather, maintenance) blocks new entries. Customers already inside are not ejected. A notification is pushed to the app (for registered users) explaining the closure |
| EA-007 | Operating hours per area are configurable and can differ from park operating hours (e.g., pool closes at sunset) |
| EA-008 | Capacity and occupancy data is exposed via API for the Flutter app to show live availability |

### 3.7 POS Operations

| # | Requirement |
|---|---|
| POS-001 | Shops, restaurants, and cafés use ERPNext POS profiles linked to their cost center |
| POS-002 | At POS, the customer taps their wristband. The system identifies the customer via NFC hash → customer lookup |
| POS-003 | The POS operator enters the order total. The system debits the customer's wallet and creates a `Wallet Transaction` |
| POS-004 | If the customer's balance is insufficient, the POS shows the shortfall and offers to top up on the spot |
| POS-005 | POS operators can top up a customer's wallet (cash received → credit wallet). This creates a `Wallet Transaction` with type `Credit` and source `POS Top-Up` |
| POS-006 | Every POS transaction creates a standard ERPNext `POS Invoice` linked to the customer and the POS profile |
| POS-007 | Daily POS closing: each POS profile must reconcile total wallet debits against physical cash/card collected. Discrepancies are flagged |

---

## 4. Data Model (DocTypes)

### 4.1 `Park Configuration` (Singleton)

| Field | Type | Default | Source |
|---|---|---|---|
| `park_name` | Data | | PK-001 |
| `currency` | Link → Currency | | PK-004 |
| `timezone` | Select | | PK-001 |
| `max_park_capacity` | Int | 1000 | PK-003 |
| `min_topup_amount` | Currency | 50 | WL-005 |
| `max_wallet_balance` | Currency | 5000 | WL-006 |
| `nfc_hash_algorithm` | Select: `HMAC-SHA256`, `HMAC-SHA1` | `HMAC-SHA256` | CW-006 |
| `nfc_hash_secret` | Password | | CW-006 |
| `operating_hours` | Table → `Operating Hour` | | PK-002 |
| `gate_entry_message` | Small Text | | |
| `capacity_full_message` | Small Text | "Park is at full capacity" | PK-003 |

### 4.2 `Operating Hour` (Child Table)

| Field | Type | Notes |
|---|---|---|
| `day_of_week` | Select | Monday–Sunday |
| `open_time` | Time | |
| `close_time` | Time | |
| `is_closed` | Check | If checked, park is closed this day |

### 4.3 `Ticket Type`

| Field | Type | Notes | Source |
|---|---|---|---|
| `ticket_name` | Data | e.g., "General Admission", "VIP" | TK-001 |
| `base_price` | Currency | Weekday price | TK-002 |
| `weekend_price` | Currency | Fri/Sat price (configurable) | TK-002 |
| `is_active` | Check | Default 1 | TK-003 |
| `allow_reentry` | Check | Default 1 | GT-005 |
| `group_discount_threshold` | Int | Quantity for group discount | TK-004 |
| `group_discount_pct` | Percent | e.g., 10 | TK-004 |
| `included_areas` | Table → `Included Area` | Areas with waived access fee | TK-005 |
| `seasonal_pricing` | Table → `Seasonal Price` | Date-range overrides | TK-002 |

### 4.4 `Included Area` (Child Table)

| Field | Type | Notes |
|---|---|---|
| `exclusive_area` | Link → Exclusive Area | Area included in this ticket type |

### 4.5 `Seasonal Price` (Child Table)

| Field | Type | Notes |
|---|---|---|
| `season_name` | Data | e.g., "Summer Peak" |
| `start_date` | Date | |
| `end_date` | Date | |
| `price` | Currency | Overrides base_price during this range |

### 4.6 `Park Customer`

| Field | Type | Notes | Source |
|---|---|---|---|
| `customer_name` | Data | Auto-generated for walk-ins: "WALK-XXXX" | CW-001, CW-002 |
| `customer_type` | Select | `Registered`, `Walk-In` | CW-001 |
| `email` | Data | Optional for walk-ins | CW-003 |
| `phone` | Data | Optional for walk-ins | CW-003 |
| `linked_user` | Link → User | For app-registered customers | CW-003 |
| `status` | Select | `Active`, `Suspended` | |
| `total_visits` | Int | Auto-incremented on gate entry | |
| `created_at_gate` | Check | True if created during walk-in flow | CW-002 |

### 4.7 `Customer Wallet`

| Field | Type | Notes | Source |
|---|---|---|---|
| `customer` | Link → Park Customer | One wallet per customer | WL-001 |
| `balance` | Currency | Current balance, always ≥ 0 | WL-001 |
| `lifetime_topup` | Currency | Sum of all credits (analytics) | |
| `lifetime_spent` | Currency | Sum of all debits (analytics) | |
| `last_activity` | Datetime | Last transaction timestamp | |

### 4.8 `Wallet Transaction`

| Field | Type | Notes | Source |
|---|---|---|---|
| `wallet` | Link → Customer Wallet | | WL-003 |
| `customer` | Link → Park Customer | Denormalized for faster queries | |
| `transaction_type` | Select | `Credit`, `Debit` | WL-003 |
| `amount` | Currency | Always positive; type determines direction | WL-003 |
| `source` | Select | `App Purchase`, `Gate POS`, `Staff Manual`, `POS Top-Up`, `Area Fee`, `POS Purchase`, `Refund`, `Balance Transfer` | WL-003 |
| `reference_doctype` | Data | e.g., "POS Invoice", "Park Ticket" | |
| `reference_name` | Data | e.g., "POS-INV-00042" | |
| `operator` | Link → User | Staff who processed (null for app self-service) | WL-007 |
| `notes` | Small Text | Optional description | |
| `balance_after` | Currency | Snapshot of wallet balance after this transaction | |

### 4.9 `Park Ticket`

| Field | Type | Notes | Source |
|---|---|---|---|
| `ticket_type` | Link → Ticket Type | | TK-001 |
| `customer` | Link → Park Customer | | |
| `purchase_date` | Date | | |
| `valid_date` | Date | Date the ticket is valid for | GT-007 |
| `quantity` | Int | Number of entries (1 for individual, 10+ for group) | TK-004 |
| `unit_price` | Currency | Price per ticket at time of purchase | |
| `total_price` | Currency | quantity × unit_price (after discount) | |
| `discount_applied` | Percent | Group discount if applicable | TK-004 |
| `purchase_source` | Select | `App`, `Gate POS` | |
| `status` | Select | `Valid`, `Used`, `Expired`, `Cancelled` | |
| `entry_time` | Datetime | Logged on first gate entry | |
| `exit_time` | Datetime | Logged on gate exit | |
| `allow_reentry` | Check | Copied from ticket type at purchase | GT-005 |
| `payment_reference` | Data | Gateway transaction ID or POS invoice | |

### 4.10 `Wristband`

| Field | Type | Notes | Source |
|---|---|---|---|
| `nfc_uid` | Data | Unique physical NFC chip UID (read-only after creation) | CW-005 |
| `customer` | Link → Park Customer | Currently linked customer | CW-005 |
| `hash_seed` | Data | Server-side seed for hashing customer ID | CW-006 |
| `status` | Select | `Available`, `Active`, `Deactivated`, `Lost` | CW-005 |
| `activated_on` | Datetime | When last linked to a customer | |
| `deactivated_on` | Datetime | When last deactivated | |
| `total_taps` | Int | Cumulative NFC counter value (analytics) | |
| `last_tap_location` | Data | Last gate/POS/area where tapped | |

### 4.11 `Exclusive Area`

| Field | Type | Notes | Source |
|---|---|---|---|
| `area_name` | Data | e.g., "Olympic Pool", "Soccer Field A" | EA-001 |
| `area_type` | Select | `Swimming Pool`, `Sports Field`, `VIP Lounge`, `Playground`, `Other` | EA-001 |
| `max_capacity` | Int | | EA-002 |
| `current_occupancy` | Int | Real-time counter, default 0 | EA-002 |
| `status` | Select | `Open`, `Closed`, `Maintenance` | EA-002 |
| `access_fee` | Currency | Fee deducted from wallet on entry (0 = free) | EA-002 |
| `operating_hours` | Table → `Operating Hour` | Per-area schedule | EA-007 |
| `closure_reason` | Small Text | Shown to customers when status = Closed | EA-006 |

### 4.12 `Area Access Log`

| Field | Type | Notes | Source |
|---|---|---|---|
| `area` | Link → Exclusive Area | | EA-003 |
| `customer` | Link → Park Customer | | |
| `wristband` | Link → Wristband | | |
| `entry_time` | Datetime | | EA-003 |
| `exit_time` | Datetime | Null until exit | EA-004 |
| `fee_charged` | Currency | 0 if included in ticket | EA-005 |
| `fee_waived` | Check | True if ticket included this area | EA-005 |
| `wallet_transaction` | Link → Wallet Transaction | If fee was charged | |

### 4.13 `Gate Log`

| Field | Type | Notes | Source |
|---|---|---|---|
| `customer` | Link → Park Customer | | |
| `ticket` | Link → Park Ticket | | |
| `wristband` | Link → Wristband | | |
| `direction` | Select | `Entry`, `Exit` | GT-001, GT-004 |
| `timestamp` | Datetime | | |
| `gate_id` | Data | Physical gate identifier | |
| `operator` | Link → User | Gate agent who processed | |

---

## 5. Workflows & State Machines

### 5.1 Ticket Lifecycle

```
                    ┌──────────┐
    Purchase ──────▶│  Valid    │
                    └────┬─────┘
                         │
               Gate entry (first scan)
                         │
                    ┌────▼─────┐
                    │   Used   │──── Re-entry allowed? ──── Yes ──▶ Allow re-scan (same day)
                    └────┬─────┘                                     │
                         │                                           │
                    End of valid_date                            No ──▶ Deny re-entry
                         │
                    ┌────▼─────┐
                    │ Expired  │
                    └──────────┘
```

### 5.2 Wristband Lifecycle

```
    ┌───────────┐    Assign to customer     ┌──────────┐
    │ Available │──────────────────────────▶│  Active  │
    └───────────┘                           └────┬─────┘
                                                 │
                              ┌──── Customer reports lost ────┐
                              │                               │
                              ▼                               ▼
                    ┌──────────────┐               ┌───────────┐
                    │ Deactivated  │               │   Lost    │
                    └──────┬───────┘               └───────────┘
                           │
                    Re-assign to new customer
                           │
                    ┌──────▼──────┐
                    │   Active    │  (new customer linked)
                    └─────────────┘
```

### 5.3 Wallet Top-Up Flow

```
    Customer / Staff initiates top-up
                │
                ▼
    ┌───────────────────────┐
    │ Validate amount:      │
    │ amount ≥ min_topup    │──── No ──▶ Reject: "Minimum top-up is X"
    │ balance + amount      │
    │   ≤ max_wallet_balance│──── No ──▶ Reject: "Maximum balance exceeded"
    └───────────┬───────────┘
                │ Yes
                ▼
    ┌───────────────────────┐
    │ Create Wallet         │
    │ Transaction (Credit)  │
    │ Update wallet.balance │
    └───────────┬───────────┘
                │
                ▼
    ┌───────────────────────┐
    │ Return updated balance│
    └───────────────────────┘
```

### 5.4 NFC Tap → Action Resolution

```
    Wristband tap at NFC reader
                │
                ▼
    ┌───────────────────────────┐
    │ NFC Gateway sends:        │
    │ {nfc_uid, counter, hash,  │
    │  reader_id, reader_type}  │
    └───────────┬───────────────┘
                │
                ▼
    ┌───────────────────────────┐
    │ Verify hash:              │
    │ HMAC(customer_id, seed,   │──── Invalid ──▶ Reject: "Invalid wristband"
    │       counter)            │
    └───────────┬───────────────┘
                │ Valid
                ▼
    ┌───────────────────────────┐
    │ Resolve reader_type:      │
    │                           │
    │ "gate_entry"  ──▶ Gate entry flow (GT-001..GT-006)
    │ "gate_exit"   ──▶ Gate exit flow (GT-004)
    │ "area_entry"  ──▶ Area access flow (EA-003..EA-005)
    │ "area_exit"   ──▶ Area exit flow (EA-004)
    │ "pos"         ──▶ POS identification (POS-002)
    └───────────────────────────┘
```

---

## 6. API Surface

### 6.1 Customer-Facing APIs (Flutter App)

| Endpoint | Method | Purpose | Auth |
|---|---|---|---|
| `/api/method/andalus.api.tickets.get_ticket_types` | GET | List active ticket types with current prices | Public |
| `/api/method/andalus.api.tickets.purchase_ticket` | POST | Buy a ticket (debits wallet or payment gateway) | Customer |
| `/api/method/andalus.api.wallet.get_balance` | GET | Current wallet balance | Customer |
| `/api/method/andalus.api.wallet.topup` | POST | Top up wallet via payment gateway | Customer |
| `/api/method/andalus.api.wallet.get_transactions` | GET | Transaction history (paginated) | Customer |
| `/api/method/andalus.api.areas.get_areas` | GET | List all exclusive areas with live capacity | Public |
| `/api/method/andalus.api.wristband.link` | POST | Link wristband to customer account (QR scan) | Customer |
| `/api/method/andalus.api.customer.register` | POST | Register new customer | Public |
| `/api/method/andalus.api.customer.login` | POST | Authenticate, return API key | Public |
| `/api/method/andalus.api.park.get_status` | GET | Park occupancy, operating status | Public |

### 6.2 NFC Gateway APIs (Internal)

| Endpoint | Method | Purpose | Auth |
|---|---|---|---|
| `/api/method/andalus.api.nfc.tap` | POST | Process NFC wristband tap (gate/area/POS) | API Key (Gateway) |
| `/api/method/andalus.api.nfc.batch_sync` | POST | Sync offline tap queue from gateway | API Key (Gateway) |

### 6.3 Staff APIs (POS App / Desk)

| Endpoint | Method | Purpose | Auth |
|---|---|---|---|
| `/api/method/andalus.api.staff.topup_wallet` | POST | Staff-initiated wallet top-up | Gate Agent / POS Operator |
| `/api/method/andalus.api.staff.issue_wristband` | POST | Assign wristband to customer | Gate Agent |
| `/api/method/andalus.api.staff.deactivate_wristband` | POST | Deactivate lost/returned wristband | Gate Agent |
| `/api/method/andalus.api.staff.adjust_occupancy` | POST | Manual area occupancy correction | Area Attendant |
| `/api/method/andalus.api.staff.sell_ticket` | POST | Sell ticket at gate POS | Gate Agent |

---

## 7. Security Requirements

| Requirement | Description |
|---|---|
| **Role-based access** | Each DocType has explicit `has_permission` rules per role (see §2) |
| **NFC hash verification** | Every wristband tap is verified server-side via HMAC before any action. Replayed or invalid hashes are rejected and logged |
| **Wallet atomicity** | All wallet debits use `SELECT ... FOR UPDATE` row locking to prevent double-spend race conditions |
| **API authentication** | Flutter app uses `token <api_key>:<api_secret>`. NFC Gateway uses a dedicated service account API key |
| **Staff audit trail** | Every manual top-up and occupancy adjustment logs the operator's user ID and timestamp |
| **CSRF** | All Frappe web calls use built-in CSRF protection |
| **AML cap** | Wallet balance hard-capped at `max_wallet_balance` to prevent large cash accumulation |
| **Rate limiting** | NFC tap endpoint rate-limited per reader (max 60 taps/minute per reader — prevents rapid replay attacks) |

---

## 8. Integration Points

| System | Direction | Purpose |
|---|---|---|
| **Flutter Customer App** | Inbound (REST) | Ticket purchase, wallet top-up, balance check, area availability |
| **NFC Gateway** | Inbound (REST) | Wristband tap events from gate/area/POS readers |
| **Staff POS App** | Inbound (REST) | Wallet top-up, ticket sales, wristband issuance |
| **Payment Gateway** | Outbound | Process app-based wallet top-ups (Tap, Stripe, PayMob — per region) |
| **Accommodation (Flat Module)** | Internal | Multi-day visitors linked to room reservation via `rental_flats` (Rental Agreement) → daily gate re-entry |
| **ERPNext POS** | Internal | POS Invoices for shop/restaurant purchases |
| **ERPNext Accounting** | Internal | Revenue journals for ticket sales, wallet top-ups |
