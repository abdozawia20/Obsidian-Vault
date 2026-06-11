---
type: "project"
id: "proj_printly_odoo_tasks"
title: "Printly Odoo Implementation Tasks"
status: "active"
priority: "high"
client: "Printly"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


# Printly — Odoo Module Implementation Task Plan
## Steps 0 → 2.1 | Phased by Module

> **Version:** 1.1 · June 2025 · Internal · Confidential
> **Changelog:** v1.1 — Vendor tech inspection tasks extracted into Phase 0. All subsequent phases renumbered. Task 2.2 (vendor tech verification) removed from Phase 2 — superseded by Phase 0. Cross-phase vendor tech checklist removed — fully replaced by Phase 0 tasks.
> **Estimates:** Senior developer. Hours cover implementation + local testing only. Functional team staging validation is not included in estimates.
> **Testing flow:** Developer tests locally → merges to staging → functional team validates on staging before merge to main.
> **Prerequisite reading:** Printly Odoo Module Implementation Plan v1.0

---

## Overview

| Phase | Module | Total Hours | Unlocks |
|---|---|---|---|
| **0** | Vendor Tech Inspection | **5 h** | Unblocks all implementation phases. No code written. |
| 1 | `printly_base` | 6 h | Foundation for all other modules |
| 2 | `printly_accounting` | 8.5 h | Step 0 — Payment reservation |
| 3 | `printly_sales` | 12 h | Steps 1, 1.1, 1.3 — SO transitions, cancellation, timeout |
| 4 | `printly_purchase` | 14 h | Steps 1.2, 2, 2.1 — PO flows, delivery PO, pickup timeout |
| 5 | `printly_portal` | 8 h | Steps 1.2, 2 via vendor portal |
| | **Total** | **53.5 h** | |

> ⚠️ **Phase 0 is a hard gate.** No implementation phase may begin until Phase 0 is fully complete and all findings are documented. Discoveries in Phase 0 may require revisions to later phases before work on them begins.

---

## Phase 0 — Vendor Tech Inspection

> **Total: 5 h**
> **Prerequisites:** Vendor tech modules installed on local Odoo 19 instance. Source code accessible. No Printly modules written yet.
> **Unlocks:** Every subsequent phase. Findings from this phase are the ground truth that all implementation decisions are built on.
> **Output:** A `VENDOR_TECH_NOTES.md` file committed to the repository root before any implementation begins. This file is the single authoritative reference for vendor tech integration points.

The purpose of this phase is to eliminate all assumptions about vendor tech's internal behaviour before a single line of Printly code is written. Every place where the implementation plan says "assumed" or "verify in source" is resolved here. If a finding contradicts an assumption in the plan, the affected phase must be revised before that phase begins — not during it.

---

### Task 0.1 — Inspect SO confirmation flow

**Duration:** 1 h
**Prerequisites:** None.

**Description:**
Open the vendor tech source and locate the code path that runs when a WooCommerce order is imported into Odoo. Trace it fully until the SO is confirmed.

Answer the following definitively:

1. Does vendor tech call the standard `sale.order.action_confirm()` to confirm the SO, or does it use a custom method? If custom, what is the method name and which model is it on?
2. At what point in the import flow is the SO confirmed — immediately on creation, or after a separate step?
3. Does vendor tech write any fields on the SO during or after confirmation that could conflict with Printly writing `sub_status_id` in the same transaction? List any fields written.
4. What is the exact technical name of the `sub_status_id` field as declared in the vendor tech source? Is it a `Many2one` (to which model?) or a `Selection` field?
5. What is the stored key/ID value for the `preparing` status — i.e. what exact value must Printly write to `sub_status_id` to set the order to `preparing`? Repeat for `processing` and `delivery`.

Document all findings in `VENDOR_TECH_NOTES.md` under a `## SO Confirmation` section.

**Acceptance criteria:**
- [ ] The exact method vendor tech calls to confirm the SO is identified and named.
- [ ] The `sub_status_id` field type (Many2one or Selection) is confirmed.
- [ ] The stored key/ID values for `processing`, `preparing`, and `delivery` are all documented.
- [ ] Any fields written by vendor tech during confirmation that overlap with Printly's intended writes are flagged with a note on how to handle the conflict.

---

### Task 0.2 — Inspect payment import and posting flow

**Duration:** 1.5 h
**Prerequisites:** None (can run in parallel with Task 0.1).

**Description:**
Locate the code path in vendor tech that handles the WooCommerce payment — from the moment it is received via polling to the moment it exists as a confirmed record in Odoo.

Answer the following definitively:

1. Does vendor tech create an `account.payment` record for the WooCommerce payment, or does it use a different model (e.g. a custom payment model, or a journal entry directly)?
2. If it creates an `account.payment`, does it call `action_post()` to post it? Or does it use a different method to confirm/validate the payment?
3. Does vendor tech link the payment record back to the originating SO? If yes:
   - What is the exact field name used for this link on `account.payment`?
   - Is it a Many2one, a Char reference, or something else?
4. If vendor tech does NOT link the payment to the SO, what information is available on the payment record that could be used to resolve the relationship at runtime (e.g. `ref`, `communication`, `sale_id`, SO name in memo)?
5. Is the payment created before or after the SO is confirmed? Does the order matter for Printly's reservation hook?
6. Does vendor tech perform any accounting entries of its own at payment creation time that Printly's reservation logic must be aware of to avoid double-counting?

Document all findings in `VENDOR_TECH_NOTES.md` under a `## Payment Import & Posting` section.

**Acceptance criteria:**
- [ ] The exact model used for WooCommerce payments in Odoo is confirmed.
- [ ] The exact method used to post/confirm the payment is identified — this is the override point for `printly_accounting`.
- [ ] The field (or fallback strategy) linking the payment to its originating SO is documented.
- [ ] Any existing accounting entries created by vendor tech are listed so the accounting team can verify there is no double-counting conflict with the reservation entry.

---

### Task 0.3 — Inspect PO and vendor portal behaviour

**Duration:** 1 h
**Prerequisites:** None (can run in parallel with Tasks 0.1 and 0.2).

**Description:**
Locate any vendor tech code that touches `purchase.order` or the Odoo vendor portal.

Answer the following definitively:

1. Does vendor tech create or modify any `purchase.order` records as part of its WooCommerce sync? If yes, describe what it creates and under what conditions — Printly must not conflict with these.
2. Does vendor tech extend or override the Odoo vendor portal (`/my/purchase`)? If yes, list what it changes — Printly's portal templates must be written to coexist.
3. Does vendor tech define or restrict which `portal.group` a vendor user must belong to in order to see POs? This determines whether Printly needs to configure portal access or can rely on Odoo defaults.
4. Does vendor tech use `button_confirm()` anywhere on `purchase.order` in a way that could interfere with Printly's override?

Document all findings in `VENDOR_TECH_NOTES.md` under a `## Purchase Orders & Portal` section.

**Acceptance criteria:**
- [ ] Confirmed whether vendor tech creates any POs — if yes, the conditions and field values are documented so Printly's `printly_po_type` filter reliably excludes them.
- [ ] Any vendor tech portal overrides are listed with the XPath or controller paths they affect.
- [ ] Portal group requirements for vendor users are documented.

---

### Task 0.4 — Verify Odoo 19 method signatures

**Duration:** 1 h
**Prerequisites:** None (can run in parallel with Tasks 0.1–0.3).

**Description:**
Directly inspect the Odoo 19 source (not documentation — source) to confirm the method signatures for every Odoo method that Printly will call or override. Do not rely on knowledge of earlier Odoo versions.

Verify each of the following:

1. `sale.order.action_confirm()` — confirm signature, return value, and whether it iterates `self` or expects a singleton.
2. `purchase.order.button_confirm()` — same.
3. `purchase.order.button_send_rfq()` — confirm this method exists in Odoo 19 and its exact name. If renamed or removed, identify the correct replacement.
4. `account.payment.action_post()` — confirm signature and return value.
5. `account.move._reverse_moves()` — confirm the exact parameter name for passing default values to the reversal entries (`default_values_list` or otherwise).
6. `purchase.order.write()` — confirm whether overriding `write()` on `purchase.order` in Odoo 19 requires any specific handling for multi-record sets.

Document all findings in `VENDOR_TECH_NOTES.md` under a `## Odoo 19 Method Signatures` section. For any method that differs from what the implementation plan assumed, note the required change to the relevant phase.

**Acceptance criteria:**
- [ ] All six method signatures are documented with their exact Odoo 19 form.
- [ ] `button_send_rfq()` existence is confirmed — if it does not exist, the correct alternative is identified and the Phase 4 tasks are flagged for revision.
- [ ] `_reverse_moves()` parameter name is confirmed and the Phase 2 tasks are flagged for revision if it differs from the plan.
- [ ] Any method that behaves differently in Odoo 19 vs the plan's assumptions is flagged with the specific task it affects.

---

### Task 0.5 — Consolidate findings and flag plan revisions

**Duration:** 0.5 h
**Prerequisites:** Tasks 0.1–0.4 complete.

**Description:**
Review all findings in `VENDOR_TECH_NOTES.md` and produce a short summary at the top of the file listing:

1. **Confirmed assumptions** — things the plan assumed that turned out to be correct.
2. **Revised assumptions** — things the plan assumed that are wrong or different, with a note on which task(s) are affected and what needs to change.
3. **New risks identified** — anything discovered that the plan did not anticipate, with a proposed resolution.

If any revised assumptions require changes to Phase 1–5 task descriptions or acceptance criteria, those changes must be made to this document before work on Phase 1 begins. Minor wording updates can be made inline. Significant structural changes (e.g. a different override point discovered for the payment hook) should be discussed with the team before proceeding.

Commit `VENDOR_TECH_NOTES.md` to the repository.

**Acceptance criteria:**
- [ ] `VENDOR_TECH_NOTES.md` exists in the repository with all four sections populated (SO Confirmation, Payment Import & Posting, Purchase Orders & Portal, Odoo 19 Method Signatures).
- [ ] The summary at the top lists confirmed assumptions, revised assumptions, and new risks.
- [ ] Any task in Phases 1–5 affected by a revised assumption has been updated in this document before Phase 1 begins.
- [ ] The file is committed and accessible to all team members.

---

## Phase 1 — `printly_base`

> **Total: 6 h**
> **Prerequisites:** Phase 0 fully complete. `VENDOR_TECH_NOTES.md` committed. Odoo 19 dev environment running locally.
> **Unlocks:** All subsequent phases depend on this module being installed.

---

### Task 1.1 — Scaffold `printly_base` module

**Duration:** 1 h
**Prerequisites:** Phase 0 complete.

**Description:**
Create the module folder and all required scaffolding files from scratch. This is the first Printly-specific code in the codebase — no existing modules to reference.

Files to create:
- `custom_addons/printly_base/__init__.py`
- `custom_addons/printly_base/__manifest__.py` — declare dependencies on `sale`, `purchase`, `account`, `helpdesk`, and the vendor tech module. Use the exact technical module name confirmed in Phase 0.
- `custom_addons/printly_base/models/__init__.py`
- `custom_addons/printly_base/security/ir.model.access.csv` — empty with header row for now
- `custom_addons/printly_base/data/printly_config_data.xml` — empty `<odoo><data></data></odoo>` for now

Install the empty module on the local Odoo instance and confirm it loads without errors.

**Acceptance criteria:**
- [ ] Module appears in Odoo's Apps list and can be installed without errors or warnings in the log.
- [ ] No other installed module is broken after installation.

---

### Task 1.2 — Implement `PrintlyConfigSettings`

**Duration:** 2 h
**Prerequisites:** Task 1.1 complete.

**Description:**
Create `printly_base/models/printly_config_settings.py`. Extend `res.config.settings` with the two SLA timeout fields needed for the current sprint:
- `printly_printing_vendor_accept_timeout` (Integer, default 24, stored as `ir.config_parameter` key `printly.printing_vendor_accept_timeout`)
- `printly_delivery_vendor_pickup_timeout` (Integer, default 24, stored as `ir.config_parameter` key `printly.delivery_vendor_pickup_timeout`)

Also add the four go-live config parameters as `ir.config_parameter` records in `printly_config_data.xml` with empty/zero default values so they exist in the database and the functional team can find and populate them:
- `printly.delivery_vendor_partner_id`
- `printly.delivery_product_id`
- `printly.reservation_journal_id`
- `printly.reservation_account_id`

**Acceptance criteria:**
- [ ] `Settings → General Settings` shows a new "Printly" section with the two timeout fields.
- [ ] Saving a value (e.g. 48) persists it and re-opening Settings shows the saved value.
- [ ] All four `ir.config_parameter` keys exist in `Settings → Technical → System Parameters` after module install, with empty/zero defaults.

---

### Task 1.3 — Implement `PrintlyTicketMixin`

**Duration:** 3 h
**Prerequisites:** Task 1.1 complete. Functional team must confirm whether tickets will use `helpdesk.ticket` or `project.task` before this task begins.

**Description:**
Create `printly_base/models/printly_ticket_mixin.py`. Implement the `printly.ticket.mixin` abstract model with a single method `_create_printly_ticket(subject, description, related_so, related_po)`.

Extend `helpdesk.ticket` (or `project.task`) with two relational fields:
- `printly_sale_order_id` — Many2one to `sale.order`
- `printly_purchase_order_id` — Many2one to `purchase.order`

Add the corresponding `ir.model.access.csv` entries for any new models or fields introduced.

Write a brief manual test in the Odoo shell (`odoo shell`) to call `_create_printly_ticket()` directly and confirm a ticket record is created with the correct field values.

**Acceptance criteria:**
- [ ] Calling `_create_printly_ticket(subject='Test', description='Test desc')` from the Odoo shell creates a visible ticket in the helpdesk/project module.
- [ ] The ticket has `printly_sale_order_id` and `printly_purchase_order_id` fields visible on the ticket form view (even if unpopulated).
- [ ] No access errors are raised when a portal user or internal user creates a ticket via the mixin.

---

## Phase 2 — `printly_accounting`

> **Total: 8.5 h**
> **Prerequisites:** Phase 1 fully complete and installed. Phase 0 findings for payment posting confirmed — the correct override point and SO-payment link field are known before any code is written. Accounting team must create the "Printly Reserved Payments" account and journal in the chart of accounts on the local dev instance, and set `printly.reservation_journal_id` and `printly.reservation_account_id` in system parameters before Task 2.3 can be tested.
> **Unlocks:** Step 0 — payment reservation fires automatically when vendor tech posts a WooCommerce payment.

---

### Task 2.1 — Scaffold `printly_accounting` module

**Duration:** 0.5 h
**Prerequisites:** Phase 1 complete.

**Description:**
Create the module folder and scaffolding:
- `custom_addons/printly_accounting/__init__.py`
- `custom_addons/printly_accounting/__manifest__.py` — depends on `printly_base` only
- `custom_addons/printly_accounting/models/__init__.py`

Install the empty module and confirm it loads cleanly.

**Acceptance criteria:**
- [ ] Module installs without errors.
- [ ] `printly_base` is listed as a satisfied dependency.

---

### Task 2.2 — Implement `account.payment` extension and reservation logic

**Duration:** 5 h
**Prerequisites:** Task 2.1 complete. Phase 0 Task 0.2 confirmed: the exact override method and the SO-payment link field are documented in `VENDOR_TECH_NOTES.md`. Accounting team has set `printly.reservation_journal_id` and `printly.reservation_account_id` in local system parameters.

**Description:**
Create `printly_accounting/models/account_payment.py`. Extend `account.payment` (or the model confirmed in Phase 0 Task 0.2 if different) with:

- `printly_origin_so_id` — Many2one to `sale.order`
- `printly_reservation_move_id` — Many2one to `account.move`, readonly
- `printly_is_reserved` — Boolean, readonly, default False

Override the payment posting method confirmed in Phase 0 (assumed `action_post()` — use whatever was verified) to call `_printly_reserve_payment()` after `super()` for any payment where `printly_origin_so_id` is set.

If Phase 0 found that vendor tech does not link the payment to the SO via a direct field, implement the fallback resolution strategy documented in `VENDOR_TECH_NOTES.md` to populate `printly_origin_so_id` at the time of posting.

Implement `_printly_reserve_payment()`:
- Read `printly.reservation_journal_id` and `printly.reservation_account_id` from `ir.config_parameter`.
- If either is missing, call `_create_printly_ticket()` with a descriptive message and return early — do not raise a hard exception.
- Create and post the reservation `account.move` with a debit on the payment's destination account and a credit on the reservation account.
- Write `printly_reservation_move_id` and set `printly_is_reserved = True`.
- Guard against double-reservation with an early return if `printly_is_reserved` is already True.

**Acceptance criteria:**
- [ ] Manually posting a payment linked to a Printly SO (via `printly_origin_so_id`) creates a new posted `account.move` visible in the accounting journal.
- [ ] The journal entry debits the correct account and credits the reservation account for the exact payment amount.
- [ ] `printly_is_reserved` is `True` on the payment after posting.
- [ ] Posting the same payment a second time does not create a duplicate reservation entry.
- [ ] Posting a payment with no `printly_origin_so_id` (a non-Printly payment) does not create any reservation entry and does not affect normal Odoo behaviour.
- [ ] Posting a payment when `printly.reservation_journal_id` is not configured creates a helpdesk ticket and does not raise a traceback.

---

### Task 2.3 — Implement `action_printly_release_reservation()`

**Duration:** 3 h
**Prerequisites:** Task 2.2 complete. `_reverse_moves()` signature confirmed in Phase 0 Task 0.4.

**Description:**
Add `action_printly_release_reservation(refund=False)` to the `account.payment` extension.

This method:
- Returns early if `printly_is_reserved` is False or `printly_reservation_move_id` is not set.
- Calls `_reverse_moves()` on the reservation journal entry using the exact parameter name confirmed in Phase 0 Task 0.4.
- Posts the reversal.
- Sets `printly_is_reserved = False`.

Note: The actual Tlync refund to the customer is handled externally (manually by Printly staff through the gateway). This method only handles the Odoo accounting side of the release.

**Acceptance criteria:**
- [ ] Calling `action_printly_release_reservation()` on a reserved payment creates a posted reversal journal entry that zeroes out the original reservation entry.
- [ ] `printly_is_reserved` is `False` after the call.
- [ ] Calling the method on a payment that was never reserved does nothing and raises no error.
- [ ] The reversal entry is visible in the accounting journal with a clear reference linking it to the originating SO.

---

## Phase 3 — `printly_sales`

> **Total: 12 h**
> **Prerequisites:** Phase 2 fully complete and installed. Phase 0 Task 0.1 confirmed: `action_confirm()` is the SO confirmation method, `sub_status_id` field type is known, and the key values for `processing`, `preparing`, and `delivery` are documented in `VENDOR_TECH_NOTES.md`.
> **Unlocks:** Steps 1, 1.1, 1.3.

---

### Task 3.1 — Scaffold `printly_sales` module

**Duration:** 0.5 h
**Prerequisites:** Phase 2 complete.

**Description:**
Create the module folder and scaffolding:
- `custom_addons/printly_sales/__init__.py`
- `custom_addons/printly_sales/__manifest__.py` — depends on `printly_base` only
- `custom_addons/printly_sales/models/__init__.py`
- `custom_addons/printly_sales/data/printly_sales_cron.xml` — empty for now

Install and confirm clean load.

**Acceptance criteria:**
- [ ] Module installs without errors.

---

### Task 3.2 — Implement `action_confirm()` override and `sub_status_id` transition

**Duration:** 3 h
**Prerequisites:** Task 3.1 complete. Phase 0 Task 0.1 findings in hand — `sub_status_id` field type and `preparing` key value confirmed.

**Description:**
Create `printly_sales/models/sale_order.py`. Inherit `sale.order` and `printly.ticket.mixin`.

Override `action_confirm()` using the exact method signature confirmed in Phase 0 Task 0.4:
- Call `super()` first — never suppress vendor tech's confirmation logic.
- After `super()`, resolve the `preparing` sub_status record using the field type and key value confirmed in Phase 0. Write it to `sub_status_id` on each confirmed SO.
- If the `preparing` status record cannot be found, raise a clear `UserError` — this is a configuration error that must be visible, not silently skipped.

Implement `action_printly_move_to_delivery()`:
- Resolve the `delivery` sub_status record and write it to `sub_status_id`.
- This method is called by `printly_purchase` when printing is complete. Define it here even though it is not callable end-to-end until Phase 4.

**Acceptance criteria:**
- [ ] Confirming a Printly SO (simulating what vendor tech does) moves `sub_status_id` to `preparing`.
- [ ] Confirming a non-Printly SO (a regular sale order with no `sub_status_id` context) is completely unaffected.
- [ ] Vendor tech's own confirmation logic still runs in full — confirm by checking all fields vendor tech sets during confirmation are still present after the override.
- [ ] If the `preparing` status record is missing from the database, a `UserError` is raised with a clear message.

---

### Task 3.3 — Implement customer cancellation (`action_printly_customer_cancel()`)

**Duration:** 4 h
**Prerequisites:** Task 3.2 complete.

**Description:**
Add `action_printly_customer_cancel()` to the `sale.order` extension.

The method must:
1. Reject cancellation if `sub_status_id` is not `processing` — raise a `UserError` with a message that names the current status and explains the constraint.
2. Search for all linked printing POs (`printly_po_type == 'printing'`, `printly_origin_so_id == self.id`) and call `button_cancel()` on each.
3. Call `action_cancel()` on the SO itself.
4. Search for the linked `account.payment` using the link field confirmed in Phase 0 Task 0.2 and call `action_printly_release_reservation(refund=True)`.

Before implementing, clarify with the functional team how WooCommerce communicates a customer cancellation to Odoo — whether vendor tech writes a field on the SO, triggers a status update, or uses another mechanism. Wire this method to that signal and document the wiring decision as a comment in the code.

**Acceptance criteria:**
- [ ] Calling `action_printly_customer_cancel()` on an SO in `processing` status cancels all linked printing POs, cancels the SO, and releases the payment reservation.
- [ ] Calling the method on an SO in `preparing` status raises a `UserError` and makes no changes to the SO, POs, or payment.
- [ ] Calling the method on an SO with no linked payment does not raise an error — SO and POs are cancelled cleanly, and a warning is logged.
- [ ] A regular sale order (no Printly POs, no reserved payment) is not affected by a normal `action_confirm()` call.

---

### Task 3.4 — Implement printing vendor timeout cron (Step 1.1)

**Duration:** 4 h
**Prerequisites:** Task 3.2 complete. `printly.printing_vendor_accept_timeout` system parameter set to a short value (e.g. 0.01 h) for local testing.

**Description:**
Add the cron record to `printly_sales_cron.xml` and implement `_cron_check_printing_vendor_timeout()` as a model method on `sale.order`.

The cron must:
- Read `printly.printing_vendor_accept_timeout` from `ir.config_parameter` at runtime (not hardcoded).
- Find all printing POs (`printly_po_type == 'printing'`) in `draft` or `sent` state where `date_order` is older than the cutoff.
- For each, check whether an open ticket already exists for that PO — skip if one exists to prevent duplicate tickets.
- Call `_create_printly_ticket()` for each overdue PO with subject, description, related SO, and related PO populated.

Set cron interval to 1 hour in the XML.

**Acceptance criteria:**
- [ ] Manually triggering the cron (via `Settings → Technical → Scheduled Actions → Run Manually`) raises a ticket for a printing PO older than the configured timeout that has not been confirmed.
- [ ] Running the cron a second time for the same overdue PO does not create a duplicate ticket.
- [ ] A confirmed printing PO (state `purchase`) does not generate a ticket.
- [ ] A delivery PO (`printly_po_type == 'delivery'`) is not affected by this cron.
- [ ] Changing `printly.printing_vendor_accept_timeout` and re-running the cron respects the new value immediately.

---

## Phase 4 — `printly_purchase`

> **Total: 14 h**
> **Prerequisites:** Phase 3 fully complete and installed. Phase 0 Task 0.3 confirmed: vendor tech does not create conflicting POs, and the correct method for sending an RFQ in Odoo 19 is documented. `printly.delivery_vendor_partner_id` and `printly.delivery_product_id` set in local system parameters by the functional team.
> **Unlocks:** Steps 1.2, 2, 2.1.

---

### Task 4.1 — Scaffold `printly_purchase` module

**Duration:** 0.5 h
**Prerequisites:** Phase 3 complete.

**Description:**
Create the module folder and scaffolding:
- `custom_addons/printly_purchase/__init__.py`
- `custom_addons/printly_purchase/__manifest__.py` — depends on `printly_base` only
- `custom_addons/printly_purchase/models/__init__.py`
- `custom_addons/printly_purchase/data/printly_purchase_cron.xml` — empty for now

Install and confirm clean load.

**Acceptance criteria:**
- [ ] Module installs without errors.

---

### Task 4.2 — Add custom fields to `purchase.order`

**Duration:** 1 h
**Prerequisites:** Task 4.1 complete.

**Description:**
Create `printly_purchase/models/purchase_order.py`. Inherit `purchase.order` and `printly.ticket.mixin`.

Add:
- `printly_origin_so_id` — Many2one to `sale.order`, `ondelete='set null'`
- `printly_po_type` — Selection field with values `printing` and `delivery`

Confirm both fields are visible on the purchase order form view in the backend.

**Acceptance criteria:**
- [ ] Both fields exist on `purchase.order` and are readable/writable via the Odoo shell.
- [ ] Both fields are visible on the PO form view in the backend UI.
- [ ] Existing POs (not created by Printly) are unaffected — both fields are `False`/empty by default.

---

### Task 4.3 — Implement printing vendor RFQ creation hook (Step 1)

**Duration:** 4 h
**Prerequisites:** Task 4.2 complete. Task 3.2 complete. Phase 0 Task 0.4 confirmed the correct RFQ send method name for Odoo 19.

**Description:**
Add a `write()` override on `sale.order` in a separate file `printly_purchase/models/sale_order_purchase_hook.py` — keeping the `sale.order` extension split between modules cleanly.

The `write()` override must:
- Watch for `sub_status_id` changing to the `preparing` status value confirmed in Phase 0.
- When detected, call `_printly_create_printing_po(sale_order)`.
- Only fire if no printing PO already exists for this SO (guard against duplicate POs).

Implement `_printly_create_printing_po()`:
- Iterate over `sale_order.order_line` and resolve the vendor from `product_id.seller_ids[:1]`.
- If no seller is found, call `_create_printly_ticket()` for that line and continue — do not block the whole order.
- Create a single PO using the single vendor assumption (see note below).
- Call the RFQ send method confirmed in Phase 0 Task 0.4 to notify the vendor automatically.

> ℹ️ **Future sprint note:** Multi-vendor support (one PO per printing vendor per order) is deferred. When implemented, this method will iterate lines grouped by supplier and create one PO per supplier. The `printly_origin_so_id` field already supports this — no schema change will be required.

**Acceptance criteria:**
- [ ] Confirming a Printly SO automatically creates a printing PO in `sent` state linked via `printly_origin_so_id` and `printly_po_type = 'printing'`.
- [ ] The PO contains one line per SO order line, with product, quantity, and unit price correctly mapped from `seller_ids`.
- [ ] The PO's `origin` field references the SO name.
- [ ] Triggering the same `sub_status_id` write a second time does not create a duplicate printing PO.
- [ ] A product with no configured supplier does not block PO creation for other lines — a ticket is raised for the missing-supplier line and remaining lines proceed.
- [ ] A regular sale order confirmation does not trigger any PO creation.

---

### Task 4.4 — Implement `button_confirm()` override for printing PO (Step 1.2)

**Duration:** 1.5 h
**Prerequisites:** Task 4.3 complete. Phase 0 Task 0.4 confirmed `button_confirm()` signature.

**Description:**
Override `button_confirm()` on `purchase.order`. After calling `super()`, add a guard checking `po.printly_po_type == 'printing'`. No additional logic is needed at this step — the override is a deliberate extension point for future sprint enhancements. Document this clearly in a code comment.

**Acceptance criteria:**
- [ ] Confirming a printing PO moves it to `purchase` state as normal.
- [ ] Confirming a delivery PO or a non-Printly PO behaves identically to standard Odoo — no regressions.

---

### Task 4.5 — Implement printing complete → delivery PO creation (Step 2)

**Duration:** 4 h
**Prerequisites:** Task 4.4 complete. `printly.delivery_vendor_partner_id` and `printly.delivery_product_id` set in local system parameters.

**Description:**
Add a `write()` override on `purchase.order` watching for `state` changing to `done` on a printing PO.

When detected, call `_printly_on_printing_complete()` which:
1. Calls `so.action_printly_move_to_delivery()` (defined in Phase 3) to move the SO status to `delivery`.
2. Calls `_printly_create_delivery_po(sale_order)`.

Implement `_printly_create_delivery_po()`:
- Read `printly.delivery_vendor_partner_id` and `printly.delivery_product_id` from `ir.config_parameter`.
- If either is missing, call `_create_printly_ticket()` and return — do not raise a hard exception.
- Create the delivery PO with `printly_po_type = 'delivery'` and call the RFQ send method confirmed in Phase 0 Task 0.4.

**Acceptance criteria:**
- [ ] Manually setting a printing PO's state to `done` moves the linked SO's `sub_status_id` to `delivery`.
- [ ] A delivery PO is created automatically in `sent` state, linked to the same SO, with `printly_po_type = 'delivery'`.
- [ ] The delivery PO's `origin` field references the SO name.
- [ ] If `printly.delivery_vendor_partner_id` is not configured, a helpdesk ticket is created and no delivery PO is created — no traceback.
- [ ] Marking a non-printing PO as done does not trigger any Printly logic.

---

### Task 4.6 — Implement delivery vendor pickup timeout cron (Step 2.1)

**Duration:** 3 h
**Prerequisites:** Task 4.5 complete. `printly.delivery_vendor_pickup_timeout` set to a short value for local testing.

**Description:**
Add the cron record to `printly_purchase_cron.xml` and implement `_cron_check_delivery_vendor_timeout()` on `purchase.order`. Logic mirrors the printing vendor timeout cron in Phase 3 but targets delivery POs (`printly_po_type == 'delivery'`). Same duplicate-ticket guard applies.

**Acceptance criteria:**
- [ ] Manually triggering the cron raises a ticket for a delivery PO older than the configured timeout that has not been confirmed.
- [ ] Running the cron a second time for the same overdue delivery PO does not create a duplicate ticket.
- [ ] A confirmed delivery PO (state `purchase`) does not generate a ticket.
- [ ] A printing PO is not affected by this cron.
- [ ] Changing `printly.delivery_vendor_pickup_timeout` and re-running the cron respects the new value immediately.

---

## Phase 5 — `printly_portal`

> **Total: 8 h**
> **Prerequisites:** Phase 4 fully complete and installed. Phase 0 Task 0.3 confirmed whether vendor tech overrides the native purchase portal and what portal group configuration is required. A test printing vendor and delivery vendor exist as portal users in the local Odoo instance.
> **Unlocks:** Steps 1.2 and 2 via the vendor-facing portal.

---

### Task 5.1 — Scaffold `printly_portal` module

**Duration:** 0.5 h
**Prerequisites:** Phase 4 complete.

**Description:**
Create the module folder and scaffolding:
- `custom_addons/printly_portal/__init__.py`
- `custom_addons/printly_portal/__manifest__.py` — depends on `printly_base` and `portal`
- `custom_addons/printly_portal/controllers/__init__.py`
- `custom_addons/printly_portal/controllers/portal_vendor.py` — empty class stub
- `custom_addons/printly_portal/views/portal_vendor_templates.xml` — empty `<odoo>` wrapper

Install and confirm clean load.

**Acceptance criteria:**
- [ ] Module installs without errors.
- [ ] Existing portal pages are not broken after installation.

---

### Task 5.2 — Implement portal controller routes

**Duration:** 3 h
**Prerequisites:** Task 5.1 complete. Phase 0 Task 0.3 confirmed vendor tech portal override scope — templates are written to coexist with any vendor tech portal changes.

**Description:**
Implement the three HTTP routes in `portal_vendor.py`:

- `POST /printly/portal/po/<int:po_id>/confirm` — printing vendor confirms PO (Step 1.2).
- `POST /printly/portal/po/<int:po_id>/mark_printed` — printing vendor marks job as done (Step 2).
- `POST /printly/portal/po/<int:po_id>/confirm_pickup` — delivery vendor confirms pickup (Step 2).

Each route must:
- Verify the PO exists and has the correct `printly_po_type` — return 404 if not.
- Verify the authenticated portal user's partner matches the PO's vendor partner before calling `sudo()` — do not allow a vendor to act on another vendor's PO.
- Redirect back to the PO's portal page on success.

**Acceptance criteria:**
- [ ] A portal user who is the vendor on a printing PO can POST to `/confirm` and the PO moves to `purchase` state.
- [ ] A portal user who is the vendor on a printing PO in `purchase` state can POST to `/mark_printed` and the PO moves to `done`, triggering delivery PO creation.
- [ ] A portal user who is the delivery vendor can POST to `/confirm_pickup` and the delivery PO moves to `purchase` state.
- [ ] A portal user attempting to act on a PO belonging to a different vendor receives a 404.
- [ ] An unauthenticated user is redirected to the login page, not a 500 error.

---

### Task 5.3 — Implement portal button templates

**Duration:** 2.5 h
**Prerequisites:** Task 5.2 complete. Phase 0 Task 0.3 confirmed the XPath target in the native portal view is not overridden by vendor tech.

**Description:**
Implement `portal_vendor_templates.xml` to extend Odoo's native purchase portal PO detail view with three conditional Printly action buttons:
- **Confirm Order** — `printly_po_type == 'printing'` and `state in ['draft', 'sent']`.
- **Mark as Printed** — `printly_po_type == 'printing'` and `state == 'purchase'`.
- **Confirm Pickup** — `printly_po_type == 'delivery'` and `state in ['draft', 'sent']`.

Non-Printly POs must show no additional buttons — the native view must be visually unchanged.

**Acceptance criteria:**
- [ ] A printing vendor sees **Confirm Order** on their unconfirmed printing PO and no extra buttons elsewhere.
- [ ] After confirming, the same page shows **Mark as Printed** instead.
- [ ] A delivery vendor sees **Confirm Pickup** on their unconfirmed delivery PO and nothing extra elsewhere.
- [ ] A non-Printly PO viewed by any portal user is visually identical to pre-installation.
- [ ] Each button click triggers the correct backend action verified by resulting PO state and downstream effects.

---

### Task 5.4 — End-to-end portal flow smoke test

**Duration:** 2 h
**Prerequisites:** Tasks 5.2 and 5.3 complete. All previous phases installed and configured.

**Description:**
Run a full end-to-end flow locally using test portal users, covering Steps 0 → 2.1 in sequence:

1. Simulate vendor tech importing a WooCommerce order (manually confirm an SO with a linked payment).
2. Verify payment reservation journal entry is created (Phase 2).
3. Verify `sub_status_id` moves to `preparing` and a printing PO is created and sent (Phases 3, 4).
4. Log in as the printing vendor portal user → click **Confirm Order** → verify PO moves to `purchase` (Phase 5).
5. Verify no timeout ticket is raised before the configured window elapses.
6. Set `printly.printing_vendor_accept_timeout` to `0` and run the printing vendor timeout cron → verify ticket raised (Phase 3).
7. Log in as printing vendor → click **Mark as Printed** → verify SO moves to `delivery` and delivery PO is created and sent (Phases 4, 5).
8. Log in as delivery vendor → click **Confirm Pickup** → verify delivery PO moves to `purchase` (Phase 5).
9. Set `printly.delivery_vendor_pickup_timeout` to `0` and run the delivery vendor timeout cron → verify ticket raised (Phase 4).
10. Simulate customer cancellation (Step 1.3) on a separate SO in `processing` status → verify PO cancelled, SO cancelled, reservation released.

Document any failures with exact step, observed behaviour, and expected behaviour. Fix all failures before marking this task done.

**Acceptance criteria:**
- [ ] All 10 steps complete without errors or tracebacks in the Odoo log.
- [ ] All correct records exist in the database after each step (PO states, SO status, journal entries, tickets).
- [ ] No unintended side effects on non-Printly records at any step.
- [ ] The Odoo log is clean — no warnings or errors attributable to Printly modules during the flow.

---

## Cross-Phase Notes

### Functional team setup tasks (run in parallel with development)

These are not development tasks but must be done before functional testing can begin on staging. The functional team owns these.

| Task | Needed For | System Parameters to Set |
|---|---|---|
| Confirm `helpdesk.ticket` or `project.task` for Printly tickets | Phase 1 Task 1.3 | — |
| Create "Printly Reserved Payments" account in chart of accounts | Phase 2 testing | `printly.reservation_account_id` |
| Create "Printly Reservations" journal | Phase 2 testing | `printly.reservation_journal_id` |
| Create or confirm delivery vendor as an Odoo partner and portal user | Phase 4–5 testing | `printly.delivery_vendor_partner_id` |
| Create a "Delivery Service" product (type: Service, no inventory tracking) | Phase 4–5 testing | `printly.delivery_product_id` |
| Configure SLA timeout values | Phase 3–4 testing | `printly.printing_vendor_accept_timeout`, `printly.delivery_vendor_pickup_timeout` |

---

*End of Document — Printly Odoo Module Implementation Task Plan v1.1 · Internal Use Only*
