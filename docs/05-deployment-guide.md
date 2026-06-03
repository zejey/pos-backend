# Module 05 — Deployment Guide

This is the working draft of the brief's required **Deployment Guide**
deliverable (system requirements, installation steps, configuration setup).
Finalize once the target platform is confirmed; record the deployment-demo video
against these steps.

> Status: draft. Production sections depend on Module 04 (`SEC-xx`).

## 1. System requirements

**Option A — Docker (recommended)**
- Docker Engine 24+ and Docker Compose v2
- 2 GB RAM, 2 GB free disk

**Option B — Manual**
- Python 3.12+
- PostgreSQL 14+
- pip / venv

## 2. Installation

### Docker
```bash
git clone <repo-url> && cd pos-backend
cp .env.example .env          # edit secrets
docker compose up --build     # builds web, starts Postgres, runs migrations
docker compose exec web python manage.py seed_demo        # optional demo data
docker compose exec web python manage.py createsuperuser  # admin login
```
App: `http://localhost:8000/api/` · Docs: `http://localhost:8000/api/docs/`

### Manual
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
createdb pos                  # or use an existing PostgreSQL database
cp .env.example .env          # set POSTGRES_* to your DB
python manage.py migrate
python manage.py seed_demo
python manage.py runserver
```

## 3. Configuration (environment variables)

| Variable | Purpose | Dev default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Crypto signing key | `dev-insecure-change-me` (**change in prod**) |
| `DJANGO_DEBUG` | Debug mode | `True` (**False in prod**) |
| `DJANGO_ALLOWED_HOSTS` | Comma-sep allowed hosts | `*` |
| `POS_DB_ENGINE` | `postgres` or `sqlite` | `postgres` |
| `POSTGRES_DB/USER/PASSWORD/HOST/PORT` | DB connection | `pos/pos/pos/db/5432` |
| `CORS_ALLOWED_ORIGINS` | Frontend origins | `localhost:3000,localhost:5173` |
| `POS_TAX_RATE` | VAT % (inclusive); `0` disables tax | `12` |
| `POS_TAX_LABEL` | Tax label shown on receipts | `VAT` |
| `POS_RECEIPT_PREFIX` | Receipt number prefix (per store) | `R` |
| `THROTTLE_ANON` / `THROTTLE_USER` / `THROTTLE_LOGIN` | DRF rate limits | `60/min` / `1000/min` / `10/min` |
| `DJANGO_SECURE_SSL_REDIRECT` | Force HTTPS redirect (prod) | `True` |

> When `DJANGO_DEBUG=False`, the app refuses to start unless `DJANGO_SECRET_KEY`,
> `DJANGO_ALLOWED_HOSTS`, and `CORS_ALLOWED_ORIGINS` are explicitly set (SEC-01/02).

## 4. First-run checklist
- [ ] `.env` created with a strong `DJANGO_SECRET_KEY`
- [ ] Database reachable; `migrate` succeeded
- [ ] Superuser (or `seed_demo` admin) created
- [ ] `GET /api/docs/` loads
- [ ] Login returns a token; an authenticated request succeeds

## 5. Production notes (do before going live)
Complete the `SEC-xx` items in [04-security-and-production.md](04-security-and-production.md):
DEBUG off, locked hosts/CORS, WhiteNoise static, security headers, gunicorn via
`docker-compose.prod.yml`, backups. Then verify with:
```bash
python manage.py check --deploy
```

## 6. Database backup & restore (SEC-07)

The Postgres data lives in the `pgdata` volume. Back it up regularly:

```bash
# Backup (writes a timestamped dump to the host)
docker compose exec -T db pg_dump -U pos pos > backup_$(date +%F).sql

# Restore into a fresh database
cat backup_2026-01-01.sql | docker compose exec -T db psql -U pos -d pos
```

## 7. Troubleshooting
- **`web` can't reach DB:** ensure the `db` healthcheck is green; web waits on it.
- **CORS errors in the browser:** add the frontend URL to `CORS_ALLOWED_ORIGINS`.
- **Static/admin unstyled under gunicorn:** WhiteNoise + `collectstatic` (SEC-04).
- **401 on every request:** missing/expired `Authorization: Bearer <access>`.
