# Backend Documentation & Backlog

This folder is the **backend's living plan**: what's already built, what to fix,
what to test, and what to add next. Each file is a self-contained *module* of
work with IDs you can reference in commits, sprint backlogs, and standups.

## Modules

| File | Module | What it covers |
|------|--------|----------------|
| [00-current-status.md](00-current-status.md) | Current Status | Baseline — what is implemented and verified today |
| [01-fixes-and-hardening.md](01-fixes-and-hardening.md) | Fixes & Hardening | Bugs, gaps, and tech debt in the existing code (`FIX-xx`) |
| [02-testing-and-qa.md](02-testing-and-qa.md) | Testing & QA | The automated test suite to build (`TEST-xx`) |
| [03-feature-enhancements.md](03-feature-enhancements.md) | Feature Enhancements | New capabilities to add (`FEAT-xx`) |
| [04-security-and-production.md](04-security-and-production.md) | Security & Production | Hardening before real-world deployment (`SEC-xx`) |
| [05-deployment-guide.md](05-deployment-guide.md) | Deployment Guide | The graded deployment-guide deliverable |
| [06-documentation-deliverables.md](06-documentation-deliverables.md) | Doc Deliverables | Mapping the brief's required docs to tasks (`DOC-xx`) |
| [07-roadmap.md](07-roadmap.md) | Roadmap | Everything above, prioritized and sequenced into phases |

## How to use this

1. Read [07-roadmap.md](07-roadmap.md) first — it tells you **what to start with**.
2. Pick an item by its ID, do the work, check the acceptance criteria.
3. Update the status column in the relevant module file.

## Legend

**Priority**
- `P0` — Must-have before the demo / final submission.
- `P1` — High value; do it this term.
- `P2` — Medium; do if time allows.
- `P3` — Nice-to-have / future.

**Effort** (rough, for one solo backend dev)
- `S` — < half a day
- `M` — 1–2 days
- `L` — 3+ days

**Status:** `TODO` · `IN PROGRESS` · `DONE` · `BLOCKED`

## Scope note

This backlog is **backend only**. Frontend, UI/UX, and mobile work is owned by
other team members and is intentionally out of scope here.
