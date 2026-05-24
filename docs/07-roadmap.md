# Module 07 — Roadmap

Everything from the other modules, prioritized and sequenced. **Start at the
top.** Phases map to the project's remaining sprints; within a phase, do P0
before P1.

## Phase 1 — Make it trustworthy (before the demo / submission)
The goal: the core flow is correct, safe, and provable. Highest grading impact
(functionality + completeness).

| Item | Why now |
|------|---------|
| FIX-01 Validate payments | Money correctness — can't demo a POS that accepts bad payments |
| FIX-02 Block inactive/unpriced sales | Prevents nonsensical sales |
| TEST-00 + TEST-01 + TEST-02 | Prove the controlled flow & edge cases; regression safety |
| SEC-01 + SEC-02 | Don't ship the dev secret / open CORS |
| FIX-04 Healthcheck | Clean deploy demo |
| DOC-02 API docs export | Quick, and unblocks the frontend team |
| FEAT-12 Dashboard KPI endpoint | Lets the frontend dashboard come together |

## Phase 2 — Make it real-world ready
The goal: features and hardening that push "real-world applicability" (a grading
criterion) and round out the deliverables.

| Item | Why |
|------|-----|
| SEC-03 Logout (blacklist) | Completes User Management 1.2 |
| SEC-04 + SEC-05 Static + headers | Real deployment; `check --deploy` clean |
| FEAT-03 Shift / cash-drawer | Strong POS realism; deepens daily-sales |
| FEAT-01 Refunds | Real stores need returns, not just voids |
| FEAT-06 VAT/tax | Real-world receipts (esp. coffee shop / grocery) |
| FEAT-13 Report export (CSV) | Feeds Business team artifacts |
| TEST-03 + TEST-04 | Permission & report coverage |
| FIX-05 Paginate reports | Performance with a real catalog |
| DOC-01 + DOC-03 + DOC-05 + DOC-06 | Finish the documentation deliverables |

## Phase 3 — Nice-to-have / polish
Do only if time allows, or if the chosen business type calls for it (see the
matrix in [03](03-feature-enhancements.md)).

| Item |
|------|
| FEAT-02 Per-line discounts · FEAT-04 Barcode lookup · FEAT-05 Parked sales |
| FEAT-07 Variants/modifiers (coffee shop) · FEAT-08 Suppliers · FEAT-09 PO/reorder |
| FEAT-10 CSV import · FEAT-11 Multi-location · FEAT-14 Notifications · FEAT-16 Images |
| FIX-06..FIX-10 remaining hardening · SEC-06..SEC-09 · TEST-05 + TEST-06 (CI) |

## Decisions waiting on the professor
These gate some Phase 2/3 choices — chase them down early:
- **Platform** (web / tablet / mobile) → affects FEAT-15 and frontend contract.
- **Business type** → affects FEAT-06, FEAT-07, FEAT-09 priority (see matrix).
- **Real community "client"?** → big for the "real-world applicability" grade.

## Suggested first three tickets to pick up
1. **FIX-01** — payment validation (small, P0, money-critical).
2. **TEST-00 + TEST-01** — stand up pytest and lock in the happy path.
3. **SEC-01/SEC-02** — 30 minutes via `manage.py check --deploy`.
