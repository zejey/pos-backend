# Module 04 — Security & Production Readiness

The current settings are tuned for **development** (DEBUG on, permissive CORS,
default secret). Address these before any real deployment or the deployment-demo
video.

| ID | Priority | Effort | Status | Item |
|----|----------|--------|--------|------|
| SEC-01 | P0 | S | TODO | Fail fast on insecure prod config |
| SEC-02 | P0 | S | TODO | Lock `ALLOWED_HOSTS` and CORS in prod |
| SEC-03 | P1 | S | TODO | Server-side logout (JWT blacklist) |
| SEC-04 | P1 | S | TODO | Serve static files in prod (WhiteNoise) |
| SEC-05 | P1 | S | TODO | Security headers / HTTPS settings |
| SEC-06 | P2 | S | TODO | API throttling / rate limits |
| SEC-07 | P2 | M | TODO | DB backup & restore procedure |
| SEC-08 | P2 | S | TODO | Production compose + gunicorn tuning |
| SEC-09 | P3 | S | TODO | Login brute-force protection |

---

### SEC-01 — Fail fast on insecure prod config · P0 · S
When `DJANGO_DEBUG=False`, refuse to start if `DJANGO_SECRET_KEY` is still the
default. Prevents shipping the dev key.
**Done when:** prod boot with the default key raises `ImproperlyConfigured`.

### SEC-02 — Lock hosts & CORS · P0 · S
`ALLOWED_HOSTS` defaults to `*` and CORS allows all in DEBUG. In prod, require an
explicit host list and explicit `CORS_ALLOWED_ORIGINS` (the React app's URL).
**Done when:** prod rejects unknown Host headers and unlisted origins.

### SEC-03 — Server-side logout · P1 · S
JWT is currently stateless — "logout" only discards the client token. Add
`rest_framework_simplejwt.token_blacklist` to `INSTALLED_APPS`, enable rotation +
blacklist, and add `POST /api/auth/logout/` that blacklists the refresh token.
(Also satisfies User Management 1.2's "Logout".)
**Done when:** a blacklisted refresh token can no longer mint access tokens.

### SEC-04 — Static files in prod · P1 · S
Gunicorn won't serve the Django admin / Swagger assets. Add WhiteNoise
middleware + `collectstatic` in the Docker build.
**Done when:** `/admin/` and `/api/docs/` render correctly under gunicorn.

### SEC-05 — Security headers · P1 · S
Set (prod-only): `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
`CSRF_COOKIE_SECURE`, `SECURE_HSTS_SECONDS`, `SECURE_PROXY_SSL_HEADER`,
`X_FRAME_OPTIONS=DENY`.
**Done when:** `manage.py check --deploy` reports no warnings.

### SEC-06 — Throttling · P2 · S
Add DRF throttle classes (e.g. tighter on `/auth/login/`) to blunt abuse/brute
force.

### SEC-07 — Backups · P2 · M
Document and script `pg_dump` backups + restore. Note the `pgdata` volume
strategy. Critical for a business handling real sales data.

### SEC-08 — Production compose · P2 · S
A `docker-compose.prod.yml`: gunicorn (not runserver), no source bind-mount,
worker/timeout tuning, `restart: unless-stopped`, env from a real `.env`.

### SEC-09 — Brute-force protection · P3 · S
Lockout/backoff after repeated failed logins (e.g. `django-axes`).

> Quick win: run `python manage.py check --deploy` and work the list it prints —
> it covers most of SEC-02 and SEC-05 automatically.
