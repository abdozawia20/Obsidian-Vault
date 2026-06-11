---
type: "project"
id: "proj_golden_gm_erpnext"
title: "Golden-GM ERPNext Migration Plan"
status: "active"
priority: "high"
client: "Golden-GM"
created_at: 2026-06-11T18:27:40+03:00
updated_at: 2026-06-11T18:27:40+03:00
tags:
  - project
---


# Golden-GM: Odoo 18 → ERPNext v16 Implementation Plan

## Context

Golden-GM is a Libyan trading company running **Odoo 18** with three custom modules. This plan
migrates all custom functionality to a **self-hosted ERPNext v16** instance via a custom Frappe
app named `golden_gm`. The project was at staging — no production data needs migrating except
optionally users and product templates/variants.

---

## Constraints & Decisions

| Decision | Value |
|---|---|
| Target platform | ERPNext v16, self-hosted via Docker (frappe_docker) |
| Custom app name | `golden_gm` |
| PDF engine | wkhtmltopdf (same as Odoo) — port CSS as-is |
| Data migration | Minimal: users + product templates/variants only |
| Open-source modules replaced | `partner_statement`, `report_xlsx*`, `auto_database_backup` → all native in ERPNext v16 |
| Repo structure | Docker files at project root, `golden_gm/` app as Git submodule or subdirectory |

---

## Phase 0 — Docker Setup

**Goal**: Replace the existing `postgres + odoo` Docker stack with a production-ready
`frappe_docker` compose stack, plus a dev override that mirrors the current project's
`docker-compose.override.yml` pattern.

> [!NOTE]
> The current project already uses Docker Compose with a `Dockerfile` / `Dockerfile.dev` split
> and a `docker-compose.override.yml` for dev. The ERPNext stack follows the same pattern but
> uses the official `frappe_docker` images as the base.

---

### 0.1 Repository Structure

Replace the Odoo files at the project root:

```
Golden-GM/                          ← same repo root
  docker-compose.yml                ← [REPLACE] ERPNext production stack
  docker-compose.override.yml       ← [REPLACE] Dev overrides (IDE access, hot-reload)
  Dockerfile                        ← [REPLACE] golden_gm custom app image
  Dockerfile.dev                    ← [REPLACE] same + debugpy
  .env                              ← [NEW] site name, passwords, image versions
  golden_gm/                        ← [NEW] Frappe custom app (the code)
  apps.json                         ← [NEW] declares golden_gm as an app to install
  odoo_modules/                     ← [KEEP] reference only, not mounted
  odoo_data/                        ← [REMOVE] no longer needed
  odoo.conf / odoo.dev.conf         ← [REMOVE] no longer needed
```

---

### 0.2 Service Architecture

ERPNext requires more services than Odoo. The stack:

| Service | Image | Role |
|---|---|---|
| `backend` | `frappe/erpnext:v16` (custom) | Gunicorn app server |
| `frontend` | `frappe/frappe-nginx:v16` | Static assets + reverse proxy to backend |
| `websocket` | `frappe/frappe-socketio:v16` | Real-time (Socket.IO) |
| `queue_short` | same as backend | RQ worker — short jobs |
| `queue_long` | same as backend | RQ worker — long jobs |
| `scheduler` | same as backend | Beat scheduler (cron) |
| `redis_cache` | `redis:7-alpine` | Cache |
| `redis_queue` | `redis:7-alpine` | Job queue |
| `db` | `mariadb:10.6` | Database (ERPNext requires MariaDB, not Postgres) |
| `proxy` | `traefik:v2.9` | TLS termination + routing (prod) |

> [!IMPORTANT]
> ERPNext v16 requires **MariaDB**, not PostgreSQL. Your current `postgres:16.11` container
> is replaced by `mariadb:10.6`. This is a hard requirement of Frappe Framework.

---

### 0.3 `apps.json` — Declare the Custom App

#### [NEW] `apps.json`
```json
[
  {
    "url": "https://github.com/frappe/frappe",
    "branch": "version-16"
  },
  {
    "url": "https://github.com/frappe/erpnext",
    "branch": "version-16"
  },
  {
    "url": "/workspace/golden_gm",
    "branch": "main"
  }
]
```

In production, the third entry points to your Git remote (GitHub/GitLab). During development,
it mounts the local directory.

---

### 0.4 `Dockerfile` — Custom App Image

#### [REPLACE] `Dockerfile`
```dockerfile
# Build stage: install apps into the frappe image
FROM frappe/bench:latest AS builder

ARG FRAPPE_BRANCH=version-16
ARG ERPNEXT_BRANCH=version-16

USER frappe
WORKDIR /home/frappe/frappe-bench

# Install Frappe, ERPNext, and golden_gm
COPY --chown=frappe:frappe apps.json apps.json
RUN pip install frappe-bench && \
    bench init --skip-redis-config-generation \
               --frappe-branch ${FRAPPE_BRANCH} . && \
    bench get-app --branch ${ERPNEXT_BRANCH} erpnext && \
    bench get-app golden_gm /workspace/golden_gm

# ── Runtime image ─────────────────────────────────────────────────────────────
FROM frappe/erpnext:${ERPNEXT_BRANCH}

# Copy the installed apps from builder
COPY --from=builder /home/frappe/frappe-bench/apps /home/frappe/frappe-bench/apps

# Install num2words (used by golden_gm for Arabic amount-in-words)
RUN pip install num2words
```

#### [REPLACE] `Dockerfile.dev`
```dockerfile
FROM frappe/erpnext:version-16

USER root

# IDE support (Antigravity / Cursor require tar, uname, find)
RUN apt-get update && \
    apt-get install -y tar coreutils findutils && \
    rm -rf /var/lib/apt/lists/*

# Dev tools
RUN pip install num2words debugpy

USER frappe
```

---

### 0.5 `docker-compose.yml` — Production Stack

#### [REPLACE] `docker-compose.yml`
```yaml
x-backend-defaults: &backend
  image: golden-gm:latest   # built from Dockerfile
  restart: unless-stopped
  volumes:
    - sites:/home/frappe/frappe-bench/sites
    - logs:/home/frappe/frappe-bench/logs
  environment:
    - DB_HOST=db
    - DB_PORT=3306
    - REDIS_CACHE=redis_cache:6379
    - REDIS_QUEUE=redis_queue:6379
  depends_on:
    - db
    - redis_cache
    - redis_queue

services:
  backend:
    <<: *backend
    command: gunicorn-entrypoint

  frontend:
    image: frappe/frappe-nginx:version-16
    restart: unless-stopped
    volumes:
      - sites:/home/frappe/frappe-bench/sites
    ports:
      - "8080:8080"   # HTTP (traefik proxies this in prod)
    depends_on:
      - backend
      - websocket

  websocket:
    <<: *backend
    command: node /home/frappe/frappe-bench/apps/frappe/socketio.js
    ports:
      - "9000:9000"

  queue_short:
    <<: *backend
    command: bench worker --queue short,default

  queue_long:
    <<: *backend
    command: bench worker --queue long

  scheduler:
    <<: *backend
    command: bench schedule

  redis_cache:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_cache:/data

  redis_queue:
    image: redis:7-alpine
    restart: unless-stopped
    volumes:
      - redis_queue:/data

  db:
    image: mariadb:10.6
    restart: unless-stopped
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
      - --skip-character-set-client-handshake
    environment:
      MYSQL_ROOT_PASSWORD: ${DB_ROOT_PASSWORD:-secret}
      MYSQL_DATABASE: ${DB_NAME:-_frappe}
    volumes:
      - database:/var/lib/mysql
    ports:
      - "3306:3306"   # only for local admin access; remove in production

volumes:
  sites:
  logs:
  database:
  redis_cache:
  redis_queue:
```

---

### 0.6 `docker-compose.override.yml` — Dev Overrides

Mirrors the existing Odoo project pattern: different image, IDE access port, live-mounted app code.

#### [REPLACE] `docker-compose.override.yml`
```yaml
services:
  backend:
    build:
      context: .
      dockerfile: Dockerfile.dev
    command: [ "tail", "-f", "/dev/null" ]   # keep container alive for IDE attach
    ports:
      - "8000:8000"   # gunicorn (started manually inside container)
      - "5678:5678"   # debugpy
    volumes:
      - ./golden_gm:/home/frappe/frappe-bench/apps/golden_gm  # live code mount

  # Expose MariaDB on a fixed port for local DB clients (TablePlus, DBeaver)
  db:
    ports:
      - "3307:3306"

  # Silence unused services during dev (optional)
  queue_short:
    command: [ "tail", "-f", "/dev/null" ]
  queue_long:
    command: [ "tail", "-f", "/dev/null" ]
  scheduler:
    command: [ "tail", "-f", "/dev/null" ]
```

---

### 0.7 `.env` — Environment Variables

#### [NEW] `.env`
```dotenv
# Site
SITE_NAME=goldengm.local

# Database
DB_ROOT_PASSWORD=changeme
DB_NAME=_frappe

# Frappe admin
ADMIN_PASSWORD=changeme

# Image versions
FRAPPE_VERSION=version-16
ERPNEXT_VERSION=version-16
```

Add `.env` to `.gitignore` (already present for Odoo secrets).

---

### 0.8 Site Initialization

First-time setup after `docker compose up -d`:

```bash
# Create the site inside the backend container
docker compose exec backend \
  bench new-site ${SITE_NAME} \
    --mariadb-root-password ${DB_ROOT_PASSWORD} \
    --admin-password ${ADMIN_PASSWORD} \
    --install-app erpnext \
    --install-app golden_gm

# Set default site
docker compose exec backend bench use ${SITE_NAME}
```

---

### 0.9 wkhtmltopdf

The `frappe/erpnext:version-16` base image includes `wkhtmltopdf` pre-installed.
Verify inside the container:
```bash
docker compose exec backend wkhtmltopdf --version
# Should print: wkhtmltopdf 0.12.6 (with patched qt)
```

Set in ERPNext: **Print Settings → PDF Generator → wkhtmltopdf** (or leave on default).

---

### Verification (Phase 0)
- `docker compose up -d` starts all 9 services without errors
- `docker compose ps` shows all services `Up`
- `http://localhost:8080` → ERPNext login screen
- `golden_gm` listed under **Installed Apps**
- `wkhtmltopdf --version` prints v0.12.6 inside backend container
- `.env` is git-ignored; no secrets committed

---

## Phase 1 — Frappe App Scaffold & ERPNext Configuration

**Goal**: `golden_gm` app structure in place, company configured, currencies active.

### Tasks

#### [NEW] `golden_gm` app directory structure
```
golden_gm/
  golden_gm/
    __init__.py
    hooks.py                  ← event hooks (doc_events, scheduler_events)
    api.py                    ← whitelisted methods for Jinja2 + client calls
    tasks.py                  ← scheduled job functions
    overrides/
      sales_order.py          ← SalesOrder controller override
      sales_invoice.py        ← SalesInvoice controller override
      delivery_note.py        ← DeliveryNote controller override
    fixtures/                 ← exported JSON for custom fields (version-controlled)
      Custom Field/
      Print Format/
      Client Script/
    public/
      images/
        header.png
        footer.png
        golden-gm.png
        em-group.png
        full-name.png
  setup.py
  MANIFEST.in
```

#### [NEW] Company & Currency Setup
- Create company: **Golden GM**
- Enable currencies: **LYD** (primary) and **USD**
- Configure Chart of Accounts (Libyan / generic)
- Set wkhtmltopdf as PDF engine in Print Settings

#### Verification
- ERPNext UI accessible at `localhost:8080`
- `golden_gm` app listed in installed apps
- Both LYD and USD currencies active

---

## Phase 2 — Custom Fields & Computed Data

**Goal**: All computed fields from the three Odoo modules exist on the correct ERPNext doctypes,
populated by Server Scripts or DocType controller overrides.

### Mapping: Odoo model → ERPNext Doctype

| Odoo Model | ERPNext Doctype |
|---|---|
| `sale.order` (Quotation status) | Quotation |
| `sale.order.line` (Quotation) | Quotation Item |
| `sale.order` (Sales Order status) | Sales Order |
| `sale.order.line` (Sales Order) | Sales Order Item |
| `account.move` (invoice) | Sales Invoice |
| `account.move.line` | Sales Invoice Item |
| `stock.picking` | Delivery Note / Stock Entry |
| `product.category` | Item Group |

---

### 1.0 Quotation & Quotation Item — Custom Fields

#### [MODIFY] Quotation and Quotation Item (via `golden_gm/install.py`)

To support Arabic Sales Quotation print formats with identical columns and calculations, the `Quotation` and `Quotation Item` DocTypes require custom fields mirroring `Sales Order` / `Sales Order Item` (excluding stock reservation).

##### Quotation Fields:
* `amount_undiscounted` (Currency) — Standard rate subtotal excluding discount lines
* `amount_discount` (Currency) — Sum of line-level discounts

##### Quotation Item Fields:
* `product_categ_id` (Link → Item Group) — التصنيف (Category)
* `qty_available` (Float) — الكمية في المخزن (Available stock)
* `packaging_type` (Data) — نوع العبوة (Package type)
* `packaging_size` (Float) — حجم العبوة (Package size)
* `packaging_qty` (Int) — عدد الصناديق (Boxes count)
* `loose_units` (Int) — عدد القطع (Loose units)
* `unit_price_after_discount` (Currency) — سعر القطعة (Price per unit)

#### [NEW] `golden_gm/overrides/quotation.py`
We will update `CustomQuotation` to compute these fields on `before_save` similar to `CustomSalesOrder` (excluding stock reservation).

---

### 1.1 Sales Order — Custom Fields

#### [MODIFY] Sales Order (via `fixtures/Custom Field/`)

| Field Name | Type | Label | Logic |
|---|---|---|---|
| `amount_undiscounted` | Currency | Amount Undiscounted | Computed: total minus discount lines |
| `amount_discount` | Currency | Discount | Computed: sum of discount line amounts |
| `amount_in_words_lyd` | Data | المبلغ بالحروف (د.ل) | Computed via `num2words` |
| `amount_in_words_usd` | Data | المبلغ بالحروف ($) | Computed via `num2words` |
| `is_reserved` | Check | Stock Reserved | Set by reserve/unreserve actions |

#### [NEW] `golden_gm/overrides/sales_order.py`
```python
import frappe
from frappe.utils import flt
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from num2words import num2words

class CustomSalesOrder(SalesOrder):

    def before_save(self):
        super().before_save()
        self._compute_discount_totals()
        self._compute_amount_in_words()

    def _compute_discount_totals(self):
        discount = sum(
            flt(line.amount) for line in self.items
            if getattr(line, 'is_discount_line', False)
        )
        self.amount_discount = discount
        self.amount_undiscounted = flt(self.grand_total) - discount

    def _compute_amount_in_words(self):
        currency = self.currency
        amount = flt(self.grand_total)
        if currency == 'LYD':
            self.amount_in_words_lyd = num2words(amount, lang='ar')
            self.amount_in_words_usd = ''
        elif currency == 'USD':
            self.amount_in_words_usd = num2words(amount, lang='ar')
            self.amount_in_words_lyd = ''
        else:
            self.amount_in_words_lyd = ''
            self.amount_in_words_usd = ''
```

#### [MODIFY] `golden_gm/hooks.py`
```python
override_doctype_class = {
    "Sales Order": "golden_gm.overrides.sales_order.CustomSalesOrder",
    "Sales Invoice": "golden_gm.overrides.sales_invoice.CustomSalesInvoice",
    "Delivery Note": "golden_gm.overrides.delivery_note.CustomDeliveryNote",
}
```

---

### 1.2 Sales Order Item — Custom Fields

| Field Name | Type | Label | Logic |
|---|---|---|---|
| `product_categ_id` | Link → Item Group | التصنيف | User-set |
| `qty_available` | Float | الكمية في المخزن | Fetched from `Bin` on item select |
| `packaging_type` | Link → Item Packing | نوع العبوة | Auto-set from item's default packaging |
| `packaging_qty` | Int | عدد الصناديق | `floor(qty / packaging_size)` |
| `loose_units` | Int | عدد القطع | `qty - (packaging_qty * packaging_size)` |
| `unit_price_after_discount` | Currency | سعر القطعة | `price - (price * discount / 100)` |

These can be computed via a **Client Script** on `Sales Order Item` for real-time updates in the
form, backed by a `before_save` calculation in the controller for report accuracy.

---

### 1.3 Sales Invoice — Custom Fields

Mirror the same computed fields to Sales Invoice (same logic, same `num2words` pattern):

| Field | Source |
|---|---|
| `amount_undiscounted` | Sum excl. discount lines |
| `amount_discount` | Sum of discount lines |
| `amount_discount_in_words_ar` | `num2words(amount_discount, lang='ar')` |
| `amount_in_words_lyd` | `num2words(grand_total, lang='ar')` |
| `amount_in_words_usd` | `num2words(grand_total, lang='ar')` |

---

### 1.4 Delivery Note — Custom Fields

| Field | Label | Logic |
|---|---|---|
| `amount_undiscounted` | Total Amount | Sum of `qty × unit_price` for non-discount lines |
| `amount_in_words_ar` | المبلغ بالحروف | `num2words(amount, lang='ar')` |
| `return_amount_subtotal` | الاجمالي | For return DNs: sum of `qty × price_unit` |
| `return_amount_discount` | الخصم | Sum of discounts |
| `return_amount_total` | الصافي | Subtotal − Discount |
| `return_amount_in_words` | المبلغ بالحروف | `num2words(net_total, lang='ar')` |
| `note` | Note | Free text note field |

---

### 1.5 Item Group — `get_top_parent()` Helper

#### [NEW] `golden_gm/api.py`
```python
@frappe.whitelist()
def get_top_parent_group(item_group_name):
    """Traverse Item Group tree to find root parent."""
    current = frappe.get_doc("Item Group", item_group_name)
    while current.parent_item_group:
        current = frappe.get_doc("Item Group", current.parent_item_group)
    return current.name
```

#### Verification (Phase 2)
- Open a Sales Order: `amount_in_words_lyd` auto-populates on save
- Change currency to USD: `amount_in_words_usd` populates instead
- Sales Order Item shows `qty_available` when item selected
- Packaging fields compute correctly

---

## Phase 2.5 — Import Static Image Assets

**Goal**: Import the legacy header and footer images from the Odoo repository to the custom Frappe app's public directory so they are served correctly for the print formats.

### Tasks
- Locate the legacy images in the Odoo codebase archive at `odoo_archieve/odoo_modules/sale_management_extension/static/src/img/`.
- Copy `header.png` and `footer.png` to `/media/zawiatgf/New Volume/Projects/Golden-GM/golden_gm/golden_gm/public/images/`.
- Verify they are accessible at `http://localhost:8000/assets/golden_gm/images/header.png` and `http://localhost:8000/assets/golden_gm/images/footer.png`.

---

## Phase 3 — PDF Print Formats (QWeb → Jinja2 Port)

**Goal**: All five custom PDF reports working in ERPNext v16 with identical Arabic RTL layout.

> [!NOTE]
> Since ERPNext v16 and Odoo both use **wkhtmltopdf**, all existing CSS (RTL, table borders,
> `page-break-after: always`, Arabic fonts) ports **without changes**. Only the template
> syntax (QWeb → Jinja2) needs to change.
>
> In Odoo, both Quotations and Sales Orders share the same `sale.order` model. In ERPNext, these are split into two separate DocTypes: `Quotation` and `Sales Order`. We will build separate but visually identical Print Formats for each.

### QWeb → Jinja2 Translation Reference

| QWeb | Jinja2 |
|---|---|
| `<t t-foreach="lines" t-as="line">` | `{% for line in doc.items %}` |
| `<t t-if="condition">` | `{% if condition %}{% endif %}` |
| `<span t-field="o.name"/>` | `{{ doc.name }}` |
| `<span t-esc="'%.3f' % val"/>` | `{{ '%.3f' \| format(val) }}` or `{{ '%.3f' % val }}` |
| `t-att-src="'/module/img.png'"` | `src="/assets/golden_gm/images/img.png"` |
| `t-call="web.basic_layout"` | Not needed — ERPNext wraps automatically |

### Pagination Helper

Add to `golden_gm/api.py` (if not already done):
```python
def get_line_chunks(lines, chunk_size=15):
    """Split a list into chunks; append empty chunk if last is full."""
    chunks = [lines[i:i+chunk_size] for i in range(0, len(lines), chunk_size)]
    if not lines:
        return [[]]
    if len(lines) % chunk_size == 0:
        chunks.append([])
    return chunks
```

Expose on the DocType controllers so Jinja2 can call `doc.get_line_chunks()`.

---

### 3.1 Arabic Sales Quotation
* **DocType**: `Quotation`
* **Target**: Print Format → `Arabic Sales Quotation` → Type: Jinja
* **Title/Label**: "عرض سعر" (Sales Quotation)
* **Key sections**: Copy the sale order report exactly, only changing the title from sale order (فاتورة مبدئية / أمر بيع) to sale quotation (عرض سعر).
  * Header image `/assets/golden_gm/images/header.png`
  * Customer info block (RTL layout)
  * Items table with columns: ت, رقم الصنف, الصنف, العبوة, عدد الصناديق, القطع, سعر القطعة, الإجمالي
  * Totals section: المجموع, الخصم, الصافي
  * Footer image `/assets/golden_gm/images/footer.png`
  * Pagination: `{% for chunk in doc.get_line_chunks() %}...{% endfor %}`

### 3.2 Arabic Sales Order (فاتورة مبدئية / أمر بيع)
* **DocType**: `Sales Order`
* **Target**: Print Format → `Arabic Sales Order` → Type: Jinja
* **Title/Label**: "فاتورة مبدئية / أمر بيع" (Proforma Invoice / Sales Order) — note: this is exactly "فاتورة مبدئية / أمر بيع", not just "فاتورة مبدئية".
* **Key sections**: Same design, layout, and calculations as the Quotation, but pointing to the `Sales Order` fields and showing the custom `is_reserved` status if active.

### 3.3 Arabic Invoice (Bilingual + Options)
* **DocType**: `Sales Invoice`
* **Target**: Print Format → `Arabic Invoice`
* **Key features**: Copy the invoice report exactly from Odoo's legacy report:
  * Bilingual header (Arabic + English)
  * Conditional price/discount hiding: `{% if not frappe.form_dict.hide_prices %}...{% endif %}`
  * Remaining balance section (conditional on `frappe.form_dict.show_balance`)
  * Uses the same chunking pattern

> [!IMPORTANT]
> The **Invoice Print Options wizard** (language, hide prices, hide discount, show balance) must
> be re-implemented. In ERPNext, this is done via a **custom Dialog** triggered from a custom
> button on the Sales Invoice form, passing options as URL params to the print action.
> Make sure to have the same exact options from Odoo's legacy wizard (Language: ar/en, Show Remaining Balance, Hide Prices, Hide Discount Column).

### 3.4 Sales Return Form (نموذج ترجيع مبيعات)
* **DocType**: `Delivery Note`
* **Target**: Print Format → `Sales Return Form`
* **Key features**:
  * Only rendered on return Delivery Notes (`doc.is_return == 1`)
  * RTL title block + return date
  * Customer info ("من الأخوة: ...")
  * Totals: `{{ doc.return_amount_subtotal }}`, `{{ doc.return_amount_discount }}`, `{{ doc.return_amount_total }}`
  * Signatures table (أمين المخزن / اسم القائم بالرد)

### 3.5 Discount Receipt
* **DocType**: `Sales Invoice`
* **Target**: Print Format → `Discount Receipt`
* **Key features**: Copy the discount receipt report exactly from Odoo's legacy report. Simple receipt layout showing customer info and the discount totals, printing dual copies of the receipt separated by a thick divider line.

---

### Verification (Phase 3)
- Print Arabic Sales Quotation → PDF is RTL, correct Arabic text, correct totals, matches Sales Order except title
- Print Arabic Sales Order → PDF is RTL, title is "فاتورة مبدئية / أمر بيع"
- Print Arabic Invoice → bilingual layout renders correctly, toggles work (matches Odoo report exactly)
- Print Sales Return → only shows on return Delivery Notes, amounts correct
- Multi-page documents paginate correctly (no cut-off rows)

---

## Phase 4 — Business Logic: Discount Wizard & Print Options

**Goal**: Replicate the `SaleOrderDiscountWizard` and `InvoicePrintOptions` dialogs.

### 3.1 Invoice Print Options

**Odoo source**: `invoice_print_options.py` + `invoice_print_options_view.xml`

#### [NEW] Custom button on Sales Invoice form

Add via **Client Script** on Sales Invoice:
```javascript
frappe.ui.form.on('Sales Invoice', {
    refresh(frm) {
        frm.add_custom_button('🖨️ طباعة (خيارات)', () => {
            const d = new frappe.ui.Dialog({
                title: 'خيارات الطباعة',
                fields: [
                    { fieldname: 'lang', fieldtype: 'Select',
                      label: 'Language', options: 'Arabic\nEnglish', default: 'Arabic' },
                    { fieldname: 'show_balance', fieldtype: 'Check',
                      label: 'Show Remaining Balance' },
                    { fieldname: 'hide_prices', fieldtype: 'Check',
                      label: 'Hide Prices' },
                    { fieldname: 'hide_discount', fieldtype: 'Check',
                      label: 'Hide Discount Column' },
                ],
                primary_action_label: 'Print',
                primary_action(values) {
                    const url = frappe.urllib.get_full_url(
                        `/api/method/golden_gm.api.print_invoice?` +
                        `name=${frm.docname}&lang=${values.lang}` +
                        `&hide_prices=${values.hide_prices ? 1 : 0}` +
                        `&hide_discount=${values.hide_discount ? 1 : 0}` +
                        `&show_balance=${values.show_balance ? 1 : 0}`
                    );
                    window.open(url);
                    d.hide();
                }
            });
            d.show();
        });
    }
});
```

#### [NEW] `golden_gm/api.py` — print endpoint
```python
@frappe.whitelist()
def print_invoice(name, lang='Arabic', hide_prices=0, hide_discount=0, show_balance=0):
    # Pass options as Jinja context via print_format_data or URL params
    # ERPNext's print_format endpoint accepts `_lang` param for language
    ...
```

The Print Format Jinja2 template reads these via `frappe.form_dict` or a custom context variable.

---

### 3.2 Discount / Promotions Wizard

**Odoo source**: `sale_order_discount_wizard.py` (177 lines) + `sale_order_discount_wizard_view.xml`

This is the most complex piece. ERPNext's equivalent concepts:
- **Promotional Scheme** → replaces `loyalty.program` of type `promotion`
- **Coupon Code** → replaces `loyalty.card` of type `coupons`

#### [NEW] DocType: `Sale Order Discount Wizard` (in `golden_gm`)

Since ERPNext doesn't have a transient/wizard DocType concept exactly like Odoo, implement this
as a **Frappe Dialog** (client-side) backed by **whitelisted server methods**.

**Server side** — `golden_gm/api.py`:
```python
@frappe.whitelist()
def get_applicable_discounts(sales_order_name):
    """
    Returns list of applicable Promotional Schemes + Coupon Codes for the SO.
    Replicates _get_applicable_promotions() + coupon card logic.
    """
    order = frappe.get_doc("Sales Order", sales_order_name)
    result = {'promotions': [], 'coupons': []}

    # 1. Promotional Schemes that meet min amount / min qty / product rules
    schemes = frappe.get_all("Promotional Scheme", filters={"disable": 0}, fields=["*"])
    for scheme in schemes:
        if _scheme_rules_met(scheme, order):
            result['promotions'].append({
                'name': scheme.name,
                'title': scheme.title,
            })

    # 2. Coupon Codes linked to this customer
    coupons = frappe.get_all("Coupon Code",
        filters={"customer": order.customer, "used": 0, "valid_upto": [">=", nowdate()]},
        fields=["name", "coupon_code", "discount_amount", "discount_percentage"]
    )
    result['coupons'] = coupons

    return result

@frappe.whitelist()
def apply_discounts(sales_order_name, selected_promotions, selected_coupons):
    """Apply selected promotions and coupon codes to the Sales Order."""
    order = frappe.get_doc("Sales Order", sales_order_name)
    # Apply Promotional Scheme pricing rules
    # Apply Coupon Code discounts
    order.save()
    return {"status": "ok"}
```

**Client side** — Client Script on Sales Order:
```javascript
frappe.ui.form.on('Sales Order', {
    refresh(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button('🏷️ تطبيق الخصومات', () => {
                frappe.call({
                    method: 'golden_gm.api.get_applicable_discounts',
                    args: { sales_order_name: frm.docname },
                    callback(r) {
                        // Build dialog with checkboxes for each promotion/coupon
                        // On confirm: call apply_discounts()
                    }
                });
            });
        }
    }
});
```

> [!NOTE]
> ERPNext v16's **Pricing Rules** and **Promotional Schemes** doctypes handle the discount
> application mechanics. The wizard simply surfaces the applicable ones for the user to select,
> then triggers the standard ERPNext pricing rule application.

---

## Phase 5 — Draft Stock Reservation (via Pick List)

**Goal**: Replicate the `action_reserve_stock` / `action_unreserve_stock` pattern using ERPNext's native **Pick List** DocType instead of a custom `Stock Reservation Entry`.

### Design Decisions
- **No Custom DocType**: We will completely remove/avoid the `Stock Reservation Entry` custom DocType.
- **Draft Reservation**: We will allow creating and submitting a `Pick List` for a draft (unsubmitted) Sales Order to act as a stock reservation.
- **Sales Order Actions**:
  - `action_reserve_stock()`: Maps the draft Sales Order items to a native `Pick List` document with `pick_manually = 1` (to preserve the Sales Order items and warehouses regardless of instant stock levels), saves, and submits it. Set `is_reserved = 1` on the Sales Order.
  - `action_unreserve_stock()`: Finds the submitted Pick List linked to the Sales Order and cancels it. Set `is_reserved = 0`.
- **Hooks**:
  - `on_cancel`: Cancel any active Pick Lists when the Sales Order is cancelled.
- **Scheduled Job**:
  - Automatically release (cancel Pick Lists of) expired draft Sales Orders where `is_reserved == 1` and `delivery_date` (or validity) is in the past.

#### [DELETE] Stock Reservation Entry

#### [MODIFY] [sales_order.py](file:///media/zawiatgf/New Volume/Projects/Golden-GM/golden_gm/golden_gm/overrides/sales_order.py)
We will implement `action_reserve_stock` and `action_unreserve_stock` using the native `Pick List` DocType:
```python
    def action_reserve_stock(self):
        if self.docstatus != 0:
            frappe.throw(_("Stock can only be reserved for draft Sales Orders."))
        if cint(self.is_reserved):
            frappe.throw(_("Stock is already reserved for this order."))

        # Map Sales Order to Pick List
        from frappe.model.mapper import get_mapped_doc
        
        def update_item_quantity(source, target, source_parent) -> None:
            target.qty = source.qty
            target.stock_qty = source.qty
            target.warehouse = source.warehouse or source_parent.set_warehouse

        doc = get_mapped_doc(
            "Sales Order",
            self.name,
            {
                "Sales Order": {
                    "doctype": "Pick List",
                    "field_map": {"set_warehouse": "parent_warehouse"},
                },
                "Sales Order Item": {
                    "doctype": "Pick List Item",
                    "field_map": {"parent": "sales_order", "name": "sales_order_item"},
                    "postprocess": update_item_quantity,
                }
            }
        )
        doc.purpose = "Delivery"
        doc.pick_manually = 1
        doc.insert(ignore_permissions=True)
        doc.submit()

        frappe.db.set_value("Sales Order", self.name, "is_reserved", 1)
        frappe.msgprint(_("Stock reserved successfully using Pick List {0}.").format(doc.name), alert=True)

    def action_unreserve_stock(self, commit=True):
        if not cint(self.is_reserved):
            return

        # Find active submitted Pick Lists for this Sales Order
        pick_lists = frappe.get_all(
            "Pick List Item",
            filters={"sales_order": self.name, "docstatus": 1},
            fields=["parent"],
            distinct=True
        )
        for pl in pick_lists:
            pl_doc = frappe.get_doc("Pick List", pl.parent)
            pl_doc.cancel()

        frappe.db.set_value("Sales Order", self.name, "is_reserved", 0)
        if commit:
            frappe.db.commit()
```

#### [MODIFY] [tasks.py](file:///media/zawiatgf/New Volume/Projects/Golden-GM/golden_gm/golden_gm/tasks.py)
Update the scheduled job to cancel Pick Lists of expired draft Sales Orders:
```python
def release_expired_reservations():
    expired = frappe.get_all(
        "Sales Order",
        filters={
            "docstatus": 0,
            "is_reserved": 1,
            "delivery_date": ["<", today()]
        },
        fields=["name"]
    )
    for so in expired:
        so_doc = frappe.get_doc("Sales Order", so.name)
        so_doc.action_unreserve_stock()
```

#### Verification (Phase 5)
- Click "Reserve Stock" on draft SO -> Pick List created and submitted, `is_reserved` is 1, items show `picked_qty`.
- Click "Unreserve" -> Pick List cancelled, `is_reserved` is 0, items `picked_qty` reset.
- Cancel draft SO -> Pick List cancelled automatically.
- Submit SO -> Pick List remains active so delivery note can be created from it.
- Run scheduled job -> cancels Pick Lists of expired draft reservations.

---

## Phase 6 — Minimal Data Migration

**Goal**: Import users and product catalog from Odoo into ERPNext.

### 5.1 Users

Export from Odoo:
```python
# Odoo shell
users = env['res.users'].search([('active', '=', True), ('share', '=', False)])
# Export: name, login, email, groups
```

Import to ERPNext via User DocType (CSV import or `frappe.get_doc().insert()`).

Map Odoo groups → ERPNext roles:
| Odoo Group | ERPNext Role |
|---|---|
| `account.group_account_manager` | Accounts Manager |
| `sale.group_sale_manager` | Sales Manager |
| `stock.group_stock_manager` | Stock Manager |

### 5.2 Product Templates + Variants

Export from Odoo:
- `product.template` → Items
- `product.product` (variants) → Item Variants
- `product.packaging` → Item Packing

Use ERPNext's **Data Import** tool (CSV) or write a migration script using `frappe.client`.

Key field mappings:
| Odoo | ERPNext |
|---|---|
| `product.template.name` | Item Name |
| `product.template.default_code` | Item Code |
| `product.category` | Item Group |
| `product.packaging.qty` | Item Packing → Packing Size |
| `product.template.list_price` | Standard Selling Rate |

---

## Phase 7 — QA & Go-Live

### Testing Checklist

- [ ] Sales Order: create, add items, packaging auto-calculates, qty_available shows
- [ ] Apply Discounts wizard: promotions filter by min amount/qty, coupons filter by customer
- [ ] Confirm SO: discount lines appear on invoice, amounts match
- [ ] Reserve Stock button: reservations created, unreserved on confirm
- [ ] Expired reservations: run cron, verify auto-release
- [ ] Print Arabic Quotation PDF: RTL, correct Arabic text, paginated
- [ ] Print Arabic Invoice: bilingual, price-hiding toggle works
- [ ] Print Sales Return: only on return DNs, totals correct, amount in words correct
- [ ] Print Discount Receipt: discount amount in Arabic words
- [ ] Amount in words: LYD order → Arabic words in LYD field; USD order → USD field
- [ ] Switch currency on invoice: correct words field populates
- [ ] Partner Ledger (built-in): export to Excel works natively ✅

---

## File Index

### New / Replaced Docker Files (project root)

| File | Action | Notes |
|---|---|---|
| `docker-compose.yml` | REPLACE | 9-service ERPNext stack |
| `docker-compose.override.yml` | REPLACE | Dev: live mount, debugpy, quiet workers |
| `Dockerfile` | REPLACE | Custom image with `golden_gm` + `num2words` |
| `Dockerfile.dev` | REPLACE | Adds `debugpy`, IDE tools |
| `apps.json` | NEW | Declares apps to install in image build |
| `.env` | NEW | Site name, DB passwords, versions (git-ignored) |
| `odoo.conf` | REMOVE | No longer needed |
| `odoo.dev.conf` | REMOVE | No longer needed |
| `odoo_data/` | REMOVE | No longer needed |

### New Files (custom app)

```
golden_gm/
  golden_gm/
    hooks.py
    api.py
    tasks.py
    overrides/
      sales_order.py
      sales_invoice.py
      delivery_note.py
    fixtures/
      Custom Field/
        sales_order_custom_fields.json
        sales_invoice_custom_fields.json
        delivery_note_custom_fields.json
        sales_order_item_custom_fields.json
      Print Format/
        arabic_sales_quotation.json
        arabic_sales_order.json
        arabic_invoice.json
        sales_return_form.json
        discount_receipt.json
      Client Script/
        sales_order_scripts.json
        sales_invoice_scripts.json
    public/
      images/
        header.png
        footer.png
```

### Odoo Files Being Replaced

| Odoo File | ERPNext Replacement |
|---|---|
| `sale_management_extension/models/sale_order.py` | `golden_gm/overrides/sales_order.py` |
| `sale_management_extension/models/account_move.py` | `golden_gm/overrides/sales_invoice.py` |
| `sale_management_extension/models/sale_order_line.py` | Custom Fields + Client Script |
| `sale_management_extension/models/loyalty_program.py` | ERPNext Pricing Rules (built-in) |
| `sale_management_extension/wizard/sale_order_discount_wizard.py` | `golden_gm/api.py` + Client Script dialog |
| `sale_management_extension/wizard/invoice_print_options.py` | Client Script dialog + `golden_gm/api.py` |
| `sale_management_extension/reports/sale_report_views.xml` | Print Format: Arabic Sales Quotation |
| `sale_management_extension/reports/invoice_report_views.xml` | Print Format: Arabic Invoice |
| `stock_extension/models/sale_order.py` | `golden_gm/overrides/sales_order.py` |
| `stock_extension/models/stock_picking.py` | `golden_gm/overrides/delivery_note.py` |
| `stock_extension/data/ir_cron.xml` | `golden_gm/hooks.py` scheduler_events |
| `stock_extension/reports/sales_return_report.xml` | Print Format: Sales Return Form |
| `account_management_extension/models/account_move.py` | `golden_gm/overrides/sales_invoice.py` |
| `account_management_extension/reports/discount_receipt_report.xml` | Print Format: Discount Receipt |
| `Open Source Modules/*` | Native ERPNext v16 (no replacement needed) |
