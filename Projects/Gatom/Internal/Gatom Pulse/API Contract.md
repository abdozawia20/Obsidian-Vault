---
tags: [gatom, pulse, api, contract, endpoints, payloads]
aliases: [API Contract, Endpoint Reference]
---

# Gatom Pulse — API Contract

> **Purpose**: Single source of truth for every HTTP endpoint between `gatom_agent` (client) and `gatom_pulse` (server). Every payload is defined once — no duplication across domain docs.
> **Status**: Architecture Design
> **Audience**: Gatom developers

---

## 1. Conventions

### 1.1 Base URL

All endpoints are Frappe whitelisted methods under:
```
{pulse_url}/api/method/gatom_pulse.api.agent.{endpoint}
```

### 1.2 Authentication

Every agent request must include:

| Header | Required | Format | Purpose |
|---|---|---|---|
| `Authorization` | ✅ | `Bearer {uuid4}` | API key authentication |
| `X-Agent-Version` | ✅ | `1.0.0` | Agent semver |
| `X-Request-Timestamp` | ✅ | Unix epoch (int) | Replay prevention (±300s tolerance) |
| `X-Request-ID` | ✅ | UUID v4 | Request deduplication (10-min TTL) |
| `Content-Type` | ✅ | `application/json` | Always JSON |

### 1.3 Standard Error Response

All error responses follow this structure:
```json
{
    "status": "error",
    "error_code": "RATE_LIMITED",
    "message": "Human-readable explanation",
    "retry_after": 30
}
```

| Error Code | HTTP | Meaning | Agent Action |
|---|---|---|---|
| `INVALID_PAYLOAD` | 400 | Malformed request body | Log ERROR, do NOT retry |
| `INVALID_TIMESTAMP` | 400 | Clock drift > 300s | Log ERROR, check clock |
| `INVALID_API_KEY` | 401 | API key not recognized | Log CRITICAL, disable agent |
| `SERVER_DECOMMISSIONED` | 403 | Server marked decommissioned | Log CRITICAL, disable agent |
| `DUPLICATE_REQUEST` | 409 | Same `X-Request-ID` seen | Log DEBUG, ignore |
| `UPGRADE_REQUIRED` | 426 | Agent version below minimum | Log CRITICAL, continue operating |
| `RATE_LIMITED` | 429 | Exceeds rate limit | Log WARNING, wait `retry_after` seconds |
| `INTERNAL_ERROR` | 500 | Pulse server error | Log WARNING, queue for retry |

### 1.4 Naming Conventions

All payload field names use **`snake_case`**. Metric names use the **canonical names** defined in this document — domain docs must reference this contract, not define their own names.

### 1.5 Payload Validation *(resolves ERR-03)*

All agent endpoints must validate incoming payloads before processing. Validation is split into two categories:

**Hard Required** — missing any of these → `400 INVALID_PAYLOAD` (entire request rejected):

| Endpoint | Hard Required Fields |
|---|---|
| `register` | `site_url`, `frappe_version`, `agent_version`, `installed_apps` |
| `heartbeat` | `server_id`, `timestamp`, `metrics.cpu_pct`, `metrics.ram_pct`, `metrics.disk_pct`, `metrics.mariadb_up`, `metrics.redis_up` |
| `logs` | `server_id`, `entries` (must be non-empty array), `entries[].timestamp`, `entries[].level`, `entries[].message` |
| `usage` | `server_id`, `collected_at`, `metrics.active_assets` |
| `backup_status` | `server_id`, `has_backup`, `backup_count`, `status` |
| `license_validate` | `server_id`, `license_jwt`, `asset_count` |

**Soft Optional** — missing these → field stored as `null`, request accepted:

| Endpoint | Soft Optional Fields |
|---|---|
| `register` | `python_version`, `os_version`, `timezone` |
| `heartbeat` | `metrics.load_avg_1m` (Linux-only), `metrics.active_workers`, `queue_status.*`, `agent_health.*` |
| `logs` | `entries[].traceback`, `entries[].fingerprint`, `entries[].source` |
| `backup_status` | `last_backup_at`, `backup_size_mb`, `backup_type`, `backup_path`, `reason` |
| `license_validate` | `installed_apps` |

**Type Validation**: Numeric fields (`cpu_pct`, `ram_pct`, etc.) must be `int` or `float`. Non-numeric values → `400 INVALID_PAYLOAD`. Boolean fields must be `true`/`false`.

```python
def validate_heartbeat_payload(data: dict) -> None:
    """Validates heartbeat payload. Raises frappe.ValidationError on failure."""
    required = ["server_id", "timestamp"]
    required_metrics = ["cpu_pct", "ram_pct", "disk_pct", "mariadb_up", "redis_up"]
    
    for field in required:
        if not data.get(field):
            frappe.throw(f"Missing required field: {field}", exc=frappe.ValidationError)
    
    metrics = data.get("metrics", {})
    for field in required_metrics:
        if field not in metrics:
            frappe.throw(f"Missing required metric: {field}", exc=frappe.ValidationError)
    
    # Type-check numeric metrics
    for field in ["cpu_pct", "ram_pct", "disk_pct", "ram_used_mb", "disk_used_gb"]:
        val = metrics.get(field)
        if val is not None and not isinstance(val, (int, float)):
            frappe.throw(f"Metric {field} must be numeric, got {type(val).__name__}",
                        exc=frappe.ValidationError)
```

---

## 2. Agent → Pulse Endpoints

### 2.1 Register Server

> **Domain**: [[Agent/A01 - Registration/functional|A01]] → [[P01 - Client & Server Registry/functional|P01]]
> **Frequency**: On install + every `bench restart`
> **Rate Limit**: 3 requests / hour (hardcoded)

```
POST /api/method/gatom_pulse.api.agent.register
```

**Request Payload**:
```json
{
    "site_url": "https://rental.alandalus.com",
    "frappe_version": "15.42.0",
    "python_version": "3.12.4",
    "os_version": "Ubuntu 22.04.4 LTS",
    "installed_apps": ["frappe", "erpnext", "rental_core", "rental_flats", "gatom_agent"],
    "agent_version": "1.0.0",
    "timezone": "Asia/Riyadh"
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `site_url` | string | ✅ | Full site URL (used for site binding) |
| `frappe_version` | string | ✅ | Frappe framework version |
| `python_version` | string | ✅ | Python runtime version |
| `os_version` | string | ✅ | Operating system version string |
| `installed_apps` | string[] | ✅ | All Frappe apps on this bench |
| `agent_version` | string | ✅ | `gatom_agent` version |
| `timezone` | string | ✅ | IANA timezone (from Frappe `time_zone`) |

**Success Response** (`200`):
```json
{
    "status": "registered",
    "server_id": "PULSE-SRV-00001",
    "server_name": "Al-Andalus Production"
}
```

**Pulse Logic**:
1. Hash Bearer token → match against `Pulse Server.api_key_hash` (or `api_key_hash_previous` during rotation)
2. No match → `401 INVALID_API_KEY`
3. Match found → update: `frappe_version`, `python_version`, `os_version`, `installed_apps`, `agent_version`, `timezone`, `status = Online`
4. Set `registered_at = now()` only on first registration
5. Write to [[#Pulse Audit Log]]: `SERVER_REGISTERED`

---

### 2.2 Heartbeat

> **Domain**: [[Agent/A02 - Heartbeat Collection/functional|A02]] → [[P02 - Server Health Monitoring/functional|P02]]
> **Frequency**: Every 60 seconds
> **Rate Limit**: 2 requests / minute (configurable: `heartbeat_rate_limit`)

```
POST /api/method/gatom_pulse.api.agent.heartbeat
```

**Request Payload**:
```json
{
    "server_id": "PULSE-SRV-00001",
    "timestamp": "2026-06-12T09:30:00Z",
    "agent_version": "1.0.0",
    "metrics": {
        "cpu_pct": 42.5,
        "ram_pct": 67.3,
        "ram_used_mb": 2756,
        "ram_total_mb": 4096,
        "disk_pct": 55.1,
        "disk_used_gb": 44.1,
        "disk_total_gb": 80.0,
        "disk_free_gb": 35.9,
        "load_avg_1m": 1.2,
        "mariadb_up": true,
        "redis_up": true,
        "rq_queue_depth": 3,
        "rq_failed_jobs": 0,
        "response_time_ms": 180,
        "http_status": 200,
        "active_workers": 4
    },
    "queue_status": {
        "pending_heartbeats": 0,
        "pending_logs": 0,
        "pending_other": 0,
        "oldest_queued_at": null
    },
    "agent_health": {
        "last_log_push": "2026-06-12T09:25:00Z",
        "last_license_check": "2026-06-12T04:00:00Z",
        "license_status": "VALID",
        "agent_disabled": false
    }
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| **Top-level** | | | |
| `server_id` | string | ✅ | Pulse Server name |
| `timestamp` | ISO 8601 | ✅ | Collection time (UTC) |
| `agent_version` | string | ✅ | Current agent version |
| **metrics** | | | |
| `cpu_pct` | float | ✅ | `psutil.cpu_percent(interval=1)` |
| `ram_pct` | float | ✅ | `psutil.virtual_memory().percent` |
| `ram_used_mb` | int | ✅ | Used RAM in MB |
| `ram_total_mb` | int | ✅ | Total RAM in MB |
| `disk_pct` | float | ✅ | `psutil.disk_usage('/').percent` |
| `disk_used_gb` | float | ✅ | Used disk in GB |
| `disk_total_gb` | float | ✅ | Total disk in GB |
| `disk_free_gb` | float | ✅ | Free disk in GB |
| `load_avg_1m` | float | | `os.getloadavg()[0]` — Linux only |
| `mariadb_up` | bool | ✅ | `frappe.db.sql("SELECT 1")` succeeds |
| `redis_up` | bool | ✅ | `frappe.cache().ping()` succeeds |
| `rq_queue_depth` | int | ✅ | Pending background jobs |
| `rq_failed_jobs` | int | ✅ | Failed jobs in RQ |
| `response_time_ms` | int | ✅ | Self-ping response time |
| `http_status` | int | ✅ | Self-ping HTTP status code |
| `active_workers` | int | ✅ | Running Gunicorn workers |
| **queue_status** | | | |
| `pending_heartbeats` | int | ✅ | Queued heartbeats in Redis |
| `pending_logs` | int | ✅ | Queued log batches |
| `pending_other` | int | ✅ | Other queued payloads |
| `oldest_queued_at` | ISO 8601? | | Timestamp of oldest queued entry |
| **agent_health** | | | |
| `last_log_push` | ISO 8601? | | When logs were last pushed |
| `last_license_check` | ISO 8601? | | When license was last checked |
| `license_status` | string? | | Current Redis license status |
| `agent_disabled` | bool | | Whether agent is self-disabled |
| `uninstalling` | bool | | Set `true` on final heartbeat before `bench uninstall-app` *(ALF-02)* |

**Success Response** (`200`):
```json
{
    "status": "ok",
    "server_time": "2026-06-12T09:30:01Z",
    "commands": {
        "rotate_key": null,
        "decommission": false
    },
    "releases": [
        {
            "release_id": "REL-00005",
            "version": "1.3.0",
            "severity": "Minor",
            "changelog": "## What's New\n- GPS tracking improvements",
            "affected_apps": ["rental_core", "rental_vehicles"]
        }
    ]
}
```

**`commands` object** *(piggybacked instructions — resolves EP-03, EP-04)*:

| Field | Type | When Set | Agent Action |
|---|---|---|---|
| `rotate_key` | string? | When admin generates a new key while old is in grace | Agent writes new key to `site_config.json`, calls `bench restart` to apply. See [[#7.7 Automated Re-Keying]] |
| `decommission` | bool | When server status is `Decommissioned` in Pulse | Agent logs CRITICAL, disables itself, stops all collectors. See [[#7.6 Server Decommission]] |

> [!NOTE]
> If `commands.decommission = true`, the agent must stop sending all requests immediately. This is the **graceful** path. The `403 SERVER_DECOMMISSIONED` error response is the **hard** path (for agents that somehow miss the command).

**Pulse Logic**:
1. Authenticate API key
2. Validate payload (see [[#1.5 Payload Validation|§1.5]])
3. Store full metrics in Redis: `pulse:heartbeat:{server_name}` (TTL: 5 min)
4. Store `queue_status` and `agent_health` in Redis: `pulse:agent_health:{server_name}` (TTL: 5 min)
5. **If `agent_health.uninstalling = true`** → set server status to `Decommissioned`, write Audit Log `SERVER_DECOMMISSIONED`, do NOT create incident ticket *(ALF-02)*
6. Update `Pulse Server.last_seen_at`
7. Evaluate thresholds (see [[#Threshold Sustained Tracking]])
8. If server was `Degraded`/`Down` → transition to `Online`, auto-resolve incident
9. Check pending releases for this server → include in response
10. Check if server has `status = Decommissioned` → set `commands.decommission = true`
11. Check if server has `api_key_hash_previous` set (rotation in progress) → set `commands.rotate_key = {nonce, ciphertext}` *(SEC-01: encrypted)*
12. Return `server_time` (so agent can detect clock drift)

---

### 2.3 Push Logs

> **Domain**: [[Agent/A03 - Log Collection/functional|A03]] + [[Agent/A04 - Error Fingerprinting/functional|A04]] → [[P03 - Log Aggregation/functional|P03]] + [[P04 - Error Tracking/functional|P04]]
> **Frequency**: Every 5 minutes
> **Rate Limit**: 1 request / 5 minutes (configurable: `logs_rate_limit`)

```
POST /api/method/gatom_pulse.api.agent.logs
```

**Request Payload**:
```json
{
    "server_id": "PULSE-SRV-00001",
    "entries": [
        {
            "timestamp": "2026-06-12T09:25:13Z",
            "level": "ERROR",
            "source": "rental_core.billing",
            "message": "Invoice creation failed for agreement AGR-00123",
            "traceback": "Traceback (most recent call last):\n  File ...",
            "fingerprint": "a3f8b2c1d4e5f6..."
        },
        {
            "timestamp": "2026-06-12T09:26:00Z",
            "level": "INFO",
            "source": "rental_core.billing",
            "message": "Invoice SI-00042 created",
            "traceback": null,
            "fingerprint": null
        }
    ],
    "log_sources": ["frappe.log", "worker.log"],
    "total_entries_in_window": 127,
    "truncated": false
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `server_id` | string | ✅ | |
| `entries` | array | ✅ | Max 500 entries per push |
| `entries[].timestamp` | ISO 8601 | ✅ | Original log timestamp |
| `entries[].level` | enum | ✅ | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `entries[].source` | string | ✅ | Module path |
| `entries[].message` | string | ✅ | Max 2,000 chars (sanitized) |
| `entries[].traceback` | string? | | Max 10,000 chars (sanitized) |
| `entries[].fingerprint` | string? | | SHA-256 hex (64 chars) — only for ERROR/CRITICAL with traceback |
| `log_sources` | string[] | ✅ | Which log files were read |
| `total_entries_in_window` | int | ✅ | Total entries before truncation |
| `truncated` | bool | ✅ | Whether entries were capped at 500 |

**Success Response** (`200`):
```json
{
    "status": "ok",
    "entries_received": 127,
    "new_issues_created": 1,
    "regressions_detected": 0
}
```

**Pulse Logic**:
1. Authenticate API key
2. Deduplicate via `X-Request-ID`
3. Bulk insert → `Pulse Log Entry` DocType
4. For entries with `fingerprint` ≠ null: run [[P04 - Error Tracking/functional|P04 Error Pipeline]] **inline** — no separate endpoint
5. Emit Socketio event `pulse:new_logs:{server_name}` for real-time dashboard
6. Return summary counts

> [!NOTE]
> The `X-Request-ID` header provides request-level deduplication. No additional `batch_id` field is needed — this resolves audit finding **PM-03**.

> [!IMPORTANT]
> **Design Decision (EP-01)**: Error processing is intentionally inline inside the logs endpoint — not a separate `/agent.errors` endpoint. Rationale:
> - The agent already pushes ERROR/CRITICAL entries with `fingerprint` as part of the regular log batch
> - A separate endpoint would double network traffic for no benefit (errors are a subset of logs)
> - P04's error pipeline is a Pulse-internal module called by P03's handler — no coupling to the agent
> - If P04 processing is slow, it can be deferred to a background job (`frappe.enqueue`) without changing the API surface

---

### 2.4 Push Usage Stats

> **Domain**: [[Agent/A06 - Usage Collection/functional|A06]] → [[P09 - Usage Analytics/functional|P09]]
> **Frequency**: Daily at 2 AM (agent pushes daily; Pulse upserts the current week's snapshot)
> **Rate Limit**: 2 requests / day (configurable: `usage_rate_limit`)

```
POST /api/method/gatom_pulse.api.agent.usage
```

**Request Payload**:
```json
{
    "server_id": "PULSE-SRV-00001",
    "collected_at": "2026-06-15T02:00:00Z",
    "metrics": {
        "active_assets": 127,
        "total_assets": 145,
        "active_agreements": 89,
        "total_agreements": 234,
        "total_users": 156,
        "active_users_7d": 42,
        "portal_visits_7d": 1830,
        "api_calls_7d": 4521,
        "storage_used_mb": 2340,
        "kyc_submissions_7d": 12,
        "invoices_generated_7d": 67,
        "payments_received_7d": 52,
        "installed_modules": ["rental_core", "rental_vehicles"],
        "frappe_version": "15.42.0",
        "agent_version": "1.0.0"
    }
}
```

**Success Response** (`200`):
```json
{
    "status": "ok",
    "snapshot_id": "SNAP-00042",
    "snapshot_mode": "updated",
    "engagement_score": "Growing",
    "tier_compliance": {
        "asset_usage_pct": 25.4,
        "status": "OK"
    }
}
```

**Pulse Logic**:
1. Authenticate API key
2. Find existing `Usage Snapshot` for this server where `week_start` = Monday of `collected_at`'s week
3. If exists → **upsert** (update with latest daily values)
4. If not exists → **create** new weekly snapshot
5. Compute engagement score (compare last 4 snapshots)
6. Check tier compliance against linked `Pulse License.max_assets`
7. Return engagement score + compliance result

> [!IMPORTANT]
> Agent pushes **daily**. Pulse groups into **weekly** snapshots by upsert. This resolves audit finding **PM-02 / SCH-01**.

---

### 2.5 Push Backup Status

> **Domain**: [[Agent/A07 - Backup Checking/functional|A07]] → [[P10 - Releases & Backups/functional|P10]]
> **Frequency**: Daily at 3 AM
> **Rate Limit**: 2 requests / day (configurable: `backup_rate_limit`)

```
POST /api/method/gatom_pulse.api.agent.backup_status
```

**Request Payload**:
```json
{
    "server_id": "PULSE-SRV-00001",
    "has_backup": true,
    "last_backup_at": "2026-06-12T01:00:00Z",
    "backup_size_mb": 245.7,
    "backup_type": "Full",
    "backup_path": "private/backups/20260612_010000-site_database.sql.gz",
    "backup_count": 7,
    "status": "Healthy",
    "reason": null
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `server_id` | string | ✅ | |
| `has_backup` | bool | ✅ | Whether any backup file was found |
| `last_backup_at` | ISO 8601? | | Most recent backup timestamp |
| `backup_size_mb` | float? | | Size of most recent backup |
| `backup_type` | enum? | | `Full` / `Partial` |
| `backup_path` | string? | | Relative path from site root (e.g., `private/backups/20260612_010000-site_database.sql.gz`). Agent must send the full relative path, **not** just the filename. *(Resolves PM-06)* |
| `backup_count` | int | ✅ | Total `.sql.gz` files in backup dir |
| `status` | enum | ✅ | `Healthy` / `Warning` / `Critical` |
| `reason` | string? | | Human-readable reason if not Healthy |

**Success Response** (`200`):
```json
{
    "status": "ok"
}
```

---

### 2.6 Validate License

> **Domain**: [[Agent/A05 - License Validation/functional|A05]] → [[P07 - Licensing/functional|P07]]
> **Frequency**: Daily at 4 AM
> **Rate Limit**: 5 requests / day (configurable: `license_rate_limit`)

```
POST /api/method/gatom_pulse.api.agent.license_validate
```

**Request Payload**:
```json
{
    "server_id": "PULSE-SRV-00001",
    "license_jwt": "eyJhbGciOiJSUzI1NiIs...",
    "asset_count": 127,
    "installed_apps": ["rental_core", "rental_vehicles"]
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `server_id` | string | ✅ | |
| `license_jwt` | string | ✅ | Full JWT token from Rental Configuration |
| `asset_count` | int | ✅ | Current count of non-retired Rental Assets |
| `installed_apps` | string[] | ✅ | Currently installed Frappe apps |

> [!NOTE]
> Field is `license_jwt` (not `license_key`) to clearly indicate it's a JWT token. This resolves audit finding **PM-05**.

**Success Response** (`200`):
```json
{
    "status": "VALID",
    "expires_at": "2027-06-12T00:00:00Z",
    "days_remaining": 365,
    "licensed_modules": ["rental_core", "rental_vehicles"],
    "max_assets": 500,
    "edition": "professional",
    "warnings": []
}
```

**Possible `status` values**:

| Status | Meaning | Agent → Redis `pulse:license_status` |
|---|---|---|
| `VALID` | License valid | `VALID` |
| `EXPIRING` | < 30 days remaining | `EXPIRING` |
| `GRACE` | Expired but within grace period | `GRACE` |
| `EXPIRED` | Expired, past grace | `EXPIRED` |
| `REVOKED` | Explicitly revoked | `REVOKED` |
| `ASSET_LIMIT` | Exceeds `max_assets` | `ASSET_LIMIT` |
| `MODULE_MISMATCH` | Unlicensed module installed | `ASSET_LIMIT` |
| `SITE_MISMATCH` | JWT `site_url` ≠ calling site | `SITE_MISMATCH` |
| `INVALID` | JWT signature verification failed | `INVALID` |

---

### 2.7 Acknowledge Release *(NEW — resolves EP-02)*

> **Domain**: [[Agent/A02 - Heartbeat Collection/functional|A02]] → [[P10 - Releases & Backups/functional|P10]]
> **Frequency**: On-demand (after heartbeat returns a release)
> **Rate Limit**: 10 requests / day (hardcoded)

```
POST /api/method/gatom_pulse.api.agent.release_ack
```

**Request Payload**:
```json
{
    "server_id": "PULSE-SRV-00001",
    "release_id": "REL-00005",
    "acknowledged": true,
    "current_version": "1.2.0"
}
```

**Success Response** (`200`):
```json
{
    "status": "ok"
}
```

**Pulse Logic**:
1. Find `Server Release Status` child row for this server + release
2. Set `notified = 1`
3. Set `current_version` (so Pulse knows what version the server is on)

---

## 3. Pulse Internal Endpoints (Dashboard API)

> These endpoints serve the React dashboard. They require Frappe session auth (not API key).

### 3.0 Security: CSRF & SameSite Policy *(resolves SEC-03)*

All dashboard endpoints use GET requests with Frappe session cookies. To prevent cross-origin data leakage:

1. **SameSite Cookie Policy**: Pulse must set `SameSite=Strict` on all session cookies. Add to `site_config.json`:
   ```json
   {
       "session_cookie_samesite": "Strict"
   }
   ```

2. **Same-Origin Enforcement**: The React dashboard MUST be served from the same origin as the Frappe backend (e.g., `https://erp.gatom.com`). It must NOT be served from a CDN or different subdomain.

3. **CORS Policy**: Do not add `Access-Control-Allow-Origin` headers to dashboard endpoints. Frappe's default CORS policy (same-origin only) is sufficient.

4. **Sensitive Data Endpoints**: The following endpoints return business-critical data and must additionally validate `Referer` header matches the Pulse domain:
   - `revenue_summary` (financial data)
   - `fleet_overview` (server infrastructure)
   - `audit_log` (security events)

```python
def validate_dashboard_access():
    """Called at the start of every dashboard API endpoint."""
    if not frappe.session.user or frappe.session.user == "Guest":
        frappe.throw("Authentication required", exc=frappe.AuthenticationError)
    
    # Verify Referer header for sensitive endpoints
    referer = frappe.request.headers.get("Referer", "")
    site_url = frappe.utils.get_url()
    if not referer.startswith(site_url):
        frappe.throw("Cross-origin request denied", exc=frappe.PermissionError)
```

**Acceptance Criteria**:
- [ ] `SameSite=Strict` configured in `site_config.json`
- [ ] Dashboard served from same origin as Frappe backend
- [ ] No CORS headers on dashboard endpoints
- [ ] Sensitive endpoints validate `Referer` header
- [ ] Unauthenticated requests → `401`

### 3.1 Fleet Overview

```
GET /api/method/gatom_pulse.api.dashboard.fleet_overview
```

**Response**:
```json
{
    "total_servers": 14,
    "servers_online": 12,
    "servers_degraded": 1,
    "servers_down": 1,
    "servers_pending": 0,
    "total_clients": 6,
    "fleet_uptime_30d_pct": 99.2,
    "servers": [
        {
            "name": "PULSE-SRV-00001",
            "server_name": "Al-Andalus Production",
            "client_name": "Al-Andalus Park",
            "environment": "Production",
            "status": "Online",
            "last_seen_ago": "45 seconds ago",
            "frappe_version": "15.42.0",
            "agent_version": "1.0.0",
            "installed_apps": ["rental_core", "rental_vehicles"],
            "cpu_pct": 42.5,
            "ram_pct": 67.3,
            "disk_pct": 55.1
        }
    ]
}
```

---

### 3.2 Revenue Summary

```
GET /api/method/gatom_pulse.api.dashboard.revenue_summary
```

**Response**:
```json
{
    "mrr": 2450.00,
    "arr": 29400.00,
    "total_clients_paying": 6,
    "overdue_invoices": 1,
    "overdue_amount": 350.00,
    "mrr_trend_12m": [1800, 2100, 2100, 2450, ...],
    "revenue_by_tier": {
        "Starter": 450,
        "Professional": 1400,
        "Enterprise": 600
    }
}
```

---

### 3.3 Usage Summary

```
GET /api/method/gatom_pulse.api.dashboard.usage_summary
```

**Response**:
```json
{
    "total_assets_managed": 847,
    "total_agreements_active": 523,
    "total_users": 891,
    "engagement_breakdown": {
        "Growing": 3,
        "Stable": 2,
        "Declining": 1
    },
    "tier_compliance": {
        "ok": 5,
        "warning": 1,
        "exceeded": 0
    }
}
```

---

### 3.4 Backup Summary

```
GET /api/method/gatom_pulse.api.dashboard.backup_summary
```

**Response**:
```json
{
    "total_servers_checked": 14,
    "healthy": 12,
    "warning": 1,
    "critical": 1,
    "servers": [
        {
            "server_name": "Al-Andalus Production",
            "status": "Healthy",
            "last_backup_at": "2026-06-12T01:00:00Z",
            "backup_size_mb": 245.7,
            "backup_count": 7
        }
    ]
}
```

---

### 3.5 Alert Summary

```
GET /api/method/gatom_pulse.api.dashboard.alert_summary
```

**Response**:
```json
{
    "unread_count": 3,
    "unresolved_count": 5,
    "recent_alerts": [
        {
            "name": "ALERT-00042",
            "title": "Server DOWN: Al-Andalus Production",
            "severity": "Critical",
            "server": "PULSE-SRV-00001",
            "created_at": "2026-06-12T09:30:00Z",
            "acknowledged": false,
            "resolved": false
        }
    ]
}
```

---

### 3.6 Pulse Health Check *(Public — no auth)*

```
GET /api/method/gatom_pulse.api.health.ping
```

**Response**:
```json
{
    "status": "ok",
    "version": "1.0.0",
    "timestamp": "2026-06-12T09:30:00Z",
    "active_servers": 14,
    "redis": true
}
```

---

## 4. Pulse Scheduler Timeline

> Resolves audit finding **SCH-02, SCH-03, SCH-04**. All Pulse-side scheduler jobs are staggered to avoid resource contention.

| Time (UTC) | Job | Domain | Description |
|---|---|---|---|
| Every 60s | `detect_stale_servers` | P02 | Check all servers for heartbeat staleness |
| Every 60s | `cleanup_rotation_keys` | P01 | Clear expired `api_key_hash_previous` entries |
| 00:30 | `purge_old_logs` | P00 | Delete log entries past retention threshold |
| 01:00 | `aggregate_daily_summaries` | P02 | Compute uptime %, avg CPU/RAM/Disk for previous day |
| 01:30 | `purge_old_backup_reports` | P10 | Delete backup reports older than 90 days |
| 02:00 | `check_overdue_payments` | P08 | Scan unpaid invoices, trigger alerts/escalation |
| 03:00 | `check_license_expiry` | P07 | Alert on licenses expiring within 30/14/7 days |
| 03:30 | `compute_weekly_engagement` | P09 | Recompute engagement scores for all clients (Sundays only) |
| 04:30 | `cleanup_decommissioned_redis` | P01 | Purge orphaned Redis keys for decommissioned servers *(SCA-01)* |
| 05:00 | `pulse_self_check` | P00 | Verify Redis, DB, scheduler, email subsystems |
| **Hourly** | `send_alert_digest` | P05 | Bundle WARNING-level alerts into digest email |
| **Weekly** (Mon 9 AM) | `send_weekly_digest` | P05 | Summary: alerts, tickets, server health, billing |

> [!TIP]
> All times are UTC. No two heavy jobs share the same slot. The `detect_stale_servers` job is lightweight (Redis reads only) and safe to run every 60s.

---

## 5. Logging & Audit Requirements

### 5.1 Unified Audit Log

**DocType**: `Pulse Audit Log`

Every significant action across all domains must create an audit entry:

| Field | Type | Notes |
|---|---|---|
| `event_type` | Select | See event types below |
| `object_type` | Data | DocType name (e.g., `Pulse Server`, `Pulse License`) |
| `object_name` | Data | Record name |
| `actor` | Data | User email, `"Agent"`, or `"System"` |
| `timestamp` | Datetime | UTC |
| `details` | Small Text | JSON with event-specific context |
| `ip_address` | Data | Request source IP |

**Event Types**:

| Category | Events |
|---|---|
| **Server Lifecycle** | `SERVER_REGISTERED`, `SERVER_STATUS_CHANGED`, `SERVER_DECOMMISSIONED` |
| **API Key** | `API_KEY_GENERATED`, `API_KEY_ROTATED`, `API_KEY_GRACE_EXPIRED` |
| **License** | `LICENSE_ISSUED`, `LICENSE_VALIDATED`, `LICENSE_EXPIRED`, `LICENSE_REVOKED`, `LICENSE_RENEWED`, `LICENSE_VALIDATION_FAILED`, `LICENSE_SUSPENDED_PAYMENT` |
| **Billing** | `PAYMENT_RECORDED`, `INVOICE_GENERATED`, `PAYMENT_OVERDUE_WARNING`, `PAYMENT_OVERDUE_SUSPEND`, `PAYMENT_OVERDUE_ESCALATION` |
| **Alert** | `ALERT_CREATED`, `ALERT_ACKNOWLEDGED`, `ALERT_RESOLVED`, `ALERT_DISPATCH_FAILED` |
| **Ticket** | `TICKET_AUTO_CREATED`, `TICKET_AUTO_RESOLVED`, `TICKET_MANUALLY_CREATED` |
| **Error Tracking** | `ISSUE_CREATED`, `ISSUE_RESOLVED`, `ISSUE_REGRESSION`, `ISSUE_ASSIGNED` |
| **Release** | `RELEASE_PUBLISHED`, `RELEASE_ACKNOWLEDGED`, `SERVER_UPDATED` |
| **Agent** | `AGENT_DISABLED`, `AGENT_VERSION_OUTDATED`, `AGENT_QUEUE_OVERFLOW` |
| **System** | `SELF_CHECK_FAILED`, `LOG_PURGE_COMPLETED`, `RATE_LIMIT_HIT` |

**Acceptance Criteria**:
- [ ] Every event type listed above must create a `Pulse Audit Log` entry
- [ ] `actor` is the Frappe session user for manual actions, `"Agent"` for agent requests, `"System"` for scheduler jobs
- [ ] `details` is a valid JSON string with context (e.g., `{"old_status": "Online", "new_status": "Down"}`)
- [ ] Audit log entries are never deleted (no retention purge)
- [ ] Dashboard: filterable audit log viewer with event type, actor, time range, object type filters

### 5.2 Per-Domain Logging Requirements

| Domain | What Must Be Logged | Where | Resolves |
|---|---|---|---|
| P01 | Server status transitions (old → new + timestamp) | Audit Log: `SERVER_STATUS_CHANGED`. Details JSON: `{"old_status": "Online", "new_status": "Down", "trigger": "stale_heartbeat"}` | LOG-02 |
| P01 | API key generation (who generated, grace period, old key expiry) | Audit Log: `API_KEY_GENERATED`. Details JSON: `{"generated_by": "admin@gatom.com", "grace_period_hours": 24, "old_key_expires_at": "..."}` | LOG-04 |
| P01 | API key rotation (successful transition from old to new) | Audit Log: `API_KEY_ROTATED`. Details JSON: `{"requests_on_old_key_during_grace": 47}` | LOG-04 |
| P01 | API key grace expiry (old key stopped working) | Audit Log: `API_KEY_GRACE_EXPIRED` | LOG-04 |
| P02 | Threshold breach events (metric, value, threshold, duration) | New DocType: `Threshold Breach Log` (see §5.3) | LOG-01 |
| P03 | Log purge results (entries deleted per level) | Audit Log: `LOG_PURGE_COMPLETED`. Details JSON: `{"deleted": {"DEBUG": 4200, "INFO": 1800, "ERROR": 12}, "retained_days": 30}` | — |
| P04 | Issue lifecycle changes (created, resolved, regressed, assigned) | Audit Log: `ISSUE_*` events | — |
| P05 | Alert dispatch results per channel (sent/failed + error) | `Pulse Alert` child table: `Alert Dispatch Log` (see §5.4) | LOG-03 |
| P06 | Ticket auto-creation/resolution triggers | Audit Log: `TICKET_*` events | — |
| P07 | Every license validation attempt (online + offline) | `Pulse License Log` child table (existing, keep) | — |
| P08 | Payment recording + overdue escalation steps | Audit Log: `PAYMENT_RECORDED`. Details JSON: `{"payment_entry": "PE-001", "sales_invoice": "SINV-001", "pulse_client": "Al-Andalus Park", "amount": 350.00, "triggered_license_reinstatement": true}` | LOG-06 |
| P08 | Overdue escalation events | Audit Log: `PAYMENT_OVERDUE_WARNING` / `PAYMENT_OVERDUE_SUSPEND` / `PAYMENT_OVERDUE_ESCALATION`. Details JSON: `{"days_overdue": 8, "invoice": "SINV-001", "action_taken": "license_suspended"}` | LOG-06 |
| P09 | Tier compliance violations | Audit Log (reuse `ALERT_CREATED` with type `Asset Limit`) | — |
| P10 | Release publish + acknowledgment | Audit Log: `RELEASE_*` events | — |
| A08 | Queue drain results | Agent-side frappe.logger: `drain_summary`. Summary: `{"endpoint": "heartbeat", "drained": 45, "dropped_stale": 12, "failed": 0, "remaining": 0}` | LOG-05 |

### 5.3 Threshold Breach Log *(NEW — resolves LOG-01)*

**DocType**: `Threshold Breach Log`

Records individual threshold breaches with duration tracking:

| Field | Type | Notes |
|---|---|---|
| `server` | Link → Pulse Server | |
| `metric` | Select | `CPU`, `RAM`, `Disk`, `Queue`, `Response Time`, `Redis`, `MariaDB` |
| `threshold_level` | Select | `Warning` / `Critical` |
| `threshold_value` | Float | The configured threshold |
| `actual_value` | Float | The measured value that breached |
| `started_at` | Datetime | When the breach was first detected |
| `ended_at` | Datetime | When the metric dropped below threshold |
| `duration_seconds` | Int | Total breach duration |
| `sustained` | Check | Whether breach lasted > `threshold_sustained_minutes` |
| `alert_created` | Check | Whether this breach triggered an alert |

### 5.4 Alert Dispatch Log *(NEW — resolves LOG-03)*

**Child table of `Pulse Alert`**: `Alert Dispatch Log`

| Field | Type | Notes |
|---|---|---|
| `channel` | Select | `Email` / `WhatsApp` / `Dashboard` / `Digest` |
| `status` | Select | `Sent` / `Failed` / `Queued` |
| `sent_at` | Datetime | When dispatch was attempted |
| `error_message` | Small Text | Error details if failed |
| `recipient` | Data | Email address or phone number |

---

## 6. New & Updated DocType Fields

### 6.1 Pulse Server — New Fields *(resolves DF-01, DF-02)*

| Field | Type | Section | Notes |
|---|---|---|---|
| `timezone` | Data | System Info | IANA timezone (reported by agent on registration) |
| `python_version` | Data | System Info | Python version (reported by agent) |
| `os_version` | Data | System Info | OS version string (reported by agent) |

### 6.2 Server Daily Summary — New Fields *(resolves DF-03)*

| Field | Type | Notes |
|---|---|---|---|
| `avg_response_time_ms` | Int | Average HTTP self-check response time |
| `max_response_time_ms` | Int | Peak response time during the day |
| `avg_queue_depth` | Int | Average RQ queue depth |
| `max_queue_depth` | Int | Peak queue depth |
| `threshold_breaches` | Int | Number of threshold breach events |

### 6.3 Pulse Alert — New Fields *(resolves DF-04)*

| Field | Type | Notes |
|---|---|---|
| `resolved` | Check | Whether the alert condition has been resolved |
| `resolved_at` | Datetime | When resolved |
| `resolved_by` | Link → User | Who resolved it |
| `dispatch_log` | Table → Alert Dispatch Log | Per-channel delivery tracking |

### 6.4 Pulse Issue — New Fields *(resolves DF-05)*

| Field | Type | Notes |
|---|---|---|
| `assigned_to` | Link → User | Developer assigned to investigate |
| `assigned_at` | Datetime | When assignment was made |
| `auto_ticket_threshold` | Int | Auto-create ticket after this many occurrences (default: 50) |

### 6.5 Pulse Client — New Fields *(resolves DF-06)*

| Field | Type | Notes |
|---|---|---|
| `contract_start_date` | Date | When the contract began |
| `contract_end_date` | Date | When the contract expires (for renewal tracking) |
| `contract_auto_renew` | Check | Whether contract auto-renews |

### 6.6 Backup Status Report — New Fields *(resolves DF-07)*

| Field | Type | Notes |
|---|---|---|
| `backup_count` | Int | Total `.sql.gz` files in backup directory |

### 6.7 Usage Snapshot — Updated *(resolves SCH-01)*

| Field | Type | Notes |
|---|---|---|
| `week_start` | Date | Monday of the snapshot week (used as upsert key) |
| `last_updated_at` | Datetime | When this snapshot was last updated by a daily push |
| `daily_push_count` | Int | How many daily pushes have updated this snapshot (1–7) |

---

## 7. Cross-Domain Integration Fixes

### 7.1 P04 → P06: Auto-Ticket for High-Frequency Errors *(resolves INT-01)*

When the P04 error pipeline processes a fingerprint and increments `occurrence_count`:

```
IF occurrence_count >= auto_ticket_threshold (default 50)
   AND linked_ticket IS NULL
   AND status != "Ignored":
   → Auto-create HD Ticket:
     - type = "Support Request"
     - subject = "⚠️ High-frequency error: {issue.title}"
     - custom_related_issue = issue.name
     - custom_auto_created = 1
   → Set issue.linked_ticket = new ticket
   → Write Audit Log: TICKET_AUTO_CREATED
```

Also: when a **regression** is detected (resolved issue reappears):
```
IF status was "Resolved" AND new occurrence detected:
   → Auto-create HD Ticket:
     - type = "Support Request"
     - subject = "🔄 Regression: {issue.title}"
     - custom_auto_created = 1
   → Write Audit Log: ISSUE_REGRESSION
```

**Acceptance Criteria**:
- [ ] Error exceeding `auto_ticket_threshold` → auto-creates ticket (once per issue)
- [ ] Regression → auto-creates ticket
- [ ] Both rules respect `status = Ignored` (no ticket for ignored issues)

---

### 7.2 P07 ↔ P08: Payment-Driven License Suspension *(resolves INT-02)*

The billing domain (P08) must call specific P07 functions to change license status:

```python
# In P08's check_overdue_payments scheduler job:

def suspend_license_for_payment(client):
    """Called when payment is 8+ days overdue. Sets license to Grace."""
    license = frappe.get_last_doc("Pulse License",
        filters={"client": client, "status": "Active"})
    if license:
        license.status = "Grace"
        license.save()
        # Write audit log
        create_audit_log("LICENSE_SUSPENDED_PAYMENT", "Pulse License",
            license.name, "System",
            {"reason": "Payment overdue", "client": client})

def expire_license_for_payment(client):
    """Called when payment is 30+ days overdue. Expires the license."""
    license = frappe.get_last_doc("Pulse License",
        filters={"client": client, "status": ["in", ["Active", "Grace"]]})
    if license:
        license.status = "Expired"
        license.save()
        create_audit_log("LICENSE_EXPIRED", "Pulse License",
            license.name, "System",
            {"reason": "Payment overdue > 30 days", "client": client})

def reinstate_license_on_payment(client):
    """Called when overdue payment is received. Reinstates the license."""
    license = frappe.get_last_doc("Pulse License",
        filters={"client": client, "status": ["in", ["Grace", "Expired"]]})
    if license and license.expires_at > now():
        license.status = "Active"
        license.save()
        create_audit_log("LICENSE_RENEWED", "Pulse License",
            license.name, "System",
            {"reason": "Payment received", "client": client})
```

**P08 Overdue Pipeline (Updated)**:

```
Day 0:   Invoice generated
Day 7:   WARNING alert → Gatom admin
Day 8:   P08 calls suspend_license_for_payment() → License.status = Grace
Day 14:  HIGH alert → Gatom admin
Day 30:  P08 calls expire_license_for_payment() → License.status = Expired
         + Create escalation ticket
Payment: P08 calls reinstate_license_on_payment() → License.status = Active
```

**Acceptance Criteria**:
- [ ] Overdue day 8 → License enters Grace (next agent check → banner on client site)
- [ ] Overdue day 30 → License expires (next agent check → site suspended)
- [ ] Payment recorded → License reinstated if not past JWT expiry date
- [ ] All transitions logged to Pulse Audit Log

---

### 7.3 Threshold Sustained Tracking *(resolves INT-03)*

Pulse must track how long a threshold has been continuously breached before triggering an alert:

```python
def evaluate_threshold(server, metric, value, threshold_warning, threshold_critical):
    """Called on every heartbeat. Uses Redis counters for sustained tracking."""
    warning_key = f"pulse:breach:{server}:{metric}:warning"
    critical_key = f"pulse:breach:{server}:{metric}:critical"
    sustained_minutes = get_pulse_config().threshold_sustained_minutes  # default: 5
    
    if value >= threshold_critical:
        count = frappe.cache().incr(critical_key)
        frappe.cache().expire(critical_key, sustained_minutes * 60 + 120)
        
        if count >= sustained_minutes:  # 1 heartbeat/min × sustained_minutes
            if not has_recent_alert(server, metric, "Critical"):
                create_alert(server, "Threshold", "Critical",
                    f"{metric} at {value}% for {count} minutes")
                create_threshold_breach(server, metric, "Critical", value,
                    started_at=now() - timedelta(minutes=count), sustained=True)
    else:
        # Breach ended — record end time
        if frappe.cache().get(critical_key):
            close_threshold_breach(server, metric, "Critical")
        frappe.cache().delete(critical_key)
    
    # Same logic for warning threshold (omitted for brevity)
```

**How it works**:
- Redis counter `pulse:breach:{server}:{metric}:{level}` increments on each heartbeat where the threshold is exceeded
- Counter has a TTL of `sustained_minutes + 2 min` (auto-resets if heartbeats stop)
- Alert is only triggered when the counter reaches `threshold_sustained_minutes`
- When the metric drops below the threshold, the counter is reset and the `Threshold Breach Log` entry is closed

**Acceptance Criteria**:
- [ ] Transient 1-minute CPU spike → no alert (counter resets at minute 2)
- [ ] Sustained 5-minute CPU spike → alert triggered on minute 5
- [ ] Breach end → `Threshold Breach Log` entry closed with duration
- [ ] Breach counter auto-expires if heartbeats stop (no stale counters)

---

### 7.4 Agent Disabled → Pulse Awareness *(resolves INT-04)*

When the agent disables itself (due to 401/403), the server goes silent. Pulse needs to distinguish this from a real crash.

**Solution**: The heartbeat endpoint (§2.2) response for auth failures returns `SERVER_DECOMMISSIONED` (403). But for the initial 401, the last heartbeat's `agent_health.agent_disabled` field will be `false` — because the agent didn't know yet.

Instead, use the Pulse Audit Log:

1. When Pulse returns `401` to an agent request → write `Audit Log: AGENT_DISABLED` with `object_name = server_name`
2. When `detect_stale_servers` finds a server going Down:
   - Check audit log: was there a recent `AGENT_DISABLED` event for this server?
   - If YES → set status to `Down (Auth Failure)` instead of `Down` — different alert message
   - Do NOT auto-create an incident ticket (it's an auth issue, not a server crash)

**Acceptance Criteria**:
- [ ] 401 response → Audit Log entry `AGENT_DISABLED`
- [ ] Stale server with recent `AGENT_DISABLED` → status shown as auth failure, not crash
- [ ] No false incident ticket for auth-disabled agents

---

### 7.5 P03 Socketio Event Specification *(resolves INT-05)*

| Event Name | Room | Payload |
|---|---|---|
| `pulse:new_logs` | `pulse:logs:{server_name}` | `{ "server": "...", "entries_count": 5, "has_errors": true }` |
| `pulse:server_status` | `pulse:fleet` | `{ "server": "...", "status": "Down", "previous": "Online" }` |
| `pulse:new_alert` | `pulse:alerts` | `{ "alert_name": "...", "severity": "Critical", "title": "..." }` |
| `pulse:heartbeat` | `pulse:server:{server_name}` | `{ "server": "...", "cpu_pct": 42.5, "ram_pct": 67.3 }` |

**Frontend subscription**:
```javascript
// Subscribe to a specific server's logs
frappe.realtime.on("pulse:new_logs", (data) => {
    if (data.server === currentServer) {
        fetchNewLogs();  // Pull latest entries via API
    }
});
```

---

### 7.6 Server Decommission via Heartbeat *(resolves EP-03)*

When a Gatom admin sets a server's status to `Decommissioned` in Pulse Desk:

1. Next heartbeat from that server → response includes `commands.decommission = true` (see §2.2)
2. Agent receives `decommission = true`:
   - Logs CRITICAL: "Server decommissioned by Pulse. Disabling agent."
   - Sets `pulse_agent_disabled = true` in Redis
   - Stops all scheduler jobs (heartbeat, logs, usage, backup, license)
   - Sends one final heartbeat with `agent_health.agent_disabled = true`
3. Pulse receives the final heartbeat → writes Audit Log: `SERVER_DECOMMISSIONED`
4. Any subsequent requests from this server → `403 SERVER_DECOMMISSIONED` (hard rejection)

**Acceptance Criteria**:
- [ ] Server set to Decommissioned in Desk → next heartbeat response includes `commands.decommission = true`
- [ ] Agent processes decommission command → disables itself cleanly
- [ ] Agent sends one final heartbeat confirming shutdown
- [ ] No incident ticket created for the expected silence after decommission

---

### 7.7 Encrypted Re-Keying via Heartbeat *(resolves EP-04, SEC-01)*

When a Gatom admin regenerates an API key for a server in Pulse Desk:

1. Pulse stores the new key hash in `api_key_hash` and moves the old hash to `api_key_hash_previous`
2. Grace period starts (default: 24 hours) — both keys are accepted
3. **Key Exchange Encryption**: Pulse encrypts the new API key using AES-256-GCM with the old API key as the symmetric key:

   ```python
   # Pulse side — encrypting the new key for transit
   import os
   from cryptography.hazmat.primitives.ciphers.aead import AESGCM
   import hashlib
   
   def encrypt_new_key(new_api_key: str, old_api_key_hash: str) -> dict:
       """Encrypt new API key using a symmetric key derived from the old key's hash.
       
       We use the first 32 bytes of the old key's SHA-256 hash as the AES key.
       The agent can reproduce this because it knows its current API key.
       """
       # Derive 256-bit key from old key hash
       aes_key = bytes.fromhex(old_api_key_hash)[:32]
       nonce = os.urandom(12)  # 96-bit nonce for GCM
       
       aesgcm = AESGCM(aes_key)
       ciphertext = aesgcm.encrypt(nonce, new_api_key.encode(), None)
       
       return {
           "nonce": nonce.hex(),
           "ciphertext": ciphertext.hex()
       }
   ```

4. Next heartbeat from the agent (using old key) → response includes:
   ```json
   {
       "commands": {
           "rotate_key": {
               "nonce": "a1b2c3d4e5f6a1b2c3d4e5f6",
               "ciphertext": "encrypted_new_api_key_hex..."
           }
       }
   }
   ```

5. Agent receives and decrypts the new key:
   ```python
   def process_rotate_key(encrypted_key_data: dict):
       """Handle encrypted key rotation command from Pulse."""
       from cryptography.hazmat.primitives.ciphers.aead import AESGCM
       import hashlib
       
       # Derive AES key from our current API key's SHA-256 hash
       current_key = get_config("pulse_api_key")
       key_hash = hashlib.sha256(current_key.encode()).hexdigest()
       aes_key = bytes.fromhex(key_hash)[:32]
       
       nonce = bytes.fromhex(encrypted_key_data["nonce"])
       ciphertext = bytes.fromhex(encrypted_key_data["ciphertext"])
       
       try:
           aesgcm = AESGCM(aes_key)
           new_key = aesgcm.decrypt(nonce, ciphertext, None).decode()
       except Exception:
           frappe.logger().error("gatom_agent: Failed to decrypt new API key")
           return
       
       # 1. Write new key to site_config.json
       frappe.conf.pulse_api_key = new_key
       update_site_config("pulse_api_key", new_key)
       
       # 2. Update in-memory client
       pulse_client.api_key = new_key
       
       # 3. Confirm by sending a heartbeat with the new key
       pulse_client.post("heartbeat", collect_heartbeat())
       
       frappe.logger().info("API key rotated successfully via Pulse command")
   ```

6. Once Pulse receives a valid request using the new key → marks rotation as complete
7. After grace period expires → `api_key_hash_previous` is cleared, old key stops working
8. If agent doesn't pick up the new key within grace period → old key expires, agent enters `Down (Auth Failure)` state

> [!IMPORTANT]
> **Why encrypted?** Even over HTTPS, the raw API key in a response body could be captured by:
> - Frappe's request/response logging middleware
> - Reverse proxy access logs that capture response bodies
> - Debug tools or APM agents that intercept HTTP traffic
> 
> AES-256-GCM encryption ensures the key is only readable by the agent that knows the current key.

**Acceptance Criteria**:
- [ ] Key regeneration in Desk → encrypted key piggybacked on next heartbeat response
- [ ] `commands.rotate_key` contains `{nonce, ciphertext}` — never plaintext
- [ ] Agent decrypts using SHA-256 hash of its current API key
- [ ] Agent writes new key to `site_config.json` without manual SSH
- [ ] Agent confirms new key works by sending a heartbeat
- [ ] Rotation logged in Pulse Audit Log: `API_KEY_ROTATED`
- [ ] Grace period expiry handled cleanly (old key revoked)
- [ ] If agent fails to decrypt → WARNING log, retry on next heartbeat
- [ ] If agent fails to rotate within grace period → alert generated for Gatom admins

---

### 7.8 Queue Drain Logging *(resolves LOG-05)*

After every queue drain operation (§A08 §6.2), the agent must log a summary:

```python
def drain_queue(self):
    """Process queued entries oldest-first. Stop on first failure."""
    drain_summary = {}
    
    for endpoint in QUEUED_ENDPOINTS:
        stats = {"drained": 0, "dropped_stale": 0, "failed": 0, "remaining": 0}
        key = f"pulse:queue:{endpoint}"
        
        while True:
            raw = frappe.cache().lindex(key, 0)
            if not raw:
                break
            
            entry = json.loads(raw)
            
            if entry_age(entry) > timedelta(hours=24):
                frappe.cache().lpop(key)
                stats["dropped_stale"] += 1
                continue
            
            try:
                response = self._raw_post(endpoint, entry["payload"])
                if response.status_code == 200:
                    frappe.cache().lpop(key)
                    stats["drained"] += 1
                elif response.status_code in (400, 401, 403):
                    frappe.cache().lpop(key)
                    stats["drained"] += 1  # dropped non-retryable
                else:
                    stats["failed"] += 1
                    break
            except (requests.ConnectionError, requests.Timeout):
                stats["failed"] += 1
                break
        
        stats["remaining"] = frappe.cache().llen(key)
        drain_summary[endpoint] = stats
    
    # Log the summary
    total_drained = sum(s["drained"] for s in drain_summary.values())
    total_stale = sum(s["dropped_stale"] for s in drain_summary.values())
    
    if total_drained > 0 or total_stale > 0:
        frappe.logger("gatom_agent").info(
            f"Queue drain complete: {total_drained} sent, {total_stale} dropped (stale)",
            drain_summary
        )
```

**Acceptance Criteria**:
- [ ] Every drain operation produces a summary log line
- [ ] Summary includes per-endpoint breakdown: drained, dropped, failed, remaining
- [ ] If `dropped_stale > 0`, a WARNING-level log is emitted
- [ ] If `remaining > 0`, a WARNING-level log is emitted with the remaining count

---

### 7.9 Decommissioned Server Redis Cleanup *(resolves SCA-01)*

When a server is decommissioned, its heartbeat Redis keys expire naturally (5-min TTL). However, several other Redis key families linger much longer:

| Key Pattern | TTL | Risk |
|---|---|---|
| `pulse:breach:{server}:{metric}:{level}` | `sustained_minutes + 2 min` | 7+ min after decommission |
| `pulse:ratelimit:{endpoint}:{server}` | Up to 86,400s (1 day) | Full day of orphaned keys |
| `pulse:agent_health:{server}` | 5 min | Low risk — expires fast |
| `pulse:heartbeat:{server}` | 5 min | Low risk — expires fast |
| `pulse:request_id:{uuid}` | 10 min | Low risk — not server-scoped |

**Scheduler job**: `cleanup_decommissioned_redis` (runs daily at 04:30 UTC)

```python
def cleanup_decommissioned_redis():
    """Purge all Redis keys for servers with status = Decommissioned.
    
    Prevents orphaned counters from accumulating in Redis memory.
    Runs daily — safe to run repeatedly (idempotent).
    """
    decommissioned = frappe.get_all("Pulse Server",
        filters={"status": "Decommissioned"},
        pluck="name")
    
    total_deleted = 0
    for server in decommissioned:
        patterns = [
            f"pulse:breach:{server}:*",
            f"pulse:ratelimit:*:{server}",
            f"pulse:heartbeat:{server}",
            f"pulse:agent_health:{server}",
        ]
        for pattern in patterns:
            keys = frappe.cache().get_keys(pattern)
            for key in keys:
                frappe.cache().delete(key)
                total_deleted += 1
    
    if total_deleted > 0:
        frappe.logger("gatom_pulse").info(
            f"Redis cleanup: deleted {total_deleted} keys for "
            f"{len(decommissioned)} decommissioned servers"
        )
        create_audit_log("LOG_PURGE_COMPLETED", "Pulse Server", None, "System",
            {"type": "redis_cleanup", "keys_deleted": total_deleted,
             "servers": decommissioned})
```

**Acceptance Criteria**:
- [ ] Runs daily at 04:30 UTC
- [ ] Deletes all Redis keys matching known patterns for decommissioned servers
- [ ] Logs summary of deleted key count
- [ ] Writes Audit Log entry
- [ ] No-op if no decommissioned servers exist (no log, no error)
- [ ] Does not touch keys for active/degraded/down servers

---

## 🔗 Related

- [[Pulse Overview|🏗️ Pulse Overview]]
- [[Pulse MOC|🫀 Pulse MOC]]
- [[Agent/Agent Overview|🤖 Agent Overview]]
- [[P00 - Configuration/functional|⚙️ P00 — Configuration]]
