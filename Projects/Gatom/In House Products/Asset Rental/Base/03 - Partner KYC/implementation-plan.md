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

Before a customer can book any rental asset, they must prove their identity through a **Know Your Customer (KYC)** process. This is a legal requirement in most jurisdictions and also protects the landlord from fraud. The KYC domain handles the complete identity verification lifecycle: the customer uploads identity documents (passport, national ID, trade license for companies), the documents are stored securely in S3, a staff member reviews and approves/rejects them, and the customer is notified of the outcome.

KYC status is a **hard gate** — the booking API in D05 refuses to proceed unless `kyc_status == Verified`. This domain also includes the **guarantor portal**, where a tenant's financial guarantor can view outstanding amounts without seeing any of the tenant's personal information.

---

## 2. Frappe — Customer KYC DocTypes

### 2.1 `Customer KYC Submission` Schema

> **Requires**: D01-2.2 (app scaffold), D01-5.2 (role permissions for this DocType)

The **Customer KYC Submission** is the central document tracking a customer's verification status. Each customer has exactly one active submission. The workflow is: customer uploads documents → status changes to `Pending Review` → staff reviews → status changes to `Verified` (approved) or `Resubmit Required` (rejected with reason). The `rejection_reason` field requires a minimum of 20 characters to ensure the customer gets a meaningful explanation of what was wrong with their documents.

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

Each KYC submission contains one or more **document rows** — the actual identity files the customer uploaded. Each row links to a document type ("National ID", "Passport", etc.) and stores the S3 file URL. The `upload_date` is auto-set so staff can see when the document was provided.

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

This is a **configurable master data** DocType that defines what kinds of documents are required for KYC. Different customer types need different documents: individuals need a National ID or Passport, while companies need a Trade License and Commercial Registration. The `required_for` field controls this filtering. The `description` text is shown to the customer on the upload form to explain what each document should contain.

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

ERPNext's built-in `Customer` DocType doesn't know about KYC by default. These custom fields are injected via `setup.py` to add rental-specific data: `custom_kyc_status` (a read-only mirror of the KYC submission status — used for quick lookups without joining to the KYC Submission table), `custom_kyc_submission` (a link to the full submission document), `custom_tenant_type` (Individual or Company), and `custom_guarantor_email` (for guarantor portal access).

The key design decision: `custom_kyc_status` is **synced** from the KYC Submission, not manually editable. Whenever the KYC Submission status changes, the Customer field updates automatically.

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

This API endpoint returns the **current KYC state** for the logged-in customer. Both the web portal (`/my-kyc`) and the Flutter app call this to determine which UI to show. The response includes the status, any rejection reason (if status is `Resubmit Required`), the list of required document types (filtered by customer type), and the list of already-submitted documents. Guest users get HTTP 401.

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

The customer-facing upload endpoint. Customers call this after selecting/photographing their identity documents. The files are uploaded to **S3** (not the local filesystem) for security and scalability. The KYC status transitions to `Pending Review`, and the Rental Manager receives an email notification to begin review. The endpoint has guards against re-submission: if documents are already under review or already verified, the call is rejected.

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

The **staff-facing review endpoint**. A Rental Manager examines the uploaded documents and makes a decision: `Verified` (identity confirmed) or `Resubmit Required` (documents are unclear, expired, or wrong type). If rejecting, the manager must provide a `rejection_reason` of at least 20 characters — this ensures the customer gets actionable feedback (not just "rejected"). The decision is recorded with the reviewer's name and timestamp for audit trail, and the customer receives push + email notification of the outcome.

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

A helper API that returns the list of document types the customer needs to upload, **filtered by their `customer_type`**. An individual customer sees "National ID" and "Passport" but not "Trade License" (which is Company-only). Types marked `required_for = Both` appear for everyone. This endpoint powers the upload form's document checklist on both web and Flutter.

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

This is the **critical gate** that connects KYC to the booking flow. It's a Python snippet injected at the very top of the booking API endpoint (in D05). Before any booking logic runs, it checks the customer's `custom_kyc_status`. If it's anything other than `Verified`, the booking is blocked with HTTP 403 and a message directing the customer to complete verification. This is not a warning — it's a hard block.

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

KYC documents are **sensitive identity files** (passports, national IDs) that must be stored securely. This handler uploads them to a **private S3 bucket** (or MinIO-compatible storage), not to Frappe's local `private/files/` directory. Files are organized by customer name and document type for easy retrieval. Access to files uses **pre-signed URLs** that expire after 15 minutes — this means even if a URL is leaked, it becomes invalid quickly.

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

KYC has three notification triggers: (1) when a customer **submits documents** → email to the Rental Manager so they know to review, (2) when staff **approves** (Verified) → push + email to the customer saying they can now book, (3) when staff **rejects** (Resubmit Required) → push + email to the customer with the specific rejection reason. All notifications are logged to the `Rental Notification Log` for audit, and notification failures never block the underlying status change.

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

The `/my-kyc` portal page is where customers manage their KYC process. The controller fetches the customer's current KYC status, the list of required document types (filtered by their customer type), and any previously submitted documents. If the customer is a Guest, they're redirected to login with a return URL so they come back here after authenticating.

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

The KYC page renders **four distinct UI states** based on the current status. `Not Submitted` and `Resubmit Required` show the upload form with required document types as file input fields (Resubmit also shows the rejection reason in a warning banner). `Pending Review` shows a read-only "your documents are under review" message with no upload controls. `Verified` shows a green confirmation badge with the verified date. This prevents customers from accidentally re-submitting or getting confused about their current state.

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

The JavaScript that handles the actual file upload from the web form. Files are sent via `frappe.call()` (for CSRF safety). A progress indicator shows during transfer so the customer knows the upload is working. File size is capped at 10 MB per file to prevent storage abuse. On success, the page reloads to show the `Pending Review` state.

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

In some rental markets, tenants have a **financial guarantor** — a person or company that guarantees rental payments. The guarantor portal gives this person visibility into the tenant's financial obligations without exposing the tenant's personal information. The portal matches agreements by `custom_guarantor_email` and shows only financial data: agreement name, total outstanding, next due date, and overdue amounts.

**Acceptance Criteria**:
- [ ] Guest → redirected to `/login?redirect-to=/guarantor-portal`
- [ ] Authenticated user with no guaranteed agreements → empty state message
- [ ] Lists only agreements where `custom_guarantor_email` matches `frappe.session.user`
- [ ] Each agreement shows: `agreement_name`, `total_outstanding`, `next_due_date`, overdue invoice amounts

---

### 9.2 Field-Level Restrictions

> **Requires**: 9.1

This is a **privacy constraint**, not a feature. The guarantor portal must **never** expose: tenant name, tenant email, tenant phone, or asset address. The guarantor only sees agreement identifiers and financial amounts. This is both a legal requirement (data minimization) and a business decision (the guarantor doesn't need to know where the tenant lives).

**Acceptance Criteria**:
- [ ] Guarantor portal does NOT return: tenant name, tenant email, tenant phone, asset address
- [ ] Guarantor portal returns ONLY: agreement name, total outstanding, next due date, overdue amounts
- [ ] API response for guarantor endpoint has no PII fields for the tenant
- [ ] Guarantor cannot see variant-specific data (unit number, vehicle plate, etc.)

---

## 10. Web — Registration Redirect

### 10.1 Post-Registration Redirect Logic

> **Requires**: D01-7.3 (`rental-signup.html` stub)

When a new user registers, they should be redirected to the KYC page by default so they can immediately begin identity verification. The registration form stores a `redirect-to` URL parameter. After email confirmation, the user is redirected there (default: `/my-kyc`). The redirect is validated to prevent **open redirect vulnerabilities** — only internal URLs (starting with `/`) are allowed.

**Acceptance Criteria**:
- [ ] Registration form includes hidden `redirect-to` field from URL parameter
- [ ] After email confirmation, user is redirected to stored URL (default: `/my-kyc`)
- [ ] If `redirect-to` is not set, user lands on `/my-kyc` by default
- [ ] `redirect-to` only allows internal URLs (no open redirect vulnerability)

---

## 11. Flutter — KYC Screen

### 11.1 `kyc_screen.dart`

> **Requires**: D01-8.6 (FrappeClient), 4.1 (get_kyc_status), 4.4 (get_required_document_types)

The **Flutter KYC screen** mirrors the web portal's four states (see 8.2) in a mobile-native UI. The key mobile enhancement: customers can **capture documents directly with the camera** (not just pick from gallery), which is the most common mobile KYC workflow. The screen shows required document types as cards with camera/file picker buttons, and handles all state transitions.

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

A Dart service class that wraps all KYC-related API calls. It provides typed methods for getting status, submitting documents, and fetching required document types. API errors are caught and surfaced to the UI layer (not swallowed silently). This class is injected via Riverpod so it can be mocked in tests.

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

After a customer's **first login**, if their KYC is not yet verified, the app automatically navigates them to the KYC screen. This is a **one-time prompt per session** (not forced on every screen transition) and the user can dismiss it and browse freely. The goal is to nudge new users toward completing verification without creating a frustrating forced flow.

**Acceptance Criteria**:
- [ ] After first login, if `kyc_status != Verified`, user is auto-navigated to KYC screen
- [ ] Auto-navigation only happens once per session (not on every screen transition)
- [ ] User can dismiss and navigate away (KYC is prompted, not forced)

---

### 11.4 Asset Detail CTA Logic

> **Requires**: 11.2 (KYC status provider), D02-7.1 (inquiry form widget)

The Flutter equivalent of the web CTA logic in D02-6.3. On the asset detail screen, the call-to-action buttons change based on KYC status: verified users see "Book Now" as primary, unverified users see "Complete Verification" which navigates to the KYC screen. The CTA updates **reactively** via the Riverpod provider when the user returns from completing KYC.

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
