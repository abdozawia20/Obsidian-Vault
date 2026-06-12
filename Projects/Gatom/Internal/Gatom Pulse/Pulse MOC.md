---
tags: [moc, gatom, internal, pulse, monitoring, licensing]
---

# 🫀 Gatom Pulse — Map of Content

> **Gatom Pulse** is the internal operations command center for managing all deployed client servers. Monitoring, licensing, billing, tickets, logs, analytics — one platform.

---

## 📋 Overview

> Architecture, features, tech stack, and user personas in a single reference doc:

- [[Pulse Overview|🏗️ Pulse Overview]]

---

## 🤖 Agent Reference

> `gatom_agent` — lightweight Frappe app installed on every client server. Agent domain functional specs live as `agent-functional.md` alongside their Pulse counterparts in each domain folder.

- [[Agent Overview|🤖 Agent Overview]] — Installation, file structure, versioning, self-diagnostics, pre-deployment mode

---

## 📜 Cross-Cutting References

> Single source of truth for every HTTP endpoint, canonical payload, scheduler timeline, and audit trail:

- [[API Contract|📜 API Contract]] — All endpoints + payloads + logging + scheduler + integration fixes

> [!TIP]
> Domain docs reference the API Contract for payload definitions — payloads are not duplicated across docs.

---

## 📁 Platform Domains

> Each domain with an agent counterpart has **two functional docs** in the same folder:
> - `functional.md` — Pulse server-side behavior
> - `agent-functional.md` — Agent client-side behavior

### P00 — Configuration & Cross-Cutting Concerns
> Pulse Configuration singleton, rate limiting, replay prevention, timezone policy, self-monitoring

- [[P00 - Configuration/functional|📄 Pulse Functional]] · [[P00 - Configuration/agent-functional|🤖 Agent: Transport & Resilience (A08)]]

---

### P01 — Client & Server Registry
> Client records, server enrollment, API key management, ERPNext Customer sync, fleet inventory

- [[P01 - Client & Server Registry/functional|📄 Pulse Functional]] · [[P01 - Client & Server Registry/agent-functional|🤖 Agent: Registration (A01)]]

---

### P02 — Server Health Monitoring
> Heartbeat ingestion, uptime tracking, resource thresholds, status state machine

- [[P02 - Server Health Monitoring/functional|📄 Pulse Functional]] · [[P02 - Server Health Monitoring/agent-functional|🤖 Agent: Heartbeat Collection (A02)]]

---

### P03 — Log Aggregation & Viewer
> Remote log storage, structured parsing, retention policy, live streaming

- [[P03 - Log Aggregation/functional|📄 Pulse Functional]] · [[P03 - Log Aggregation/agent-functional|🤖 Agent: Log Collection & Sanitization (A03)]]

---

### P04 — Error Tracking & Deduplication
> Error issue lifecycle, regression detection, cross-fleet analysis

- [[P04 - Error Tracking/functional|📄 Pulse Functional]] · [[P04 - Error Tracking/agent-functional|🤖 Agent: Error Fingerprinting (A04)]]

---

### P05 — Alerting & Notifications
> Multi-channel alerts, escalation rules, per-client configuration, digest mode

- [[P05 - Alerting/functional|📄 Functional Analysis]]

---

### P06 — Ticket System
> Incident, support, and change request tracking with SLA measurement

- [[P06 - Tickets/functional|📄 Functional Analysis]]

---

### P07 — Licensing Engine
> RSA-signed JWT license issuance, validation, revocation, and audit trail

- [[P07 - Licensing/functional|📄 Pulse Functional]] · [[P07 - Licensing/agent-functional|🤖 Agent: License Validation (A05)]]

---

### P08 — Billing & Subscriptions
> Subscription lifecycle, payment tracking, revenue reporting, overdue escalation

- [[P08 - Billing/functional|📄 Functional Analysis]]

---

### P09 — Usage Analytics
> Client usage metrics, tier compliance, feature adoption, engagement scoring

- [[P09 - Usage Analytics/functional|📄 Pulse Functional]] · [[P09 - Usage Analytics/agent-functional|🤖 Agent: Usage Collection (A06)]]

---

### P10 — Releases & Backup Monitoring
> Version management, changelog distribution, backup health verification

- [[P10 - Releases & Backups/functional|📄 Pulse Functional]] · [[P10 - Releases & Backups/agent-functional|🤖 Agent: Backup Checking (A07)]]

---

## 📊 Domain ↔ Agent Mapping (Quick Reference)

| Pulse Domain | Agent Domain | Agent Doc |
|---|---|---|
| P00 — Configuration | A08 — Transport & Resilience | [[P00 - Configuration/agent-functional\|agent-functional.md]] |
| P01 — Client Registry | A01 — Registration | [[P01 - Client & Server Registry/agent-functional\|agent-functional.md]] |
| P02 — Health Monitoring | A02 — Heartbeat Collection | [[P02 - Server Health Monitoring/agent-functional\|agent-functional.md]] |
| P03 — Log Aggregation | A03 — Log Collection | [[P03 - Log Aggregation/agent-functional\|agent-functional.md]] |
| P04 — Error Tracking | A04 — Error Fingerprinting | [[P04 - Error Tracking/agent-functional\|agent-functional.md]] |
| P05 — Alerting | *(no agent counterpart)* | — |
| P06 — Tickets | *(no agent counterpart)* | — |
| P07 — Licensing | A05 — License Validation | [[P07 - Licensing/agent-functional\|agent-functional.md]] |
| P08 — Billing | *(no agent counterpart)* | — |
| P09 — Usage Analytics | A06 — Usage Collection | [[P09 - Usage Analytics/agent-functional\|agent-functional.md]] |
| P10 — Releases & Backups | A07 — Backup Checking | [[P10 - Releases & Backups/agent-functional\|agent-functional.md]] |

---

## 🔗 Related

- [[../../Gatom MOC|🗺 Gatom MOC]]
- [[../../In House Products/In House Products MOC|📦 In House Products]]
