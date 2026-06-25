# Architecture & System Flow

How the backend is wired together and how data flows through it. Companion to
[data-model.md](data-model.md) (the tables) — this doc is the **verbs**: how a
request becomes a stock change, a sale, a receipt, and a report.

It also maps every **Core Feature** from the project brief to where it lives in
the code (see [Requirements traceability](#requirements-traceability)).

---

## The one rule everything is built around

The brief mandates a **controlled flow** with no direct stock edits:

```
   STOCK-IN  ──▶  INVENTORY UPDATE  ──▶  POS SALE  ──▶  REPORTS
 (purchase)      (ledger + balance)     (deduct)      (read-only)
```

In code, every arrow that touches stock passes through **one gateway**:

> `apps/inventory/services.apply_movement()` — updates the cached
> `Product.quantity_on_hand` **and** writes an immutable `StockMovement` row, in
> a single row-locked atomic transaction.

Nothing else is allowed to write `quantity_on_hand` (it's `editable=False`). That
single chokepoint is what makes "all movements traceable" true.

---

## Layered architecture

Each request flows down through thin layers; the real rules live in `services.py`.

```
   HTTP request (JWT bearer token)
        │
        ▼
   ┌─────────────┐   urls.py            route → viewset/action
   │   View      │   views.py           authz (IsAdmin / IsAdminOrReadOnly),
   │  (thin)     │                      parse input, call a service, log_activity()
   └─────┬───────┘
         │
         ▼
   ┌─────────────┐   services.py        ALL business rules live here:
   │  Service    │                      validation, totals, state transitions,
   │ (atomic)    │                      stock math — wrapped in @transaction.atomic
   └─────┬───────┘
         │
         ▼
   ┌─────────────┐   models.py          persistence; apply_movement() is the
   │   Models    │                      ONLY writer of quantity_on_hand
   └─────────────┘
         │
         ▼
   PostgreSQL  (Product.quantity_on_hand  +  StockMovement ledger)
```

**Cross-cutting:** `log_activity()` (audit trail) is called from views after
meaningful actions; the custom exception handler turns business-rule violations
into clean HTTP 400s instead of 500s.

---

## End-to-end flows

### 1. Stock-in → inventory update  *(the start of the controlled flow)*

```
Admin                  StockInViewSet            purchasing.services        inventory.services
  │  POST /stock-ins/        │                          │                          │
  ├─────────────────────────▶ create DRAFT (+ items)    │                          │
  │                          │  log STOCKIN_CREATE       │                          │
  │  POST .../post_document/ │                          │                          │
  ├─────────────────────────▶ post_stock_in(stock_in) ──▶ for each item w/ qty>0:   │
  │                          │                          ├─ apply_movement(STOCK_IN,+qty) ─▶ lock product,
  │                          │                          │                          │   balance += qty,
  │                          │                          │                          │   write StockMovement
  │                          │                          ├─ product.cost_price = unit_cost
  │                          │                          └─ status=POSTED, posted_at=now
  │                          │  log STOCKIN_POST         │                          │
  ◀──────────────────────────┘ 200 (posted document)    │                          │
```
A draft does nothing to stock; **posting** is the inventory update. A posted
document is locked (no double-posting). `quantity_received` (not ordered) is what
enters stock, and a mismatch requires a `discrepancy_reason` → handles damaged/
missing items.

### 2. POS sale → automatic deduction → receipt

```
Cashier                SaleViewSet               sales.services             pricing / inventory
  │  POST /sales/            │  create DRAFT                                  │
  │  POST .../set_items/     │  set_sale_items() ──▶ for each line:           │
  │                          │                      get_effective_price() ────▶ promo price or list price
  │                          │                      snapshot unit_price, line_total
  │                          │                      recalc subtotal/discount/total
  │  POST .../complete/      │  complete_sale(payments):                      │
  │   {payments:[...]}       │   ├─ validate paid ≥ total                     │
  │                          │   ├─ generate receipt_no (R{date}-{id})        │
  │                          │   ├─ for each line: apply_movement(SALE, −qty) ─▶ balance −= qty,
  │                          │   │       (raises InsufficientStock → rollback)    write StockMovement
  │                          │   ├─ create Payment rows (CASH/GCASH/CARD/…)   │
  │                          │   └─ status=COMPLETED, completed_at=now        │
  │                          │  log SALE_COMPLETE                             │
  ◀──────────────────────────┘ 200 → GET .../receipt/ for printable payload  │
```
The whole completion is atomic: if any line is short on stock, the entire sale
rolls back — you can never half-sell or deduct partially.

### 3. Draft item void request → admin review

This is the "wrong item was scanned" path for an unpaid cart.
It applies only while the sale is still `DRAFT`.

- cashier creates a void request for a scanned sale line
- admin approves or denies the request
- if approved, the requested quantity is removed from the draft cart
- if denied, the draft sale is left unchanged

```
Cashier → POST /sales/item-void-requests/ {sale_item, quantity?, reason}
      → pending request created against a draft sale line
Admin   → POST /sales/item-void-requests/{id}/approve/  → line removed from draft sale
Admin   → POST /sales/item-void-requests/{id}/deny/     → request marked denied
```

The request is separate from payment and separate from sale-level voiding.
No inventory movement happens here because stock is only deducted when the
sale is completed.

### 4. Void → reversal *(admin only)*

Void is the undo path for a sale that has already been completed and paid.
It is not a generic refund or partial return flow. The service enforces three
rules before doing anything:

- the sale must already be `COMPLETED`
- a non-empty reason must be supplied
- the action must be performed by an admin

If those checks pass, the reversal is applied transactionally:

1. Each sale line is replayed back into inventory with a positive quantity.
2. The stock ledger records a `SALE_REVERSAL` movement for each returned line.
3. The sale is marked `VOID` and stamped with `voided_at` and `void_reason`.
4. An audit log entry records the `SALE_VOID` action.

```
Admin → POST /sales/{id}/void/ {reason}
      → void_sale(): for each line apply_movement(SALE_REVERSAL, +qty)  → stock returned
                     status=VOID, voided_at, void_reason   →  log SALE_VOID
```

Because the whole flow runs inside a database transaction, the sale status and
stock ledger always change together. If the reversal fails at any point, the
request rolls back and the completed sale remains untouched.

Example:

```http
POST /api/sales/sales/42/void/
Authorization: Bearer <admin-token>
Content-Type: application/json

{ "reason": "Customer requested cancellation after payment" }
```

Expected outcome:

```json
{
      "status": "VOID",
      "void_reason": "Customer requested cancellation after payment",
      "voided_at": "2026-06-25T14:30:00Z"
}
```

The sale's stock is not deleted. Instead, each sold line is written back into
inventory as a `SALE_REVERSAL` movement, which restores on-hand quantity and
preserves the audit trail.

### 5. Manual adjustment *(damaged stock, recounts)*

```
Admin → POST /inventory/movements/adjust/ {product, new_quantity|delta, reason}
      → manual_adjustment(): reason REQUIRED → apply_movement(ADJUSTMENT, delta)  → log STOCK_ADJUSTMENT
```

### 5. Reports — the read side

Reports never compute or cache their own stock numbers; they read the same
ledger/sale tables the flows above wrote, so they're always consistent with
reality. All are admin-only and date-ranged.

---

## How the pieces connect (dependency map)

```
            accounts (User, roles, JWT, log_activity)
                 ▲           ▲            ▲
                 │           │            │
   catalog ──▶ inventory ◀── purchasing   sales ──▶ pricing
  (Product)   (apply_movement,            (Sale,     (effective
              StockMovement)              Payment)    price, discount)
                 ▲                          │
                 └────────── reports ◀───────┘
                       (reads sales + ledger + products)

   common = shared spine: base model, IsAdmin/IsAdminOrReadOnly,
            pagination, exception handler  (used by every app)
```
- **inventory** is the hub every stock writer depends on (`purchasing`, `sales`).
- **pricing** is read by `sales` at cart time to snapshot prices.
- **reports** is downstream-only; it reads, never writes.
- **accounts/common** are cross-cutting (auth, audit, permissions) everywhere.

---

## Requirements traceability

Every Core Feature from the brief → where it's implemented. Useful for the
"completeness of required features" grading criterion.

### Point of Sale
| Brief requirement | Implemented in |
|---|---|
| Fast transaction interface | `SaleViewSet` draft → set_items → complete flow (`apps/sales/views.py`) |
| Add/remove items from cart | `POST /sales/{id}/set_items/` → `set_sale_items()` |
| Auto price calculation | `_recalculate()` + `get_effective_price()` (`apps/pricing/services.py`) |
| Multiple payment types | `Payment.method` enum: CASH/GCASH/MAYA/CARD/BANK/OTHER |
| Receipt generation | `GET /sales/{id}/receipt/`; `receipt_no` set on completion |
| Daily sales tracking | `GET /sales/daily_summary/` |

### Inventory Management
| Brief requirement | Implemented in |
|---|---|
| Product listing | `ProductViewSet` (`GET /catalog/products/`) |
| Stock quantity tracking | `Product.quantity_on_hand` (read-only cache of the ledger) |
| Automatic stock deduction per sale | `complete_sale()` → `apply_movement(SALE, −qty)` |
| Low-stock alerts | `GET /inventory/movements/low_stock/`; `Product.is_low_stock` |
| Manual stock adjustment w/ reason | `POST /inventory/movements/adjust/` → `manual_adjustment()` (reason required) |
| Batch / bulk product entry | `POST /catalog/products/batch/` |

### Stock-in / Purchase Recording
| Brief requirement | Implemented in |
|---|---|
| Record purchased items | `StockInViewSet` + `StockInItem` |
| product, quantity, cost, date, reference | `StockInItem.{product,quantity_*,unit_cost}`, `StockIn.{purchase_date,reference_no}` |
| Automatic inventory update after stock-in | `POST /stock-ins/{id}/post_document/` → `post_stock_in()` |
| Handle discrepancies | `StockInItem.discrepancy_reason` (required when received ≠ ordered) |
| Stock-in record + reference (audit trail) | unique `reference_no`; every post writes `StockMovement(STOCK_IN, source=stock_in)` |

### User Management
| Brief requirement | Implemented in |
|---|---|
| Role-based access (Admin / Cashier) | `User.role` + `IsAdmin` / `IsAdminOrReadOnly` (`apps/common/permissions.py`) |
| Login / Logout | `POST /auth/login/`, `POST /auth/refresh/`, `POST /auth/logout/` (JWT; logout blacklists the refresh token) |
| Activity logging | `ActivityLog` + `log_activity()` (`apps/accounts/services.py`) |

### Reports & Analytics
| Brief requirement | Implemented in |
|---|---|
| Daily / weekly / monthly sales | `GET /reports/sales-summary/?period=` |
| Top-selling products | `GET /reports/top-products/` |
| Inventory status report | `GET /reports/inventory-status/` |
| Stock-in (purchase) history | `GET /reports/stock-in-history/` |
| Basic profit estimation | `GET /reports/profit-estimate/` |
| Dashboard KPIs (one call) | `GET /reports/dashboard/` (FEAT-12) |
| Barcode lookup | `GET /catalog/products/by-barcode/` (FEAT-04) |
| Health check | `GET /api/health/` (FIX-04) |

### Pricing & Discounts
| Brief requirement | Implemented in |
|---|---|
| Discount application (% / fixed) | `Discount` (`discount_type` PERCENTAGE/FIXED) → applied in `_recalculate()` |
| Promo pricing | `Promo` (per-product, date-windowed) → `get_effective_price()` |

> **Coverage:** every Core Feature in the brief maps to a concrete endpoint and
> service. The one deliberate addition beyond the brief is the `Supplier` table
> (the brief implies suppliers in stock-in; see [data-model.md](data-model.md)).
