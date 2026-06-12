# Domain 07 — Notifications & Escalation: Implementation Plan

> **Variant**: Base
> **Domain**: Notifications & Escalation
> **Sequence**: 7 of 8
> **Depends on**: Domain 01 (config + FCM setup), all other domains (notification triggers)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

This domain is the **communication backbone** of the platform. Every notification in the system — payment reminders, KYC updates, escalation warnings, booking confirmations — flows through a unified pipeline. The system supports four channels: **email** (via Frappe's built-in `frappe.sendmail()`), **push notifications** (via Firebase Cloud Messaging), **SMS** (via Twilio/Unifonic), and **WhatsApp** (via Twilio or similar provider).

The domain also includes the **escalation engine**: a tiered system that progressively increases notification severity for overdue payments (D+1 → D+3 → D+7 → D+14 → D+30 legal escalation).

> [!NOTE]
> **Architecture Decision: Why a Custom Pipeline Instead of Frappe's `Notification` DocType?**
>
> Frappe provides a built-in `Notification` DocType for config-driven alerts. We evaluated it and determined it's insufficient for this platform's needs:
> - Frappe's `Notification` supports **one channel per rule** (email OR system notification). The rental platform needs **multi-channel dispatch** (same event → email + push + SMS simultaneously).
> - Frappe has **no built-in FCM, SMS, or WhatsApp** channels. Custom gateway adapters are required regardless.
> - The **escalation ladder** (D+1/D+3/D+7/D+14/D+30 with idempotency) is domain-specific business logic that cannot be expressed as Notification DocType conditions.
> - The **customer-facing notification inbox** (portal bell icon + Flutter screen) needs a portal-accessible DocType. Frappe's `Notification Log` is Desk-only.
>
> **What we DO use from Frappe**: `frappe.sendmail()` for email delivery (§5.2), Frappe's SMTP connection pooling, and Frappe's `Notification Log` for **staff-facing** Desk notifications (when a KYC submission arrives, when a legal case is created). The custom `Customer Notification` DocType (§2.1) is **customer-facing only**.

---

## 2. Frappe — `Customer Notification` DocType

### 2.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory), D01-5.2 (role permissions)

The **Customer Notification** (formerly `Rental Notification Log`) is the **customer-facing** notification record. It serves as the data source for the web portal bell icon (§7.1) and Flutter notification screen (§8.2). Every notification sent to a customer — whether it succeeded, partially failed, or completely failed — creates an entry here.

> [!IMPORTANT]
> **Scope distinction**: `Customer Notification` is for **customers** (portal + Flutter). For **staff** notifications (Desk users), the platform uses Frappe's built-in `Notification Log` DocType via `frappe.publish_realtime()`. This avoids re-inventing the Desk notification system.

This DocType serves three purposes: (1) customer notification inbox (browseable in portal and Flutter), (2) staff debugging ("did the customer get notified?"), and (3) compliance audit ("can we prove we sent the 90-day renewal notice?"). Logs are immutable — no one can edit or delete them.

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

A **daily scheduler job** that identifies invoices due in 3 days and sends the customer a reminder via email + push. This is a proactive nudge — reminding tenants before the due date reduces late payments and the need for escalation. The scheduler includes an **idempotency check** to prevent duplicate reminders if the job runs multiple times on the same day.

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

Sends **renewal alerts** at configurable intervals before a fixed-term contract expires (default: 90, 60, and 30 days). This gives both the tenant and the operator time to discuss renewal terms. Open-ended agreements (no `end_date`) are excluded — they don't expire, so renewal alerts don't apply. Each alert day fires once per agreement (not repeated daily).

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

The **escalation engine** implements a tiered escalation ladder for overdue payments. This is the business's progressive response to non-payment, matching the functional specification (BR-071, BR-075):

- **D+1**: Email + push to customer — first overdue reminder.
- **D+3**: Email + push to customer — second reminder, stronger language.
- **D+7**: Email + push + WhatsApp to **both customer and guarantor** simultaneously — involving the financial backer.
- **D+14**: Email + push + WhatsApp to **both customer and guarantor** — final warning before legal.
- **D+30**: Email to legal team + automatic `Legal Case` creation — pre-litigation.

Each tier fires **once per invoice** (idempotent). WhatsApp and SMS are only used when enabled in config.

```python
def run_overdue_escalation():
    TIERS = [
        {"days": 1,  "channels": ["email", "push"],              "recipient": "customer",            "priority": "medium"},
        {"days": 3,  "channels": ["email", "push"],              "recipient": "customer",            "priority": "medium"},
        {"days": 7,  "channels": ["email", "push", "whatsapp"],  "recipient": "customer+guarantor",  "priority": "high"},
        {"days": 14, "channels": ["email", "push", "whatsapp"],  "recipient": "customer+guarantor",  "priority": "urgent"},
        {"days": 30, "channels": ["email"],                      "recipient": "legal",              "priority": "critical"},
    ]
    for tier in TIERS:
        overdue = get_overdue_invoices(tier["days"])
        for inv in overdue:
            if already_escalated(inv.name, tier["days"]):
                continue
            escalate(inv, tier)
```

**Acceptance Criteria**:
- [ ] Invoice 1 day overdue → email + push to customer
- [ ] Invoice 3 days overdue → email + push to customer (stronger language)
- [ ] Invoice 7 days overdue → email + push + WhatsApp to customer AND guarantor simultaneously
- [ ] Invoice 14 days overdue → email + push + WhatsApp to customer AND guarantor (final warning)
- [ ] Invoice 30 days overdue → email to legal team, creates `Legal Case` record
- [ ] Each tier fires once per invoice (idempotent — `already_escalated` check)
- [ ] WhatsApp messages sent only when `whatsapp_enabled = 1` in config
- [ ] All escalations logged in `Rental Notification Log` with `notification_type = Escalation`

---

### 4.2 `Legal Case` DocType (stub for D08 enhancement)

> **Requires**: D01-2.2 (app scaffold), D01-5.2 (role permissions)

When the 60-day escalation tier fires, a **Legal Case** record is automatically created. This is a lightweight DocType that captures the customer, agreement, total outstanding amount, and a status tracker. It's designed to be the handoff point to the legal team or external legal counsel. The Legal Case is **invisible to the customer** — only Rental Managers and System Managers can view it.

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

### 4.3 Rejection Reason Validation

> **Requires**: D04-6.2 (rejection handler), D05-2.1 (Rental Agreement with `rejection_reason` field)

Functional requirement BR-077 states: "The rejection reason field requires a **minimum of 20 characters**. The staff UI must show a character counter and sample placeholder text." When a Rental Manager rejects a Draft Agreement, they must provide a meaningful explanation that the customer will see. A terse "No" or "Rejected" is unacceptable — the 20-character minimum forces the manager to write something informative.

The validation happens at **two levels**:

1. **Server-side** (Frappe DocType validation): The `Rental Agreement` controller's `validate()` method checks that when `status == "Rejected"`, `rejection_reason` has at least 20 characters. This is the authoritative check.

2. **Client-side** (Frappe Desk form script): A client script on the Rental Agreement form shows a **character counter** below the `rejection_reason` field (e.g., "12 / 20 characters minimum"). The counter turns green when the minimum is met. The field's placeholder text reads: "Please provide a clear reason for rejection, e.g., 'Incomplete documentation — missing proof of address.'"

```python
def validate(self):
    if self.status == "Rejected":
        if not self.rejection_reason or len(self.rejection_reason.strip()) < 20:
            frappe.throw(_("Rejection reason must be at least 20 characters"))
```

```javascript
// In rental_agreement.js (client script)
frappe.ui.form.on('Rental Agreement', {
    rejection_reason(frm) {
        const len = (frm.doc.rejection_reason || '').trim().length;
        frm.get_field('rejection_reason').set_description(
            `${len} / 20 characters minimum ${len >= 20 ? '✅' : '❌'}`
        );
    },
});
```

**Acceptance Criteria**:
- [ ] Setting status to "Rejected" with fewer than 20 characters → `ValidationError`
- [ ] Setting status to "Rejected" with 20+ characters → save succeeds
- [ ] Desk form shows character counter below `rejection_reason` field
- [ ] Counter turns green (✅) when 20+ characters are entered
- [ ] Placeholder text provides a sample rejection reason
- [ ] Empty `rejection_reason` on rejection → error message: "Rejection reason must be at least 20 characters"
- [ ] Rejection reason is visible to the customer in portal and app (stored on agreement)

---

## 5. Frappe — Multi-Channel Dispatch

### 5.1 `send_notification` Utility Function

> **Requires**: 2.1 (Notification Log schema), D01-3.1 (config for gateway selection)

The **central dispatch function** that all notification-sending code in the platform calls. It accepts a notification type, customer, reference document, subject, body, and a list of channels. It then attempts delivery on each channel sequentially, catching errors per-channel. The delivery status is determined by the results: all succeed = `Sent`, some fail = `Partial`, all fail = `Failed`. WhatsApp being disabled is NOT counted as a failure.

Critically, this function **never throws exceptions** — notification failures are logged but do not block the calling business logic (e.g., a KYC review shouldn't fail because the email server is down).

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

The email channel uses Frappe's built-in `frappe.sendmail()` function, which respects the site's configured outgoing email account (SMTP settings). Emails use a branded HTML template (`rental_reminder.html`) for a professional appearance. SMTP failures are caught and returned as error strings (not thrown).

**Acceptance Criteria**:
- [ ] Uses Frappe's `frappe.sendmail()` — respects outgoing email account settings
- [ ] Subject and body are passed correctly
- [ ] Uses `rental_reminder.html` email template
- [ ] Failure (SMTP error) is caught and returned as error string

---

### 5.3 FCM Push Channel (`gateways/fcm.py`)

> **Requires**: 5.1, D01-8.8 (FCM token registered on login)

The push notification channel uses **Firebase Cloud Messaging (FCM)** to deliver real-time notifications to the customer's mobile device. Tokens are registered when the customer logs in to the Flutter app (D01-8.8). A customer can have **multiple tokens** (multiple devices), and push notifications are sent to all of them. Invalid tokens (e.g., app uninstalled) cause errors that are logged but don't block delivery to other devices.

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

The WhatsApp channel is an **optional escalation-only channel**. It's enabled/disabled via config (`whatsapp_enabled`). When enabled, it sends messages through a WhatsApp Business API provider (e.g., Twilio). The customer's phone number is read from the ERPNext Customer DocType. Missing phone numbers and API failures are logged but don't throw exceptions.

**Acceptance Criteria**:
- [ ] When `whatsapp_enabled = 0` → channel silently skipped
- [ ] When `whatsapp_enabled = 1` + `whatsapp_provider = Twilio` → Twilio API called
- [ ] Message sent to customer's phone number (from Customer DocType)
- [ ] Missing phone number → error logged, not thrown
- [ ] API failure → error caught and returned

---

### 5.5 SMS Channel (`gateways/sms_gateway.py`)

> **Requires**: 5.1, D01-3.1 (`sms_provider`, `sms_api_key`, `sms_sender_id`)

Functional requirement BR-073 specifies four notification channels: Email, **SMS**, WhatsApp, and Push. The current plan conflates SMS with WhatsApp in a single file (`gateways/sms.py`). This subtask adds a **dedicated SMS channel** for plain text messages via a configurable provider.

SMS is distinct from WhatsApp because: (1) SMS works on feature phones and in regions where WhatsApp adoption is low (parts of Africa, some rural areas), (2) SMS doesn't require the customer to have a smartphone or data plan, and (3) some regulatory frameworks require SMS as a fallback for financial notifications.

The SMS channel supports three providers (matching the regional focus of the platform):
- **Twilio** — global coverage, most common
- **Unifonic** — popular in GCC (UAE, KSA, Kuwait)
- **Vonage** — European markets

The provider is configurable in `Rental Configuration`. All providers implement the same interface: `send_sms(phone, message) → success/failure`.

SMS is used as a **supplementary channel** alongside email and push. It's NOT a replacement for email (which carries richer content). SMS messages are kept under 160 characters to avoid multi-part billing. For escalation tiers (D07-4.1), SMS is sent at D+3 and beyond (not D+1, to avoid spamming on the first day).

```python
class TwilioSMSGateway:
    def send_sms(self, phone, message):
        from twilio.rest import Client
        config = frappe.get_single("Rental Configuration")
        client = Client(config.sms_api_key, config.sms_api_secret)
        result = client.messages.create(
            body=message[:160],
            from_=config.sms_sender_id,
            to=phone,
        )
        return result.status == "queued"
```

**Acceptance Criteria**:
- [ ] SMS channel is separate from WhatsApp channel (different file, different config fields)
- [ ] When `sms_provider = Twilio` → Twilio SMS API called
- [ ] When `sms_provider = Unifonic` → Unifonic API called
- [ ] SMS messages capped at 160 characters
- [ ] Missing phone number → error logged, not thrown
- [ ] Missing `sms_api_key` → channel silently skipped with log warning
- [ ] SMS sent to customer's phone number from ERPNext Customer DocType
- [ ] API failure → error caught, logged, not thrown

---

## 6. Frappe — Notification API

### 6.1 `get_customer_notifications`

> **Requires**: 2.1 (Notification Log schema)

Returns the current customer's **notification inbox**: a paginated list of all notifications sent to them, sorted newest-first. The response includes an `unread_count` field at the top level for badge display (web bell icon and Flutter bottom nav badge). Each entry includes the notification type, subject, body, timestamp, and read status.

**Acceptance Criteria**:
- [ ] Returns notifications for the current customer only
- [ ] Sorted by `sent_at` descending (newest first)
- [ ] Paginated per D01-6.2 standard
- [ ] Each entry includes: `notification_type`, `subject`, `body`, `sent_at`, `read`
- [ ] Unread count returned as top-level field: `unread_count`

---

### 6.2 `mark_notification_read`

> **Requires**: 6.1

Marks a specific notification as read (sets `read = 1`). This is called when the customer taps/clicks a notification in the UI. The operation is **idempotent** — marking an already-read notification doesn't error. Customer isolation is enforced: a customer can only mark their own notifications.

**Acceptance Criteria**:
- [ ] Customer can mark their own notification as read
- [ ] Customer CANNOT mark another customer's notification
- [ ] Already-read notification → no error (idempotent)
- [ ] `read` field set to 1 after call

---

### 6.3 `register_fcm_token` / `deregister_fcm_token`

> **Requires**: D01-8.8 (Auth flow calls these on login/logout)

These endpoints manage the **FCM token registry**. On login, the Flutter app sends its device's FCM token to `register_fcm_token`. On logout, it calls `deregister_fcm_token` to remove it. Multiple tokens per user are allowed (the user may have a phone and a tablet). Token registration is **idempotent** — registering the same token twice doesn't create a duplicate.

**Acceptance Criteria**:
- [ ] `register_fcm_token` stores token for current user
- [ ] Multiple tokens per user allowed (multi-device)
- [ ] `deregister_fcm_token` removes the specific token for current user
- [ ] Duplicate token registration → no error (idempotent)

---

## 7. Web — Notification Popover

### 7.1 Portal Header Bell Icon

> **Requires**: D01-7.3 (`portal_header.html` template), 6.1 (notification API)

A **bell icon** in the portal header that shows the unread notification count as a badge. Clicking the bell opens a dropdown with the 10 most recent notifications. Each notification shows the subject, relative time ("2 hours ago"), and an unread dot. Clicking a notification marks it as read and optionally navigates to the referenced document (e.g., the invoice page). The badge count refreshes periodically (JS polling every 60 seconds) or via WebSocket.

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

A **branded HTML email template** used for all rental-related emails (reminders, receipts, escalations, KYC updates). The template includes a branded header (with logo placeholder), subject line, body text area, and a footer with business contact info pulled from Rental Configuration. All strings are wrapped in `_()` for i18n support. The template must render correctly across Gmail, Outlook, and Apple Mail (using inline CSS for compatibility).

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

The **FCM Service** manages the Flutter app's push notification lifecycle. On login, it retrieves the device's FCM token and registers it with the server. On logout, it deregisters. When a push notification arrives while the app is in the **foreground**, it uses `flutter_local_notifications` to display a system notification (FCM doesn't auto-display foreground pushes). When a notification is tapped, it navigates to the relevant screen using a deep link embedded in the `data` payload. The service also handles **token refresh events** (Firebase may rotate tokens) by re-registering with the server.

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

The Flutter **notification center** screen. Lists all notifications with a type icon (payment, KYC, booking, etc.), subject, body preview, relative time, and an unread dot. Tapping a notification marks it as read (dot removed) and navigates to the referenced screen (e.g., the invoice detail). The unread count is displayed as a badge on the bottom navigation bar.

**Acceptance Criteria**:
- [ ] Lists notifications: type icon, subject, body preview, time ago, unread dot
- [ ] Pull-to-refresh reloads notifications
- [ ] Tapping notification marks it as read (dot removed) and navigates to reference
- [ ] Empty state: illustration + "No notifications yet" text
- [ ] Unread count shown in bottom navigation badge

---

### 8.3 Notification Provider

> **Requires**: D01-8.6 (FrappeClient), 6.1 (API)

Two Riverpod providers: `customerNotifications` (paginated list of all notifications) and `unreadNotificationCount` (a lightweight int for badge display). The count provider is kept **separate** from the full list because it needs to refresh frequently (every 60 seconds) without fetching the entire notification list. Marking a notification as read triggers `ref.invalidate()` to update both providers.

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
