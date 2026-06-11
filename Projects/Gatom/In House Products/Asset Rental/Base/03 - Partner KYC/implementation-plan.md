# Domain 03 — Partner KYC: Implementation Plan

> **Variant**: Base
> **Domain**: Partner KYC
> **Sequence**: 3 of 8
> **Depends on**: Domain 01 (config fields + S3 setup)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

> [!CAUTION]
> KYC is a **hard prerequisite** for booking. No customer can reserve an asset without KYC status `Verified`. This domain blocks Domain 05 (Rental Contracting).

---

## 1. Overview

Customer onboarding and identity verification. Includes KYC DocType, document upload to S3, staff review workflow, guarantor portal, web/Flutter KYC pages, and the API gate that blocks unverified customers from booking.

---

## 2. Frappe — Customer KYC DocTypes

### 2.1 `Customer KYC Submission` Schema

> **Requires**: D01-2.2 (app scaffold), D01-5.2 (role permissions for this DocType)

| Field | Type | Notes |
|---|---|---|
| `customer` | Link → Customer | Required. One active submission per customer. |
| `kyc_status` | Select: `Not Submitted`, `Pending Review`, `Verified`, `Resubmit Required` | Default: `Not Submitted` |
| `customer_type` | Select: `Individual`, `Company` | Mirrors Customer classification |
| `documents` | Table → `KYC Document` (child table) | See 2.2 |
| `reviewed_by` | Link → User | Set on review |
| `reviewed_on` | Datetime | Set on review |
| `rejection_reason` | Small Text | Required when status = `Resubmit Required`. Min 20 chars. |
| `submission_date` | Datetime | Set when customer submits documents |

**Acceptance Criteria**:
- [ ] DocType exists and is accessible in Frappe Desk
- [ ] `customer` field links to ERPNext `Customer` DocType
- [ ] `kyc_status` defaults to `Not Submitted`
- [ ] Only one active submission (status not `Verified`) per customer is allowed
- [ ] `rejection_reason` is mandatory when `kyc_status = Resubmit Required`
- [ ] `rejection_reason` enforces minimum 20 character length
- [ ] `reviewed_by` and `reviewed_on` are read-only (set programmatically)

---

### 2.2 `KYC Document` Child Table

> **Requires**: 2.1 (parent DocType must exist)

| Field | Type | Notes |
|---|---|---|
| `document_type` | Link → `KYC Document Type` | |
| `file_url` | Attach | S3/MinIO signed URL |
| `upload_date` | Datetime | Auto-set |

**Acceptance Criteria**:
- [ ] Child table rows appear inside `Customer KYC Submission`
- [ ] `document_type` links to `KYC Document Type` master data
- [ ] `upload_date` is auto-populated on row creation
- [ ] `file_url` stores the S3 attachment URL

---

### 2.3 `KYC Document Type` Master Data

> **Requires**: D01-2.2 (app scaffold)

| Field | Type | Notes |
|---|---|---|
| `title` | Data | e.g., "National ID", "Passport", "Trade License" |
| `required_for` | Select: `Individual`, `Company`, `Both` | |
| `description` | Small Text | Displayed to customer during upload |

**Acceptance Criteria**:
- [ ] DocType exists as master data in Frappe Desk
- [ ] Can create entries like "National ID" (Individual), "Trade License" (Company)
- [ ] `required_for = Both` appears for both individual and company KYC flows
- [ ] `description` renders on the customer-facing upload form

---

## 3. Frappe — Customer Record Extension

### 3.1 Custom Fields on ERPNext `Customer`

> **Requires**: 2.1 (KYC Submission DocType must exist for the link)

| Field | Type | Notes |
|---|---|---|
| `custom_kyc_status` | Select: `Not Submitted`, `Pending Review`, `Verified`, `Resubmit Required` | Synced from KYC Submission. Read-only. |
| `custom_kyc_submission` | Link → `Customer KYC Submission` | Auto-populated |
| `custom_tenant_type` | Select: `Individual`, `Company` | Set during registration |
| `custom_guarantor_email` | Data | For guarantor portal access |

**Acceptance Criteria**:
- [ ] Custom fields appear in the Customer form in Frappe Desk
- [ ] `custom_kyc_status` is read-only (cannot be edited directly by user)
- [ ] `custom_kyc_status` mirrors the status in the linked `Customer KYC Submission`
- [ ] Changing status in `Customer KYC Submission` auto-updates `custom_kyc_status` on the Customer
- [ ] `custom_guarantor_email` accepts valid email format

---

## 4. Frappe — KYC API Endpoints

### 4.1 `get_kyc_status`

> **Requires**: 2.1 (KYC Submission schema), 3.1 (Customer custom fields)

| Task | Detail |
|---|---|
| Method | GET |
| Auth | Customer (logged in) |
| Returns | `{ kyc_status, rejection_reason, required_document_types[], submitted_documents[] }` |

**Acceptance Criteria**:
- [ ] Returns current `kyc_status` for the logged-in customer
- [ ] When status is `Resubmit Required`, `rejection_reason` is included in response
- [ ] `required_document_types` is filtered by the customer's `tenant_type`
- [ ] `submitted_documents` lists all documents with `document_type` and `file_url`
- [ ] Guest call returns HTTP 401

---

### 4.2 `submit_kyc_documents`

> **Requires**: 4.1 (get status must work), 2.2 (KYC Document child table), 6.1 (S3 upload)

| Task | Detail |
|---|---|
| Method | POST |
| Auth | Customer |
| Input | `customer_type`, `documents[]` (file uploads) |
| Side effects | Sets status to `Pending Review`. Notifies Rental Manager. |

**Acceptance Criteria**:
- [ ] Customer can upload one or more documents
- [ ] Each document is stored in S3 (not local filesystem)
- [ ] `kyc_status` transitions from `Not Submitted` → `Pending Review`
- [ ] `kyc_status` transitions from `Resubmit Required` → `Pending Review` on re-submission
- [ ] `submission_date` is set to current datetime
- [ ] Rental Manager receives notification (email) about new submission
- [ ] Submitting when `kyc_status = Pending Review` returns error "Documents already under review"
- [ ] Submitting when `kyc_status = Verified` returns error "Already verified"

---

### 4.3 `review_kyc`

> **Requires**: 2.1 (KYC Submission schema), 3.1 (Customer custom fields), D07 notification dispatcher

| Task | Detail |
|---|---|
| Method | POST |
| Auth | Rental Manager+ |
| Input | `customer`, `decision` (`Verified` / `Resubmit Required`), `rejection_reason` |

**Acceptance Criteria**:
- [ ] Setting decision to `Verified` → `kyc_status` updated on both KYC Submission and Customer
- [ ] Setting decision to `Resubmit Required` → `rejection_reason` required (min 20 chars)
- [ ] `rejection_reason` with < 20 chars returns HTTP 400
- [ ] `reviewed_by` set to current user, `reviewed_on` set to current datetime
- [ ] Customer receives push + email on `Verified` outcome
- [ ] Customer receives push + email on `Resubmit Required` with the rejection reason
- [ ] Customer role CANNOT call this endpoint (HTTP 403)

---

### 4.4 `get_required_document_types`

> **Requires**: 2.3 (KYC Document Type master data)

| Task | Detail |
|---|---|
| Method | GET |
| Auth | Any authenticated user |
| Returns | List of `{ title, description, required_for }` filtered by `customer_type` |

**Acceptance Criteria**:
- [ ] Returns only types matching the given `customer_type` or `Both`
- [ ] Individual customer gets "National ID", "Passport" etc. but not "Trade License" (Company-only)
- [ ] Company customer gets "Trade License", "CR" etc. plus `Both` types
- [ ] Response includes `description` field for display in upload forms

---

## 5. Frappe — KYC Gate in Booking API

### 5.1 Booking Block for Unverified Customers

> **Requires**: 3.1 (`custom_kyc_status` on Customer), D05 booking API (this is injected at the top of it)

```python
customer = frappe.get_doc("Customer", frappe.session.user)
if customer.custom_kyc_status != "Verified":
    frappe.throw(
        _("You must complete identity verification before booking."),
        exc=frappe.PermissionError,
        title=_("KYC Required")
    )
```

**Acceptance Criteria**:
- [ ] Customer with `kyc_status = Not Submitted` → booking returns HTTP 403 with "KYC Required"
- [ ] Customer with `kyc_status = Pending Review` → booking returns HTTP 403
- [ ] Customer with `kyc_status = Resubmit Required` → booking returns HTTP 403
- [ ] Customer with `kyc_status = Verified` → booking proceeds normally
- [ ] Error message includes guidance to visit KYC page

---

## 6. Frappe — S3 Upload Integration

### 6.1 Upload Handler

> **Requires**: D01-3.1 (`kyc_s3_bucket`, `kyc_s3_region`, AWS keys in Rental Configuration)

**Acceptance Criteria**:
- [ ] KYC documents are uploaded to S3 (not Frappe's local `private/files/`)
- [ ] Uploaded file URL stored in `KYC Document.file_url`
- [ ] File download uses 15-minute pre-signed S3 URL (not public bucket)
- [ ] Pre-signed URL expires after 15 minutes — subsequent requests generate a new one
- [ ] Missing AWS credentials → upload returns HTTP 500 with logged error (not silent failure)
- [ ] Files are stored under path: `kyc/{customer_name}/{document_type}/{filename}`

---

## 7. Frappe — KYC Notification Triggers

### 7.1 Notification Events

> **Requires**: 4.2 (submit triggers), 4.3 (review triggers), D07 notification dispatcher

| Event | Channels | Recipient | Template |
|---|---|---|---|
| Customer submits KYC | Email | Rental Manager | "New KYC submission for {customer}" |
| Staff marks Verified | Push + Email | Customer | "Your identity has been verified" |
| Staff marks Resubmit Required | Push + Email | Customer | "Your documents need resubmission: {reason}" |

**Acceptance Criteria**:
- [ ] KYC submission triggers email to Rental Manager within 1 minute
- [ ] Verification sends push + email to customer with "you can now book" message
- [ ] Resubmit sends push + email to customer with the rejection reason text
- [ ] All notifications are logged in `Rental Notification Log` with `notification_type = KYC Update`
- [ ] Failed notification does NOT block the KYC status update

---

## 8. Web — `/my-kyc` Portal Page

### 8.1 Controller `www/my-kyc.py`

> **Requires**: D01-7.3 (page stub), 4.1 (get_kyc_status API), 2.3 (document types)

```python
def get_context(context):
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login?redirect-to=/my-kyc"
        raise frappe.Redirect
    # ... fetch KYC data
```

**Acceptance Criteria**:
- [ ] Guest visiting `/my-kyc` → redirected to `/login?redirect-to=/my-kyc`
- [ ] After login, user returns to `/my-kyc`
- [ ] Context includes `kyc_status`, `required_doc_types`, `submitted_documents`, `rejection_reason`
- [ ] User with no Customer record sees error message (not a crash)

---

### 8.2 Template States

> **Requires**: 8.1 (controller), D01-7.1 (CSS design system)

- **`Not Submitted` / `Resubmit Required`**: Upload form with required document types
- **`Pending Review`**: Read-only "under review" message
- **`Verified`**: Green confirmation badge with verified date

**Acceptance Criteria**:
- [ ] `Not Submitted`: form shows required document types as file upload fields
- [ ] `Resubmit Required`: rejection reason displayed above the form in a warning alert
- [ ] `Resubmit Required`: previously uploaded documents are shown but can be replaced
- [ ] `Pending Review`: no upload form — only status message
- [ ] `Verified`: shows green badge, verified date, and no upload form
- [ ] Status badge uses design system colors

---

### 8.3 JS Upload Handler

> **Requires**: 8.2 (form HTML), 4.2 (submit API endpoint)

**Acceptance Criteria**:
- [ ] Files uploaded via `frappe.call` (CSRF-safe)
- [ ] Upload progress indicator shown during file transfer
- [ ] On success, page reloads to show `Pending Review` state
- [ ] On failure, error message shown (not silent)
- [ ] Maximum file size enforced (e.g., 10 MB per file)

---

## 9. Web — Guarantor Portal

### 9.1 Controller `www/guarantor-portal.py`

> **Requires**: D01-7.3 (page stub), 3.1 (Customer `custom_guarantor_email`)

**Acceptance Criteria**:
- [ ] Guest → redirected to `/login?redirect-to=/guarantor-portal`
- [ ] Authenticated user with no guaranteed agreements → empty state message
- [ ] Lists only agreements where `custom_guarantor_email` matches `frappe.session.user`
- [ ] Each agreement shows: `agreement_name`, `total_outstanding`, `next_due_date`, overdue invoice amounts

---

### 9.2 Field-Level Restrictions

> **Requires**: 9.1

**Acceptance Criteria**:
- [ ] Guarantor portal does NOT return: tenant name, tenant email, tenant phone, asset address
- [ ] Guarantor portal returns ONLY: agreement name, total outstanding, next due date, overdue amounts
- [ ] API response for guarantor endpoint has no PII fields for the tenant
- [ ] Guarantor cannot see variant-specific data (unit number, vehicle plate, etc.)

---

## 10. Web — Registration Redirect

### 10.1 Post-Registration Redirect Logic

> **Requires**: D01-7.3 (`rental-signup.html` stub)

**Acceptance Criteria**:
- [ ] Registration form includes hidden `redirect-to` field from URL parameter
- [ ] After email confirmation, user is redirected to stored URL (default: `/my-kyc`)
- [ ] If `redirect-to` is not set, user lands on `/my-kyc` by default
- [ ] `redirect-to` only allows internal URLs (no open redirect vulnerability)

---

## 11. Flutter — KYC Screen

### 11.1 `kyc_screen.dart`

> **Requires**: D01-8.6 (FrappeClient), 4.1 (get_kyc_status), 4.4 (get_required_document_types)

**Acceptance Criteria**:
- [ ] Screen fetches current KYC status on load
- [ ] `Not Submitted`: shows list of required document types with camera/file upload buttons
- [ ] `Resubmit Required`: shows rejection reason prominently + upload form
- [ ] `Pending Review`: shows "under review" message, no upload controls
- [ ] `Verified`: shows green checkmark badge with verified date
- [ ] Camera picker opens device camera for document capture
- [ ] File picker allows selecting from device gallery/files

---

### 11.2 KYC API Provider

> **Requires**: D01-8.6 (FrappeClient)

```dart
class KycApi {
  final FrappeClient _client;
  KycApi(this._client);
  Future<Map<String, dynamic>> getKycStatus() => _client.get('rental_core.api.kyc.get_kyc_status');
  Future<void> submitDocuments(Map<String, dynamic> data) => _client.post('rental_core.api.kyc.submit_kyc_documents', body: data);
  Future<List<Map<String, dynamic>>> getRequiredDocTypes() => _client.get('rental_core.api.kyc.get_required_document_types').then(/*...*/);
}
```

**Acceptance Criteria**:
- [ ] `getKycStatus()` returns parsed status, rejection reason, submitted docs
- [ ] `submitDocuments()` sends files to the API and returns success/failure
- [ ] `getRequiredDocTypes()` returns list filtered by customer type
- [ ] API errors are caught and surfaced to the UI (not swallowed)

---

### 11.3 Post-Login KYC Prompt

> **Requires**: 11.1 (KYC screen), D01-8.8 (AuthNotifier for login event)

**Acceptance Criteria**:
- [ ] After first login, if `kyc_status != Verified`, user is auto-navigated to KYC screen
- [ ] Auto-navigation only happens once per session (not on every screen transition)
- [ ] User can dismiss and navigate away (KYC is prompted, not forced)

---

### 11.4 Asset Detail CTA Logic

> **Requires**: 11.2 (KYC status provider), D02-7.1 (inquiry form widget)

**Acceptance Criteria**:
- [ ] `kyc_status == Verified` → "Book Now" button shown as primary CTA
- [ ] `kyc_status != Verified` → "Complete Verification" shown, navigates to KYC screen
- [ ] CTA updates reactively when KYC status changes (provider re-fetches)

---

## 12. Domain-Level Acceptance Criteria

- [ ] Full flow: register → submit KYC → staff reviews → Verified → booking unlocked
- [ ] Full flow: submit KYC → staff rejects → re-submit → staff approves
- [ ] KYC gate blocks booking for all non-Verified statuses
- [ ] S3 upload stores files securely with signed URL access
- [ ] Guarantor portal shows only financial summary — no tenant PII
- [ ] All notifications logged

---

## 13. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (DocTypes + API + S3 + notifications) | 5 days |
| Web (/my-kyc + guarantor portal + registration redirect) | 3 days |
| Flutter (KYC screen + API + CTA logic) | 3 days |
| **Total** | **11 days** |
