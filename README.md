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
$env:POS_DB_ENGINE="sqlite" # for Windows users

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

# Usage guide

Two parts: **management commands** (what to run in a terminal) and **API
operations** (what clients call). Pair this with the interactive Swagger UI at
`/api/docs/` and the runnable request collection in
[api-requests/controlled-flow.http](api-requests/controlled-flow.http).

## Management commands

Run from the project root. With Docker, prefix with `docker compose exec web`
(e.g. `docker compose exec web python manage.py migrate`). For a quick offline
run, set `POS_DB_ENGINE=sqlite` to use a local SQLite file instead of PostgreSQL.

### Setup & run

| Command | What it does |
|---|---|
| `pip install -r requirements.txt` | Install dependencies. In this repo's relocated venv, prefer `python -m pip install -r requirements.txt`. |
| `python manage.py migrate` | Create/upgrade the database schema. Run on first setup and after pulling model changes. |
| `python manage.py seed_demo` | **Load demo data**: admin + cashier users, categories, 6 products, a posted stock-in (100 units each), and 3 completed sales so reports/analytics show data right away. Safe to re-run — skips if products already exist. |
| `python manage.py createsuperuser` | Create your own admin login (alternative to the seeded `admin`). |
| `python manage.py runserver` | Start the dev server at `http://localhost:8000/`. |
| `python manage.py collectstatic` | Gather static files for the Django admin (needed under gunicorn/production). |

### Inspect & verify

| Command | What it does |
|---|---|
| `python manage.py check` | Run system checks (no DB writes). |
| `python manage.py check --deploy` | Production-readiness checks (DEBUG, headers, HTTPS…). |
| `python manage.py makemigrations --check --dry-run` | Fail if models changed without a migration — good for CI. |
| `python manage.py spectacular --file docs/api-schema.yml` | Export the OpenAPI schema to a file. |
| `python manage.py shell` | Interactive Django shell (inspect/admin via the ORM). |
| `python -m pytest -q` | Run the automated test suite (34 tests). |

### Docker

| Command | What it does |
|---|---|
| `docker compose up --build` | Build and start Postgres + web; runs migrations on boot. |
| `docker compose exec web python manage.py seed_demo` | Seed demo data inside the container. |
| `docker compose exec web python manage.py createsuperuser` | Create an admin inside the container. |
| `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d` | Start the production stack (gunicorn). |
| `docker compose exec -T db pg_dump -U pos pos > backup_$(date +%F).sql` | Back up the database (see [docs/05-deployment-guide.md](docs/05-deployment-guide.md)). |

---

# API operations

Base URL: `http://localhost:8000/api`. All responses are JSON.

## Authentication

Every endpoint except `health/`, `login/`, and `refresh/` requires a header:

```
Authorization: Bearer <access-token>
```

```bash
# 1. Log in -> returns { "access", "refresh", "user" }
curl -X POST localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# 2. Reuse the access token on every call
AUTH="Authorization: Bearer <access>"
curl localhost:8000/api/catalog/products/ -H "$AUTH"
```

Access tokens expire; get a new one with `POST /api/auth/refresh/`
(`{"refresh": "<refresh>"}`), and end a session with `POST /api/auth/logout/`.

## Roles at a glance

- **Admin** — full access: manage users, products, pricing, stock-in, voids, reports.
- **Cashier** — can sell (carts, payments, receipts) and **read** catalog/pricing;
  cannot manage users, post stock-in, void sales, or read reports.

`Read = anyone logged in` · `Admin = admin only` · `Cashier+ = cashier or admin`.

## Endpoint reference

### System
| Method & path | Access | Purpose |
|---|---|---|
| `GET /api/health/` | Public | Liveness + DB check. |
| `GET /api/schema/` · `GET /api/docs/` | Public | OpenAPI schema · interactive Swagger UI. |

### Auth & users — `/api/auth/`
| Method & path | Access | Purpose |
|---|---|---|
| `POST /auth/login/` | Public | Get access + refresh tokens. |
| `POST /auth/refresh/` | Public | Exchange a refresh token for a new access token. |
| `POST /auth/logout/` | Cashier+ | Blacklist a refresh token (`{"refresh": "..."}`). |
| `GET/POST /auth/users/` · `GET/PUT/PATCH/DELETE /auth/users/{id}/` | Admin | Manage user accounts. |
| `GET /auth/users/me/` | Cashier+ | Your own profile. |
| `POST /auth/users/change_password/` | Cashier+ | `{"old_password","new_password"}`. |
| `GET /auth/activity/` | Admin | Activity / audit log (filter `?action=&entity=&user=`). |

### Catalog — `/api/catalog/`
| Method & path | Access | Purpose |
|---|---|---|
| `GET/POST /catalog/categories/` · `/{id}/` | Read / Admin write | Product categories. |
| `GET/POST /catalog/products/` · `/{id}/` | Read / Admin write | Products (search `?search=`, filter `?category=&is_active=`). |
| `POST /catalog/products/batch/` | Admin | Bulk-create products (`{"products":[ ... ]}`). |
| `GET /catalog/products/by-barcode/?barcode=` | Cashier+ | Fast scan lookup of one active product. |

### Purchasing / Stock-in — `/api/purchasing/`
| Method & path | Access | Purpose |
|---|---|---|
| `GET/POST /purchasing/suppliers/` · `/{id}/` | Admin | Suppliers / vendors. |
| `GET/POST /purchasing/stock-ins/` · `/{id}/` | Admin | Stock-in documents (create as DRAFT). |
| `POST /purchasing/stock-ins/{id}/post_document/` | Admin | **Post** the stock-in → inventory rises (controlled flow). |

### Inventory — `/api/inventory/`
| Method & path | Access | Purpose |
|---|---|---|
| `GET /inventory/movements/` · `/{id}/` | Admin | Stock audit trail (filter `?product=&movement_type=`). |
| `POST /inventory/movements/adjust/` | Admin | Manual adjustment with **mandatory reason** (`{"product","delta"\|"new_quantity","reason"}`). |
| `GET /inventory/movements/low_stock/` | Admin | Products at/below reorder level. |

### Sales / POS — `/api/sales/`
| Method & path | Access | Purpose |
|---|---|---|
| `GET/POST /sales/sales/` · `/{id}/` | Cashier+ | List sales / open a cart (optionally pass `cart` + `discount`). |
| `POST /sales/sales/{id}/set_items/` | Cashier+ | Replace cart items (`[{"product","quantity"}, ...]`). |
| `POST /sales/item-void-requests/` | Cashier+ | Request removal of a scanned item from a draft sale (`{"sale_item","quantity"?,"reason"}`). |
| `POST /sales/item-void-requests/{id}/approve/` | Admin | Approve a pending draft-item void request and remove the line from the draft sale. |
| `POST /sales/item-void-requests/{id}/deny/` | Admin | Deny a pending draft-item void request. |
| `POST /sales/sales/{id}/complete/` | Cashier+ | Take payment, deduct stock, issue receipt (`{"payments":[...]}`). |
| `POST /sales/sales/{id}/void/` | Admin | Void a completed sale only, return stock with `SALE_REVERSAL` entries, and require `{"reason":"..."}`. |
| `GET /sales/sales/{id}/receipt/` | Cashier+ | Receipt payload for printing. |
| `GET /sales/sales/daily_summary/` | Cashier+ | Today's sales totals. |

### Pricing — `/api/pricing/`
| Method & path | Access | Purpose |
|---|---|---|
| `GET/POST /pricing/discounts/` · `/{id}/` | Read / Admin write | Order-level %/fixed discounts. |
| `GET/POST /pricing/promos/` · `/{id}/` | Read / Admin write | Product promo pricing (date-windowed). |

### Reports & Analytics — `/api/reports/` (Admin only)
| Method & path | Purpose |
|---|---|
| `GET /reports/dashboard/` | One-call KPI snapshot (today's sales, low-stock count, top item). |
| `GET /reports/sales-summary/?period=daily\|weekly\|monthly&date=` | Sales totals for a period. |
| `GET /reports/top-products/?start=&end=&limit=` | Best sellers by quantity + revenue. |
| `GET /reports/inventory-status/` | Current stock snapshot + valuation + low-stock flags. |
| `GET /reports/stock-in-history/?start=&end=` | Posted purchase history + total cost. |
| `GET /reports/profit-estimate/?start=&end=` | Revenue − estimated COGS. |

## Walkthrough: a full POS transaction

```bash
AUTH="Authorization: Bearer <access>"   # from /auth/login/

# 1. Open a cart (prices + tax snapshot at creation)
SALE=$(curl -s -X POST localhost:8000/api/sales/sales/ -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"cart":[{"product":1,"quantity":2},{"product":3,"quantity":1}]}' \
  | python -c "import sys,json;print(json.load(sys.stdin)['id'])")

# 2. Take payment -> deducts stock, issues receipt
curl -X POST localhost:8000/api/sales/sales/$SALE/complete/ -H "$AUTH" \
  -H "Content-Type: application/json" \
  -d '{"payments":[{"method":"CASH","amount":"100.00","tendered":"100.00"}]}'

# 3. Print the receipt
curl localhost:8000/api/sales/sales/$SALE/receipt/ -H "$AUTH"
```

For the complete stock-in → sale → reports sequence as clickable requests, open
[api-requests/controlled-flow.http](api-requests/controlled-flow.http) in VS Code
(REST Client extension).

## Notes for the frontend team

- The API is fully decoupled; build against the schema at `/api/schema/`
  (OpenAPI) or the Swagger UI at `/api/docs/`.
- `quantity_on_hand` is **read-only** — change stock only via stock-in,
  sale, or the adjustment endpoint, never by editing the product.
