---
type: "project"
id: "proj_printly_progress"
title: "Printly Progress Analysis"
status: "active"
priority: "high"
client: "Printly"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


# Done tasks
Note: all done tasks are FUNCTIONAL. 
1. Sale order
	- added new sale order statuses that are synced across WordPress and odoo. These new order statuses help with state management in odoo (will be used for automation) and tracking progress of the order from zero to hero
	- added a new plugin for WordPress to help create new custom sale order statuses (free)
2. User login
	- analyzed and disabled OTP service to allow for staging demo customers to login and create new accounts (MUST BE REVERTED IN PRODUCTION) (wordpress)
3. Products
	- added a new field definition and field synchronization to toggle off the 'track inventory' boolean across any created product template (printly has no inventory as they are acting as a middle man between customers, real printing providers, and real shipping providers). This requires python knowledge, and maybe open a subtask to auto create the 2 records.
4. Payment
	- toggled test mode for staging in tlync payment gateway to prevent real transactions (failed to auth for some reason, requires further investigation)
# On going tasks
1. Helpdesk (all technical tasks)
	- writing automation for certain **sale order status** to trigger the creation of tickets (full documentation the road map task/subtask)
	- writing automations for certain **time delays** to trigger the creation of tickets
2. Payment (all functional tasks)
	- remove 'cash on delivery' payment option
# future work
1. Investigate why font color and and background color are identical in WordPress checkout page (unreadable text)
2. Investigate why WordPress is fetching too many requests (images and js pulled to the browser) and only 1% of the asset is realistically used (all across the customers website) which causes 30+ sec to load 1 full page
3. Sale order status field should be set to read-only, and replace it with a button to prevent users from go-back in the order workflow and ensure one-way workflow for the sale order
4. Automate certain actions to be triggered when the sale order status is changed (inherit the on going task). This includes confirming the SO, creating/confirming invoice, creating/confirming delivery, creating/confirming payment, and creating/confirming tickets