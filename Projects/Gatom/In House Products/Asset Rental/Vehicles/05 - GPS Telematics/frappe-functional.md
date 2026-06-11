# GPS Telematics — Frappe: Functional Document

> **Product**: Asset Rental Platform — Vehicle Variant
> **Domain**: GPS Telematics
> **Module**: `rental_vehicles` — Live Tracking, Geofence & Speed Alerts

---

## 1. Purpose & Scope

Defines GPS event ingestion, live position streaming, speed/geofence alerting, data retention, and the raw SQL storage architecture. Entirely Desk/Fleet Manager-managed — customers never see GPS data (except estimated mileage via the Mileage domain).

---

## 2. Business Requirements

| # | Requirement |
|---|---|
| VR-040 | GPS-equipped vehicles must stream live position updates |
| VR-041 | Raw GPS events stored: `device_id`, `latitude`, `longitude`, `speed_kmh`, `heading`, `timestamp` |
| VR-042 | Speed threshold alert to Fleet Manager |
| VR-043 | Geofence violations loggable |
| VR-044 | Live positions visible to Fleet Manager only |
| VR-045 | GPS events ingested via webhook from GPS provider |
| VR-046 | **Schema**: raw event table **partitioned by month** for time-series performance |
| VR-047 | **Retention**: Raw events older than **90 days** aggregated into `gps_daily_summary` (vehicle, date, total_km, max_speed, avg_speed, start/end position) then purged. Cron runs daily at **2 AM**. |
| VR-048 | **Live map protocol**: **Frappe Socketio** for real-time push; **10-second polling fallback** for non-WebSocket environments |

---

## 3. Security Requirements

| Requirement | Description |
|---|---|
| **HMAC webhook** | Validate on every inbound event. On failure: log to `GPS Webhook Failure Log`, return 401, alert Fleet Manager if >5 failures/hour. |
| **Live map access** | Fleet Manager role only — not exposed to customer-facing API |

---

## 4. Integration Points

| System | Direction | Purpose |
|---|---|---|
| GPS provider (Teltonika, Queclink, etc.) | Inbound webhook | Raw position and speed events |
| Frappe Socketio | Internal | Live map real-time push |
