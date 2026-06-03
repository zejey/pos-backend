# Module 00 — Current Status (Baseline)

A snapshot of what the backend does **today**, so the rest of the backlog has a
reference point. Verified: migrations apply, `manage.py check` reports 0 issues,
and the controlled flow passed an end-to-end test (stock-in → sale auto-deduct →
ledger → oversell rollback → profit reconciliation).

## Architecture invariant

> Stock changes **only** through `apps/inventory/services.apply_movement()`,
> which updates the cached `quantity_on_hand` and writes an immutable
> `StockMovement` row in one atomic, row-locked transaction.

This is what guarantees the brief's rule: *no direct editing of stock without a
record; all movements traceable.* Do not add code paths that write
`quantity_on_hand` directly — always go through the service.

## Implemented per core feature

| Core feature | Status | Notes |
|---|---|---|
| **User Management** | ✅ | Admin/Cashier roles, JWT login + refresh + **server-side logout** (blacklist), activity log (now covers all admin CRUD). |
| **Product catalog** | ✅ | Products, categories, bulk entry. `quantity_on_hand` read-only. |
| **Inventory** | ✅ | Ledger, auto-deduction, low-stock endpoint, manual adjustment w/ mandatory reason. |
| **Stock-in / Purchasing** | ✅ | Draft → post, reference no., discrepancy handling, cost refresh, audit trail. `supplier` is now a `Supplier` FK (was free text — `FEAT-08`). |
| **Point of Sale** | ✅ | Cart, multi-payment, receipt payload, atomic deduction, void/reversal, daily summary. |
| **Pricing & Discounts** | ✅ | Order-level %/fixed discount, product promo pricing. |
| **Reports & Analytics** | ✅ | Sales summary (daily/weekly/monthly), top sellers, inventory status, stock-in history, profit estimate. |

## Module → app map

| App | Path | Owns |
|-----|------|------|
| accounts | `apps/accounts/` | users, roles, auth, activity log |
| catalog | `apps/catalog/` | products, categories |
| inventory | `apps/inventory/` | stock ledger + the `apply_movement` gateway |
| purchasing | `apps/purchasing/` | stock-in documents |
| sales | `apps/sales/` | POS sales, payments |
| pricing | `apps/pricing/` | discounts, promos |
| reports | `apps/reports/` | read-only analytics |
| common | `apps/common/` | base model, permissions, pagination, exceptions |

## Progress (2026-06-04)

- ✅ **Module 01** (fixes & hardening) — all 10 FIX items done.
- ✅ **Module 02** (testing) — 34 tests, ~84% coverage, CI workflow.
- ✅ **Module 04** (security/prod) — SEC-01–08 done; SEC-09 partial.
- ◑ **Module 03** (features) — VAT tax (inclusive), Suppliers, dashboard KPI
  (FEAT-12) and barcode lookup (FEAT-04) done; the rest remain business-type
  dependent → [03](03-feature-enhancements.md).

## Remaining gaps

- Real-world POS features still open (refunds, shifts, VAT-exclusive,
  multi-location) — hold until the target business is confirmed → [03](03-feature-enhancements.md).
- `django-axes` login lockout not added (login throttle is in place) → `SEC-09`.
