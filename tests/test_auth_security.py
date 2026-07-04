"""Auth/security: JWT login, server-side logout via blacklist (SEC-03)."""
import pytest

pytestmark = pytest.mark.django_db


def test_login_returns_tokens(api, cashier_user):
    resp = api.post(
        "/api/auth/login/",
        {"username": "cashier", "password": "pass12345"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access" in body and "refresh" in body


def test_login_updates_last_login(api, cashier_user):
    assert cashier_user.last_login is None

    resp = api.post(
        "/api/auth/login/",
        {"username": "cashier", "password": "pass12345"},
        format="json",
    )
    assert resp.status_code == 200

    cashier_user.refresh_from_db()
    assert cashier_user.last_login is not None


def test_logout_blacklists_refresh_token(api, cashier_user):
    tokens = api.post(
        "/api/auth/login/",
        {"username": "cashier", "password": "pass12345"},
        format="json",
    ).json()
    api.force_authenticate(user=cashier_user)

    # Logout blacklists the refresh token.
    out = api.post("/api/auth/logout/", {"refresh": tokens["refresh"]}, format="json")
    assert out.status_code == 200

    # The blacklisted refresh token can no longer mint a new access token.
    api.force_authenticate(user=None)
    refreshed = api.post(
        "/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json"
    )
    assert refreshed.status_code == 401
