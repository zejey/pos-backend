# Module 06 — Documentation Deliverables

The brief requires several documents. Several are **backend-owned or
backend-assisted**. This module maps each to a concrete task so nothing is
forgotten at submission. Shared with the Documentation & Business team.

| ID | Priority | Effort | Status | Deliverable |
|----|----------|--------|--------|-------------|
| DOC-01 | P1 | M | TODO | Technical Documentation |
| DOC-02 | P0 | S | TODO | API Documentation |
| DOC-03 | P1 | S | TODO | Database Schema / ERD |
| DOC-04 | P2 | M | TODO | User Manual (admin/backend parts) |
| DOC-05 | P1 | M | IN PROGRESS | Deployment Guide → [05](05-deployment-guide.md) |
| DOC-06 | P1 | M | TODO | Video walkthrough scripts |

---

### DOC-01 — Technical Documentation · P1 · M
System overview, architecture (the controlled flow + ledger invariant), module
breakdown, business-logic notes (how `apply_movement`, `complete_sale`,
`post_stock_in` work), and key decisions. Much of this can be lifted from
[00-current-status.md](00-current-status.md) and code docstrings.

### DOC-02 — API Documentation · P0 · S
**Mostly automated** — `drf-spectacular` already serves:
- OpenAPI schema: `GET /api/schema/`
- Swagger UI: `GET /api/docs/`
**Do:** export a static schema for submission and skim endpoints for clear
descriptions/examples:
```bash
python manage.py spectacular --file docs/api-schema.yml
```
**Done when:** `docs/api-schema.yml` is committed and Swagger reads cleanly.

### DOC-03 — Database Schema / ERD · P1 · S
Generate an ERD from the models so the schema is documented visually.
**Do:** add `django-extensions` + Graphviz and run
`manage.py graph_models -a -o docs/erd.png` (or document tables/relations
manually). Cross-references the Backend team's "Database Schema" output.

### DOC-04 — User Manual (backend/admin) · P2 · M
The Django admin and admin-only flows (managing users, posting stock-ins,
adjustments, reading reports). The cashier-facing manual is mostly frontend.

### DOC-05 — Deployment Guide · P1 · M · IN PROGRESS
Draft lives in [05-deployment-guide.md](05-deployment-guide.md). Finalize after
the `SEC-xx` production items land.

### DOC-06 — Video walkthrough scripts · P1 · M
Two videos are required. Draft step-by-step scripts so recording is smooth:
1. **System demonstration** — per feature: login → stock-in → see inventory rise
   → POS sale → stock falls → low-stock alert → manual adjustment → reports.
   (This is exactly the controlled flow — a natural narrative.)
2. **Deployment** — clone → `.env` → `docker compose up` → migrate → seed →
   open `/api/docs/` → make a successful API call.
