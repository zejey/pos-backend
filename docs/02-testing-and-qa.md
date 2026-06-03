# Module 02 — Testing & QA

There is **no automated test suite yet** — the only verification so far was a
one-off manual script. This module builds a real regression suite. It also feeds
the QA team's deliverables (Test Cases, Test Results).

## Setup

> **Status: ✅ implemented (2026-06-04).** 34 tests in `tests/`, ~84% coverage
> overall (92% on `apps/sales/services.py`). Run with `pytest`; config in
> `pytest.ini` + `config/settings_test.py` (in-memory sqlite). Dev deps in
> `requirements-dev.txt`.

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| TEST-00 | P0 | S | ✅ DONE | pytest + pytest-django + model-bakery + pytest-cov |
| TEST-01 | P0 | M | ✅ DONE | Controlled-flow happy-path tests (`tests/test_controlled_flow.py`) |
| TEST-02 | P0 | M | ✅ DONE | Edge-case & failure tests (`tests/test_edge_cases.py`) |
| TEST-03 | P1 | M | ✅ DONE | Permission matrix tests (`tests/test_permissions.py`) |
| TEST-04 | P1 | S | ✅ DONE | Reports correctness tests (`tests/test_reports.py`) |
| TEST-05 | P2 | S | ✅ DONE | Schema/contract + health (`tests/test_schema_and_health.py`) |
| TEST-06 | P2 | M | ✅ DONE | CI pipeline (`.github/workflows/ci.yml`) |

> Note: the concurrent-last-unit test (TEST-02) is meaningful only on Postgres;
> the suite runs on sqlite, where `select_for_update` is a no-op. Run that case
> against Postgres in CI if you want true concurrency coverage.

## TEST-00 — Tooling
Add to `requirements-dev.txt`: `pytest`, `pytest-django`, `model-bakery`,
`pytest-cov`. Add a `pytest.ini` with `DJANGO_SETTINGS_MODULE=config.settings`
and `POS_DB_ENGINE=sqlite`. Target: **≥ 80% coverage on `services.py` files**.

## TEST-01 — Controlled-flow happy path
Mirror (and expand) the manual smoke test as real tests:
- Stock-in posting raises `quantity_on_hand` and refreshes `cost_price`.
- A completed sale deducts stock and writes a `SALE` movement.
- Receipt number is generated; `change_due` is correct.
- Void returns stock and writes a `SALE_REVERSAL` movement.
- Manual adjustment writes an `ADJUSTMENT` movement with the reason.

## TEST-02 — Edge cases & failures (the high-value ones)
- **Oversell** → `InsufficientStock`, and the whole sale rolls back (no partial
  deduction, no orphan payments).
- **Concurrent sales on the last unit** — only one succeeds (validates
  `select_for_update`). *Note: meaningful only on Postgres, not sqlite.*
- Completing an already-completed sale → 400.
- Posting an already-posted stock-in → 400.
- Voiding a draft (not completed) sale → 400.
- Stock-in with received ≠ ordered and **no** discrepancy reason → 400.
- Adjustment with no reason → 400.
- Payment less than total → 400 (after `FIX-01`).

## TEST-03 — Permission matrix
For each endpoint, assert the role rules:
- Cashier: can create/complete sales, read products; **cannot** manage users,
  post stock-ins, adjust stock, void sales, or read the audit trail.
- Admin: full access.
- Unauthenticated: 401 everywhere.

## TEST-04 — Reports correctness
Seed known data, assert exact figures for sales-summary (each period boundary),
top-products ordering, profit estimate (revenue − COGS), inventory-status totals.

## TEST-05 — Schema/contract
Assert `GET /api/schema/` returns 200 and that key serializers expose the fields
the frontend depends on (guards against accidental breaking changes).

## TEST-06 — CI
GitHub Actions: spin up Postgres service, run migrations + `pytest --cov`, fail
under the coverage threshold. Gives the team green-check confidence per PR.

## Hand-off to the QA team
Each `TEST-xx` scenario above maps 1:1 to a manual **Test Case** the QA team can
document (ID, steps, expected, actual). Share this file with them so manual and
automated coverage line up.
