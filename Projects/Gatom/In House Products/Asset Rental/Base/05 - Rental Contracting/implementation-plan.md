# Domain 05 — Rental Contracting: Implementation Plan

> **Variant**: Base
> **Domain**: Rental Contracting
> **Sequence**: 5 of 8
> **Depends on**: Domain 01 (config), Domain 03 (KYC gate), Domain 04 (concurrency lock)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Rental agreement lifecycle: multi-step booking, KYC gate, e-signature, activation, renewal, open-ended termination, self-cancellation, and exit inspection.

---

## 2. Frappe — `Rental Agreement` DocType

### 2.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory), D01-5.2 (role permissions), D04-2.1 (Rental Asset for link)

| Field | Type | Required | Notes |
|---|---|---|---|
| `agreement_number` | Data | auto | Series: `RNT-.YYYY.-.####` |
| `asset` | Link → Rental Asset | ✅ | |
| `tenant_type` | Select | ✅ | `Individual`, `Company` |
| `customer` | Link → Customer | ✅ | |
| `start_date` | Date | ✅ | |
| `end_date` | Date | | Null = open-ended |
| `billing_cycle` | Select | ✅ | `Monthly`, `Weekly`, `Daily` |
| `monthly_rate` | Currency | ✅ | Editable copy from asset |
| `deposit_amount` | Currency | ✅ | |
| `deposit_status` | Select | | `Held`, `Partially Released`, `Refunded` |
| `status` | Select | ✅ | `Draft`, `Active`, `Expired`, `Terminated`, `Rejected`, `Cancelled` |
| `signed_agreement` | Attach | | Generated PDF |
| `signature_data` | Long Text | | Base64 canvas |
| `additional_charges` | Table → `Additional Charge` | | |
| `erpnext_subscription` | Link → Subscription | | Set on submit |
| `notes` | Text | | Internal only |
| `rejection_reason` | Small Text | | Min 20 chars. Visible to customer. |
| `termination_date` | Datetime | | |
| `termination_notice_days` | Int | | Default from config |
| `annual_escalation_pct` | Float | | |
| `escalation_justification` | Long Text | | Required when exceeding cap |
| `agreement_pdf_url` | Data | | Auto-set on activation |

**Acceptance Criteria**:
- [ ] DocType is accessible in Frappe Desk under "Rental" module
- [ ] `agreement_number` auto-generates with series `RNT-.YYYY.-.####`
- [ ] `asset`, `customer`, `start_date`, `billing_cycle`, `monthly_rate`, `deposit_amount` are mandatory
- [ ] `status` defaults to `Draft` on creation
- [ ] `end_date` is nullable (open-ended agreements)
- [ ] `track_changes = 1` enabled for version history

---

### 2.2 Controller — `on_submit`

> **Requires**: 2.1, D04-5.1 (concurrency lock), D06-2.1 (subscription factory)

```python
def on_submit(self):
    reserve_asset(self.asset)
    self.erpnext_subscription = create_subscription(self)
    create_deposit_ledger(self)
```

**Acceptance Criteria**:
- [ ] Submission atomically reserves the asset (uses `SELECT FOR UPDATE`)
- [ ] ERPNext Subscription is created and linked
- [ ] Deposit Ledger record is created with `original_amount = self.deposit_amount`
- [ ] If asset is already Reserved/Rented, submission fails with conflict error
- [ ] `erpnext_subscription` field is populated after submit

---

### 2.3 Controller — `on_cancel`

> **Requires**: 2.1, 2.2, D04-2.2 (status transitions)

**Acceptance Criteria**:
- [ ] Cancelled agreement's asset returns to `Available`
- [ ] Linked ERPNext Subscription is cancelled
- [ ] Already-Active agreements can be cancelled by Rental Manager
- [ ] Cancelled agreements cannot be re-submitted

---

## 3. Frappe — Self-Cancellation API

### 3.1 `cancel_booking_request` Endpoint

> **Requires**: 2.1 (agreement schema), D01-3.1 (`self_cancel_limit` config field)

```python
@frappe.whitelist()
def cancel_booking_request(agreement_name):
    agr = frappe.get_doc("Rental Agreement", agreement_name)
    if agr.docstatus != 0 or agr.status != "Draft":
        frappe.throw(_("Only Draft bookings can be cancelled"))
    customer = frappe.db.get_value("Customer", {"email_id": frappe.session.user}, "name")
    if agr.customer != customer:
        frappe.throw(_("You can only cancel your own bookings"), frappe.PermissionError)
    config = frappe.get_single("Rental Configuration")
    limit = config.self_cancel_limit or 3
    recent_cancels = frappe.db.count("Rental Agreement", {
        "customer": customer, "status": "Cancelled",
        "modified": [">", add_days(today(), -30)]
    })
    if recent_cancels >= limit:
        frappe.throw(_("Maximum cancellation limit reached"))
    agr.status = "Cancelled"
    agr.save(ignore_permissions=True)
    frappe.db.set_value("Rental Asset", agr.asset, "status", "Available")
    return {"status": "ok"}
```

**Acceptance Criteria**:
- [ ] Customer can cancel their own Draft booking
- [ ] Customer CANNOT cancel another customer's booking (HTTP 403)
- [ ] Customer CANNOT cancel an Active agreement via this endpoint
- [ ] After 3 cancellations in 30 days (default limit), next cancel returns error
- [ ] Cancelled booking's asset returns to `Available`
- [ ] Customer receives email confirmation of cancellation
- [ ] Rolling 30-day window resets — cancellation from 31 days ago doesn't count

---

## 4. Frappe — Open-Ended Termination

### 4.1 `initiate_termination`

> **Requires**: 2.1 (agreement with `termination_date`), D01-3.1 (`open_ended_notice_days`)

**Acceptance Criteria**:
- [ ] Only active, open-ended (no `end_date`) agreements can be terminated
- [ ] Termination date must be at least `open_ended_notice_days` from today
- [ ] Termination date less than notice period raises validation error with required days
- [ ] Termination notice sent to customer via push + email
- [ ] Fixed-term agreements (with `end_date`) cannot be terminated via this method

---

### 4.2 Pro-Rated Last Invoice

> **Requires**: 4.1, D06-2.1 (billing engine)

**Acceptance Criteria**:
- [ ] When termination month arrives, final invoice is pro-rated: `days_remaining / days_in_month * monthly_rate`
- [ ] Subscription is cancelled after final invoice generation
- [ ] Full-month termination (on 1st of month) generates a full invoice (no pro-rating)

---

## 5. Frappe — Rent Escalation

### 5.1 Annual Escalation with Cap

> **Requires**: 2.1 (`annual_escalation_pct`, `escalation_justification`), D01-3.1 (`rent_escalation_cap_pct`)

**Acceptance Criteria**:
- [ ] Escalation within cap (e.g., 3% when cap is 5%) applies without justification
- [ ] Escalation exceeding cap requires non-empty `escalation_justification`
- [ ] Exceeding cap without justification raises validation error with cap percentage
- [ ] New `monthly_rate` = old rate × (1 + escalation_pct / 100)
- [ ] Escalation is logged in version history (`track_changes`)

---

## 6. Frappe — PDF Agreement & E-Signature

### 6.1 PDF Generation on Activation

> **Requires**: 2.1 (agreement data), D01-3.1 (config for branding)

**Acceptance Criteria**:
- [ ] When status changes to `Active`, PDF is auto-generated
- [ ] PDF contains: header with brand, tenant/landlord details, terms, charges table, e-signature image
- [ ] PDF is attached to the agreement record
- [ ] `agreement_pdf_url` is populated with the storage URL
- [ ] PDF stored in S3 (not local filesystem)

---

### 6.2 E-Signature Advisory

> **Requires**: D01-3.1 (`esignature_advisory_shown` config flag)

**Acceptance Criteria**:
- [ ] First agreement submission shows advisory: "Canvas e-signature is a convenience acknowledgement only"
- [ ] After acknowledgement, `esignature_advisory_shown` is set to 1
- [ ] Second agreement submission does NOT show the advisory again
- [ ] Advisory is a `frappe.confirm()` dialog (blocks until dismissed)

---

## 7. Frappe — Booking API Endpoints

### 7.1 `submit_booking_request`

> **Requires**: 2.1, D03-5.1 (KYC gate), D04-5.1 (concurrency lock)

**Acceptance Criteria**:
- [ ] KYC-unverified customer → HTTP 403 with "KYC Required"
- [ ] Available asset → Draft agreement created, asset set to `Reserved`
- [ ] Response includes `agreement_name`, `status`, `draft_expiry_hours`, `payment_url`
- [ ] `payment_url` is null when no immediate payment is required

---

### 7.2 `get_my_agreements`

> **Requires**: 2.1

**Acceptance Criteria**:
- [ ] Returns only agreements for the current customer
- [ ] Includes both active and past agreements
- [ ] Draft agreements included with "Pending Review" indication
- [ ] Another customer's agreements never returned

---

### 7.3 `sign_agreement`

> **Requires**: 2.1 (`signature_data` field)

**Acceptance Criteria**:
- [ ] Stores base64 signature data on the agreement
- [ ] Only the owning customer can sign their own agreement
- [ ] Empty signature data returns validation error
- [ ] Signing an already-signed agreement overwrites (allowed)

---

## 8. Web — Booking Form (5-Step)

### 8.1 Controller `www/rentals/{asset}/book.py`

> **Requires**: D01-7.3 (page stub), D03-5.1 (KYC gate)

**Acceptance Criteria**:
- [ ] Guest → redirected to `/login?redirect-to=/rentals/{asset}/book`
- [ ] Non-KYC-verified user → redirected to `/my-kyc`
- [ ] KYC-verified user → form renders with asset data and config
- [ ] Context includes: asset details, customer details, KYC ID types

---

### 8.2 Step Validation (`booking.js`)

> **Requires**: 8.1 (form HTML)

```javascript
const STEPS = ['dates', 'details', 'kyc', 'sign', 'confirm'];
```

**Acceptance Criteria**:
- [ ] 5 panels: dates, details, kyc, sign, confirm
- [ ] "Next" validates current step before advancing
- [ ] Invalid step shows inline errors (not alert box)
- [ ] "Back" navigates to previous step without losing data
- [ ] Step indicator shows current position (1 of 5, 2 of 5, etc.)

---

### 8.3 Auto-Save to sessionStorage

> **Requires**: 8.2

**Acceptance Criteria**:
- [ ] Each step advancement saves form state to `sessionStorage`
- [ ] Page reload restores form data and step position
- [ ] `sessionStorage` cleared on successful submission
- [ ] `sessionStorage` cleared on explicit cancel

---

### 8.4 Submission Handler

> **Requires**: 8.2, 7.1 (submit API)

**Acceptance Criteria**:
- [ ] Submission calls `submit_booking_request` via `frappe.call`
- [ ] On success with `payment_url`: redirect to payment gateway
- [ ] On success without `payment_url`: redirect to `/my-rentals`
- [ ] On error: show error message, stay on confirm step

---

### 8.5 Signature Pad (`signature_pad.js`)

> **Requires**: 8.2 (step 4 panel)

**Acceptance Criteria**:
- [ ] Canvas renders for freehand signature drawing
- [ ] "Clear" button resets the canvas
- [ ] Produces non-empty base64 string on "Done"
- [ ] Empty canvas → "Next" is disabled

---

## 9. Web — Self-Cancel & Pending Screen

### 9.1 Pending Confirmation Page

> **Requires**: 8.4 (submission success redirects here), 3.1 (cancel API)

**Acceptance Criteria**:
- [ ] Shows "Pending Review" badge with ETA
- [ ] "Cancel Request" button calls `cancel_booking_request`
- [ ] After cancel: redirect to catalog with confirmation toast
- [ ] Cancel failure (limit reached): show error message

---

## 10. Web — My Rentals Portal

### 10.1 Controller `www/my-rentals.py`

> **Requires**: D01-7.3 (page stub), 7.2 (get_my_agreements)

**Acceptance Criteria**:
- [ ] Guest → redirected to login
- [ ] Active agreements shown with status badge, asset name, rate
- [ ] Draft agreements shown with "Pending Review" badge
- [ ] Past agreements (Expired, Terminated, Cancelled) shown in separate section
- [ ] Past agreements limited to 10 most recent

---

### 10.2 Suspended Account Block

> **Requires**: 10.1

**Acceptance Criteria**:
- [ ] Suspended customer sees "Account on hold" instead of "Book" CTA
- [ ] Non-clickable badge (not a disabled button)
- [ ] Contact info shown if configured in Rental Configuration

---

## 11. Flutter — Booking Flow

### 11.1 Booking Notifier (State Management)

> **Requires**: D01-8.6 (FrappeClient), 7.1 (submit API)

**Acceptance Criteria**:
- [ ] `BookingState` holds: dates, personal details, signature, loading flag, error
- [ ] `setDates()`, `setPersonalDetails()`, `setSignature()` update state immutably
- [ ] `submit()` calls API and returns `payment_url` on success
- [ ] `submit()` on connectivity error saves to outbox (not lost)
- [ ] `isLoading` flag prevents double-submission

---

### 11.2 Step Screens

> **Requires**: 11.1 (state management), D01-8.3 (screen stubs)

| Step | File | Purpose |
|---|---|---|
| 1 | `step_dates.dart` | Start date, duration, billing cycle |
| 2 | `step_details.dart` | Personal details, tenant type |
| 3 | `step_kyc.dart` | KYC doc display (pre-verified) |
| 4 | `step_signature.dart` | Canvas e-signature pad |
| 5 | `step_confirm.dart` | Review + submit |

**Acceptance Criteria**:
- [ ] Each step validates before allowing navigation to next
- [ ] Step indicator shows progress (1/5, 2/5, etc.)
- [ ] Back navigation preserves entered data
- [ ] Step 3 shows KYC status badge (read-only — verification done in D03)
- [ ] Step 4 signature pad produces non-empty base64
- [ ] Step 5 shows summary of all entered data before final submit

---

### 11.3 Auto-Save to SharedPreferences

> **Requires**: 11.1

**Acceptance Criteria**:
- [ ] Each step completion serializes `BookingState` to `SharedPreferences`
- [ ] App kill → reopen → `BookingFlowScreen` restores saved state
- [ ] Cleared on successful submission
- [ ] Cleared on explicit cancel

---

### 11.4 Booking Outbox (Offline)

> **Requires**: 11.1, D01-8.2 (`connectivity_plus` dependency)

```dart
@riverpod
class BookingOutbox extends _$BookingOutbox { /* ... */ }
```

**Acceptance Criteria**:
- [ ] Booking submitted offline → saved to outbox (local storage)
- [ ] User sees "Saved offline — will retry when connected" message
- [ ] Connectivity restored → `retryAll()` automatically fires
- [ ] Successful retry removes booking from outbox
- [ ] Failed retry keeps booking in outbox for next attempt
- [ ] Outbox persists across app restart

---

### 11.5 Self-Cancel & Pending Screen

> **Requires**: 11.1 (post-submission), 3.1 (cancel API)

**Acceptance Criteria**:
- [ ] After submission: pending screen with "Cancel Request" button
- [ ] Cancel success → navigate to My Rentals with confirmation toast
- [ ] Cancel failure (limit reached) → show error toast

---

## 12. Flutter — My Rentals Screen

### 12.1 Provider

> **Requires**: D01-8.6 (FrappeClient), 7.2 (get_my_agreements API)

**Acceptance Criteria**:
- [ ] Fetches all agreements for current customer
- [ ] Includes Draft agreements with "Pending Review" badge
- [ ] Pull-to-refresh reloads data

---

### 12.2 Agreement Detail Screen

> **Requires**: 12.1

**Acceptance Criteria**:
- [ ] Shows agreement details: asset, dates, rate, status
- [ ] PDF download button when `agreement_pdf_url` is set
- [ ] Deposit status section (data from D08 enhanced API)

---

## 13. Domain-Level Acceptance Criteria

- [ ] Full booking flow: KYC gate → dates → details → sign → submit → pending → active
- [ ] Self-cancel within limit succeeds; over limit fails
- [ ] Open-ended termination respects notice period
- [ ] Rent escalation with cap enforced
- [ ] PDF generated on activation
- [ ] Offline booking outbox works end-to-end
- [ ] E-signature advisory shown once globally

---

## 14. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (Agreement + APIs + self-cancel + termination + escalation + PDF) | 7 days |
| Web (booking form + my-rentals + self-cancel + auto-save) | 3 days |
| Flutter (booking flow + outbox + my-rentals + auto-save) | 4 days |
| **Total** | **14 days** |
