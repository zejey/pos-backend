# Module 03 — Feature Enhancements

New capabilities beyond the brief's core features. Grouped by area. Several are
**business-type dependent** — see the matrix at the bottom; pick based on what
the professor confirms as the target business.

## A. Point of Sale

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| FEAT-01 | P1 | M | TODO | Returns / refunds (partial), distinct from full void |
| FEAT-02 | P2 | M | TODO | Per-line item discounts (currently order-level only) |
| FEAT-03 | P1 | M | TODO | Shift / cash-drawer management (open/close, X & Z reports) |
| FEAT-04 | P2 | S | ✅ DONE | Barcode lookup endpoint (`GET /catalog/products/by-barcode/`) |
| FEAT-05 | P2 | S | TODO | Parked/held sales: list & resume open drafts |

- **FEAT-01** Refunds: a `Return` referencing a sale + items; re-adds stock via a
  `RETURN` movement type. Cleaner than void for "customer returned 1 of 3".
- **FEAT-03** Shifts tie directly to "daily sales tracking": cashier opens a
  shift with a starting cash float, closes it with a counted amount; system
  reports expected vs actual (over/short). Strong real-world POS feature.

## B. Pricing & Tax

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| FEAT-06 | P1 | M | ◑ PARTIAL | VAT tax support — **inclusive** done (configurable `POS_TAX_RATE`, on sales/receipts/reports); exclusive mode not built |
| FEAT-07 | P3 | M | TODO | Product variants / modifiers (sizes, add-ons) |

- **FEAT-06** ◑ Done for **VAT-inclusive**: rate is configurable via
  `POS_TAX_RATE` (default 12, `0` disables) and snapshotted per sale; the tax is
  carved out of the total and shown on the receipt (`tax_amount`, `net_of_tax`,
  `tax_label`) and in reports. Remaining: a VAT-**exclusive** mode (add on top)
  if a target business needs it.

## C. Inventory & Purchasing

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| FEAT-08 | P2 | M | ✅ DONE | Supplier model (replaced free-text `supplier` on stock-in) — see [data-model.md](data-model.md) |
| FEAT-09 | P2 | M | TODO | Purchase-order generation + reorder suggestions from low-stock |
| FEAT-10 | P3 | S | TODO | Bulk CSV import (products, stock-in) |
| FEAT-11 | P3 | L | TODO | Multi-location / branch stock |
| FEAT-16 | P3 | M | TODO | Product images (upload + serve) |

## D. Reports & Dashboard

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| FEAT-12 | P1 | S | ✅ DONE | Dashboard KPI endpoint (`GET /reports/dashboard/`) — today's sales, low-stock count, top item in one call |
| FEAT-13 | P1 | M | TODO | Report export (CSV first, PDF later) |
| FEAT-14 | P2 | M | TODO | Low-stock notifications (email or websocket), beyond the list endpoint |

- **FEAT-12** lets the frontend dashboard load with a single request instead of
  several — good for tablet/real-time UX.
- **FEAT-13** directly supports the Business team's costing/sales artifacts.

## E. Platform

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| FEAT-15 | P3 | L | TODO | Offline-friendly sync (queue + idempotent checkout) — only if mobile is chosen |

## Business-type relevance matrix

Use this once the professor confirms the target business. ●= high value, ○= nice.

| Feature | Sari-sari | Canteen | Coffee shop | Grocery |
|---|:---:|:---:|:---:|:---:|
| FEAT-01 Refunds | ○ | ○ | ● | ● |
| FEAT-03 Shifts/cash drawer | ● | ● | ● | ● |
| FEAT-04 Barcode lookup | ● | ○ | ○ | ● |
| FEAT-06 VAT/tax | ○ | ○ | ● | ● |
| FEAT-07 Variants/modifiers | ○ | ● | ● | ○ |
| FEAT-09 PO / reorder | ● | ○ | ○ | ● |
| FEAT-10 Bulk CSV import | ● | ○ | ○ | ● |

> Recommendation: **FEAT-03 (shifts)** and **FEAT-12 (dashboard KPIs)** are worth
> doing regardless of business type. Hold the rest until the target is confirmed.
