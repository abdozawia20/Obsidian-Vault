---
tags: [gatom, pulse, p07, licensing, jwt, rsa, functional]
---

# P07 — Licensing Engine: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P07 — Licensing Engine
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers, operations staff

---

## 1. Purpose & Scope

This domain is the license server that was identified as missing during the Asset Rental architecture review. Now that Pulse exists, it serves as the centralized license management system. Licenses are RSA-signed JWT tokens issued from Pulse and validated both online (agent calls Pulse) and offline (agent verifies JWT signature locally).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| P07-001 | Licenses must be cryptographically signed JWT tokens (RSA-2048, RS256 algorithm) |
| P07-002 | Each license must be bound to a specific client, server, and set of modules |
| P07-003 | License issuance must be a one-click operation in the Pulse dashboard |
| P07-004 | License validation must work online (agent → Pulse API) AND offline (local JWT verification) |
| P07-005 | Offline tolerance: agent must continue validating locally for 7 days if Pulse is unreachable |
| P07-006 | License revocation must be effective within 24 hours (next agent license check) |
| P07-007 | License approaching expiry (30/14/7 days) must trigger alerts (P05) |
| P07-008 | Full audit trail: issuance, validation attempts, renewals, revocations must be logged |
| P07-009 | Module gating: license specifies which apps are permitted (`rental_core`, `rental_flats`, `rental_vehicles`) |
| P07-010 | Asset limits: license specifies maximum `Rental Asset` records per tier |

---

## 3. RSA Key Management *(updated — resolves SEC-02)*

### 3.1 Key Pair

| Key | Storage | Purpose |
|---|---|---|
| Private key (`gatom_license_private_v{N}.pem`) | Pulse server environment variable (`PULSE_LICENSE_PRIVATE_KEY`) | Sign JWTs during issuance |
| Public keys (`gatom_license_public_v{N}.pem`) | Embedded in `gatom_agent` under `keys/` directory | Offline JWT verification on client servers |

> [!IMPORTANT]
> The private key is stored as an environment variable on Gatom's server, NOT in the database. It is loaded at runtime by the license issuance code. If the private key is compromised, ALL licenses can be forged.

### 3.2 Key Versioning & Rotation

The RSA key pair may need rotation due to:
- Private key compromise
- Algorithm upgrade (e.g., RS256 → RS384)
- Periodic rotation policy (recommended: every 2 years)

**Key ID (KID) Claim**: Every JWT includes a `kid` (Key ID) header that tells the agent which public key to use for verification:

```json
{
  "alg": "RS256",
  "kid": "v1",
  "typ": "JWT"
}
```

**Agent Key Resolution**:

```python
def get_public_key(kid: str) -> str:
    """Load the correct public key based on the JWT kid header."""
    key_path = os.path.join(
        os.path.dirname(__file__), "..", "keys",
        f"gatom_license_public_{kid}.pem"
    )
    if not os.path.exists(key_path):
        raise ValueError(f"Unknown key ID: {kid}")
    return open(key_path).read()

def offline_validate(license_key: str):
    """Verify JWT using the correct versioned public key."""
    # Read kid from JWT header WITHOUT verifying signature first
    unverified_header = jwt.get_unverified_header(license_key)
    kid = unverified_header.get("kid", "v1")  # default to v1 for legacy tokens
    
    public_key = get_public_key(kid)
    claims = jwt.decode(license_key, public_key, algorithms=["RS256"],
                       options={"verify_exp": True})
    # ... continue with site_url check, etc.
```

### 3.3 Key Rotation Process

| Step | Action | Timeline |
|---|---|---|
| 1 | Generate new RSA-2048 key pair (`v2`) | Day 0 |
| 2 | Deploy new public key (`v2.pem`) to all agents via `bench update` | Day 0 – Day 14 |
| 3 | Start issuing new licenses with `kid: v2` | Day 14 (after all agents have the new key) |
| 4 | Existing licenses (signed with `v1`) remain valid until their `exp` date | Ongoing |
| 5 | Once ALL `v1` licenses have expired or been re-issued with `v2`, remove `v1` private key | Day 365+ |
| 6 | Keep `v1` public key in agents for at least 90 days after last `v1` license expires | Final cleanup |

> [!WARNING]
> **Dual-key overlap**: Agents must ALWAYS support at least 2 public keys simultaneously. The `kid` claim determines which key is used. Never remove a public key from agents while any active license references it.

**Pulse Configuration Fields**:

| Field | Type | Notes |
|---|---|---|
| `active_signing_kid` | Data | Currently used KID for new license issuance (e.g., `v1`) |
| `supported_kids` | Small Text | JSON array of all valid KIDs (e.g., `["v1", "v2"]`) |

---

## 4. JWT Token Specification

### 4.1 JWT Header

```json
{
  "alg": "RS256",
  "kid": "v1",
  "typ": "JWT"
}
```

| Header | Type | Required | Purpose |
|---|---|---|---|
| `alg` | string | ✅ | Algorithm — always `RS256` |
| `kid` | string | ✅ | Key ID — tells the agent which public key to use (see §3.2) |
| `typ` | string | ✅ | Token type — always `JWT` |

### 4.2 Payload Claims

```json
{
  "iss": "gatom-pulse",
  "iat": 1718150400,
  "exp": 1749772800,
  "client_id": "al-andalus-park",
  "client_name": "Al-Andalus Park Real Estate",
  "server_id": "PULSE-SRV-00001",
  "site_url": "rental.alandalus.com",
  "modules": ["rental_core", "rental_vehicles"],
  "max_assets": 500,
  "edition": "professional"
}
```

| Claim | Type | Required | Purpose |
|---|---|---|---|
| `iss` | string | ✅ | Issuer — always `"gatom-pulse"` |
| `iat` | int (Unix) | ✅ | Issued-at timestamp |
| `exp` | int (Unix) | ✅ | Expiry timestamp — the core enforcement mechanism |
| `client_id` | string | ✅ | Links to `Pulse Client.client_id` |
| `client_name` | string | ✅ | Display name for license info page |
| `server_id` | string | ✅ | Links to `Pulse Server.name` |
| `site_url` | string | ✅ | Bound to specific Frappe site (prevents key sharing) |
| `modules` | string[] | ✅ | Licensed Frappe apps |
| `max_assets` | int | ✅ | Maximum active `Rental Asset` records |
| `edition` | string | ✅ | `starter` / `professional` / `enterprise` |

### 4.2 Edition Tiers

| Tier | Modules Allowed | Max Assets | Features |
|---|---|---|---|
| Starter | `rental_core` + 1 variant | 50 | Base features only |
| Professional | `rental_core` + any variants | 500 | All features, standard support |
| Enterprise | `rental_core` + all variants | Unlimited | All features, priority support, custom development |

---

## 5. DocTypes

### 5.1 Pulse License

| Field | Type | Notes |
|---|---|---|
| `client` | Link → Pulse Client | ✅ Required |
| `server` | Link → Pulse Server | ✅ Required |
| `edition` | Select | `Starter` / `Professional` / `Enterprise` |
| `modules` | Small Text | JSON array of licensed apps |
| `max_assets` | Int | Maximum active rental assets |
| `issued_at` | Datetime | When JWT was generated |
| `expires_at` | Datetime | Expiry date from JWT `exp` claim |
| `status` | Select | `Active` / `Expired` / `Revoked` / `Grace` |
| `jwt_token` | Long Text | The full JWT string (for copy-to-clipboard) |
| `revoked_at` | Datetime | When revoked (if applicable) |
| `revocation_reason` | Small Text | Why it was revoked |
| `last_validated_at` | Datetime | Last successful online validation by agent |
| `validation_count` | Int | Total online validation checks received |
| `renewed_from` | Link → Pulse License | Previous license (if this is a renewal) |

### 5.2 Pulse License Log (Child Table)

Audit trail for every license event:

| Field | Type |
|---|---|
| `event` | Select: `Issued`, `Validated`, `Expired`, `Revoked`, `Renewed`, `Validation Failed` |
| `timestamp` | Datetime |
| `details` | Small Text |
| `actor` | Link → User (for manual actions) or "Agent" (for automated) |

---

## 6. API Endpoints

### 6.1 License Validation (`allow_guest=True`)

```
POST /api/method/gatom_pulse.api.agent.license_validate
Authorization: Bearer {api_key}
Body: {
    "license_key": "eyJhbGciOiJSUzI1NiIs...",
    "server_id": "PULSE-SRV-00001",
    "asset_count": 127,
    "installed_apps": ["rental_core", "rental_vehicles"]
}
```

**Response**:
```json
{
    "status": "VALID",
    "expires_at": "2027-06-12T00:00:00Z",
    "days_remaining": 365,
    "modules": ["rental_core", "rental_vehicles"],
    "max_assets": 500,
    "edition": "professional"
}
```

**Possible statuses**: `VALID`, `EXPIRING` (< 30 days), `GRACE`, `EXPIRED`, `REVOKED`, `MODULE_MISMATCH`, `ASSET_LIMIT`, `SITE_MISMATCH`, `INVALID`

**Logic**:
1. Authenticate API key
2. Decode JWT with public key (verify signature)
3. Check `server_id` matches the authenticated server
4. Check `status` in Pulse License record (catch revocations)
5. Check expiry → calculate grace period if expired
6. Check `installed_apps` against `modules` claim
7. Check `asset_count` against `max_assets` claim
8. Log validation attempt in License Log
9. Update `last_validated_at`

### 6.2 Issue License (Internal, Desk)

Triggered by Gatom admin from the Pulse License form:
1. Read private key from environment
2. Build JWT payload from form fields
3. Sign with RS256
4. Store JWT in `jwt_token` field
5. Display in copy-to-clipboard modal

### 6.3 Revoke License (Internal, Desk)

1. Set `status = Revoked`, `revoked_at = now()`
2. Record reason in `revocation_reason`
3. Log event in License Log
4. Next agent validation check → receives `REVOKED` response → agent suspends Frappe site

### 6.4 Payment-Driven License Changes *(P08 Integration)*

The billing domain (P08) can change license status based on payment status:

| Payment Event | License Action | New Status |
|---|---|---|
| Invoice overdue 8+ days | `suspend_license_for_payment()` | `Grace` |
| Invoice overdue 30+ days | `expire_license_for_payment()` | `Expired` |
| Overdue payment received | `reinstate_license_on_payment()` | `Active` |

> ⚠️ **Full integration spec**: [[../API Contract#7.2 P07 ↔ P08 Payment-Driven License Suspension|API Contract §7.2]]

**Acceptance Criteria**:
- [ ] P08 overdue pipeline calls P07 functions to change license status
- [ ] Reinstatement only works if JWT `exp` hasn't passed (can't reinstate a truly expired JWT)
- [ ] All payment-driven transitions logged in Pulse Audit Log

---

## 7. Agent-Side License Validation (`gatom_agent`)

```python
def validate_license():
    """Daily at 4 AM — check license with Pulse, fallback to local."""
    lic_key = frappe.get_single("Rental Configuration").license_key
    
    # Try online validation first
    try:
        response = pulse_client.post("/license/validate", {
            "license_key": lic_key,
            "server_id": get_server_id(),
            "asset_count": frappe.db.count("Rental Asset", {"is_active": 1}),
            "installed_apps": frappe.get_installed_apps()
        })
        handle_license_response(response)
        cache.set("last_license_check", now())
        return
    except ConnectionError:
        pass  # Pulse unreachable — try offline
    
    # Offline fallback: local JWT verification
    last_online = cache.get("last_license_check")
    if last_online and (now() - last_online).days > 7:
        # Offline too long — hard block
        suspend_site()
        return
    
    # Verify JWT signature locally with embedded public key
    claims = jwt.decode(lic_key, PUBLIC_KEY, algorithms=["RS256"])
    if claims["exp"] < now().timestamp():
        handle_expiry(claims)
```

---

## 8. Dashboard Views (React)

### 8.1 License Overview

- Table of all licenses: client, server, edition, expires_at, status, days remaining
- Status badges: green (Active), yellow (Expiring < 30d), orange (Grace), red (Expired/Revoked)
- Sortable by days remaining (most urgent first)
- Quick actions: Renew, Revoke, View JWT

### 8.2 License Detail

- Full license info card
- Copy JWT button
- Audit log timeline
- Linked server health status
- Renewal history chain

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A05 — License Validation (Agent side)]]
