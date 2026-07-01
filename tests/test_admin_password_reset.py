import pytest

pytestmark = pytest.mark.django_db


def test_admin_can_reset_user_password_via_user_update(api, admin_user, cashier_user):
    api.force_authenticate(user=admin_user)

    response = api.patch(
        f"/api/auth/users/{cashier_user.id}/",
        {"password": "NewPass123!"},
        format="json",
    )

    assert response.status_code == 200
    cashier_user.refresh_from_db()
    assert cashier_user.check_password("NewPass123!")
    assert not cashier_user.check_password("pass12345")
