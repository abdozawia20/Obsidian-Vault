---
tags: [gatom, pulse, agent, a08, transport, resilience, retry, queue, functional]
---

# A08 — Transport & Resilience: Functional Analysis

> **Component**: `gatom_agent`
> **Domain**: A08 — Transport & Resilience
> **Pulse Counterpart**: [[functional|P00 — Configuration & Cross-Cutting]]
> **Files**: `transport/pulse_client.py`, `transport/queue.py`, `transport/request_signer.py`
> **Audience**: Gatom developers

---

## 1. Purpose & Scope

This domain defines how the agent communicates with Pulse: the HTTP client, retry logic, offline queue, request signing (replay prevention), and error handling contracts. Every other agent domain (A01–A07) depends on this transport layer — they all call `pulse_client.post()` to send data.

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| A08-001 | All Pulse communication must use HTTPS with valid SSL certificates |
| A08-002 | All requests must include `Authorization: Bearer {api_key}` header |
| A08-003 | All requests must include `X-Request-Timestamp` (Unix epoch, UTC) for replay prevention |
| A08-004 | All requests must include `X-Request-ID` (UUID v4) for idempotency |
| A08-005 | Request timeout must be configurable (default: 10 seconds) |
| A08-006 | Failed requests must be queued locally in Redis for retry |
| A08-007 | Queue must have size limits to prevent Redis memory exhaustion |
| A08-008 | Queued data older than 24 hours must be dropped (stale data has no value) |
| A08-009 | On first successful request after failure, agent must drain the queue |
| A08-010 | Agent must handle every Pulse HTTP status code deterministically |

---

## 3. HTTP Client (`pulse_client.py`)

### 3.1 Configuration

```python
class PulseClient:
    TIMEOUT = 10             # seconds per request
    MAX_RETRIES = 3          # retries per request attempt (with backoff)
    BACKOFF_BASE = 2         # exponential backoff: 2s, 4s, 8s
    MAX_BACKOFF = 30         # cap at 30 seconds
```

### 3.2 Request Format

Every request to Pulse follows this format:

```python
def post(self, endpoint: str, payload: dict) -> Response:
    url = f"{self.pulse_url}/api/method/gatom_pulse.api.agent.{endpoint}"
    
    headers = {
        "Authorization": f"Bearer {self.api_key}",
        "Content-Type": "application/json",
        "X-Agent-Version": __version__,
        "X-Request-Timestamp": str(int(time.time())),
        "X-Request-ID": str(uuid.uuid4()),
    }
    
    for attempt in range(self.MAX_RETRIES):
        try:
            response = requests.post(url, json=payload, headers=headers,
                                     timeout=self.TIMEOUT, verify=True)
            return self._handle_response(response, endpoint, payload)
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt < self.MAX_RETRIES - 1:
                sleep(min(self.BACKOFF_BASE ** (attempt + 1), self.MAX_BACKOFF))
            else:
                self._queue_for_retry(endpoint, payload)
                raise PulseUnreachableError(str(e))
```

---

## 4. Error Handling Contract

### 4.1 Response Handling

| HTTP Status | Error Code | Agent Action |
|---|---|---|
| `200` | — | Success. Clear from retry queue. Trigger queue drain. |
| `400` | `INVALID_PAYLOAD` | Log ERROR. **Do NOT retry** (fix required). Drop from queue. |
| `400` | `INVALID_TIMESTAMP` | Log ERROR. Check system clock. Do NOT retry. |
| `401` | `INVALID_API_KEY` | Log CRITICAL. **Disable agent** (`pulse_agent_disabled = true`). |
| `403` | `SERVER_DECOMMISSIONED` | Log CRITICAL. **Disable agent**. |
| `409` | `DUPLICATE_REQUEST` | Log DEBUG. Ignore (idempotency working correctly). |
| `426` | `UPGRADE_REQUIRED` | Log CRITICAL: "Agent version too old." Continue operating. |
| `429` | `RATE_LIMITED` | Log WARNING. Retry after `retry_after` seconds. |
| `500` | `INTERNAL_ERROR` | Log WARNING. **Queue for retry** with backoff. |
| `502/503` | — | Log WARNING. **Queue for retry** with backoff. |
| Connection timeout | — | Log WARNING. **Queue for retry** with backoff. |
| DNS failure | — | Log WARNING. **Queue for retry** with backoff. |

### 4.2 Standard Error Response from Pulse

```json
{
    "status": "error",
    "error_code": "RATE_LIMITED",
    "message": "Heartbeat rate limit exceeded. Max 2 per minute.",
    "retry_after": 30
}
```

The agent always checks `response.json().get("error_code")` to determine specific handling.

---

## 5. Offline Queue (`queue.py`)

### 5.1 Design

When Pulse is unreachable (5xx, timeout, DNS failure), data is queued in the client server's own Redis:

```python
# Redis key structure
pulse:queue:{endpoint}    # List — FIFO queue per endpoint
pulse:queue:meta          # Hash — queue metadata (sizes, timestamps)
```

### 5.2 Queue Entry Format

```json
{
    "endpoint": "heartbeat",
    "payload": { ... },
    "queued_at": "2026-06-12T06:30:00Z",
    "attempt_count": 0
}
```

### 5.3 Queue Limits

| Parameter | Value | Rationale |
|---|---|---|
| Max entries per endpoint | 500 | Prevents Redis memory exhaustion |
| Max total queue size | 2,000 entries | Hard cap (~10 MB estimated) |
| Max entry age | 24 hours | Stale heartbeats/logs have no value |
| Queue persistence | Redis RDB snapshots | Survives `bench restart` |

### 5.4 Queue Overflow

When a queue reaches its limit:
- Oldest entries are dropped first (FIFO)
- A warning is logged: "Queue overflow: dropped {N} oldest {endpoint} entries"

---

## 6. Queue Drain Strategy

### 6.1 Trigger

Queue drain is triggered after **any successful Pulse request** (200 response):

```python
def on_successful_request(self):
    """Called after any 200 response from Pulse."""
    if not self._draining:
        self._draining = True
        try:
            self.drain_queue()
        finally:
            self._draining = False
```

### 6.2 Drain Logic

```python
def drain_queue(self):
    """Process queued entries oldest-first. Stop on first failure."""
    drain_summary = {}
    
    for endpoint in QUEUED_ENDPOINTS:
        stats = {"drained": 0, "dropped_stale": 0, "failed": 0, "remaining": 0}
        key = f"pulse:queue:{endpoint}"
        
        while True:
            # Peek at oldest entry (don't pop yet)
            raw = frappe.cache().lindex(key, 0)
            if not raw:
                break
            
            entry = json.loads(raw)
            
            # Drop stale entries
            if entry_age(entry) > timedelta(hours=24):
                frappe.cache().lpop(key)
                stats["dropped_stale"] += 1
                continue
            
            # Try to send
            try:
                response = self._raw_post(endpoint, entry["payload"])
                if response.status_code == 200:
                    frappe.cache().lpop(key)  # Success — remove
                    stats["drained"] += 1
                elif response.status_code in (400, 401, 403):
                    frappe.cache().lpop(key)  # Non-retryable — drop
                    stats["drained"] += 1
                else:
                    stats["failed"] += 1
                    break  # Pulse went offline again — stop draining
            except (requests.ConnectionError, requests.Timeout):
                stats["failed"] += 1
                break  # Network down — stop draining
        
        stats["remaining"] = frappe.cache().llen(key)
        drain_summary[endpoint] = stats
    
    # Log drain summary (resolves LOG-05)
    total_drained = sum(s["drained"] for s in drain_summary.values())
    total_stale = sum(s["dropped_stale"] for s in drain_summary.values())
    
    if total_drained > 0 or total_stale > 0:
        frappe.logger("gatom_agent").info(
            f"Queue drain: {total_drained} sent, {total_stale} stale dropped",
            drain_summary
        )
    if total_stale > 0:
        frappe.logger("gatom_agent").warning(
            f"Dropped {total_stale} stale queue entries (>24h old)"
        )
```

### 6.3 Queue Status Reporting

Every heartbeat includes the current queue status:

```json
{
    "queue_status": {
        "pending_heartbeats": 45,
        "pending_logs": 12,
        "pending_other": 3,
        "oldest_queued_at": "2026-06-12T06:30:00Z"
    }
}
```

This tells Pulse "I was offline for a while — here's how much data I have queued."

---

## 7. Replay Prevention (`request_signer.py`)

### 7.1 What It Does

Every outbound request includes:
- **`X-Request-Timestamp`**: Unix epoch seconds (UTC) — Pulse rejects requests > 300 seconds from its own clock
- **`X-Request-ID`**: UUID v4 — Pulse deduplicates requests with the same ID (10-minute TTL)

### 7.2 Why It Matters

Without replay prevention:
- A network attacker who captures a valid heartbeat request could replay it to forge server status
- A retried request could be processed twice (duplicate log entries, duplicate heartbeats)

### 7.3 Implementation

```python
def sign_request(headers: dict) -> dict:
    """Add replay prevention headers to outbound request."""
    headers["X-Request-Timestamp"] = str(int(time.time()))
    headers["X-Request-ID"] = str(uuid.uuid4())
    return headers
```

---

## 8. Acceptance Criteria

- [ ] All requests use HTTPS with SSL verification enabled
- [ ] All requests include `Authorization`, `X-Agent-Version`, `X-Request-Timestamp`, `X-Request-ID`
- [ ] Timeout set to 10 seconds per request
- [ ] 3 retries with exponential backoff (2s, 4s, 8s) before queuing
- [ ] Every HTTP status code handled per §4.1 table
- [ ] 401/403 → agent disables itself
- [ ] 5xx / timeout / DNS failure → data queued in Redis
- [ ] Queue limited to 500 entries per endpoint, 2000 total
- [ ] Entries older than 24h dropped on drain
- [ ] Drain triggered after any successful request
- [ ] Drain stops on first failure (doesn't exhaust retry budget)
- [ ] Every drain operation produces a summary log (entries drained, stale dropped, failed, remaining)
- [ ] Stale drops logged as WARNING
- [ ] Queue status included in heartbeat payload

---

## 🔗 Related

- [[../Agent Overview|🤖 Agent Overview]]
- [[functional|P00 — Configuration & Cross-Cutting (Pulse side)]]
- [[../P02 - Server Health Monitoring/agent-functional|A02 — Heartbeat Collection (primary consumer)]]
