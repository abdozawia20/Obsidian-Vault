---
tags: [gatom, pulse, agent, a02, heartbeat, health-monitoring, functional]
---

# A02 — Heartbeat Collection: Functional Analysis

> **Component**: `gatom_agent`
> **Domain**: A02 — Heartbeat Collection
> **Pulse Counterpart**: [[functional|P02 — Server Health Monitoring]]
> **File**: `collectors/heartbeat.py`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

The heartbeat is the most critical agent function. Every 60 seconds, the agent collects system health metrics (CPU, RAM, Disk, MariaDB, Redis, background jobs) and pushes them to Pulse. If Pulse stops receiving heartbeats, it transitions the server to `Degraded` → `Down` and triggers alerts/tickets.

The heartbeat is also the vehicle for Pulse to send instructions back to the agent (e.g., new release notifications).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| A02-001 | Agent must collect and push system metrics every 60 seconds |
| A02-002 | Metrics must include: CPU %, RAM %, Disk %, MariaDB status, Redis status, RQ queue depth, HTTP response time |
| A02-003 | If any metric exceeds threshold, agent must flag it in the payload (threshold evaluation is Pulse-side) |
| A02-004 | Heartbeat payload must include agent queue status so Pulse knows if data was queued offline |
| A02-005 | Agent must process Pulse's heartbeat response for piggybacked instructions (release notifications) |
| A02-006 | Heartbeat must not take more than 5 seconds to collect + send (timeout budget) |

---

## 3. Metrics Collection

### 3.1 System Metrics (`utils/system_metrics.py`)

| Metric | Collection Method | Unit |
|---|---|---|
| `cpu_pct` | `psutil.cpu_percent(interval=1)` | % |
| `ram_pct` | `psutil.virtual_memory().percent` | % |
| `ram_used_mb` | `psutil.virtual_memory().used / (1024**2)` | MB |
| `ram_total_mb` | `psutil.virtual_memory().total / (1024**2)` | MB |
| `disk_pct` | `psutil.disk_usage('/').percent` | % |
| `disk_used_gb` | `psutil.disk_usage('/').used / (1024**3)` | GB |
| `disk_total_gb` | `psutil.disk_usage('/').total / (1024**3)` | GB |
| `disk_free_gb` | `psutil.disk_usage('/').free / (1024**3)` | GB |
| `load_avg_1m` | `os.getloadavg()[0]` | float |

### 3.2 Service Metrics

| Metric | Collection Method | Unit |
|---|---|---|
| `mariadb_up` | `frappe.db.sql("SELECT 1")` — if no error, True | bool |
| `redis_up` | `frappe.cache().ping()` | bool |
| `rq_queue_depth` | `len(frappe.utils.scheduler.get_jobs())` | int |
| `rq_failed_jobs` | Count of failed jobs in RQ | int |

### 3.3 Application Metrics

| Metric | Collection Method | Unit |
|---|---|---|
| `response_time_ms` | Time a `GET /api/method/ping` to self | ms |
| `http_status` | HTTP status code from self-ping | int |
| `active_workers` | Count of running Gunicorn workers | int |

---

## 4. Heartbeat Payload

> ⚠️ **Canonical payload defined in**: [[../../API Contract#2.2 Heartbeat|API Contract §2.2]]
> All field names below use the canonical names from the API Contract.

The heartbeat payload includes three sections:

1. **`metrics`** — system health data (see §3 above)
2. **`queue_status`** — agent's local Redis queue state (tells Pulse if data was queued offline)
3. **`agent_health`** — agent's own operational status (tells Pulse if subsystems are healthy)
```

---

## 5. Request & Response

### 5.1 Request

```
POST /api/method/gatom_pulse.api.agent.heartbeat
Authorization: Bearer {pulse_api_key}
X-Agent-Version: 1.0.0
X-Request-Timestamp: 1749720000
X-Request-ID: {uuid4}
```

### 5.2 Pulse Response (Success)

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

### 5.3 Processing the Response

The agent processes three things from the heartbeat response:
1. **Commands** (decommission, key rotation) — always checked first
2. **Releases** — notification + acknowledgment
3. **Server time** — clock drift detection

```python
def process_heartbeat_response(response):
    # 1. Process commands (highest priority)
    commands = response.get("commands", {})
    
    if commands.get("decommission"):
        # Server has been decommissioned in Pulse — shut down agent
        frappe.logger("gatom_agent").critical(
            "Server decommissioned by Pulse. Disabling agent."
        )
        disable_agent()  # Sets pulse_agent_disabled = true, stops collectors
        return  # Don't process anything else
    
    if commands.get("rotate_key"):
        # Pulse is telling us to use a new API key
        process_rotate_key(commands["rotate_key"])
    
    # 2. Process releases
    releases = response.get("releases", [])
    for release in releases:
        # Show notification to System Manager
        frappe.get_doc({
            "doctype": "Notification Log",
            "subject": f"🆕 Update Available: v{release['version']} ({release['severity']})",
            "email_content": release["changelog"],
            "for_user": get_system_manager(),
            "type": "Alert",
        }).insert(ignore_permissions=True)
        
        # Acknowledge receipt to Pulse
        pulse_client.post("/release_ack", {
            "server_id": get_server_id(),
            "release_id": release["release_id"],
            "acknowledged": True,
            "current_version": get_current_version(release["affected_apps"][0])
        })
    
    # 3. Check clock drift
    server_time = response.get("server_time")
    if server_time:
        drift = abs(time.time() - parse_iso(server_time).timestamp())
        if drift > 60:
            frappe.logger("gatom_agent").warning(
                f"Clock drift detected: {drift:.0f}s from Pulse server"
            )

def process_rotate_key(new_key):
    """Handle key rotation command from Pulse (resolves EP-04)."""
    frappe.conf.pulse_api_key = new_key
    update_site_config("pulse_api_key", new_key)
    pulse_client.api_key = new_key
    
    # Confirm new key works
    pulse_client.post("heartbeat", collect_heartbeat())
    frappe.logger("gatom_agent").info("API key rotated successfully via Pulse command")
```

> ⚠️ **Full decommission spec**: [[../../API Contract#7.6 Server Decommission via Heartbeat|API Contract §7.6]]
> ⚠️ **Full re-keying spec**: [[../../API Contract#7.7 Automated Re-Keying via Heartbeat|API Contract §7.7]]

---

## 6. Error Handling

| Scenario | Agent Action |
|---|---|
| Metric collection fails (e.g., `psutil` error) | Send heartbeat with `null` for that metric. Log WARNING. |
| Pulse returns 200 | Success. Reset retry counter. Trigger queue drain. |
| Pulse returns 429 | Rate limited. Skip this heartbeat cycle. Log WARNING. |
| Pulse returns 401/403 | API key invalid. Disable agent. Log CRITICAL. |
| Pulse returns 5xx / timeout | Queue heartbeat locally (see [[../P00 - Configuration/agent-functional\|A08]]). |

---

## 7. Timing Budget

The heartbeat must complete within 5 seconds total:

| Step | Budget |
|---|---|
| Collect system metrics (psutil) | 1.5s (CPU uses `interval=1`) |
| Collect service metrics (DB + Redis ping) | 0.5s |
| Collect app metrics (self-ping) | 1.0s |
| HTTP POST to Pulse | 2.0s (timeout) |
| **Total** | **5.0s** |

If collection + send exceeds 5s, the heartbeat is abandoned for this cycle (not queued).

---

## 8. Acceptance Criteria

- [ ] Heartbeat fires every 60 seconds via Frappe scheduler
- [ ] All 11 metrics collected correctly
- [ ] Payload includes `queue_status` showing pending queued items
- [ ] Heartbeat response containing `releases` → creates Notification Log
- [ ] Failed metric collection → heartbeat still sent with `null` for that metric
- [ ] Pulse unreachable → heartbeat queued locally (A08)
- [ ] Heartbeat completes within 5 seconds or is abandoned

---

## 🔗 Related

- [[../Agent Overview|🤖 Agent Overview]]
- [[functional|P02 — Server Health Monitoring (Pulse side)]]
- [[../P00 - Configuration/agent-functional|A08 — Transport & Resilience]]
