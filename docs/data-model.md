# Data Model Reference

Authoritative list of every database table in the POS & inventory backend, generated from the Django models. Use this to review the schema (it supersedes the earlier ER diagram, which was a conceptual draft).

> For how these tables connect and how data flows through them, see
> [architecture-and-flow.md](architecture-and-flow.md).

**Stack:** Django 5.2 / PostgreSQL. Every table has an auto `id` (BigAutoField) primary key. Tables marked _(timestamped)_ also have `created_at` and `updated_at` (auto-managed). Money/quantity fields are `Decimal(12,2)` unless noted.

---

## Accounts

### User
Authentication + role. Extends Django's `AbstractUser`.

| Field | Type | Notes |
|---|---|---|
| username | char(150) | unique, login id |
| first_name / last_name | char(150) | |
| email | email | |
| role | char(10) | `ADMIN` or `CASHIER` (default `CASHIER`) |
| is_active / is_staff / is_superuser | bool | standard Django flags |
| password, last_login, date_joined | — | standard Django auth fields |

### ActivityLog
Audit trail of user actions.

| Field | Type | Notes |
|---|---|---|
| user | FK → User | nullable (SET_NULL) |
| action | char(120) | e.g. `STOCKIN_POST` |
| entity | char(60) | model name acted on |
| entity_id | char(60) | id of that record |
| detail | JSON | arbitrary context |
| ip_address | inet | nullable |
| created_at | datetime | |

---

## Catalog

### Category _(timestamped)_

| Field | Type | Notes |
|---|---|---|
| name | char(80) | unique |
| description | char(255) | optional |
| is_active | bool | default true |

### Product _(timestamped)_
A sellable item. `quantity_on_hand` is a cached balance — never written directly; it only changes through inventory `StockMovement` records (controlled flow / audit requirement).

| Field | Type | Notes |
|---|---|---|
| sku | char(40) | unique |
| barcode | char(64) | indexed, optional |
| name | char(160) | |
| category | FK → Category | nullable (SET_NULL) |
| unit | char(20) | default `pc` |
| cost_price | decimal(12,2) | |
| selling_price | decimal(12,2) | |
| quantity_on_hand | decimal(12,2) | read-only / system-managed |
| reorder_level | decimal(12,2) | low-stock threshold |
| is_active | bool | default true |

---

## Inventory

### StockMovement
Append-only ledger of every stock change. Lets you reconstruct stock history for any product.

| Field | Type | Notes |
|---|---|---|
| product | FK → Product | required (PROTECT) |
| movement_type | char(20) | `STOCK_IN`, `SALE`, `SALE_REVERSAL`, `ADJUSTMENT`, `OPENING` |
| quantity | decimal(12,2) | signed (+ in / − out) |
| balance_after | decimal(12,2) | running balance snapshot |
| reference | char(64) | optional |
| reason | char(255) | optional |
| source_type / source_id | char | generic backlink to originating record |
| user | FK → User | nullable (SET_NULL) |
| created_at | datetime | |

> Replaces the diagram's `InvAdjustment` — a manual adjustment is just a `StockMovement` with `movement_type = ADJUSTMENT`.

---

## Pricing

### Discount _(timestamped)_
Order-level discount, optionally time-bound.

| Field | Type | Notes |
|---|---|---|
| name | char(80) | |
| discount_type | char(10) | `PERCENTAGE` or `FIXED` |
| value | decimal(12,2) | |
| is_active | bool | default true |
| start_date / end_date | date | nullable |

### Promo _(timestamped)_
Product-level promotional price, optionally time-bound.

| Field | Type | Notes |
|---|---|---|
| product | FK → Product | required (CASCADE) |
| promo_price | decimal(12,2) | |
| start_date / end_date | date | nullable |
| is_active | bool | default true |

---

## Purchasing

### Supplier _(timestamped)_ — **NEW**
Vendor that products are purchased from. (Added to close the gap vs. the ER diagram, which modelled suppliers as a table; previously this was free text on StockIn.)

| Field | Type | Notes |
|---|---|---|
| name | char(160) | unique |
| contact_person | char(120) | optional |
| contact_no | char(40) | optional (text, not numeric — preserves leading zeros / formatting) |
| address | char(255) | optional |
| is_active | bool | default true |

### StockIn _(timestamped)_
A purchase / stock-in document. Created as `DRAFT`, then `POSTED`; posting is what flows received quantities into inventory.

| Field | Type | Notes |
|---|---|---|
| reference_no | char(64) | unique — supplier receipt/invoice no. |
| supplier | FK → Supplier | nullable (SET_NULL) — **was free text, now a real FK** |
| purchase_date | date | |
| note | text | optional |
| status | char(10) | `DRAFT` or `POSTED` |
| created_by | FK → User | nullable (SET_NULL) |
| posted_at | datetime | nullable |
| _total_cost_ | computed | sum of item line costs (not stored) |

### StockInItem
Line item on a StockIn.

| Field | Type | Notes |
|---|---|---|
| stock_in | FK → StockIn | required (CASCADE) |
| product | FK → Product | required (PROTECT) |
| quantity_ordered | decimal(12,2) | |
| quantity_received | decimal(12,2) | |
| unit_cost | decimal(12,2) | |
| discrepancy_reason | char(255) | required when received ≠ ordered |

---

## Sales

### Sale _(timestamped)_
A sales transaction.

| Field | Type | Notes |
|---|---|---|
| receipt_no | char(32) | unique, nullable |
| cashier | FK → User | nullable (SET_NULL) |
| status | char(10) | `DRAFT`, `COMPLETED`, `VOID` |
| discount | FK → Discount | nullable (SET_NULL) |
| subtotal | decimal(14,2) | |
| discount_total | decimal(14,2) | |
| total | decimal(14,2) | gross; VAT-inclusive (tax is *carved out*, not added) |
| tax_rate | decimal(5,2) | VAT % snapshotted at creation (from `POS_TAX_RATE`); 0 = no tax |
| tax_amount | decimal(14,2) | VAT portion carved out of `total` (= total × rate ÷ (100+rate)) |
| note | char(255) | optional |
| completed_at / voided_at | datetime | nullable |
| void_reason | char(255) | optional |

### SaleItem
Line item on a Sale. Prices are **snapshotted** at sale time so historical receipts stay correct even if the product price later changes.

| Field | Type | Notes |
|---|---|---|
| sale | FK → Sale | required (CASCADE) |
| product | FK → Product | required (PROTECT) |
| quantity | decimal(12,2) | |
| unit_price | decimal(12,2) | snapshot |
| line_total | decimal(14,2) | |

### Payment
Payment(s) against a sale. Modelled as its own table so a single sale can have **split payments** (e.g. cash + GCash).

| Field | Type | Notes |
|---|---|---|
| sale | FK → Sale | required (CASCADE) |
| method | char(10) | `CASH`, `GCASH`, `MAYA`, `CARD`, `BANK`, `OTHER` |
| amount | decimal(14,2) | |
| tendered | decimal(14,2) | amount handed over (for change) |
| reference | char(64) | e.g. digital/card txn id |

---

## Relationship summary

```
User ──< ActivityLog
User ──< Sale (cashier)        User ──< StockIn (created_by)        User ──< StockMovement

Category ──< Product
Product ──< SaleItem,  StockInItem,  StockMovement,  Promo

Supplier ──< StockIn ──< StockInItem
Discount ──< Sale ──< SaleItem
            Sale ──< Payment
```

## Notes for review
- **Payment method** is an enum/choice on `Payment`, not a separate table (the diagram showed a `PaymentMethod` table). This keeps it simple; if you need admins to add methods at runtime, we'd promote it to a table.
- The earlier diagram's `paidAmount` / `changeAmount` on the sale live in the `Payment` table here (`amount` / `tendered`), supporting split payments.
- The `supplier` column change from text → FK assumes a fresh database. If any `StockIn` rows already exist with text supplier names, we'll need a one-off data migration to map them onto `Supplier` rows before applying this.
