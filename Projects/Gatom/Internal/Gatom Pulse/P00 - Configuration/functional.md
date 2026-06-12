---
tags: [gatom, pulse, p00, configuration, cross-cutting, functional]
---

# P00 — Pulse Configuration & Cross-Cutting Concerns: Functional Analysis

> **Product**: Gatom Pulse
> **Domain**: P00 — Platform Configuration & Cross-Cutting Concerns
> **Module**: `gatom_pulse`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

This domain defines the global configuration singleton, cross-cutting technical concerns (rate limiting, timezone handling, API contracts, security hardening), and operational policies that apply across all other domains (P01–P10). It is the first domain to implement.

---

## 2. Pulse Configuration Singleton

### 2.1 DocType: `Pulse Configuration`

A Frappe SingleDocType — one per site, editable by Pulse Admin role.

#### Section: General

| Field | Type | Default | Notes |
|---|---|---|---|
| `pulse_site_name` | Data | | Human-readable name for this Pulse instance |
| `company_name` | Data | `Gatom` | Used in license JWT `iss` claim |
| `default_timezone` | Link → Timezone | `UTC` | Dashboard display timezone |

#### Section: Monitoring Defaults

| Field | Type | Default | Notes |
|---|---|---|---|
| `heartbeat_degraded_seconds` | Int | `120` | Seconds of silence → `Degraded` status |
| `heartbeat_down_seconds` | Int | `300` | Seconds of silence → `Down` status |
| `cpu_warning_pct` | Float | `85` | CPU % threshold for WARNING alert |
| `cpu_critical_pct` | Float | `95` | CPU % threshold for CRITICAL alert |
| `ram_warning_pct` | Float | `85` | RAM % threshold |
| `ram_critical_pct` | Float | `95` | RAM % threshold |
| `disk_warning_pct` | Float | `80` | Disk % threshold |
| `disk_critical_pct` | Float | `90` | Disk % threshold |
| `queue_warning_depth` | Int | `50` | Background job queue depth for WARNING |
| `queue_critical_depth` | Int | `200` | Queue depth for CRITICAL |
| `response_warning_ms` | Int | `2000` | HTTP response time threshold (WARNING) |
| `response_critical_ms` | Int | `5000` | HTTP response time threshold (CRITICAL) |
| `threshold_sustained_minutes` | Int | `5` | How long a threshold must be exceeded before alerting |

#### Section: Log Configuration

| Field | Type | Default | Notes |
|---|---|---|---|
| `log_retention_info_days` | Int | `30` | Days to retain INFO/DEBUG logs |
| `log_retention_error_days` | Int | `90` | Days to retain WARNING/ERROR/CRITICAL logs |
| `log_max_entries_per_push` | Int | `500` | Max log entries accepted per agent push |

#### Section: Alerting

| Field | Type | Default | Notes |
|---|---|---|---|
| `alert_dedup_window_minutes` | Int | `15` | Suppress duplicate alerts within this window |
| `digest_frequency` | Select | `Hourly` | Options: `Hourly` / `Every 6 Hours` / `Daily` |
| `weekly_digest_day` | Select | `Monday` | Day to send weekly summary |
| `weekly_digest_hour` | Int | `9` | Hour (in `default_timezone`) to send weekly summary |
| `whatsapp_enabled` | Check | `0` | Enable WhatsApp alerting via Twilio |
| `twilio_account_sid` | Data | | Twilio credentials (if WhatsApp enabled) |
| `twilio_auth_token` | Password | | Twilio credentials |
| `twilio_whatsapp_from` | Data | | Twilio sender number |
| `default_alert_recipients` | Small Text | | Comma-separated email addresses for alerts |

#### Section: Licensing

| Field | Type | Default | Notes |
|---|---|---|---|
| `license_grace_period_days` | Int | `14` | Days after expiry before hard suspension |
| `license_offline_tolerance_days` | Int | `7` | Days agent can validate offline |
| `min_agent_version` | Data | `1.0.0` | Minimum supported agent version |
| `recommended_agent_version` | Data | `1.0.0` | Latest recommended agent version |

#### Section: Billing

| Field | Type | Default | Notes |
|---|---|---|---|
| `payment_warning_days` | Int | `7` | Days overdue before WARNING alert |
| `payment_suspend_days` | Int | `14` | Days overdue before license suspension |
| `payment_escalation_days` | Int | `30` | Days overdue before escalation ticket |
| `default_currency` | Link → Currency | `USD` | Default billing currency |

#### Section: Rate Limiting

| Field | Type | Default | Notes |
|---|---|---|---|
| `heartbeat_rate_limit` | Int | `2` | Max heartbeats per server per minute |
| `logs_rate_limit` | Int | `1` | Max log pushes per server per 5 minutes |
| `usage_rate_limit` | Int | `2` | Max usage pushes per server per day |
| `backup_rate_limit` | Int | `2` | Max backup status pushes per server per day |
| `license_rate_limit` | Int | `5` | Max license validations per server per day |

#### Section: Security

| Field | Type | Default | Notes |
|---|---|---|---|
| `api_key_rotation_grace_hours` | Int | `1` | Hours both old and new API keys are valid during rotation |
| `request_timestamp_tolerance_seconds` | Int | `300` | Max clock drift before rejecting agent requests |
| `ip_whitelist_enabled` | Check | `0` | Whether to restrict agent endpoints to specific IPs |
| `ip_whitelist` | Small Text | | Comma-separated IP addresses (if enabled) |

---

## 3. Rate Limiting Implementation

### 3.1 How It Works

Rate limiting uses Redis counters per server per endpoint:

```python
def check_rate_limit(server_name: str, endpoint: str, limit: int, window_seconds: int) -> bool:
    """Returns True if request is within rate limit, False if exceeded."""
    key = f"pulse:ratelimit:{endpoint}:{server_name}"
    current = frappe.cache().get(key)
    
    if current and int(current) >= limit:
        return False
    
    pipe = frappe.cache().pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    pipe.execute()
    return True
```

### 3.2 Rate Limits by Endpoint

| Endpoint | Limit | Window | Configurable Via |
|---|---|---|---|
| `agent.heartbeat` | 2 requests | 60 seconds | `heartbeat_rate_limit` |
| `agent.logs` | 1 request | 300 seconds | `logs_rate_limit` |
| `agent.usage` | 2 requests | 86400 seconds | `usage_rate_limit` |
| `agent.backup_status` | 2 requests | 86400 seconds | `backup_rate_limit` |
| `agent.license_validate` | 5 requests | 86400 seconds | `license_rate_limit` |
| `agent.register` | 3 requests | 3600 seconds | Hardcoded |

### 3.3 Rate Limit Response

```json
HTTP 429 Too Many Requests
{
    "status": "error",
    "error_code": "RATE_LIMITED",
    "message": "Heartbeat rate limit exceeded. Max 2 per minute.",
    "retry_after": 30
}
```

---

## 4. Replay Attack Prevention

### 4.1 Timestamp Validation

Every agent request must include `X-Request-Timestamp` header (Unix seconds, UTC).

```python
def validate_request_timestamp(request):
    ts = int(request.headers.get("X-Request-Timestamp", 0))
    tolerance = get_pulse_config().request_timestamp_tolerance_seconds
    server_time = int(time.time())
    
    if abs(server_time - ts) > tolerance:
        frappe.throw(
            f"Request timestamp {ts} is {abs(server_time - ts)}s from server time",
            title="Invalid Timestamp",
            http_status_code=400
        )
```

### 4.2 Request ID Deduplication

Every request must include `X-Request-ID` header (UUID v4).

```python
def check_request_id(request_id: str):
    key = f"pulse:request_id:{request_id}"
    if frappe.cache().get(key):
        frappe.throw("Duplicate request", http_status_code=409)
    frappe.cache().set(key, "1", ex=600)  # 10 minute TTL
```

---

## 5. API Key Rotation Grace Period (GAP-15)

### 5.1 Dual-Key Rotation

When a Gatom admin regenerates an API key for a server:

1. New key generated → new hash stored in `api_key_hash`
2. Old hash moved to `api_key_hash_previous`
3. `api_key_rotation_at` set to `now()`
4. For the next `api_key_rotation_grace_hours` (default: 1 hour), BOTH keys are valid

```python
def authenticate_agent(api_key: str) -> PulseServer:
    key_hash = sha256(api_key)
    
    # Try current key
    server = frappe.get_value("Pulse Server", {"api_key_hash": key_hash})
    if server:
        return server
    
    # Try previous key (rotation grace period)
    server = frappe.get_value("Pulse Server", {"api_key_hash_previous": key_hash})
    if server:
        rotation_at = frappe.get_value("Pulse Server", server, "api_key_rotation_at")
        grace_hours = get_pulse_config().api_key_rotation_grace_hours
        if rotation_at and (now() - rotation_at).total_seconds() < grace_hours * 3600:
            return server  # Within grace period — accept old key
    
    frappe.throw("Invalid API key", http_status_code=401)
```

### 5.2 Additional Fields on Pulse Server (P01)

| Field | Type | Notes |
|---|---|---|
| `api_key_hash_previous` | Data | SHA-256 hash of the previous API key (for rotation grace) |
| `api_key_rotation_at` | Datetime | When the last key rotation occurred |

---

## 6. Timezone Policy

### 6.1 Storage

- **All timestamps in Pulse DocTypes**: stored as UTC
- **All timestamps from agent**: sent as UTC (ISO 8601 with `Z` suffix)
- **Heartbeat `X-Request-Timestamp`**: Unix epoch (inherently UTC)

### 6.2 Display

- **Pulse Dashboard (React)**: displays in `Pulse Configuration.default_timezone`
- **Agent scheduler jobs**: run in client server's local timezone (Frappe's `time_zone` from `site_config.json`)
- **Alert emails**: include both UTC and recipient's timezone

### 6.3 Clock Drift

- Agent clock drift > 300 seconds from Pulse server → request rejected (replay prevention)
- Agent includes system time in heartbeat payload for Pulse-side drift detection
- If drift detected consistently → create WARNING alert: "Server clock may be misconfigured"

---

## 7. Data Volume Estimates

### 7.1 Per Client Server

| Data Type | Volume/Day | Retention | Total at Retention |
|---|---|---|---|
| Heartbeats (Redis only) | 1,440 events | Real-time only | ~1 per server (latest) |
| Server Daily Summary | 1 record | 90 days | 90 records |
| Log entries | ~5,760 entries | 30/90 days | ~170K–520K entries |
| Pulse Alerts | ~5–20 records | Indefinite | Growing slowly |
| Usage Snapshots | 1/week | 12 months | 52 records |
| Backup Status | 1/day | 90 days | 90 records |
| License Logs | ~1/day | Indefinite | Growing slowly |

### 7.2 Fleet-Wide (10 Clients)

| Data Type | Total Records at Scale |
|---|---|
| Server Daily Summaries | ~900 |
| Log entries (30d INFO) | ~1.7M |
| Log entries (90d ERROR) | ~500K (if 10% are errors) |
| Usage Snapshots | ~520 |
| Backup Status Reports | ~900 |

### 7.3 MariaDB Capacity

At 10 clients, total data is well within MariaDB's comfort zone (~50 MB). At 50+ clients, consider:
- Partitioning `Pulse Log Entry` table by month
- More aggressive log retention (7d INFO, 30d ERROR)
- Archiving old log entries to compressed files

---

## 8. Pulse Self-Monitoring (GAP-19)

### 8.1 External Uptime Check

Pulse must be monitored by an external service since it cannot monitor itself:

**Recommended**: [UptimeRobot](https://uptimerobot.com) (free tier, 5-minute checks)
- Monitor URL: `{pulse_url}/api/method/gatom_pulse.api.health.ping`
- Alert: email + SMS when down

### 8.2 Health Check Endpoint

```python
@frappe.whitelist(allow_guest=True)
def ping():
    """Lightweight health check — no auth required."""
    return {
        "status": "ok",
        "version": __version__,
        "timestamp": now_utc().isoformat(),
        "active_servers": frappe.db.count("Pulse Server", {"status": ["!=", "Decommissioned"]}),
        "redis": frappe.cache().ping()
    }
```

### 8.3 Internal Scheduler Health

A daily scheduler job checks Pulse's own health:

```python
def pulse_self_check():
    """Daily — verify Pulse subsystems are healthy."""
    checks = {
        "redis": frappe.cache().ping(),
        "db": frappe.db.sql("SELECT 1"),
        "scheduler": frappe.is_scheduler_inactive() == False,
        "email": bool(frappe.conf.get("mail_server")),
    }
    if not all(checks.values()):
        # Can't use normal alerting (it may be broken)
        send_emergency_notification(f"Pulse self-check failed: {checks}")


def send_emergency_notification(message: str):
    """Send critical notification via direct SMTP + webhook fallback.
    
    Bypasses Frappe's email queue entirely — uses raw SMTP so that
    email subsystem failures don't prevent notification delivery.
    
    Resolves ERR-02: send_emergency_email was previously undefined.
    """
    admin_emails = frappe.get_all("User",
        filters={"role_profile_name": ["like", "%Pulse Admin%"], "enabled": 1},
        pluck="email")
    
    if not admin_emails:
        admin_emails = [frappe.conf.get("admin_email", "admin@gatom.com")]
    
    # Channel 1: Direct SMTP (bypass Frappe email queue)
    try:
        import smtplib
        from email.mime.text import MIMEText
        
        smtp_host = frappe.conf.get("mail_server")
        smtp_port = int(frappe.conf.get("mail_port", 587))
        smtp_user = frappe.conf.get("mail_login")
        smtp_pass = frappe.conf.get("mail_password")
        
        if smtp_host and smtp_user:
            msg = MIMEText(f"🚨 PULSE EMERGENCY\n\n{message}\n\nTimestamp: {now_utc()}")
            msg["Subject"] = "🚨 Pulse Self-Check FAILED"
            msg["From"] = smtp_user
            msg["To"] = ", ".join(admin_emails)
            
            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
            server.quit()
            
            frappe.logger("gatom_pulse").info("Emergency email sent via direct SMTP")
    except Exception as e:
        frappe.logger("gatom_pulse").error(f"Emergency SMTP failed: {e}")
    
    # Channel 2: Webhook fallback (e.g., UptimeRobot, PagerDuty, Slack)
    webhook_url = get_config().get("emergency_webhook_url")
    if webhook_url:
        try:
            import requests
            requests.post(webhook_url, json={
                "event": "pulse_self_check_failed",
                "message": message,
                "timestamp": now_utc().isoformat(),
                "source": "gatom_pulse"
            }, timeout=10)
            frappe.logger("gatom_pulse").info("Emergency webhook sent")
        except Exception as e:
            frappe.logger("gatom_pulse").error(f"Emergency webhook failed: {e}")
    
    # Channel 3: Local file (always succeeds — last resort)
    try:
        emergency_log = os.path.join(frappe.get_site_path(), "logs", "pulse_emergency.log")
        with open(emergency_log, "a") as f:
            f.write(f"\n[{now_utc()}] {message}\n")
    except Exception:
        pass
```

**Pulse Configuration — Emergency Fields**:

| Field | Type | Default | Notes |
|---|---|---|---|
| `emergency_webhook_url` | Data | (empty) | URL for webhook fallback (Slack, PagerDuty, UptimeRobot) |

**Acceptance Criteria**:
- [ ] Self-check failure → direct SMTP email bypassing Frappe queue
- [ ] If SMTP fails → webhook notification sent
- [ ] If webhook fails → emergency written to local `logs/pulse_emergency.log`
- [ ] All three channels are attempted independently (one failure doesn't block others)
- [ ] `emergency_webhook_url` configurable in Pulse Configuration

## 9. Log Retention Automation (GAP-13)

### 9.1 Scheduler Job: `purge_old_logs`

Runs daily at 00:30 AM UTC (staggered from P02's 01:00 daily aggregator):

> ⚠️ **Full scheduler timeline**: [[../API Contract#4. Pulse Scheduler Timeline|API Contract §4]]

```python
def purge_old_logs():
    """Delete log entries past retention threshold."""
    config = get_pulse_config()
    
    # Purge INFO/DEBUG older than retention
    cutoff_info = add_days(today(), -config.log_retention_info_days)
    frappe.db.delete("Pulse Log Entry", {
        "level": ["in", ["DEBUG", "INFO"]],
        "timestamp": ["<", cutoff_info]
    })
    
    # Purge WARNING/ERROR/CRITICAL older than error retention
    cutoff_error = add_days(today(), -config.log_retention_error_days)
    frappe.db.delete("Pulse Log Entry", {
        "level": ["in", ["WARNING", "ERROR", "CRITICAL"]],
        "timestamp": ["<", cutoff_error]
    })
    
    frappe.db.commit()
    log_info(f"Log purge complete. INFO cutoff: {cutoff_info}, ERROR cutoff: {cutoff_error}")
```

---

## 10. IP Whitelisting (GAP-17)

### 10.1 Nginx-Level Configuration

For production deployments, add to the Nginx site config:

```nginx
# Pulse agent endpoints — restrict to known client IPs
location /api/method/gatom_pulse.api.agent {
    # Allow known client server IPs
    allow 203.0.113.10;    # Client A
    allow 198.51.100.20;   # Client B
    allow 192.0.2.30;      # Client C
    deny all;
    
    proxy_pass http://frappe-bench;
}
```

### 10.2 Application-Level Fallback

If `ip_whitelist_enabled` is set in Pulse Configuration:

```python
def check_ip_whitelist(request):
    config = get_pulse_config()
    if not config.ip_whitelist_enabled:
        return
    
    allowed_ips = [ip.strip() for ip in config.ip_whitelist.split(",")]
    client_ip = frappe.get_request_header("X-Forwarded-For", "").split(",")[0].strip()
    
    if client_ip not in allowed_ips:
        frappe.throw(f"IP {client_ip} not in whitelist", http_status_code=403)
```

---

## 11. Deployment & Migration Strategy *(resolves OPS-01)*

### 11.1 Initial Deployment

Both `gatom_pulse` and `gatom_agent` follow standard Frappe app deployment:

```bash
# Pulse (Gatom's ERPNext server)
bench get-app gatom_pulse <repo_url>
bench --site erp.gatom.com install-app gatom_pulse
bench migrate
bench restart

# Agent (each client server)
bench get-app gatom_agent <repo_url>
bench --site <site> install-app gatom_agent
bench migrate
bench restart
```

### 11.2 Schema Migration Rules

When adding new fields to existing DocTypes after initial deployment:

| Scenario | Approach |
|---|---|
| New optional field on existing DocType | `bench migrate` handles this automatically — Frappe adds columns with `NULL` default |
| New required field on existing DocType | Add with `default` value in DocType definition, then `bench migrate` |
| New field on `Pulse Configuration` (singleton) | `bench migrate` adds it; singleton auto-populates from `default` in field definition |
| Backfill existing records | Create a one-time `patch` in `patches.txt` that runs during `bench migrate` |
| Rename field | Use Frappe's `rename_field` patch pattern (preserves data) |
| Delete field | Remove from DocType JSON → `bench migrate` drops column |

**Patching Example** (backfill `week_start` on existing `Usage Snapshot` records):

```python
# In gatom_pulse/patches/v1_1/backfill_week_start.py
import frappe
from frappe.utils import get_first_day_of_week

def execute():
    """One-time backfill for Usage Snapshot.week_start field."""
    snapshots = frappe.get_all("Usage Snapshot",
        filters={"week_start": ["is", "not set"]},
        fields=["name", "collected_at"])
    
    for snap in snapshots:
        week_start = get_first_day_of_week(snap.collected_at)
        frappe.db.set_value("Usage Snapshot", snap.name, "week_start", week_start)
    
    frappe.db.commit()
```

### 11.3 Version Upgrade Process

```
1. git pull (update code)           → bench update --pull
2. Run migrations                   → bench migrate
3. Run patches (auto-discovered)    → (included in bench migrate)
4. Restart workers                  → bench restart
5. Verify                           → check /api/method/gatom_pulse.api.health.ping
```

### 11.4 Agent Version Compatibility

When Pulse adds a new feature that requires agent changes:

| Agent Version | Required Pulse Version | Migration Notes |
|---|---|---|
| 1.0.x | 1.0.x | Initial release |
| 1.1.x | 1.1.x+ | New fields in heartbeat (soft optional — old agents still work) |
| 2.0.x | 2.0.x+ | Breaking change — set `min_agent_version = 2.0.0` in Pulse Configuration |

---

## 12. Disaster Recovery *(resolves OPS-02)*

### 12.1 RTO/RPO Targets

| Metric | Target | Notes |
|---|---|---|
| **Recovery Time Objective (RTO)** | 4 hours | Pulse restored and accepting heartbeats |
| **Recovery Point Objective (RPO)** | 24 hours | At most 1 day of lost data (log entries, heartbeat metrics) |
| **Agent Queue Tolerance** | 24 hours | Agents queue data locally for 24h; data older than 24h is dropped |

### 12.2 What Happens When Pulse Is Down

| Component | Behavior During Outage | Data Loss Risk |
|---|---|---|
| Agent heartbeats | Queued locally (24h max) | None if restored within 24h |
| Agent log pushes | Queued locally (24h max) | Log entries > 24h old are dropped |
| Agent license check | Offline fallback (7 days) | None — JWT verified locally |
| Agent usage push | Queued (24h max, only 1/day) | Low — next day's push has fresh data |
| Dashboard | Unavailable | No data loss — reads from DB |
| Alerts | Not generated | Missed during outage window |
| Billing | No overdue checks | Checked on next cycle after recovery |

### 12.3 Pulse Backup Strategy

| What | How | Frequency | Retention |
|---|---|---|---|
| MariaDB database | `bench backup --with-files` | Daily at 1 AM UTC | 30 days |
| `site_config.json` | Included in bench backup | Daily | 30 days |
| Private files | Included in bench backup | Daily | 30 days |
| RSA private key | Stored in env var — backed up separately | On change | Indefinitely |
| Redis data | NOT backed up (ephemeral by design) | — | — |

### 12.4 Recovery Runbook

```
1. Restore MariaDB from latest backup
   → bench --site erp.gatom.com restore <backup.sql.gz>

2. Restore private files
   → extract backup files to site/private/

3. Verify site_config.json
   → ensure mail_server, redis_*, db_* are correct

4. Set RSA private key
   → export PULSE_LICENSE_PRIVATE_KEY="$(cat gatom_license_private_v1.pem)"

5. Start services
   → bench restart
   → bench scheduler enable

6. Verify health
   → curl https://erp.gatom.com/api/method/gatom_pulse.api.health.ping

7. Monitor agent reconnection
   → Watch Fleet Overview — agents will drain their queues automatically
   → Expect 10-30 minutes for all agents to reconnect

8. Check for missed alerts
   → Review Audit Log for events during outage window
   → Manually run: bench execute gatom_pulse.pulse.jobs.check_overdue_payments
```

### 12.5 Extended Outage (> 24 Hours)

If Pulse is down for more than 24 hours:

1. **Agent queues overflow** — oldest entries are dropped (24h TTL)
2. **License offline tolerance** — agents have 7 days of offline validation
3. **Dashboard data gap** — `Server Daily Summary` will have missing days (no heartbeat data to aggregate)

**Post-recovery**: Run `bench execute gatom_pulse.pulse.jobs.aggregate_daily_summaries` with explicit date parameters to fill gaps where possible from any drained heartbeat data.

---

## 🔗 Related

- [[../Pulse Overview|🏗️ Pulse Overview]]
- [[../Pulse MOC|🫀 Pulse MOC]]
- [[agent-functional|🤖 A08 — Transport & Resilience (Agent side)]]

