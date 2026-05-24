# Module 01 — Fixes & Hardening

Gaps and tech debt in the **existing** code. These are grounded in specific
files/functions, so they're concrete to pick up.

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| FIX-01 | P0 | S | TODO | Validate payments on checkout |
| FIX-02 | P0 | S | TODO | Block selling inactive / unpriced products |
| FIX-03 | P1 | S | TODO | Reject non-positive quantities & costs |
| FIX-04 | P1 | S | TODO | Healthcheck endpoint for `web` |
| FIX-05 | P1 | M | TODO | Paginate report endpoints |
| FIX-06 | P2 | S | TODO | Friendly 400 when deleting referenced records |
| FIX-07 | P2 | S | TODO | Consistent activity logging coverage |
| FIX-08 | P2 | S | TODO | Receipt-number format & concurrency review |
| FIX-09 | P2 | M | TODO | Standardize the API error envelope |
| FIX-10 | P3 | S | TODO | Decimal rounding/quantization review |

---

### FIX-01 — Validate payments on checkout · P0 · S
`apps/sales/services.py:complete_sale` sums `payment.amount` but never checks
each amount is positive, and `PaymentSerializer.amount` has no `min_value`. A
negative amount could satisfy the total incorrectly.
**Do:** reject `amount <= 0`; for `CASH`, require `tendered >= amount`; validate
`method` is a known choice.
**Done when:** a negative or zero payment returns 400; cash with insufficient
tender returns 400.

### FIX-02 — Block selling inactive / unpriced products · P0 · S
`set_sale_items` adds any product, even `is_active=False` or `selling_price=0`.
**Do:** raise a `BusinessRuleError` if the product is inactive or has no
sellable price (unless a valid promo exists).
**Done when:** adding an inactive/zero-priced item to a cart returns 400.

### FIX-03 — Reject non-positive quantities & costs · P1 · S
`StockInItem.quantity_ordered/received/unit_cost` and adjustment deltas accept
negatives/zero at the serializer level.
**Do:** add `min_value` validators (received ≥ 0, ordered > 0, unit_cost ≥ 0).
**Done when:** negative quantities/costs are rejected with a clear message.

### FIX-04 — Healthcheck endpoint · P1 · S
`docker-compose.yml` has a DB healthcheck but none for `web`.
**Do:** add `GET /api/health/` returning `{"status":"ok"}` (and a DB ping); wire
a compose healthcheck.
**Done when:** `docker compose ps` shows `web` healthy.

### FIX-05 — Paginate report endpoints · P1 · M
`reports/InventoryStatusReport` and `TopProductsReport` build full lists in
Python with no pagination. With a large grocery catalog this is slow/heavy.
**Do:** paginate (or cap + offer CSV export, see `FEAT-13`); push valuation math
into the DB with annotations where possible.
**Done when:** inventory-status responds in O(page), not O(catalog).

### FIX-06 — Friendly 400 on protected deletes · P2 · S
Products/categories use `on_delete=PROTECT`. Deleting one that has movements
currently surfaces as a 500.
**Do:** catch `ProtectedError` in the exception handler → 400 with a clear
message ("cannot delete; has stock history — deactivate instead").
**Done when:** deleting a product with sales returns a clean 400.

### FIX-07 — Consistent activity logging · P2 · S
Logging exists on key actions (login, sale, stock-in, adjustment) but not on all
create/update/delete paths (e.g. product edits, discount changes).
**Do:** extract a small `LoggedModelMixin` for viewsets, or log in
`perform_update/perform_destroy` consistently.
**Done when:** every state-changing admin action appears in the activity log.

### FIX-08 — Receipt number review · P2 · S
`_generate_receipt_no` uses `R{date}-{pk:06d}`. Unique, but resets meaning
across days and exposes the pk.
**Do:** confirm uniqueness under concurrency; consider a per-day sequence and a
configurable store prefix from settings.
**Done when:** format is documented and concurrency-safe.

### FIX-09 — Standardize error envelope · P2 · M
`BusinessRuleError` returns `{detail, code}`, but DRF validation errors use a
different shape. The frontend benefits from one consistent format.
**Do:** extend `apps/common/exceptions.api_exception_handler` to normalize
validation errors to the same envelope.
**Done when:** all 4xx responses share one documented shape.

### FIX-10 — Decimal rounding review · P3 · S
Money/quantity quantization is mostly handled but not audited end-to-end.
**Do:** confirm all monetary results quantize to 2dp; centralize a `money()`
helper.
**Done when:** no float creep; totals always 2dp.
