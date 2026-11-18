import time
import uuid
from pathlib import Path
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()
PASSWORD = "Password123!"
REPO_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def idle_org(make_org):
    suffix = uuid.uuid4().hex[:6]
    return make_org(f"Idle Org {suffix}", f"owner-{suffix}@idle.test")


@pytest.mark.django_db
def test_default_session_idle_timeout_is_5_minutes(client, idle_org, make_member):
    """Verifies that the session idle timeout defaults to 300s (5 minutes) across settings, context, and HTML."""
    assert settings.SESSION_IDLE_TIMEOUT_SECONDS == 300

    member = make_member(idle_org, "idle5@alpha.test", "operations_manager")
    client.force_login(member.user)

    resp = client.get("/app/")
    assert resp.status_code == 200
    assert b'data-idle-timeout-ms="300000"' in resp.content
    assert "_last_activity_ts" in client.session


@pytest.mark.django_db
def test_inactivity_over_5_minutes_triggers_server_side_logout_redirect(client, idle_org, make_member):
    """Simulates 5+ minutes (301s) of inactivity and verifies server-side session expiration and redirect."""
    member = make_member(idle_org, "idle-expire@alpha.test", "operations_manager")
    client.force_login(member.user)

    session = client.session
    # Set last activity to 305 seconds ago (> 300 seconds / 5 mins)
    session["_last_activity_ts"] = int(time.time()) - 305
    session.save()

    resp = client.get("/app/")
    assert resp.status_code == 302
    assert "/accounts/login/?logged_out=1" in resp["Location"]
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_inactivity_under_5_minutes_keeps_session_alive(client, idle_org, make_member):
    """Activity within 5 minutes keeps the session active and updates activity timestamp."""
    member = make_member(idle_org, "active-within-5@alpha.test", "operations_manager")
    client.force_login(member.user)

    stale_ts = int(time.time()) - 120  # 2 minutes ago
    session = client.session
    session["_last_activity_ts"] = stale_ts
    session.save()

    resp = client.get("/app/")
    assert resp.status_code == 200
    assert client.session["_last_activity_ts"] > stale_ts
    assert client.session["_auth_user_id"] == str(member.user.pk)


@pytest.mark.django_db
def test_background_notification_bell_poll_does_not_reset_inactivity_timer(client, idle_org, make_member):
    """Verifies that automated 60s background HTMX polling (/app/notifications/bell/) does NOT refresh _last_activity_ts."""
    member = make_member(idle_org, "bell-poll@alpha.test", "operations_manager")
    client.force_login(member.user)

    stale_ts = int(time.time()) - 180  # 3 minutes ago
    session = client.session
    session["_last_activity_ts"] = stale_ts
    session.save()

    # Background HTMX poll to notifications bell
    resp = client.get("/app/notifications/bell/", HTTP_HX_REQUEST="true")
    assert resp.status_code == 200

    # Ensure activity timestamp was NOT refreshed by the background poll
    assert client.session["_last_activity_ts"] == stale_ts
    assert client.session["_auth_user_id"] == str(member.user.pk)


@pytest.mark.django_db
def test_background_notification_bell_poll_after_5_minutes_triggers_htmx_redirect(client, idle_org, make_member):
    """Verifies that an HTMX background poll arriving after 5 minutes triggers an immediate HX-Redirect to login with timeout banner."""
    member = make_member(idle_org, "bell-poll-expired@alpha.test", "operations_manager")
    client.force_login(member.user)

    expired_ts = int(time.time()) - 310  # 5+ minutes ago
    session = client.session
    session["_last_activity_ts"] = expired_ts
    session.save()

    # Background HTMX poll with HX-Current-URL
    resp = client.get(
        "/app/notifications/bell/",
        HTTP_HX_REQUEST="true",
        HTTP_HX_CURRENT_URL="http://testserver/app/work-orders/",
    )
    assert resp.status_code == 200
    assert "HX-Redirect" in resp
    assert "/accounts/login/?logged_out=1&timeout=1&next=%2Fapp%2Fwork-orders%2F" in resp["HX-Redirect"]
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_page_renders_timeout_message_on_timeout_param(client):
    """When redirected with ?timeout=1, login view adds an informational inactivity banner."""
    resp = client.get("/accounts/login/?logged_out=1&timeout=1")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")
    assert "Your session has expired due to 5 minutes of inactivity" in content


def test_app_js_client_side_idle_timeout_configuration():
    """Verifies that client-side script app.js enforces the 5-minute (300000 ms) idle timer."""
    js_content = (REPO_ROOT / "src" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "data-idle-timeout-ms" in js_content
    assert "300000" in js_content
    assert "checkIdleExpiration" in js_content
    assert "performIdleSignOut" in js_content
    assert "nexus_last_activity_at" in js_content
