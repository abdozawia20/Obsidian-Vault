---
type: "project"
id: "proj_printly_functional_docs"
title: "Printly Functional Documentation"
status: "active"
priority: "medium"
client: "Printly"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---



### In Scope

- Mapping the source of existing non-standard order statuses (e.g., Quote-related statuses).
- Identifying configuration locations for order statuses within the `wp-admin` control panel and odoo.
- Steps to implement custom fulfillment-related statuses (e.g., _In Delivery_, _Delivered_) using both plugin-based.

### Out of Scope

- Custom payment gateway integration mappings.
- Modifications to core WooCommerce database tables beyond native Hooks/APIs (already handled using vendor tech's module documentation).
- Third-party shipping carrier API synchronizations.
- Product image/attachment synchronization between odoo and woocommerce
# Newly added plugins (wordpress)
- Ni Woocommerce Custom Order Status
  Justification: needed to allow woocommerce to have new order statuses (used to add delivery/delivered) to meet printly business requirements
# Newly added modules (odoo)
- N/A as of writing this analysis document.
- REJECTED MODULE: create a minimalist custom module to automate the functional data entry of:
	- Creating 3 new 'Order Status' in odoo's Sales module & the custom integration module then map them
	- Create new 'Field Definition' for the vendor tech module that will help sync product templates to not track inventory

# Current Q/A
### Sale order status automation
***Vendor tech's customization allow for automating workflows (non customizable) `when setting different` states for the sale order. Are there any specified workflow requirement for each stage of the sale order?***
### Answer:
a new task was opened internally containing the answer. Check the sub-tasks of the project's roadmap

### Support Ticket triggers
***What are the conditions for triggering the support tickets? And are there already such features prebuilt in Odoo that can help me identify the functional tasks for creating tickets based on events as a whole? (timebased & action based)***
### Answer
1. Trigger conditions:
	1. timebased
		1. vendor delay to accept
		2. vendor delay to print
	    3. delivery delay to pickup
	    4. delivery delay to deliver
	2. Actions based
	    1. vendor rejects
	    2. delivery rejects to pickup
	    3. Client rejects to receive
2. Odoo prebuilt feature for auto tickets generation
	No prebuilt logic exists. Technical customization is required



### Side-tasks:
- Wordpress: remove countries from change account detailed as printly provides services on in Libya, not internaltionally
- calls between odoo & wordpress: sync attachments from wordpress to odoo (there are 4 possible formats, the client didn't confirm which format is used in the market yet)
- wordpress:  error message on checkout should be in a diff font color (white) as the current font color is identical to the background color, which 'hides' the text using illusions
- wordpress: invistigate tlync payment error in staging (payment fails, and order doesn't get created)
- wordpress: investigate why alot of unneeded asset are being pulled when accessing any page (30 secs delay!)
- order state should trigger actions (tickets/payment/invoice/delivery creation & confirmation)