---
tags: [gatom, pulse, agent, overview, architecture]
aliases: [Agent Overview]
---

# Gatom Agent — Overview

> **Component**: `gatom_agent`
> **Type**: Lightweight Frappe app installed on every client server
> **Purpose**: Collects health data, logs, usage metrics, and validates licenses — pushes everything to Pulse
> **Status**: Architecture Design

---

## 1. What This App Does

`gatom_agent` is the client-side half of Gatom Pulse. It runs silently on every deployed Frappe server, collecting system health, application logs, usage data, and backup status, then pushing everything to the Pulse command center over HTTPS.

**Without the agent**, Pulse is blind — it cannot see what's happening on client servers.

The agent must be:
- **Lightweight** — no heavy DocTypes, no user-facing UI, minimal CPU/RAM usage
- **Resilient** — continues operating when Pulse is unreachable; queues and retries
- **Secure** — API key stored outside the database; sensitive data stripped before push
- **Invisible** — clients should not notice its presence

---

## 2. Installation & Configuration

### 2.1 Installation

```bash
bench get-app gatom_agent <repo_url>
bench --site {site} install-app gatom_agent
```

On install, `gatom_agent` runs an `after_install` hook that:
1. Prompts for (or reads from env) the Pulse API key and Pulse URL
2. Writes both to `site_config.json`
3. Calls Pulse's registration endpoint to announce itself
4. Stores the returned `server_id` in `site_config.json`

### 2.2 Configuration Keys (`site_config.json`)

| Key | Type | Required | Notes |
|---|---|---|---|
| `pulse_api_key` | string | ✅ | UUID v4 API key (sent as Bearer token) |
| `pulse_url` | string | ✅ | Full URL of Gatom's ERPNext (e.g., `https://erp.gatom.com`) |
| `pulse_server_id` | string | Auto | Set after first successful registration |
| `pulse_agent_disabled` | bool | | Set `true` to temporarily disable all agent jobs |
| `pulse_log_level` | string | | Agent's own log level: `DEBUG` / `INFO` / `WARNING` (default: `INFO`) |

### 2.3 Uninstallation

```bash
bench --site {site} uninstall-app gatom_agent
```

On uninstall, `gatom_agent` runs a `before_uninstall` hook that:
1. Sends a final heartbeat with `agent_health.agent_disabled = true` and `agent_health.uninstalling = true`
2. Clears `pulse_*` keys from `site_config.json`
3. Flushes the local retry queue (Redis)

> [!NOTE]
> **Why `agent_health.uninstalling`?** This uses the existing heartbeat schema (not a custom `status` field). When Pulse receives a heartbeat with `uninstalling = true`, it sets the server status to `Decommissioned` and does NOT auto-create an incident ticket. This prevents false alerts for intentional agent removals. See [[API Contract#7.6 Server Decommission via Heartbeat|API Contract §7.6]].

---

## 3. File Structure

```
gatom_agent/
├── gatom_agent/
│   ├── __init__.py
│   ├── hooks.py                    # Frappe hooks: scheduler_events, after_install, before_uninstall
│   ├── config.py                   # Read pulse_url, pulse_api_key from site_config
│   │
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── heartbeat.py            # → A02: System health metrics
│   │   ├── log_collector.py        # → A03: Log parsing + sanitization
│   │   ├── error_fingerprint.py    # → A04: Traceback fingerprinting
│   │   ├── license_checker.py      # → A05: License validation
│   │   ├── usage_collector.py      # → A06: Asset/agreement/user counts
│   │   └── backup_checker.py       # → A07: Backup file verification
│   │
│   ├── transport/
│   │   ├── __init__.py
│   │   ├── pulse_client.py         # → A08: HTTP client with retry, timeout, error handling
│   │   ├── queue.py                # → A08: Local Redis queue for offline resilience
│   │   └── request_signer.py       # → A08: Timestamp injection for replay prevention
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── sanitizer.py            # Regex-based sensitive data stripping (used by A03)
│   │   └── system_metrics.py       # psutil wrappers for CPU/RAM/Disk (used by A02)
│   │
│   ├── keys/
│   │   ├── gatom_license_public_v1.pem  # RSA public key v1 for offline license verification
│   │   └── gatom_license_public_v2.pem  # RSA public key v2 (added during key rotation)
│   │
│   └── scheduler_events.py         # All cron job registrations
│
├── setup.py
└── requirements.txt                 # psutil, PyJWT, cryptography
```

---

## 4. Scheduler Events

Registered in `hooks.py`:

```python
scheduler_events = {
    "cron": {
        "* * * * *": [                            # Every 60 seconds
            "gatom_agent.gatom_agent.collectors.heartbeat.send_heartbeat"
        ],
        "*/5 * * * *": [                          # Every 5 minutes
            "gatom_agent.gatom_agent.collectors.log_collector.push_logs"
        ],
        "0 2 * * *": [                            # Daily at 2 AM (local time)
            "gatom_agent.gatom_agent.collectors.usage_collector.push_usage_stats"
        ],
        "0 3 * * *": [                            # Daily at 3 AM (local time)
            "gatom_agent.gatom_agent.collectors.backup_checker.check_backup_status"
        ],
        "0 4 * * *": [                            # Daily at 4 AM (local time)
            "gatom_agent.gatom_agent.collectors.license_checker.validate_license"
        ]
    }
}
```

> [!NOTE]
> All daily jobs use the **client server's local timezone** (Frappe's `time_zone` from `site_config.json`). Heartbeat and log push use cron syntax which runs in server-local time.

---

## 5. Versioning & Upgrades

### 5.1 Semantic Versioning

`gatom_agent` follows semantic versioning independently from `rental_core`:

| Version Part | Meaning |
|---|---|
| Major (1.x.x) | Breaking API changes (Pulse requires minimum version) |
| Minor (x.1.x) | New collectors or features |
| Patch (x.x.1) | Bug fixes |

### 5.2 Version Compatibility

Pulse tracks `agent_version` (reported on every heartbeat). Pulse Configuration defines:
- `min_agent_version` — reject heartbeats from agents below this version (returns `426 Upgrade Required`)
- `recommended_agent_version` — shows "update available" in Pulse dashboard

### 5.3 Upgrade Process

```bash
bench update --pull      # Pulls latest gatom_agent code
bench migrate            # Runs any schema changes
bench restart            # Restarts workers
```

On first heartbeat after upgrade, agent sends new `agent_version` → Pulse updates the record.

---

## 6. Dependencies

### Python Dependencies (`requirements.txt`)

```
psutil>=5.9.0          # CPU, RAM, Disk metrics
PyJWT>=2.8.0           # JWT decoding for offline license validation
cryptography>=41.0.0   # RSA public key loading
requests>=2.31.0       # HTTP client (may already be available via Frappe)
```

### Frappe Dependencies

- Frappe 15+ (scheduler, Redis, `site_config` access)
- **Does NOT depend on** `rental_core`, `rental_flats`, or `rental_vehicles`
- License checking reads `Rental Configuration` if it exists, but gracefully handles its absence

---

## 7. Security Considerations

| Concern | Mitigation |
|---|---|
| API key storage | Stored in `site_config.json` (file-level access, not in MariaDB) |
| API key in memory | Read once at process start, held in memory (not re-read per request) |
| Log data leakage | All log content sanitized with regex patterns before push (see A03) |
| Agent as attack vector | Agent has NO write access to client DocTypes; read-only queries only |
| Network security | All Pulse communication over HTTPS; agent validates SSL certificates |
| Clock manipulation | Agent uses system clock; if clock is off by > 300s, Pulse rejects requests |

---

## 8. Self-Diagnostics

The agent exposes a local-only diagnostic endpoint (not pushed to Pulse):

```python
@frappe.whitelist(allow_guest=False)
@frappe.only_for("System Manager")
def agent_status():
    """Returns agent health for local debugging.
    
    Restricted to System Manager role only (SEC-04).
    This endpoint is local-only — not pushed to Pulse.
    """
    return {
        "agent_version": __version__,
        "pulse_url": get_config("pulse_url"),
        "pulse_reachable": test_pulse_connectivity(),
        "server_id": get_config("pulse_server_id"),
        "last_heartbeat_sent": cache.get("pulse:last_heartbeat"),
        "last_log_push": cache.get("pulse:last_log_push"),
        "last_license_check": cache.get("pulse:last_license_check"),
        "license_status": cache.get("pulse:license_status"),
        "queue_size": get_total_queue_size(),
        "agent_disabled": get_config("pulse_agent_disabled", False),
        "auth_retry_count": cache.get("pulse:auth_retry_count") or 0,
    }
```

---

## 9. Agent Self-Recovery *(resolves ERR-01)*

When the agent receives a `401 Invalid API Key` response, it must NOT immediately and permanently disable itself. Instead, it follows a **graduated recovery** strategy:

### 9.1 Retry-Before-Disable

```python
MAX_AUTH_RETRIES = 3
AUTH_RETRY_INTERVAL_SECONDS = 300  # 5 minutes between retries
RECOVERY_CHECK_INTERVAL_HOURS = 6

def handle_auth_failure(response):
    """Graduated response to 401 errors. Never permanently disable."""
    retry_count = int(frappe.cache().get("pulse:auth_retry_count") or 0)
    retry_count += 1
    frappe.cache().set("pulse:auth_retry_count", retry_count)
    
    if retry_count <= MAX_AUTH_RETRIES:
        # Phase 1: Retry — might be a transient issue or key rotation in progress
        frappe.logger().warning(
            f"gatom_agent: Auth failed (attempt {retry_count}/{MAX_AUTH_RETRIES}). "
            f"Retrying in {AUTH_RETRY_INTERVAL_SECONDS}s."
        )
        return  # Next heartbeat (60s) will retry naturally
    
    elif retry_count == MAX_AUTH_RETRIES + 1:
        # Phase 2: Disable collectors, but keep recovery check alive
        frappe.logger().error(
            "gatom_agent: Auth failed after max retries. "
            "Disabling collectors. Recovery check every 6 hours."
        )
        frappe.cache().set("pulse:agent_soft_disabled", True)
    
    # Phase 3 (ongoing): Don't set pulse_agent_disabled in site_config.
    # The recovery check (§9.2) will periodically attempt re-registration.
```

### 9.2 Periodic Recovery Check

Even when soft-disabled, the agent runs a **recovery check every 6 hours**:

```python
def recovery_check():
    """Attempt re-registration every 6 hours when auth-disabled.
    
    Registered as a separate cron job: '0 */6 * * *'
    Only runs when pulse:agent_soft_disabled is True.
    """
    if not frappe.cache().get("pulse:agent_soft_disabled"):
        return
    
    frappe.logger().info("gatom_agent: Attempting recovery registration...")
    
    try:
        response = pulse_client.post("register", collect_registration_payload())
        
        if response.status_code == 200:
            # Recovery successful — re-enable all collectors
            frappe.cache().delete("pulse:agent_soft_disabled")
            frappe.cache().set("pulse:auth_retry_count", 0)
            frappe.logger().info("gatom_agent: Recovery successful! Agent re-enabled.")
        elif response.status_code == 401:
            frappe.logger().warning("gatom_agent: Recovery check failed — still unauthorized.")
        elif response.status_code == 403:
            # SERVER_DECOMMISSIONED — this is intentional, stop trying
            frappe.logger().critical(
                "gatom_agent: Server decommissioned by Pulse. Stopping recovery."
            )
            update_site_config("pulse_agent_disabled", True)
    except Exception:
        frappe.logger().warning("gatom_agent: Recovery check failed — Pulse unreachable.")
```

### 9.3 Scheduler Registration

```python
# In hooks.py — add to scheduler_events
"0 */6 * * *": [
    "gatom_agent.gatom_agent.transport.pulse_client.recovery_check"
]
```

### 9.4 Manual Recovery

If the admin has corrected the API key in `site_config.json`, they can force an immediate recovery:

```bash
bench --site {site} execute gatom_agent.gatom_agent.transport.pulse_client.recovery_check
bench restart
```

**Acceptance Criteria**:
- [ ] First 401 → WARNING log, retry on next heartbeat (no disable)
- [ ] After 3 consecutive 401s → soft-disable collectors (heartbeats stop)
- [ ] Soft-disabled agent runs recovery check every 6 hours
- [ ] Successful recovery → all collectors re-enabled, retry count reset
- [ ] 403 (decommissioned) → hard disable (this IS permanent)
- [ ] `pulse_agent_disabled` in `site_config.json` is ONLY set for 403 responses
- [ ] Manual `bench execute recovery_check` works for immediate recovery

---

## 10. Pre-Deployment Mode *(resolves ALF-01)*

The agent may be installed on a server that doesn't have `rental_core` yet (e.g., a fresh Frappe instance being prepared for deployment). In this state:

### 10.1 Behavior

| Collector | Behavior |
|---|---|
| A01 (Registration) | ✅ Runs normally — reports installed apps (which won't include `rental_core`) |
| A02 (Heartbeat) | ✅ Runs normally — system metrics don't depend on rental apps |
| A03 (Log Collection) | ✅ Runs normally — reads Frappe logs regardless of installed apps |
| A04 (Error Fingerprinting) | ✅ Runs normally — processes any Python traceback |
| A05 (License Validation) | ⏭️ **Skipped** — no `Rental Configuration` DocType exists |
| A06 (Usage Collection) | ⏭️ **Skipped** — `safe_count()` returns 0 for all rental DocTypes |
| A07 (Backup Checking) | ✅ Runs normally — checks Frappe backup files regardless of apps |

### 10.2 Detection

```python
def is_rental_core_installed() -> bool:
    """Check if rental_core is installed on this site."""
    return "rental_core" in frappe.get_installed_apps()

def skip_if_no_rental_core(func):
    """Decorator to skip collectors that depend on rental_core."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not is_rental_core_installed():
            frappe.logger().debug(
                f"gatom_agent: Skipping {func.__name__} — rental_core not installed"
            )
            return
        return func(*args, **kwargs)
    return wrapper
```

### 10.3 License Status

When `rental_core` is absent, the agent sets `pulse:license_status = PRE_DEPLOYMENT` in Redis. This status is NOT a suspend-trigger — `rental_core` doesn't exist to read it anyway.

**Acceptance Criteria**:
- [ ] Agent installs and runs on bare Frappe (no rental apps) without errors
- [ ] Heartbeats report system health correctly even without rental apps
- [ ] License validation and usage collection silently skip when rental_core is absent
- [ ] `installed_apps` accurately reports what's installed (Pulse dashboard shows pre-deployment state)
- [ ] When `rental_core` is later installed, the agent starts collecting license/usage data on next scheduler tick

---

## 11. Domain Documentation Index

> Agent domain functional specs live alongside their Pulse counterparts as `agent-functional.md` in each domain folder.

| # | Agent Domain | Co-located With | Agent Doc |
|---|---|---|---|
| A01 | Server Registration | [[P01 - Client & Server Registry/functional\|P01 — Client & Server Registry]] | [[P01 - Client & Server Registry/agent-functional\|agent-functional.md]] |
| A02 | Heartbeat Collection | [[P02 - Server Health Monitoring/functional\|P02 — Server Health Monitoring]] | [[P02 - Server Health Monitoring/agent-functional\|agent-functional.md]] |
| A03 | Log Collection & Sanitization | [[P03 - Log Aggregation/functional\|P03 — Log Aggregation]] | [[P03 - Log Aggregation/agent-functional\|agent-functional.md]] |
| A04 | Error Fingerprinting | [[P04 - Error Tracking/functional\|P04 — Error Tracking]] | [[P04 - Error Tracking/agent-functional\|agent-functional.md]] |
| A05 | License Validation | [[P07 - Licensing/functional\|P07 — Licensing Engine]] | [[P07 - Licensing/agent-functional\|agent-functional.md]] |
| A06 | Usage Collection | [[P09 - Usage Analytics/functional\|P09 — Usage Analytics]] | [[P09 - Usage Analytics/agent-functional\|agent-functional.md]] |
| A07 | Backup Checking | [[P10 - Releases & Backups/functional\|P10 — Releases & Backups]] | [[P10 - Releases & Backups/agent-functional\|agent-functional.md]] |
| A08 | Transport & Resilience | [[P00 - Configuration/functional\|P00 — Configuration & Cross-Cutting]] | [[P00 - Configuration/agent-functional\|agent-functional.md]] |

---

## 🔗 Related

- [[Pulse Overview|🏗️ Pulse Overview]]
- [[Pulse MOC|🫀 Pulse MOC]]
- [[P00 - Configuration/functional|⚙️ P00 — Pulse Configuration]]
