# Domain 07 — Notifications & Escalation: Implementation Plan

> **Variant**: Base
> **Domain**: Notifications & Escalation
> **Sequence**: 7 of 8
> **Depends on**: Domain 01 (config + FCM setup), all other domains (notification triggers)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Unified notification pipeline: reminder scheduler, escalation engine, multi-channel dispatch (email, push, WhatsApp), notification log, and Flutter notification center.

---

## 2. Frappe — `Rental Notification Log` DocType

### 2.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory), D01-5.2 (role permissions)

| Field | Type | Notes |
|---|---|---|
| `notification_type` | Select | `Payment Reminder`, `Payment Received`, `Invoice Created`, `Renewal Alert`, `Contract Expired`, `KYC Update`, `Escalation`, `Booking Status` |
| `reference_doctype` | Data | e.g., `Rental Agreement`, `Sales Invoice` |
| `reference_name` | Data | e.g., agreement/invoice name |
| `customer` | Link → Customer | Recipient |
| `subject` | Data | Short summary line |
| `body` | Text | Full notification content |
| `channels_used` | Data | e.g., "email,push" |
| `read` | Check | Default 0 |
| `sent_at` | Datetime | |
| `delivery_status` | Select | `Sent`, `Failed`, `Partial` |
| `failure_reason` | Text | |

**Acceptance Criteria**:
- [ ] DocType exists in Frappe Desk
- [ ] `notification_type` includes all 8 listed types
- [ ] `read` defaults to 0
- [ ] `delivery_status` defaults to `Sent`
- [ ] `failure_reason` is populated when `delivery_status = Failed`
- [ ] Read-only for all roles except System Manager (logs are immutable)
- [ ] Customer can view their own notifications via portal/API

---

## 3. Frappe — Reminder Dispatcher

### 3.1 `send_payment_reminders` Scheduler Job

> **Requires**: D01-2.3 (hooks.py), D01-3.1 (`renewal_alert_days`), ERPNext Sales Invoice

```python
def send_payment_reminders():
    upcoming = frappe.get_all("Sales Invoice", filters={
        "docstatus": 1,
        "outstanding_amount": [">", 0],
        "due_date": add_days(today(), 3),  # 3 days before due
    }, fields=["name", "customer", "grand_total", "due_date"])
    for inv in upcoming:
        send_notification(
            notification_type="Payment Reminder",
            customer=inv.customer,
            reference_doctype="Sales Invoice",
            reference_name=inv.name,
            subject=_("Payment due in 3 days"),
            body=_("Your invoice {0} of {1} is due on {2}").format(inv.name, inv.grand_total, inv.due_date),
            channels=["email", "push"]
        )
```

**Acceptance Criteria**:
- [ ] Invoice due in 3 days → customer receives payment reminder via email + push
- [ ] Invoice due in 10 days → NO reminder (not within 3-day window)
- [ ] Already-paid invoice (outstanding = 0) → no reminder
- [ ] Cancelled invoice → no reminder
- [ ] Notification logged in `Rental Notification Log` with `notification_type = Payment Reminder`
- [ ] Scheduler runs daily; multiple runs on same day don't send duplicate reminders (idempotent check by date+invoice)

---

### 3.2 `check_contract_renewals` Scheduler Job

> **Requires**: D01-3.1 (`renewal_alert_days` = "90,60,30"), D05-2.1 (Rental Agreement with `end_date`)

```python
def check_contract_renewals():
    config = frappe.get_single("Rental Configuration")
    alert_days = [int(d.strip()) for d in (config.renewal_alert_days or "90,60,30").split(",")]
    for days in alert_days:
        target_date = add_days(today(), days)
        expiring = frappe.get_all("Rental Agreement", filters={
            "status": "Active", "end_date": target_date,
        }, fields=["name", "customer", "asset", "end_date"])
        for agr in expiring:
            send_notification(
                notification_type="Renewal Alert",
                customer=agr.customer,
                reference_doctype="Rental Agreement",
                reference_name=agr.name,
                subject=_("Contract expiring in {0} days").format(days),
                body=_("Your agreement {0} for {1} expires on {2}").format(agr.name, agr.asset, agr.end_date),
                channels=["email", "push"]
            )
```

**Acceptance Criteria**:
- [ ] Agreement expiring in exactly 90 days → renewal alert sent
- [ ] Agreement expiring in exactly 60 days → renewal alert sent
- [ ] Agreement expiring in exactly 30 days → renewal alert sent
- [ ] Agreement expiring in 45 days → NO alert (not in configured list)
- [ ] Open-ended agreements (no `end_date`) → no renewal alert
- [ ] Already-terminated agreements → no alert
- [ ] Each alert day triggers only once (no repeat on re-run same day)

---

## 4. Frappe — Escalation Engine

### 4.1 `run_overdue_escalation` Scheduler Job

> **Requires**: D01-2.3 (hooks.py), ERPNext Sales Invoice, D05-2.1 (Rental Agreement)

```python
def run_overdue_escalation():
    TIERS = [
        {"days": 15, "channels": ["email", "push"], "recipient": "customer", "priority": "medium"},
        {"days": 30, "channels": ["email", "push", "whatsapp"], "recipient": "customer", "priority": "high"},
        {"days": 45, "channels": ["email", "push", "whatsapp"], "recipient": "customer+guarantor", "priority": "urgent"},
        {"days": 60, "channels": ["email"], "recipient": "legal", "priority": "critical"},
    ]
    for tier in TIERS:
        overdue = get_overdue_invoices(tier["days"])
        for inv in overdue:
            if already_escalated(inv.name, tier["days"]):
                continue
            escalate(inv, tier)
```

**Acceptance Criteria**:
- [ ] Invoice 15 days overdue → email + push to customer
- [ ] Invoice 30 days overdue → email + push + WhatsApp to customer (if enabled)
- [ ] Invoice 45 days overdue → email + push + WhatsApp to customer AND guarantor
- [ ] Invoice 60 days overdue → email to legal team, creates `Legal Case` record
- [ ] Each tier fires once per invoice (idempotent — `already_escalated` check)
- [ ] WhatsApp messages sent only when `whatsapp_enabled = 1` in config
- [ ] All escalations logged in `Rental Notification Log` with `notification_type = Escalation`

---

### 4.2 `Legal Case` DocType (stub for D08 enhancement)

> **Requires**: D01-2.2 (app scaffold), D01-5.2 (role permissions)

| Field | Type | Notes |
|---|---|---|
| `agreement` | Link → Rental Agreement | |
| `customer` | Link → Customer | |
| `total_outstanding` | Currency | Sum of all overdue invoices |
| `escalation_date` | Date | |
| `status` | Select | `Open`, `In Progress`, `Resolved`, `Closed` |
| `notes` | Text | |

**Acceptance Criteria**:
- [ ] Created automatically when 60-day escalation triggers
- [ ] `total_outstanding` sums all overdue invoices for this customer
- [ ] Only Rental Manager and System Manager can view/edit
- [ ] Customer CANNOT see Legal Case records

---

## 5. Frappe — Multi-Channel Dispatch

### 5.1 `send_notification` Utility Function

> **Requires**: 2.1 (Notification Log schema), D01-3.1 (config for gateway selection)

```python
def send_notification(notification_type, customer, reference_doctype, reference_name,
                     subject, body, channels=None):
    channels = channels or ["email"]
    results = {}
    for ch in channels:
        try:
            if ch == "email":
                send_email(customer, subject, body)
                results["email"] = "ok"
            elif ch == "push":
                send_fcm_push(customer, subject, body)
                results["push"] = "ok"
            elif ch == "whatsapp":
                config = frappe.get_single("Rental Configuration")
                if config.whatsapp_enabled:
                    send_whatsapp(customer, body)
                    results["whatsapp"] = "ok"
                else:
                    results["whatsapp"] = "disabled"
        except Exception as e:
            results[ch] = str(e)
    # Log
    status = "Sent" if all(v == "ok" for v in results.values()) else "Partial"
    if all(v not in ("ok", "disabled") for v in results.values()):
        status = "Failed"
    frappe.get_doc({
        "doctype": "Rental Notification Log",
        "notification_type": notification_type,
        "reference_doctype": reference_doctype,
        "reference_name": reference_name,
        "customer": customer,
        "subject": subject,
        "body": body,
        "channels_used": ",".join(channels),
        "delivery_status": status,
        "failure_reason": str({k: v for k, v in results.items() if v not in ("ok", "disabled")}),
        "sent_at": now_datetime(),
    }).insert(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Single channel (email only) → `delivery_status = Sent`
- [ ] Multi-channel (email + push) both succeed → `delivery_status = Sent`
- [ ] Email succeeds, push fails → `delivery_status = Partial`, `failure_reason` describes push error
- [ ] All channels fail → `delivery_status = Failed`
- [ ] WhatsApp channel skipped when `whatsapp_enabled = 0` → NOT counted as failure
- [ ] Notification failure does NOT throw exception (caller is not blocked)
- [ ] Every call creates exactly one `Rental Notification Log` entry

---

### 5.2 Email Channel

> **Requires**: 5.1, Frappe email setup

**Acceptance Criteria**:
- [ ] Uses Frappe's `frappe.sendmail()` — respects outgoing email account settings
- [ ] Subject and body are passed correctly
- [ ] Uses `rental_reminder.html` email template
- [ ] Failure (SMTP error) is caught and returned as error string

---

### 5.3 FCM Push Channel (`gateways/fcm.py`)

> **Requires**: 5.1, D01-8.8 (FCM token registered on login)

```python
def send_fcm_push(customer, title, body):
    tokens = get_customer_fcm_tokens(customer)
    if not tokens:
        return
    for token in tokens:
        firebase_admin.messaging.send(
            messaging.Message(notification=messaging.Notification(title=title, body=body), token=token)
        )
```

**Acceptance Criteria**:
- [ ] Customer with registered FCM token receives push notification
- [ ] Customer with no registered token → no error, no notification
- [ ] Customer with multiple devices → push sent to ALL tokens
- [ ] Invalid token → error logged, other tokens still receive push
- [ ] Push message includes `title` and `body`

---

### 5.4 WhatsApp Channel (`gateways/sms.py`)

> **Requires**: 5.1, D01-3.1 (`whatsapp_provider`, `whatsapp_api_key`)

**Acceptance Criteria**:
- [ ] When `whatsapp_enabled = 0` → channel silently skipped
- [ ] When `whatsapp_enabled = 1` + `whatsapp_provider = Twilio` → Twilio API called
- [ ] Message sent to customer's phone number (from Customer DocType)
- [ ] Missing phone number → error logged, not thrown
- [ ] API failure → error caught and returned

---

## 6. Frappe — Notification API

### 6.1 `get_customer_notifications`

> **Requires**: 2.1 (Notification Log schema)

**Acceptance Criteria**:
- [ ] Returns notifications for the current customer only
- [ ] Sorted by `sent_at` descending (newest first)
- [ ] Paginated per D01-6.2 standard
- [ ] Each entry includes: `notification_type`, `subject`, `body`, `sent_at`, `read`
- [ ] Unread count returned as top-level field: `unread_count`

---

### 6.2 `mark_notification_read`

> **Requires**: 6.1

**Acceptance Criteria**:
- [ ] Customer can mark their own notification as read
- [ ] Customer CANNOT mark another customer's notification
- [ ] Already-read notification → no error (idempotent)
- [ ] `read` field set to 1 after call

---

### 6.3 `register_fcm_token` / `deregister_fcm_token`

> **Requires**: D01-8.8 (Auth flow calls these on login/logout)

**Acceptance Criteria**:
- [ ] `register_fcm_token` stores token for current user
- [ ] Multiple tokens per user allowed (multi-device)
- [ ] `deregister_fcm_token` removes the specific token for current user
- [ ] Duplicate token registration → no error (idempotent)

---

## 7. Web — Notification Popover

### 7.1 Portal Header Bell Icon

> **Requires**: D01-7.3 (`portal_header.html` template), 6.1 (notification API)

**Acceptance Criteria**:
- [ ] Bell icon in portal header shows unread badge count
- [ ] Clicking bell opens dropdown with recent 10 notifications
- [ ] Each notification shows: subject, time ago, unread dot
- [ ] Clicking a notification marks it as read and navigates to reference (if applicable)
- [ ] Empty state: "No notifications yet"
- [ ] Badge count updates without page reload (JS polling every 60s or WebSocket)

---

### 7.2 Email Template (`templates/emails/rental_reminder.html`)

> **Requires**: D01-2.2 (template directory)

**Acceptance Criteria**:
- [ ] Template includes branded header with logo placeholder
- [ ] Subject line in header
- [ ] Body text area
- [ ] Footer with business contact info from config
- [ ] All strings wrapped in `_()` for translation
- [ ] Template renders correctly in Gmail, Outlook, Apple Mail (tested with inline styles)

---

## 8. Flutter — Notification Center

### 8.1 FCM Service (`core/services/fcm_service.dart`)

> **Requires**: D01-8.2 (firebase_messaging dependency), D01-8.5 (secure storage for token), 6.3 (register API)

```dart
class FcmService {
  final Ref ref;
  FcmService(this.ref);

  Future<void> registerToken() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) {
      await ref.read(frappeClientProvider)
          .post('rental_core.api.notifications.register_fcm_token', body: {'token': token});
    }
  }

  Future<void> deregisterToken() async {
    final token = await FirebaseMessaging.instance.getToken();
    if (token != null) {
      await ref.read(frappeClientProvider)
          .post('rental_core.api.notifications.deregister_fcm_token', body: {'token': token});
    }
  }
}
```

**Acceptance Criteria**:
- [ ] `registerToken()` is called after successful login (D01-8.8)
- [ ] `deregisterToken()` is called before logout
- [ ] Foreground notification → local notification displayed via `flutter_local_notifications`
- [ ] Background notification → stored in notification list
- [ ] Tapping notification navigates to relevant screen (deep link from `data` payload)
- [ ] Token refresh event → re-registers with server

---

### 8.2 Notification Screen

> **Requires**: D01-8.3 (screen stub), 6.1 (notification API)

**Acceptance Criteria**:
- [ ] Lists notifications: type icon, subject, body preview, time ago, unread dot
- [ ] Pull-to-refresh reloads notifications
- [ ] Tapping notification marks it as read (dot removed) and navigates to reference
- [ ] Empty state: illustration + "No notifications yet" text
- [ ] Unread count shown in bottom navigation badge

---

### 8.3 Notification Provider

> **Requires**: D01-8.6 (FrappeClient), 6.1 (API)

```dart
@riverpod
Future<NotificationList> customerNotifications(Ref ref, {int page = 1}) async {
  final client = ref.read(frappeClientProvider);
  final data = await client.get('rental_core.api.notifications.get_customer_notifications',
      params: {'page': page});
  return NotificationList.fromJson(data);
}

@riverpod
Future<int> unreadNotificationCount(Ref ref) async {
  /* ... returns unread_count */
}
```

**Acceptance Criteria**:
- [ ] Provider fetches paginated notifications
- [ ] `unreadNotificationCount` provider is separate (for badge — lightweight)
- [ ] Badge count auto-refreshes every 60 seconds
- [ ] `ref.invalidate()` after marking a notification as read updates the count

---

## 9. Domain-Level Acceptance Criteria

- [ ] Payment reminder sent 3 days before due date
- [ ] Renewal alerts sent at 90, 60, 30 days before contract end
- [ ] Escalation tiers fire at 15, 30, 45, 60 days overdue
- [ ] No duplicate notifications for same event
- [ ] WhatsApp disabled → channel silently skipped
- [ ] Failed notifications do NOT block business operations
- [ ] Flutter push notification navigates to correct screen
- [ ] Web bell icon shows unread count

---

## 10. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (Notification Log + Reminder + Escalation + Dispatch + APIs) | 4 days |
| Web (bell popover + email template) | 1 day |
| Flutter (FCM service + notification screen + provider) | 3 days |
| **Total** | **8 days** |
