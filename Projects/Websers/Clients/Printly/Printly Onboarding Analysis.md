---
type: "project"
id: "proj_printly_onboarding"
title: "Printly Onboarding Analysis"
status: "completed"
priority: "medium"
client: "Printly"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


# Printly — Platform Onboarding & Architecture Analysis

> **Version:** 1.1 · June 2025 · Internal Developer Reference · Confidential  
> **Changelog:** v1.1 — Workflow requirements updated; step-by-step automation triggers revised; sprint boundary clarified; deferred steps documented with open questions.

---

## Table of Contents

1. [Project Overview](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#1-project-overview)
2. [Technology Stack](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#2-technology-stack)
3. [Sprint Scope](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#3-sprint-scope)
4. [Order Lifecycle & Workflow](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#4-order-lifecycle--workflow)
5. [Order Status Reference](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#5-order-status-reference)
6. [Support Ticket Triggers](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#6-support-ticket-triggers)
7. [Plugins & Custom Modules](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#7-plugins--custom-modules)
8. [Open Tasks & Known Issues](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#8-open-tasks--known-issues)
9. [Architectural Decisions & Rationale](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#9-architectural-decisions--rationale)
10. [Glossary](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#10-glossary)

---

## 1. Project Overview

Printly is a Libyan-market digital platform that acts as a managed middleman between customers who need custom printing services and two types of vendors: **printing vendors** (who produce the physical items) and a **delivery vendor** (who ships the finished products to customers). All workflows — from order placement to payment, fulfilment, and billing — are handled digitally through an integrated WordPress/WooCommerce storefront and an Odoo ERP back-office.

### Key Business Characteristics

- Operates **exclusively in Libya** (LYD currency only, single-country checkout).
- Does **not** produce anything itself — pure coordination and financial middleman.
- Supports **multiple printing vendors** per order; **single delivery vendor** (subject to expansion).
- All customer payments are collected **online at checkout** via the Tlync gateway. No cash-on-delivery or offline payment flows currently.
- Payments are **fully charged upfront** and held in reserve until the complete order lifecycle is finished.

> ⚠️ The vendor portal (how printing and delivery vendors interact with Odoo) has not yet been fully analysed and is out of scope for the current sprint.

---

## 2. Technology Stack

|Component|Layer|Responsibilities|Notes|
|---|---|---|---|
|**WordPress + WooCommerce**|Customer-facing storefront|Customer order creation, payment checkout via Tlync, order status display|NI WooCommerce Custom Order Status plugin added for custom statuses|
|**Odoo (ERP)**|Back-office operations|Sales orders, purchase orders, invoicing, vendor portal access, accounting journals|Vendor tech custom integration module handles WooCommerce sync|
|**Vendor Tech Module**|WooCommerce → Odoo sync layer|Polls WooCommerce every 15 min via scheduled action; failed orders logged in a dedicated model with retry capability|Not real-time — 15 min polling lag must be factored into all workflows|
|**Tlync Payment Gateway**|Online payment processing|Full charge at checkout; payment reserved until delivery completion|Only supported gateway at this time; subject to expansion|
|**Odoo Vendor Portal**|Vendor-facing interface|Printing & delivery vendors accept/reject/confirm orders; Odoo native portal with planned customisations|Portal analysis not yet completed for this sprint|

### 2.1 WordPress ↔ Odoo Sync

The vendor tech custom module in Odoo uses a **scheduled action** to poll WooCommerce every 15 minutes and import new orders. This is not a real-time webhook — there is always a potential lag of up to 15 minutes between a customer placing an order and it appearing in Odoo.

**Failure handling is built into the vendor tech module:**

- Failed orders are logged in a dedicated **"Failed Orders"** model inside Odoo.
- Staff can view failed orders and trigger **manual retries** from this model.
- The system **alerts users** when failures occur — no silent data loss.

> ℹ️ A task exists to sync order attachments (customer design files) from WooCommerce to Odoo. Supported formats will include PDF, SVG, PNG, and JPEG. The exact format(s) used by customers in the Libyan market are still to be confirmed by the client.

---

## 3. Sprint Scope

### In Scope ✅ — Current Sprint (Steps 0 → 2.1)

The current sprint covers the workflow from order creation through to the delivery vendor confirmation timeout. All steps below are **concrete and fully defined**.

- Order creation in WooCommerce and automatic SO creation + payment reservation in Odoo.
- SO status field sync between Odoo and WooCommerce (`processing` → `preparing`).
- Printing vendor PO (RFQ) creation and confirmation flow.
- Time-based ticket trigger for printing vendor non-response.
- Customer cancellation flow (available only in `processing` state).
- Printing completion trigger and delivery vendor PO creation.
- Time-based ticket trigger for delivery vendor non-response.

### Deferred ⏸️ — Pending Client Clarification (Steps 2.2 → 3)

The following steps are **blocked on open questions** that must be resolved before implementation can begin. See [Section 4.3](https://claude.ai/chat/967287cc-3687-4c3f-a461-ce89ce731fe8#43-deferred-steps--open-questions) for full details.

- Delivery failure handling (Step 2.2) — deferred due to scalability concern around PO-to-SO relationship.
- Customer rejection of received product (Step 2.3) — deferred due to unresolved question on when/how the customer can trigger this.
- Final financial close-out: billing, invoicing, and payment release (Step 3) — blocked by the same PO scalability concern as Step 2.2.

### Out of Scope ❌

- Custom payment gateway integration mappings (beyond Tlync).
- Core WooCommerce database table modifications (handled via vendor tech module documentation).
- Third-party shipping carrier API synchronisation.
- Product image/attachment sync between Odoo and WooCommerce (pending format confirmation).
- Vendor portal deep customisation (separate sprint).
- `On Hold` status — **scrapped**; removal is a standalone task.

---

## 4. Order Lifecycle & Workflow

The workflow is broken into numbered steps that correspond directly to automation triggers and their resulting actions. Each step is marked with its current sprint status.

---

### Step 0 — Customer Creates Order & Pays ✅ In Scope

**Trigger:** Customer completes checkout on WooCommerce and payment is confirmed by the Tlync gateway. Online payment is the **only** accepted method. The SO is created in WooCommerce at this point.

**Automated actions:**

- SO is created in Odoo via the vendor tech polling cycle (up to 15 min lag) and **natively confirmed** immediately — it is never left as a quotation.
- Payment record is created in Odoo and **reserved** (full charge held in accounting journal entry).

> ℹ️ The SO in Odoo maps to WooCommerce's native `processing` status. No status field change occurs at this step — the order simply exists and is confirmed.

---

### Step 1 — SO Confirmed → Printing PO Created ✅ In Scope

**Trigger:** The SO is confirmed in Odoo (which happens automatically at Step 0). A separate **SO status field** — shared between Odoo and WooCommerce — is updated to `preparing`.

**Automated actions:**

- SO status field is moved from `processing` → `preparing` (synced to WooCommerce).
- A **Purchase Order (RFQ)** is created in Odoo for the printing vendor.
    - If the product has a single configured supplier, the vendor is auto-assigned.
    - If multiple printing vendors exist, Printly staff selects the vendor (one action on the SO).
- The PO becomes visible to the assigned printing vendor on their Odoo portal.

> ⚠️ Note the distinction: Odoo's **native SO state** (confirmed/done) is separate from the **custom SO status field** (`processing`, `preparing`, `delivery`, etc.) that is synced with WooCommerce. Both exist on the SO simultaneously.

---

#### Step 1.1 — Printing Vendor Does Not Respond in Time ✅ In Scope

**Trigger:** The printing vendor PO is not confirmed after a **configurable time offset** (e.g. 24 h).

**Automated actions:**

- A support ticket is created in Odoo automatically.

---

#### Step 1.2 — Printing Vendor Confirms the PO ✅ In Scope

**Trigger:** The printing vendor accepts and confirms the PO via their Odoo portal.

**Automated actions:**

- The PO is marked as a confirmed **Purchase Order** (moves out of RFQ state).

> ℹ️ No SO status change occurs at this point. The SO remains in `preparing` until the vendor marks the job as printed (Step 2).

---

#### Step 1.3 — Customer Cancels the Order ✅ In Scope

**Trigger:** Customer requests cancellation. This action is **only available while the SO status is `processing`** — i.e. before Step 1 automation has run (before the PO has been created and the status moved to `preparing`).

**Automated actions:**

- The printing vendor PO is cancelled.
- The SO is cancelled in Odoo.
- The payment reservation is released and the customer is refunded.

> ⚠️ Once the order has moved to `preparing` (Step 1 automation has fired), customer cancellation is no longer available through this flow.

---

### Step 2 — Printing Complete → Delivery PO Created ✅ In Scope

**Trigger:** The printing vendor marks the PO as done/printed on their Odoo portal.

**Automated actions:**

- SO status field is moved from `preparing` → `delivery` (synced to WooCommerce).
- A second **PO is created automatically** for the delivery vendor.
- A notification is sent to the delivery vendor (via Odoo email/portal) to arrange pickup.

---

#### Step 2.1 — Delivery Vendor Does Not Respond in Time ✅ In Scope

**Trigger:** The delivery vendor PO is not confirmed after a **configurable time offset** (e.g. 24 h).

**Automated actions:**

- A support ticket is created in Odoo automatically.

---

### Step 2.2 — Delivery Vendor Marks Order as Failed ⏸️ Deferred

**Trigger:** Delivery vendor flags the delivery as failed on their portal.

**Intended automation:**

- Create a support ticket with the vendor-provided failure reason.

**⛔ Blocked — open architectural question:**

> Managing delivery failure state on the SO level assumes a 1-to-1 relationship between a delivery PO and an SO. However, a future scalability requirement has been identified: **one delivery PO may need to cover multiple SOs** (e.g. a batch delivery run). If delivery failure state is tracked on the SO, this scalability path is closed.  
> **Resolution needed:** Confirm with the client whether batch delivery POs are a requirement, and if so, define where failure state should be tracked (PO level vs SO level).

---

### Step 2.3 — Customer Rejects the Delivered Product ⏸️ Deferred

**Trigger:** Customer flags that they did not accept the product — done through the WordPress website.

**Intended automation:**

- Create a support ticket.

**⛔ Blocked — open business question:**

> It is unclear **at what point in the process** the customer can trigger this. Two possible interpretations exist:
> 
> 1. The customer can only reject **after** the order is marked `delivered` (post-delivery, via their account on the website).
> 2. The customer validates the product **physically during delivery** (i.e. in front of the delivery vendor), meaning the rejection must happen in real-time at the moment of handoff.
> 
> **Resolution needed:** Client must confirm which scenario applies. This determines whether the rejection window is time-based (after `delivered`) or event-based (at the moment of handoff).

---

### Step 3 — Order Delivered → Financial Close-Out ⏸️ Deferred

**Trigger:** Delivery vendor marks the SO as `delivered`.

**Intended automated actions:**

- Create and confirm the **delivery vendor bill**.
- Create the **printing vendor bill(s)** (one per printing vendor involved in the order).
- Create and confirm the **customer invoice**.
- **Release the payment reservation** created at Step 0 and link it to the confirmed invoice.

**⛔ Blocked — same architectural question as Step 2.2:**

> The financial close-out (billing and payment release) is currently designed to be triggered by the SO reaching `delivered` state. This assumes a 1-to-1 mapping between one delivery PO and one SO.  
> If the future model allows **one delivery PO to service multiple SOs**, triggering billing from the SO state becomes ambiguous — the delivery PO cannot be confirmed until all SOs in the batch are delivered.  
> **Resolution needed:** Same client confirmation as Step 2.2. Once the PO-to-SO relationship model is locked, the financial close-out triggers can be finalised.

---

## 5. Order Status Reference

> ℹ️ The **`On Hold`** status that previously existed has been scrapped and must be removed from both WooCommerce and Odoo as a standalone task.

> ⚠️ There are **two distinct status concepts** on a Printly SO:
> 
> 1. **Odoo native SO state** — standard Odoo states (`draft`, `sale`, `done`, `cancel`). Managed by Odoo internally.
> 2. **Custom SO status field** — a separate field synced between Odoo and WooCommerce representing the fulfilment stage. This is what customers see and what the automations act on.
> 
> All statuses in the table below refer to the **custom SO status field**.

|Status|WooCommerce Slug|Sprint Status|Trigger|Automated Actions|
|---|---|---|---|---|
|`Processing`|`processing`|✅ In scope|SO created in WooCommerce and confirmed in Odoo|SO confirmed in Odoo; payment reserved (full charge)|
|`Preparing`|`preparing`|✅ In scope|SO confirmed in Odoo (fires immediately after Step 0)|SO status updated to `preparing`; printing vendor RFQ/PO created|
|`Delivery`|`delivery`|✅ In scope|Printing vendor marks PO as done/printed|SO status updated to `delivery`; delivery vendor PO created; delivery vendor notified|
|`Delivered`|`delivered`|⏸️ Deferred|Delivery vendor marks order as delivered|_(Pending)_ Payment released; customer invoice created & confirmed; delivery vendor bill created; printing vendor bill(s) created|
|`Cancelled`|`cancelled`|✅ In scope|Customer cancels during `processing` state|Printing PO cancelled; SO cancelled; payment reservation released and customer refunded|
|`Failed`|`failed`|⏸️ Deferred|Delivery vendor reports delivery failure|_(Pending)_ Support ticket created with vendor-provided reason|
|`Refunded`|`refunded`|⏸️ Deferred|Customer rejects received product (via website)|_(Pending)_ Support ticket created; resolution flow TBD pending client clarification|

> ℹ️ **Custom statuses** (`Preparing`, `Delivery`, `Delivered`, `Failed`, `Refunded`) are registered in WooCommerce using the **NI WooCommerce Custom Order Status** plugin. Standard statuses (`Processing`, `Cancelled`) are native WooCommerce statuses.

> ℹ️ In Odoo, the custom SO status field is managed through the vendor tech integration module and mapped to the corresponding WooCommerce slugs.

---

## 6. Support Ticket Triggers

Support tickets are raised automatically in Odoo based on **time-based thresholds** and specific **vendor/customer actions**. There is no prebuilt Odoo feature for this — all ticket automation requires **custom technical development**.

Time-based thresholds are **configurable per trigger** in Odoo settings (e.g. "raise ticket if vendor has not confirmed within X hours"), allowing Printly operations staff to tune SLA expectations without developer involvement.

|Type|Trigger|Active State|Condition|Sprint Status|
|---|---|---|---|---|
|⏱ Time-based|Printing vendor delay to confirm|`Preparing`|Configurable hours after PO sent with no vendor confirmation|✅ In scope|
|⏱ Time-based|Delivery vendor delay to confirm pickup|`Delivery`|Configurable hours after delivery PO created with no pickup confirmation|✅ In scope|
|⏱ Time-based|Delivery vendor delay to deliver|`Delivery`|Configurable hours after pickup confirmation with no delivery confirmation|⏸️ Deferred|
|⚡ Action-based|Delivery vendor marks order as failed|`Delivery`|Vendor flags failure on portal with reason|⏸️ Deferred|
|⚡ Action-based|Customer rejects received product|`Delivered`|Customer reports rejection via WordPress website|⏸️ Deferred|

> ⚠️ No prebuilt Odoo logic exists for any of these triggers. All ticket automation is a custom technical requirement. Refer to the internal sub-task created for SLA/workflow automation specifications.

---

## 7. Plugins & Custom Modules

### 7.1 WordPress Plugins Added This Sprint

#### NI WooCommerce Custom Order Status

**Purpose:** Extends WooCommerce to support custom order statuses beyond the native set. Required to register and activate the following statuses: `Preparing`, `Delivery`, `Delivered`, `Failed`, and `Refunded` — all of which are needed to represent the Printly fulfilment lifecycle.

- **Configuration location:** `WooCommerce → Settings → Custom Statuses` (via plugin menu in `wp-admin`).
- These statuses are visible to customers on the **My Account → Orders** page.

### 7.2 Odoo Modules

No new Odoo modules were added in this sprint beyond the pre-existing vendor tech integration module.

#### Rejected Module Proposal — Custom Odoo Status Automation Module

A proposal was made to create a minimal custom Odoo module to automate the data entry of:

- Creating new order statuses in Odoo's Sales module.
- Mapping them in the integration module.
- Creating a new field definition to prevent inventory tracking on synced product templates.

**This was rejected.** The time cost for a developer to build and maintain this module exceeds the time for a functional analyst to perform the same configuration manually through Odoo's UI. The functional team handles this configuration directly — no custom module required.

---

## 8. Open Tasks & Known Issues

### 8.1 Blocked — Requires Client Clarification

|#|Affects|Question|Blocked Steps|
|---|---|---|---|
|Q1|Delivery failure & billing|Will one delivery PO ever need to cover multiple SOs (batch delivery)? If yes, where should delivery failure state and financial close-out be tracked — PO level or SO level?|Steps 2.2, 3|
|Q2|Customer rejection|Can the customer reject a product only _after_ it is marked `delivered` (post-delivery via website), or must they validate it _physically during handoff_ in front of the delivery vendor?|Step 2.3|
|Q3|Attachment formats|Which file formats do customers actually use in the Libyan market for design uploads — all of PDF, SVG, PNG, JPEG, or a subset?|Attachment sync task|

### 8.2 Development Tasks

|System|Type|Description|
|---|---|---|
|WordPress|🐛 Bug|Restrict checkout to Libya only — remove all international countries from the address/account form|
|WordPress|🐛 Bug|Error message at checkout is invisible — font colour matches the background; change to white|
|WordPress|🐛 Bug|Investigate Tlync payment failure on staging — payment fails and order is never created|
|WordPress|⚡ Performance|Investigate excessive asset loading on page load (~30 s delay) — identify and remove unused assets|
|Odoo + WP|✨ Feature|Sync order attachments from WooCommerce to Odoo (pending format confirmation — see Q3 above)|
|Odoo|🧹 Cleanup|Remove `On Hold` status from both Odoo and WooCommerce — status was scrapped; requires its own dedicated task|
|Odoo|✨ Feature|Implement Steps 0 → 2.1 automation chain (current sprint)|
|Odoo|✨ Feature|Implement Steps 2.2 → 3 automation chain (pending resolution of Q1 & Q2)|

---

## 9. Architectural Decisions & Rationale

### SO status field is separate from Odoo's native SO state

Odoo's native SO states (`draft`, `sale`, `done`, `cancel`) reflect the commercial lifecycle of the order. The custom **SO status field** (`processing`, `preparing`, `delivery`, `delivered`, etc.) reflects the **operational fulfilment stage** and is the field synced with WooCommerce. Both coexist on the same SO record. This separation avoids overloading Odoo's native state machine with business-specific statuses that have no meaning in standard Odoo workflows.

### Full-charge payment reservation (not pre-auth hold)

Printly opted for a **full charge at checkout** rather than a card pre-authorisation hold. The payment sits reserved in an Odoo accounting journal entry and is released only upon successful delivery. This was chosen for simplicity given the Tlync gateway's available capabilities in the Libyan market.

### SO is confirmed immediately on import — never left as a quotation

When the vendor tech module imports an order from WooCommerce, the resulting Odoo SO is **confirmed automatically**. It is never left in draft/quotation state. This is intentional: the payment has already been collected, so there is nothing for Printly staff to manually approve on the SO itself. Vendor selection (for multi-vendor products) is the only manual step, and it happens on the already-confirmed SO.

### Delivery failure and financial close-out deferred pending scalability decision

Steps 2.2 and 3 are deferred because the current design (tracking state changes on the SO) assumes a 1-to-1 relationship between a delivery PO and an SO. A future requirement to support **one delivery PO for multiple SOs** (batch delivery runs) would break this assumption. Rather than implement a design that may need to be torn out, both steps are held until the client confirms the delivery PO model.

### Entire order flagged on partial printing vendor rejection

If any printing vendor in a multi-vendor order rejects their PO, the **whole order is flagged** rather than partially fulfilled. This avoids complexity in payment splitting, invoicing, and customer communication in the first iteration.

### No `On Hold` status

The `On Hold` status was included in early planning but scrapped before implementation. It had no defined automation and added unnecessary complexity. It must be removed from both systems via a dedicated cleanup task.

### No custom Odoo module for status configuration

A proposed custom module to automate functional configuration was rejected in favour of manual configuration by the functional team. The developer cost outweighed the time saved, and it reinforces the principle of preferring native platform capabilities over custom code wherever possible.

### Vendor portal analysis deferred

Full analysis and customisation of the Odoo vendor portal has been deferred to a future sprint. Current sprint work assumes vendors can access the native Odoo portal with minimal customisation.

---

## 10. Glossary

|Term|Definition|
|---|---|
|**SO**|Sales Order — the order record in Odoo representing the customer's purchase|
|**PO**|Purchase Order — created in Odoo for a vendor (printing or delivery) to fulfil part of the order|
|**RFQ**|Request for Quotation — the initial unconfirmed state of a PO in Odoo, before the vendor accepts|
|**Native SO state**|Odoo's built-in order state (`draft`, `sale`, `done`, `cancel`) — separate from the custom SO status field|
|**Custom SO status field**|A separate field on the Odoo SO that tracks the operational fulfilment stage and is synced to WooCommerce (`processing`, `preparing`, `delivery`, `delivered`, `cancelled`, `failed`, `refunded`)|
|**Vendor Tech Module**|Third-party Odoo module that polls WooCommerce every 15 min and syncs orders into Odoo|
|**Tlync**|The online payment gateway used at WooCommerce checkout (Libyan market)|
|**Payment Reservation**|A full charge held in an Odoo accounting journal entry, not released until delivery is complete|
|**Printing Vendor**|The vendor responsible for physically printing the customer's order (mugs, flags, paper, etc.)|
|**Delivery Vendor**|The vendor responsible for picking up the printed items and delivering them to the customer|
|**Vendor Portal**|The Odoo web portal where vendors log in to view, accept, reject, and update their assigned orders|
|**NI WooCommerce Custom Order Status**|WordPress plugin used to register custom order statuses beyond WooCommerce's native set|
|**Failed Orders Model**|A dedicated Odoo data model (provided by vendor tech) that logs orders that failed to sync, with retry capability|

---

_End of Document — Printly Platform Onboarding Analysis v1.1 · Internal Use Only_