# Domain 08 — Reporting: Implementation Plan

> **Variant**: Base
> **Domain**: Reporting
> **Sequence**: 8 of 8
> **Depends on**: All previous domains (data sources)
> **Functional Refs**: [[frappe-functional|Frappe]] · [[web-functional|Web]] · [[flutter-functional|Flutter]]

---

## 1. Overview

This domain provides **management visibility** into the rental business. Operators need to know: How many assets are occupied? How much revenue came in this month? Which invoices are overdue and by how long? What's the ROI on each asset? How many leads are converting to actual bookings?

The domain delivers this through **Frappe Script Reports** (data tables with filters), a **Desk Dashboard** (number cards and quick links), a **monthly automated email** summarizing key metrics, and **Flutter chart widgets** for the mobile experience. All reports respect role-based permissions — only Rental Managers and System Managers can access sensitive financial data.

---

## 2. Frappe — Script Reports

### 2.1 Occupancy Report

> **Requires**: D04-2.1 (Rental Asset with `status`), D05-2.1 (Rental Agreement)

The **occupancy report** answers the most basic landlord question: "How full are my assets?" It groups assets by type (Flat/Vehicle) and counts how many are Rented vs. Available vs. Maintenance. The occupancy rate is the key metric: `rented / total_active * 100`. Retired assets are excluded from the calculation (they're permanently out of service).

| Item | Detail |
|---|---|
| File | `rental_core/report/occupancy_report/occupancy_report.py` |
| Columns | `asset_type`, `total_assets`, `rented`, `available`, `maintenance`, `occupancy_rate_pct` |
| Filters | Asset Type (optional), Location (optional) |
| Permissions | Rental Manager, System Manager |

```python
def execute(filters=None):
    asset_filters = {"is_active": 1}
    if filters.get("asset_type"):
        asset_filters["asset_type"] = filters["asset_type"]
    if filters.get("location"):
        asset_filters["location"] = ["like", f"%{filters['location']}%"]
    assets = frappe.get_all("Rental Asset", filters=asset_filters, fields=["status", "asset_type"])
    # Group by asset_type and compute rates...
```

**Acceptance Criteria**:
- [ ] Report runs from Frappe Desk without errors
- [ ] `occupancy_rate_pct` = `rented / total_assets * 100`, rounded to 1 decimal
- [ ] Asset type filter correctly scopes results (e.g., only Flats)
- [ ] Location filter is case-insensitive and uses `LIKE` matching
- [ ] `Retired` assets are excluded from the count
- [ ] Only `Rental Manager` and `System Manager` can access (other roles get permission error)

---

### 2.2 Revenue Report

> **Requires**: ERPNext Sales Invoice, D05-2.1 (Rental Agreement for linking)

The **revenue report** tracks financial performance over time: how much was invoiced, how much was actually collected, and what's still outstanding. Data is grouped by **month** within a date range, so operators can spot trends ("collection rate dropped in March"). Months with zero revenue still appear as rows (not omitted) to make gaps visible. The Accountant role has access to this report.

| Item | Detail |
|---|---|
| File | `rental_core/report/revenue_report/revenue_report.py` |
| Columns | `month`, `total_invoiced`, `total_received`, `total_outstanding`, `collection_rate_pct` |
| Filters | Date range, Asset Type (optional) |
| Permissions | Rental Manager, Accountant, System Manager |

**Acceptance Criteria**:
- [ ] Report groups data by month within the selected date range
- [ ] `total_invoiced` = sum of `grand_total` for submitted invoices in that month
- [ ] `total_received` = sum of `paid_amount` for those invoices
- [ ] `total_outstanding` = `total_invoiced - total_received`
- [ ] `collection_rate_pct` = `total_received / total_invoiced * 100`, rounded to 1 decimal
- [ ] Asset type filter scopes to invoices linked to agreements with that asset type
- [ ] Empty date range returns validation error
- [ ] Months with zero revenue appear as rows with all zeros (not omitted)
- [ ] Accountant can access this report

---

### 2.3 Overdue Aging Report

> **Requires**: ERPNext Sales Invoice, D06-3.1 (late fee tracking)

The **overdue aging report** shows which invoices are unpaid and for how long. Invoices are bucketed into aging ranges: 0-15 days (warning), 15-30 days (concern), 30-60 days (serious), and 60+ days (critical/legal). This directly maps to the escalation tiers in D07 and helps the Rental Manager prioritize collection efforts. The report also shows whether a late fee has been applied, catching any invoices that slipped through.

| Item | Detail |
|---|---|
| File | `rental_core/report/overdue_aging/overdue_aging.py` |
| Columns | `customer`, `invoice`, `due_date`, `outstanding_amount`, `days_overdue`, `aging_bucket`, `late_fee_applied` |
| Filters | Aging bucket (optional: 0-15, 15-30, 30-60, 60+), Customer (optional) |
| Permissions | Rental Manager, Accountant, System Manager |

**Acceptance Criteria**:
- [ ] Only shows invoices where `outstanding_amount > 0` and `due_date < today`
- [ ] `days_overdue` = `today - due_date` in days
- [ ] `aging_bucket` computed: `0-15`, `15-30`, `30-60`, `60+`
- [ ] Aging bucket filter correctly scopes results
- [ ] `late_fee_applied` shows Yes/No based on `custom_late_fee_applied` field
- [ ] Sorted by `days_overdue` descending (worst first)
- [ ] Paid invoices NEVER appear (even if late)

---

### 2.4 Asset ROI Report

> **Requires**: D04-2.1 (`acquisition_cost` field), ERPNext Sales Invoice, D05-2.1 (agreement dates)

The **ROI report** answers: "Is each asset profitable, and when will it pay for itself?" For each asset, it computes total revenue (all paid invoices), total expenses (maintenance + write-offs), net income, and ROI percentage. The `months_to_breakeven` metric tells the operator how long until the asset's acquisition cost is recovered at the current earnings rate. Assets without an `acquisition_cost` show "N/A" for ROI calculations.

| Item | Detail |
|---|---|
| File | `rental_core/report/asset_roi/asset_roi.py` |
| Columns | `asset`, `acquisition_cost`, `total_revenue`, `total_expenses`, `net_income`, `roi_pct`, `months_to_breakeven` |
| Filters | Asset Type (optional), Date range |
| Permissions | Rental Manager, System Manager |

**Acceptance Criteria**:
- [ ] `total_revenue` = sum of all paid invoices linked to agreements for this asset
- [ ] `total_expenses` = sum of maintenance costs + late fee write-offs (placeholder for child app costs)
- [ ] `net_income` = `total_revenue - total_expenses`
- [ ] `roi_pct` = `net_income / acquisition_cost * 100` (0 if no acquisition cost)
- [ ] `months_to_breakeven` = `acquisition_cost / (net_income / months_active)` rounded up
- [ ] Assets with `acquisition_cost = 0` show "N/A" for ROI and breakeven
- [ ] Date range scopes revenue to invoices within that period

---

### 2.5 Legal Case Summary Report

> **Requires**: D07-4.2 (Legal Case DocType)

A **litigation tracking report** that lists all Legal Case records created by the escalation engine (D07-4.1). It shows the customer, agreement, total outstanding amount, days open, and status. Sorted by `total_outstanding` descending so the highest-value cases are at the top. This report is restricted to Rental Managers and System Managers — Accountants cannot access it because Legal Case data is sensitive.

| Item | Detail |
|---|---|
| File | `rental_core/report/legal_case_summary/legal_case_summary.py` |
| Columns | `case_name`, `customer`, `agreement`, `total_outstanding`, `escalation_date`, `status`, `days_open` |
| Filters | Status (optional), Date range |
| Permissions | Rental Manager, System Manager |

**Acceptance Criteria**:
- [ ] Lists all Legal Case records matching filters
- [ ] `days_open` = `today - escalation_date` for open cases
- [ ] Status filter: `Open`, `In Progress`, `Resolved`, `Closed`
- [ ] Sorted by `total_outstanding` descending (highest first)
- [ ] Accountant CANNOT access this report

---

### 2.6 Lead Conversion Funnel Report

> **Requires**: D02-2.1 (Rental Lead), D02-3.1 (Rental Quotation), D05-2.1 (Rental Agreement)

The **lead funnel report** tracks the sales pipeline: how many leads came in, how many converted to quotations, and how many ultimately became rental agreements. Data is grouped by **lead source** (Web Form, Mobile App, Walk-In, Phone, Referral) so the operator can see which channels are most effective. The conversion rate helps justify marketing spend and identify underperforming channels.

| Item | Detail |
|---|---|
| File | `rental_core/report/lead_conversion_funnel/lead_conversion_funnel.py` |
| Columns | `source`, `total_leads`, `quotation_generated`, `converted_to_agreement`, `conversion_rate_pct` |
| Filters | Date range |
| Permissions | Rental Manager, System Manager |

**Acceptance Criteria**:
- [ ] Groups leads by `source` (Web Form, Mobile App, Walk-In, Phone, Referral)
- [ ] `quotation_generated` = count of leads where `converted_to` is not null
- [ ] `converted_to_agreement` = count of leads where the linked quotation has a Rental Agreement
- [ ] `conversion_rate_pct` = `converted_to_agreement / total_leads * 100`, rounded to 1 decimal
- [ ] Date range scopes by lead `creation` date
- [ ] Source with zero leads is omitted (not shown as zero row)
- [ ] Rental Agent CANNOT access this report

---

## 3. Frappe — Desk Dashboard

### 3.1 Rental Manager Dashboard

> **Requires**: 2.1–2.6 (all reports), D04-2.1 (asset counts), D06-4.1 (deposit data)

A **Frappe Desk dashboard page** that provides an at-a-glance overview of the rental business. It uses **Number Cards** (large, colored count displays) for the most critical metrics: active agreements, overdue invoices, occupancy rate, pending KYC reviews, and open legal cases. Quick links below the cards let the manager jump directly to the relevant report for drill-down. The dashboard must load within 3 seconds even with 1000+ records.

Dashboard page in Frappe Desk with Number Cards and Quick Links.

**Number Cards**:
| Card | Query | Color |
|---|---|---|
| Total Active Agreements | `count(Rental Agreement where status=Active)` | Blue |
| Overdue Invoices | `count(Sales Invoice where outstanding > 0 and due_date < today)` | Red |
| Occupancy Rate | `count(Rental Asset where status=Rented) / count(where is_active=1) * 100` | Green |
| Pending KYC Reviews | `count(Customer KYC Submission where kyc_status=Pending Review)` | Orange |
| Open Legal Cases | `count(Legal Case where status in (Open, In Progress))` | Red |

**Quick Links**:
- Occupancy Report
- Revenue Report
- Overdue Aging
- Lead Conversion Funnel

**Acceptance Criteria**:
- [ ] Dashboard accessible from Frappe Desk sidebar under "Rental" module
- [ ] All 5 number cards render with correct counts
- [ ] Number cards refresh on page load (not cached)
- [ ] Quick links navigate to the correct report pages
- [ ] Only `Rental Manager` and `System Manager` can see this dashboard
- [ ] Dashboard loads within 3 seconds with 1000+ records in database

---

## 4. Frappe — Monthly Automated Report Email

### 4.1 `generate_monthly_report` Scheduler Job

> **Requires**: 2.1-2.6 (all reports), D01-2.3 (hooks.py monthly scheduler)

An **automated monthly email** sent on the 1st of each month to all Rental Managers and System Managers. It summarizes the previous month's key metrics: occupancy summary, total revenue and collection rate, and overdue invoice count. The email uses a branded HTML template. This ensures management stays informed even if they don't regularly log in to the Desk dashboard.

```python
def generate_monthly_report():
    occupancy = execute_occupancy_report({})
    revenue = execute_revenue_report({"from_date": first_day_of_last_month, "to_date": last_day_of_last_month})
    aging = execute_overdue_aging({})
    # Build HTML summary
    html = render_template("rental_core/templates/emails/monthly_report.html", {
        "occupancy": occupancy, "revenue": revenue, "aging": aging,
        "month": last_month_name, "year": last_month_year,
    })
    frappe.sendmail(
        recipients=get_rental_managers(),
        subject=f"Rental Report – {last_month_name} {last_month_year}",
        message=html,
    )
```

**Acceptance Criteria**:
- [ ] Email sent on the 1st of each month with data from the previous month
- [ ] Email contains: occupancy summary, revenue total, overdue count
- [ ] Sent to all users with `Rental Manager` or `System Manager` role
- [ ] Email renders correctly in major email clients
- [ ] Scheduler failure logged but does not crash other monthly jobs

---

## 5. Frappe — Webhook Log Purge

### 5.1 `purge_old_webhook_logs` Scheduler Job

> **Requires**: D06-6.2 (Payment Webhook Log), D01-3.1 (`webhook_log_retention_months`)

Webhook logs grow indefinitely if not cleaned up. This **monthly scheduler job** deletes `Payment Webhook Log` entries older than the configured retention period (default 13 months — just over a year, which satisfies most audit requirements). Even unprocessed (stale) logs are purged past retention because they're no longer actionable. The count of deleted logs is written to Frappe's error log for audit verification.

```python
def purge_old_webhook_logs():
    config = frappe.get_single("Rental Configuration")
    months = config.webhook_log_retention_months or 13
    cutoff = add_months(today(), -months)
    frappe.db.delete("Payment Webhook Log", {"created_at": ["<", cutoff]})
```

**Acceptance Criteria**:
- [ ] Logs older than `webhook_log_retention_months` are deleted
- [ ] Default retention is 13 months when not configured
- [ ] Unprocessed logs (processed=0) are also purged if past retention (they are stale)
- [ ] Purge runs monthly without error when no old logs exist
- [ ] Count of deleted logs is written to Frappe's error log (for auditing)

---

## 6. Flutter — Dashboard & Charts

### 6.1 Dashboard Provider

> **Requires**: D01-8.6 (FrappeClient), 7.1-7.3 (API summary endpoints or custom dashboard API)

A Riverpod provider that fetches **summary metrics** for the Flutter home screen: active agreement count, overdue invoice count, occupancy percentage, and next payment details. The data is cached (`keepAlive: true`) to prevent unnecessary re-fetches on navigation. Pull-to-refresh forces a cache invalidation.

**Acceptance Criteria**:
- [ ] Provider fetches summary data: active agreements count, overdue count, occupancy %, next payment
- [ ] Data cached with `keepAlive: true`
- [ ] Pull-to-refresh invalidates cache

---

### 6.2 Home Screen Dashboard Cards

> **Requires**: 6.1 (dashboard provider), D01-8.3 (screen stubs)

Three **tappable metric cards** on the Flutter home screen: "Active Rentals" (count), "Next Payment" (amount + due date), and "Overdue" (count with red warning styling). Each card navigates to the relevant detail screen when tapped. These give the customer (or staff on mobile) an instant financial snapshot.

**Acceptance Criteria**:
- [ ] "Active Rentals" card shows count
- [ ] "Next Payment" card shows amount and due date
- [ ] "Overdue" card shows count with warning styling (red background)
- [ ] Cards are tappable — navigate to relevant detail screens

---

### 6.3 Revenue Chart Widget

> **Requires**: D01-8.2 (`fl_chart` dependency), 6.1 (data provider)

A **bar chart** showing the last 6 months of revenue data. Each month shows invoiced vs. received amounts (either side-by-side bars or stacked). This gives the manager a visual trend of collection performance over time. The widget handles loading states (shimmer skeleton) and empty states ("No revenue data yet").

```dart
class RevenueChartWidget extends ConsumerWidget {
  // Uses fl_chart to render bar chart of monthly revenue
}
```

**Acceptance Criteria**:
- [ ] Bar chart shows monthly revenue for last 6 months
- [ ] X-axis: month names; Y-axis: amount
- [ ] Bars show invoiced vs received (side-by-side or stacked)
- [ ] Loading skeleton while data fetches
- [ ] Empty state when no revenue data exists

---

### 6.4 Occupancy Donut Chart

> **Requires**: D01-8.2 (`fl_chart` dependency), 6.1

A **donut/pie chart** visualizing the asset status distribution: Rented (green), Available (blue), Maintenance (orange), Retired (gray). The center of the donut shows the overall occupancy percentage. A legend below the chart labels each segment. This gives the manager a quick visual read on portfolio utilization.

**Acceptance Criteria**:
- [ ] Donut/pie chart shows: Rented vs Available vs Maintenance vs Retired
- [ ] Each segment has distinct color from the theme
- [ ] Center text shows overall occupancy percentage
- [ ] Legend shown below the chart

---

## 7. Flutter — Report Deep Links

### 7.1 Report Navigation

> **Requires**: D01-8.9 (GoRouter)

The **deep link navigation** from dashboard cards to detail screens. Tapping a card doesn't just go to a generic screen — it navigates to the specific context: "Active Rentals" → My Rentals screen, "Overdue" → Invoices screen pre-filtered to overdue only, "Next Payment" → Payment screen for that specific invoice.

**Acceptance Criteria**:
- [ ] Tapping "Active Rentals" card → navigates to My Rentals screen
- [ ] Tapping "Overdue" card → navigates to Invoices screen filtered to overdue
- [ ] Tapping "Next Payment" card → navigates to Payment screen for that invoice

---

## 8. Domain-Level Acceptance Criteria

- [ ] All 6 Script Reports run without error from Frappe Desk
- [ ] Report data is accurate against known test data set
- [ ] Dashboard number cards match report totals
- [ ] Monthly email sent with correct data
- [ ] Webhook log purge respects retention period
- [ ] Flutter charts render correctly with test data
- [ ] Permission restrictions enforced on all reports

---

## 9. Estimated Effort

| Layer | Effort |
|---|---|
| Frappe (6 reports + dashboard + monthly email + purge job) | 4 days |
| Web (N/A — reports are Desk-only, email is template) | 0.5 days |
| Flutter (dashboard cards + 2 charts + deep links) | 2.5 days |
| **Total** | **7 days** |
