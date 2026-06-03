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
| **User Management** | ✅ | Admin/Cashier roles, JWT login + refresh, activity log. Logout is client-side only (see `SEC-03`). |
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

## Known explicit gaps (detailed in later modules)

- No automated test suite yet → [02](02-testing-and-qa.md)
- A handful of input-validation holes → [01](01-fixes-and-hardening.md)
- Not production-hardened (DEBUG, CORS, static, secrets) → [04](04-security-and-production.md)
- Several real-world POS features not built (refunds, tax, shifts) → [03](03-feature-enhancements.md)
