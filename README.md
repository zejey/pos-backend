# POS & Inventory Management — Backend

Django + Django REST Framework + PostgreSQL backend for a community-based
Point of Sale and Inventory Management system. API-first, so the React
frontend, tablet, or a future mobile app all consume the same endpoints.

It enforces the project's **controlled flow**:

```
STOCK-IN  ──►  INVENTORY UPDATE  ──►  POS SALE  ──►  REPORTS
```

> No stock is ever edited directly. Every change to a product's quantity goes
> through one atomic gateway that writes an immutable `StockMovement`, giving a
> complete audit trail.

---

## Modules (one Django app per core feature)

| App | Core feature area | Highlights |
|-----|-------------------|-----------|
| `accounts` | User Management | Admin/Cashier roles, JWT login, activity log |
| `catalog` | Product listing | Products, categories, bulk product entry |
| `inventory` | Inventory Management | Stock ledger, auto-deduction gateway, low-stock, manual adjustment w/ reason |
| `purchasing` | Stock-in / Purchasing | Stock-in docs, references, discrepancy handling, audit trail |
| `sales` | Point of Sale | Cart, multi-payment, receipt, atomic stock deduction, void |
| `pricing` | Pricing & Discounts | %/fixed discounts, promo pricing |
| `reports` | Reports & Analytics | Sales summary, top sellers, inventory status, stock-in history, profit |
| `common` | (shared) | Base model, role permissions, pagination, domain exceptions |

---

## System requirements

- Docker + Docker Compose **(recommended)**, OR
- Python 3.12+ and PostgreSQL 14+ for a manual setup.

## Quick start (Docker)

```bash
cp .env.example .env          # adjust secrets if you like
docker compose up --build     # starts Postgres + web, runs migrations
docker compose exec web python manage.py seed_demo        # demo data
docker compose exec web python manage.py createsuperuser  # optional
```

API is now at `http://localhost:8000/api/` and interactive docs at
`http://localhost:8000/api/docs/`.

## Quick start (manual / no Docker)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Point at your PostgreSQL (or use SQLite for a quick look):
export POS_DB_ENGINE=sqlite            # omit to use PostgreSQL via .env

python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

## Configuration

All config is environment-driven (see `.env.example`): `DJANGO_SECRET_KEY`,
`DJANGO_DEBUG`, `POS_DB_ENGINE` (`postgres`|`sqlite`), the `POSTGRES_*`
connection vars, and `CORS_ALLOWED_ORIGINS` for the React app.

## Demo accounts (after `seed_demo`)

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Cashier | `cashier` | `cashier123` |

---

## API at a glance

Authenticate, then send `Authorization: Bearer <access>`.

```bash
# Login
curl -X POST localhost:8000/api/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}'
```

| Method & path | Purpose |
|---|---|
| `POST /api/auth/login/` `/refresh/` | JWT auth |
| `GET/POST /api/auth/users/` | Manage users (admin) |
| `GET /api/auth/activity/` | Activity log (admin) |
| `GET/POST /api/catalog/products/` · `…/batch/` | Products + bulk entry |
| `GET/POST /api/purchasing/stock-ins/` · `…/{id}/post_document/` | Stock-in + posting |
| `GET /api/inventory/movements/` | Stock audit trail (admin) |
| `POST /api/inventory/movements/adjust/` | Manual adjustment w/ reason |
| `GET /api/inventory/movements/low_stock/` | Low-stock alerts |
| `POST /api/sales/sales/` · `…/{id}/set_items/` · `…/complete/` | Cart → checkout |
| `POST /api/sales/sales/{id}/void/` | Void (admin) |
| `GET /api/sales/sales/{id}/receipt/` | Receipt payload |
| `GET /api/sales/sales/daily_summary/` | Today's sales |
| `GET/POST /api/pricing/discounts/` · `/promos/` | Discounts & promos |
| `GET /api/reports/{sales-summary,top-products,inventory-status,stock-in-history,profit-estimate}/` | Reports |

### Typical POS checkout

```bash
# 1. open a cart
SALE=$(curl -s -X POST localhost:8000/api/sales/sales/ -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"cart":[{"product":1,"quantity":2},{"product":3,"quantity":1}]}' | jq .id)

# 2. take payment -> deducts stock, issues receipt
curl -X POST localhost:8000/api/sales/sales/$SALE/complete/ -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"payments":[{"method":"CASH","amount":100,"tendered":100}]}'
```

## Tests / verification

```bash
POS_DB_ENGINE=sqlite python manage.py check
POS_DB_ENGINE=sqlite python manage.py makemigrations --check --dry-run
```

## Notes for the frontend team

- The API is fully decoupled; build against the schema at `/api/schema/`
  (OpenAPI) or the Swagger UI at `/api/docs/`.
- `quantity_on_hand` is **read-only** — change stock only via stock-in,
  sale, or the adjustment endpoint, never by editing the product.
