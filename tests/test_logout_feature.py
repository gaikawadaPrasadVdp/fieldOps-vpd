import json
import pytest
from django.test import Client
from apps.accounts.models import User
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


def test_logout_standard_post_clears_session_and_cookies(client):
    """Test standard POST logout invalidates session, deletes cookies, and redirects."""
    user = User.objects.create_user(email="logout.user@nexus.test", password="Password@123")
    client.force_login(user)

    # Verify user is authenticated
    resp_before = client.get("/accounts/profile/")
    assert resp_before.status_code == 200

    # Perform standard POST logout
    resp = client.post("/accounts/logout/")
    assert resp.status_code == 302
    assert "/accounts/login" in resp.url

    # Check cookies are marked for deletion
    assert resp.cookies["sessionid"]["max-age"] == 0 or resp.cookies["sessionid"].value == ""

    # Verify user is no longer authenticated
    resp_after = client.get("/accounts/profile/")
    assert resp_after.status_code == 302
    assert "/accounts/login" in resp_after.url


def test_logout_ajax_fetch_returns_json_and_logs_out(client, owner_a, org_a):
    """Test Fetch/AJAX POST logout (used by app.js cross-tab sync) returns JSON and logs out."""
    client.force_login(owner_a)

    # Perform AJAX logout
    resp = client.post(
        "/accounts/logout/",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        HTTP_ACCEPT="application/json",
    )
    assert resp.status_code == 200
    data = json.loads(resp.content.decode("utf-8"))
    assert data["status"] == "logged_out"
    assert data["redirect_url"].startswith("/accounts/login/")
    assert "next=/app/" in data["redirect_url"]

    # Check audit log recorded the logout
    audit_exists = AuditLog.objects.filter(action="auth.logout", actor=owner_a).exists()
    assert audit_exists, "AuditLog for auth.logout was not recorded"

    # Verify session is dead
    resp_after = client.get("/app/")
    assert resp_after.status_code == 302
    assert "/accounts/login" in resp_after.url


def test_logout_get_method_rejected(client, owner_a):
    """GET /accounts/logout/ must be rejected with 405 Method Not Allowed."""
    client.force_login(owner_a)

    resp = client.get("/accounts/logout/")
    assert resp.status_code == 405


def test_cross_tab_auth_sync_code_and_markup_present(client, owner_a):
    """Verify templates and static JavaScript have the cross-tab logout synchronization logic wired up."""
    client.force_login(owner_a)

    # Check dashboard markup contains the logout button with proper ids
    resp = client.get("/app/")
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert 'id="fx-logout-form"' in html
    assert 'id="fx-logout-btn"' in html
    assert "app.js" in html

    # Verify app.js contains the BroadcastChannel and storage listeners
    from django.contrib.staticfiles import finders
    app_js_path = finders.find("js/app.js")
    assert app_js_path is not None
    with open(app_js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "nexus_auth_sync" in js_code, "BroadcastChannel name missing"
    assert "nexus_logout_event" in js_code, "localStorage sync key missing"
    assert "broadcastLogout()" in js_code, "broadcastLogout function missing"
    assert "redirectToLogin()" in js_code, "redirectToLogin handler missing"
    assert 'window.addEventListener("storage"' in js_code or "window.addEventListener('storage'" in js_code


def test_authenticated_views_include_cache_prevention_headers(client, owner_a):
    """Authenticated views must include no-store, no-cache, and private headers to prevent bfcache leaks."""
    client.force_login(owner_a)
    resp = client.get("/app/")
    assert resp.status_code == 200

    cache_control = resp.headers.get("Cache-Control", "")
    assert "no-store" in cache_control, "Cache-Control must contain no-store"
    assert "no-cache" in cache_control, "Cache-Control must contain no-cache"
    assert "must-revalidate" in cache_control, "Cache-Control must contain must-revalidate"
    assert resp.headers.get("Pragma") == "no-cache"
    assert resp.headers.get("Expires") == "0"


def test_post_logout_back_navigation_denied(client, owner_a):
    """After logging out, requests to authenticated pages must redirect to login, preventing back-button bypass."""
    client.force_login(owner_a)
    resp_dash = client.get("/app/")
    assert resp_dash.status_code == 200

    # User logs out
    resp_logout = client.post("/accounts/logout/")
    assert resp_logout.status_code == 302

    # Attempting to access dashboard simulates back button requesting page from server
    resp_back = client.get("/app/")
    assert resp_back.status_code == 302
    assert "/accounts/login" in resp_back.headers.get("Location")


def test_app_js_includes_bfcache_and_history_replace():
    """app.js must handle bfcache pageshow events and use location.replace on logout."""
    from django.contrib.staticfiles import finders
    app_js_path = finders.find("js/app.js")
    assert app_js_path is not None
    with open(app_js_path, "r", encoding="utf-8") as f:
        js_code = f.read()

    assert "window.location.replace" in js_code, "app.js must use location.replace for clean logout history"
    assert "pageshow" in js_code, "app.js must listen to pageshow for bfcache detection"
    assert "event.persisted" in js_code, "app.js must inspect event.persisted"


def test_logout_then_login_lands_at_app(client, owner_a):
    """User story: If a user clicks log out and then logs in, they should land at /app location."""
    from tests.conftest import PASSWORD
    owner_a.set_password(PASSWORD)
    owner_a.save()

    # 1. User starts logged in at an inner page
    client.force_login(owner_a)
    r1 = client.get("/app/roles/")
    assert r1.status_code == 200

    # 2. User logs out via AJAX
    r_logout = client.post(
        "/accounts/logout/",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        HTTP_ACCEPT="application/json",
    )
    assert r_logout.status_code == 200
    logout_data = json.loads(r_logout.content.decode("utf-8"))
    assert "/accounts/login/" in logout_data["redirect_url"]

    # 3. User navigates to the login page
    r_login_page = client.get(logout_data["redirect_url"])
    assert r_login_page.status_code == 200

    # 4. User logs in again
    r_login_post = client.post(
        "/accounts/login/",
        {"username": owner_a.email, "password": PASSWORD, "next": "/app/"},
        follow=True,
    )
    # Must redirect and land directly at /app/
    assert r_login_post.status_code == 200
    assert r_login_post.request["PATH_INFO"] == "/app/"
    assert any(dest == "/app/" for dest, _ in r_login_post.redirect_chain)


def test_login_submit_with_slash_next_redirects_to_app(client, owner_a):
    """When user submits login form with next='/' (or from root landing), they must redirect to /app/."""
    from tests.conftest import PASSWORD
    owner_a.set_password(PASSWORD)
    owner_a.save()

    # Form markup check: visiting /accounts/login/?next=/ sets hidden next value to /app/
    resp_page = client.get("/accounts/login/?next=/")
    assert resp_page.status_code == 200
    assert '<input type="hidden" name="next" value="/app/">' in resp_page.content.decode("utf-8")

    # POST with next='/' explicitly should still safely redirect to /app/
    resp_post = client.post(
        "/accounts/login/",
        {"username": owner_a.email, "password": PASSWORD, "next": "/"},
        follow=True,
    )
    assert resp_post.status_code == 200
    assert resp_post.request["PATH_INFO"] == "/app/"
    assert any(dest == "/app/" for dest, _ in resp_post.redirect_chain)


def test_login_submit_with_accounts_next_redirects_to_app(client, owner_a):
    """When user arrives with next pointing to /accounts/*, login redirects to /app/."""
    from tests.conftest import PASSWORD
    owner_a.set_password(PASSWORD)
    owner_a.save()

    resp_post = client.post(
        "/accounts/login/",
        {"username": owner_a.email, "password": PASSWORD, "next": "/accounts/login/"},
        follow=True,
    )
    assert resp_post.status_code == 200
    assert resp_post.request["PATH_INFO"] == "/app/"
    assert any(dest == "/app/" for dest, _ in resp_post.redirect_chain)


