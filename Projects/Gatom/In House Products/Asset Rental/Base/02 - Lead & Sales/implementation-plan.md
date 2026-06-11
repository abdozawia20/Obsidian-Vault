# Domain 02 — Lead & Sales: Implementation Plan

> **Variant**: Base
> **Domain**: Lead & Sales
> **Sequence**: 2 of 8
> **Depends on**: Domain 01 (Rental Configuration must exist)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

Pre-contract sales pipeline: inquiry capture from web/app/walk-in/phone, quotation generation, lead-to-agreement conversion tracking, and follow-up scheduling.

---

## 2. Frappe — `Rental Lead` DocType

### 2.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory `rental_lead/` must exist), D01-5.2 (role permissions)

| Field | Type | Required | Notes |
|---|---|---|---|
| `lead_name` | Data | auto | Series: `RL-.YYYY.-.####` |
| `customer_name` | Data | ✅ | Full name of the inquirer |
| `email` | Data | ✅ | |
| `phone` | Data | | |
| `source` | Select | ✅ | `Web Form`, `Mobile App`, `Walk-In`, `Phone`, `Referral` |
| `asset_type` | Select | | `Flat`, `Vehicle` |
| `preferred_asset` | Link → Rental Asset | | If customer inquired about a specific asset |
| `preferred_location` | Data | | |
| `budget_range` | Data | | Free text: "2000–3000 AED/month" |
| `notes` | Text | | Internal notes by agent |
| `status` | Select | ✅ | `New`, `Contacted`, `Qualified`, `Converted`, `Lost` |
| `assigned_to` | Link → User | | The Rental Agent working this lead |
| `follow_up_date` | Date | | Next follow-up reminder |
| `converted_to` | Link → Rental Quotation | | Set on conversion |

**Acceptance Criteria**:
- [ ] DocType is accessible in Frappe Desk under "Rental" module
- [ ] `lead_name` auto-generates with series `RL-.YYYY.-.####`
- [ ] `customer_name` and `email` are mandatory — form blocks save without them
- [ ] `source` select shows all 5 options
- [ ] `preferred_asset` link resolves only to `Rental Asset` records
- [ ] `status` defaults to `New` on creation

---

### 2.2 Controller Logic — Validation

> **Requires**: 2.1 (schema must be created)

```python
def validate(self):
    if self.email and not validate_email_address(self.email):
        frappe.throw(_("Invalid email address"))
    if frappe.db.exists("Rental Lead", {
        "email": self.email,
        "preferred_asset": self.preferred_asset or "",
        "status": ["not in", ["Converted", "Lost"]],
        "name": ["!=", self.name]
    }):
        frappe.throw(_("An active lead already exists for this email and asset"))
```

**Acceptance Criteria**:
- [ ] Invalid email format (e.g., `abc@`) raises `ValidationError` with message "Invalid email address"
- [ ] Creating a second active lead for the same email + asset raises "An active lead already exists"
- [ ] Second lead for same email but DIFFERENT asset is allowed
- [ ] Lead with same email but status `Converted` or `Lost` allows new lead creation

---

### 2.3 Controller Logic — Conversion

> **Requires**: 2.1 (lead schema), 3.1 (quotation schema must exist to create link)

```python
def on_update(self):
    if self.has_value_changed("status") and self.status == "Converted":
        self._create_quotation()

def _create_quotation(self):
    quotation = frappe.get_doc({
        "doctype": "Rental Quotation",
        "lead": self.name,
        "customer_name": self.customer_name,
        "email": self.email,
        "asset": self.preferred_asset,
    })
    quotation.insert(ignore_permissions=True)
    self.converted_to = quotation.name
    self.save(ignore_permissions=True)
```

**Acceptance Criteria**:
- [ ] Setting status to `Converted` auto-creates a `Rental Quotation` linked to this lead
- [ ] `converted_to` field is populated with the new quotation name
- [ ] Quotation inherits `customer_name`, `email`, `preferred_asset` from lead
- [ ] Setting status to `Contacted` or `Qualified` does NOT create a quotation
- [ ] Attempting to convert a lead with no `preferred_asset` creates quotation with empty asset (nullable)

---

## 3. Frappe — `Rental Quotation` DocType

### 3.1 Schema Definition

> **Requires**: D01-2.2 (DocType directory `rental_quotation/` must exist), D01-5.2 (role permissions)

| Field | Type | Required | Notes |
|---|---|---|---|
| `quotation_number` | Data | auto | Series: `RQ-.YYYY.-.####` |
| `lead` | Link → Rental Lead | | Source lead (nullable for direct quotations) |
| `customer_name` | Data | ✅ | |
| `email` | Data | ✅ | |
| `asset` | Link → Rental Asset | ✅ | |
| `proposed_start_date` | Date | ✅ | |
| `proposed_end_date` | Date | | Null = open-ended |
| `proposed_rate` | Currency | ✅ | Can differ from listed rate (negotiated) |
| `deposit_amount` | Currency | ✅ | |
| `billing_cycle` | Select | ✅ | `Monthly`, `Weekly`, `Daily` |
| `valid_until` | Date | ✅ | Quotation expiry |
| `notes` | Text | | Terms, special conditions |
| `status` | Select | ✅ | `Draft`, `Sent`, `Accepted`, `Rejected`, `Expired` |
| `quotation_pdf` | Attach | | Generated PDF |

**Acceptance Criteria**:
- [ ] DocType is accessible in Frappe Desk under "Rental" module
- [ ] `quotation_number` auto-generates with series `RQ-.YYYY.-.####`
- [ ] `asset`, `proposed_start_date`, `proposed_rate`, `deposit_amount`, `billing_cycle`, `valid_until` are mandatory
- [ ] `lead` is nullable — direct quotations (without lead) are allowed
- [ ] `status` defaults to `Draft` on creation

---

### 3.2 Controller Logic — Validation

> **Requires**: 3.1 (schema), D04 availability service (soft dependency — can stub initially)

```python
def validate(self):
    if not is_asset_available(self.asset, self.proposed_start_date, self.proposed_end_date):
        frappe.throw(_("Asset is not available for the proposed dates"))
    if self.valid_until < today():
        frappe.throw(_("Validity date must be today or later"))
```

**Acceptance Criteria**:
- [ ] Quotation for an asset that's `Rented` or `Reserved` raises "Asset is not available"
- [ ] `valid_until` set to yesterday raises "Validity date must be today or later"
- [ ] `valid_until` set to today passes validation
- [ ] Quotation for an `Available` asset with valid dates saves successfully

---

### 3.3 Controller Logic — Email on Submit

> **Requires**: 3.1 (schema), 3.2 (validation must pass)

```python
def on_submit(self):
    send_quotation_email(self)
```

**Acceptance Criteria**:
- [ ] Submitting a quotation sends an email to `self.email` with the quotation PDF
- [ ] Email contains quotation number, proposed rate, proposed dates
- [ ] Email sending failure does NOT block the submission (logged, not thrown)
- [ ] `status` is set to `Sent` after submission

---

### 3.4 Quotation Expiry Scheduler

> **Requires**: 3.1 (quotation schema with `valid_until` and `status` fields), D01-2.3 (`hooks.py` registers `expire_stale_quotations`)

```python
def expire_stale_quotations():
    stale = frappe.db.get_all("Rental Quotation", filters={
        "status": "Sent",
        "valid_until": ["<", today()],
    }, fields=["name"])
    for q in stale:
        frappe.db.set_value("Rental Quotation", q.name, "status", "Expired")
```

**Acceptance Criteria**:
- [ ] Quotation with `status=Sent` and `valid_until` yesterday → auto-set to `Expired`
- [ ] Quotation with `status=Draft` and past `valid_until` → NOT expired (only `Sent` ones)
- [ ] Quotation with `status=Accepted` → NOT expired regardless of date
- [ ] Scheduler runs daily without error when no stale quotations exist

---

## 4. Frappe — Lead Submission API

### 4.1 Guest Inquiry Endpoint

> **Requires**: 2.1 (Rental Lead DocType must exist), D01-3.1 (`default_lead_assignee` field in config)

| Task | Detail |
|---|---|
| Endpoint | `@frappe.whitelist(allow_guest=True)` at `rental_core.api.leads.submit_inquiry` |
| Input | `name`, `email`, `phone` (optional), `message`, `asset_name` (optional), `source` |
| Output | `{ "status": "ok", "message": "We'll get back to you within 24 hours" }` |
| Rate limiting | `@frappe.rate_limiter(limit=5, seconds=3600)` per email |

**Acceptance Criteria**:
- [ ] Guest (unauthenticated) can call this endpoint without 401
- [ ] Valid submission creates a `Rental Lead` with correct `source`, `customer_name`, `email`
- [ ] `asset_name` is stored in `preferred_asset` when provided
- [ ] Empty `name` or `message` returns HTTP 400
- [ ] Invalid email format returns HTTP 400
- [ ] 6th submission from the same email within 1 hour returns HTTP 429
- [ ] When `default_lead_assignee` is set in config, lead is auto-assigned via `frappe.desk.form.assign_to.add`
- [ ] When `default_lead_assignee` is empty, lead is created without assignment

---

## 5. Frappe — Conversion Funnel Report

### 5.1 Script Report

> **Requires**: 2.1 (leads), 3.1 (quotations), D05 agreements (soft dependency — can count 0 initially)

| Item | Detail |
|---|---|
| File | `rental_core/report/lead_conversion_funnel/lead_conversion_funnel.py` |
| Columns | `source`, `total_leads`, `quotation_generated`, `converted_to_agreement`, `conversion_rate_pct` |
| Filters | Date range |
| Permissions | Rental Manager, System Manager |

**Acceptance Criteria**:
- [ ] Report runs from Frappe Desk without errors
- [ ] Results group leads by `source` (Web Form, Mobile App, Walk-In, Phone, Referral)
- [ ] `quotation_generated` counts leads where `converted_to` is not null
- [ ] `conversion_rate_pct` = `converted_to_agreement / total_leads * 100`, rounded to 1 decimal
- [ ] Date range filter correctly scopes leads by `creation` date
- [ ] Rental Agent role CANNOT access this report
- [ ] Accountant role CANNOT access this report

---

## 6. Web — Inquiry Form on Asset Detail

### 6.1 Template Section

> **Requires**: D01-7.3 (asset detail page stub must exist), D01-7.1 (CSS design system)

Add a "Request Info" collapsible form at the bottom of `/rentals/{asset}`:

```html
<div class="rental-inquiry-form mt-4 p-4" style="border-top: 1px solid var(--rental-border)">
    <h4>{{ _("Request Information") }}</h4>
    <form id="inquiry-form">
        <input type="text" name="name" placeholder="{{ _('Your Name') }}" required>
        <input type="email" name="email" placeholder="{{ _('Your Email') }}" required>
        <input type="tel" name="phone" placeholder="{{ _('Phone (optional)') }}">
        <textarea name="message" placeholder="{{ _('Your Message') }}" required></textarea>
        <button type="submit" class="btn btn-primary">{{ _("Send Inquiry") }}</button>
    </form>
</div>
```

**Acceptance Criteria**:
- [ ] Inquiry form is visible on every asset detail page (`/rentals/{asset}`)
- [ ] All fields use `placeholder` text wrapped in `_()`
- [ ] `name`, `email`, `message` fields have `required` attribute
- [ ] `phone` field is optional (no `required` attribute)
- [ ] Form uses `rental-inquiry-form` CSS class from design system
- [ ] Form is styled consistently with the rest of the page

---

### 6.2 JS Handler

> **Requires**: 6.1 (form HTML must exist), 4.1 (API endpoint must exist)

```javascript
document.getElementById('inquiry-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const fd = new FormData(e.target);
    const r = await frappe.call({
        method: 'rental_core.api.leads.submit_inquiry',
        args: {
            name: fd.get('name'), email: fd.get('email'),
            phone: fd.get('phone'), message: fd.get('message'),
            asset_name: window.ASSET_NAME,
        },
    });
    if (r.message.status === 'ok') {
        e.target.innerHTML = '<p class="text-success">✓ ' + __("We'll get back to you shortly") + '</p>';
    }
});
```

**Acceptance Criteria**:
- [ ] Submission calls `rental_core.api.leads.submit_inquiry` via `frappe.call` (CSRF-safe)
- [ ] On success, form is replaced with confirmation message (no form reset)
- [ ] Confirmation message is translated via `__()`
- [ ] `asset_name` is passed from the page context (set in `window.ASSET_NAME`)
- [ ] On API error (400, 429), user sees a meaningful error message (not a silent failure)

---

### 6.3 CTA Visibility Logic

> **Requires**: 6.1 (form exists), D03 (KYC status check available — can stub initially)

- **Guests and non-KYC'd users**: Show "Request Info" as primary CTA on asset detail
- **KYC-verified users**: Show "Book Now" as primary, "Request Info" as secondary

**Acceptance Criteria**:
- [ ] Guest user sees "Request Info" as the main button (no "Book Now")
- [ ] Logged-in user with `kyc_status != Verified` sees "Request Info" primary + "Complete Verification" link
- [ ] Logged-in user with `kyc_status == Verified` sees "Book Now" primary + "Request Info" secondary
- [ ] CTA state updates without page reload when KYC status changes (use `frappe.call` to check)

---

## 7. Flutter — Inquiry Screen

### 7.1 `InquiryFormWidget`

> **Requires**: D01-8.6 (FrappeClient for API calls), D01-8.8 (auth state to pre-fill profile)

Bottom sheet on Asset Detail screen:

```dart
class InquiryFormWidget extends ConsumerStatefulWidget {
  final String? assetName;
  const InquiryFormWidget({this.assetName, super.key});
  // ...
}
```

**Acceptance Criteria**:
- [ ] Tapping "Request Info" on asset detail opens a bottom sheet with form fields
- [ ] Fields: name, email, phone (optional), message (required)
- [ ] When user is logged in, name and email are pre-filled from profile
- [ ] Pre-filled fields are editable (not locked)
- [ ] Form validates email format client-side before submission
- [ ] Successful submission shows `SnackBar` with "We'll get back to you shortly"
- [ ] Bottom sheet dismisses after successful submission
- [ ] API failure shows error `SnackBar` (not a crash)

---

### 7.2 CTA Visibility on Asset Detail

> **Requires**: 7.1 (inquiry widget), D03 (KYC status provider — can stub initially)

**Acceptance Criteria**:
- [ ] If `kyc_status == Verified`: "Book Now" button is primary (prominent), "Request Info" is secondary
- [ ] If `kyc_status != Verified`: "Request Info" is primary, "Complete Verification" link shown
- [ ] Tapping "Complete Verification" navigates to KYC screen
- [ ] CTA state reflects the current KYC status from the provider (reactive)

---

## 8. Domain-Level Acceptance Criteria

- [ ] Guest can submit inquiry from web → Lead created with `source=Web Form`
- [ ] Flutter user submits inquiry → Lead created with `source=Mobile App`
- [ ] Rate limiting blocks > 5 inquiries per email per hour
- [ ] Lead auto-assigned to configured assignee
- [ ] Duplicate active lead is rejected
- [ ] Lead → Quotation conversion creates linked quotation
- [ ] Stale quotations expire daily
- [ ] Conversion Funnel report shows correct data

---

## 9. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (Lead + Quotation DocTypes + API + report) | 3 days |
| Web (inquiry form + template + JS) | 1 day |
| Flutter (inquiry widget + CTA logic) | 1 day |
| **Total** | **5 days** |
