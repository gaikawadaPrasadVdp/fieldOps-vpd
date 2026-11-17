import time
import pytest
from axes.handlers.proxy import AxesProxyHandler
from axes.models import AccessAttempt
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture(autouse=True)
def clean_axes_and_cache():
    AxesProxyHandler.reset_attempts()
    AccessAttempt.objects.all().delete()
    from django.core.cache import cache
    cache.clear()
    yield
    AxesProxyHandler.reset_attempts()
    AccessAttempt.objects.all().delete()
    cache.clear()


@pytest.mark.django_db
def test_auth_009_empty_credentials_returns_400():
    """AUTH-009: Empty credentials POST /auth/token/ must return HTTP 400 (never 429 or 500)."""
    api = APIClient()
    # Test both /auth/token/ and /api/v1/auth/token/
    for path in ("/auth/token/", "/api/v1/auth/token/"):
        resp = api.post(path, {"email": "", "password": ""}, format="json")
        assert resp.status_code == 400, f"Expected 400 for {path}, got {resp.status_code}: {resp.content}"
        data = resp.json()
        assert "error" in data or "email" in data


@pytest.mark.django_db
def test_auth_010_whitespace_credentials_returns_400():
    """AUTH-010: Whitespace credentials POST /auth/token/ must return HTTP 400 (never 429 or 500)."""
    api = APIClient()
    for path in ("/auth/token/", "/api/v1/auth/token/"):
        resp = api.post(path, {"email": "   ", "password": "   "}, format="json")
        assert resp.status_code == 400, f"Expected 400 for {path}, got {resp.status_code}: {resp.content}"
        data = resp.json()
        assert "error" in data or "email" in data


@pytest.mark.django_db
def test_auth_050_brute_force_lockout_after_5_failures():
    """AUTH-050: 7 consecutive failed logins must lockout (HTTP 429) after 5 failures."""
    api = APIClient()
    target_email = "nonexistent_brute_force_test@nexus.local"
    statuses = []

    for i in range(7):
        resp = api.post(
            "/api/v1/auth/token/",
            {"email": target_email, "password": f"wrong-pass-{i}"},
            format="json",
        )
        statuses.append(resp.status_code)

    # First 5 should fail with 401 Unauthorized
    assert statuses[:5] == [401, 401, 401, 401, 401], f"Expected first 5 to be 401, got {statuses}"
    # Attempts 6 and 7 must be locked out with HTTP 429
    assert statuses[5:] == [429, 429], f"Expected attempts 6 and 7 to be 429 lockout, got {statuses}"


@pytest.mark.django_db
def test_auth_074_access_token_revoked_after_logout():
    """AUTH-074: Access token used on GET /auth/me/ after logout must return HTTP 401 (revoked)."""
    user = User.objects.create_user(
        email="token_revoke_test@nexus.local",
        password="ValidPassword123!",
        full_name="Revoke Test User",
    )

    api = APIClient()
    # 1. Obtain tokens
    login_resp = api.post(
        "/api/v1/auth/token/",
        {"email": "token_revoke_test@nexus.local", "password": "ValidPassword123!"},
        format="json",
    )
    assert login_resp.status_code == 200, login_resp.content
    tokens = login_resp.json()
    access_token = tokens["access"]
    refresh_token = tokens["refresh"]

    # 2. Verify access token works on /auth/me/ before logout
    api.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    me_resp = api.get("/api/v1/auth/me/")
    assert me_resp.status_code == 200, me_resp.content
    assert me_resp.json()["email"] == "token_revoke_test@nexus.local"

    # Also test /auth/me/ route
    me_resp_root = api.get("/auth/me/")
    assert me_resp_root.status_code == 200, me_resp_root.content

    # 3. Perform logout
    time.sleep(0.05)  # Ensure issued_at < logout timestamp
    logout_resp = api.post(
        "/api/v1/auth/logout/",
        {"refresh": refresh_token},
        format="json",
    )
    assert logout_resp.status_code == 200, logout_resp.content

    # 4. Reuse access token after logout on /auth/me/ -> must return 401
    reuse_resp = api.get("/api/v1/auth/me/")
    assert reuse_resp.status_code == 401, f"Expected 401 revoked after logout, got {reuse_resp.status_code}: {reuse_resp.content}"

    reuse_resp_root = api.get("/auth/me/")
    assert reuse_resp_root.status_code == 401, f"Expected 401 revoked after logout, got {reuse_resp_root.status_code}: {reuse_resp_root.content}"
