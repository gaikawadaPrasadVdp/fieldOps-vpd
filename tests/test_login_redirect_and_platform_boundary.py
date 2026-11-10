"""Regression tests for login redirection, platform admin boundary, and error page recovery.

Ensures that:
1. Newly created organization owners and tenant users are never routed to /platform/*
   even if a stale next=/platform/... parameter exists in the URL or form.
2. Platform admins are routed to /platform/organizations/.
3. Authenticated tenant users receiving a 403 on restricted endpoints have a working
   'Return to Dashboard' button linking to /app/ rather than the public landing page.
4. Tenant owners created via services.create_organization can log in immediately and access /app/.
"""
import re
import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from apps.tenancy import services as tenancy_services, selectors as tenancy_selectors

pytestmark = pytest.mark.django_db
User = get_user_model()
TEST_PASSWORD = "TenantOwnerPassword@2026!"


def get_browser():
    return Client(enforce_csrf_checks=True, HTTP_HOST="localhost")


def login_client(client, email, password, next_url=None):
    url = "/accounts/login/"
    if next_url:
        url += f"?next={next_url}"
    page = client.get(url)
    match = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())
    token = match.group(1) if match else ""
    post_data = {
        "csrfmiddlewaretoken": token,
        "username": email,
        "password": password,
    }
    if next_url:
        post_data["next"] = next_url
    return client.post(
        url,
        post_data,
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER=f"http://localhost{url}",
    )


def test_tenant_owner_login_with_platform_next_redirects_to_app(owner_a):
    from tests.conftest import PASSWORD

    owner_a.set_password(PASSWORD)
    owner_a.save()

    c = get_browser()
    # Log in with stale next pointing to platform admin
    resp = login_client(c, owner_a.email, PASSWORD, next_url="/platform/organizations/")
    assert resp.status_code == 302
    assert resp["Location"] == "/app/"

    # Follow to /app/ and ensure dashboard loads with 200
    home_resp = c.get("/app/")
    assert home_resp.status_code == 200
    assert c.session.get(tenancy_selectors.SESSION_KEY) is not None


def test_platform_admin_login_with_platform_next_redirects_to_platform(monkeypatch):
    from tests.test_login_integration import make_admin, PW

    admin = make_admin(monkeypatch, email="platadmin@fieldops.test", password=PW)
    c = get_browser()
    resp = login_client(c, admin.email, PW, next_url="/platform/organizations/")
    assert resp.status_code == 302
    assert resp["Location"] == "/platform/organizations/"

    plat_resp = c.get("/platform/organizations/")
    assert plat_resp.status_code == 200


def test_platform_admin_login_without_next_redirects_to_platform(monkeypatch):
    from tests.test_login_integration import make_admin, PW

    admin = make_admin(monkeypatch, email="platadmin2@fieldops.test", password=PW)
    c = get_browser()
    resp = login_client(c, admin.email, PW)
    assert resp.status_code == 302
    assert resp["Location"] == "/app/"
    final = c.get("/app/", follow=True)
    assert final.redirect_chain[-1][0] == "/platform/organizations/"
    assert final.status_code == 200


def test_tenant_owner_login_without_next_redirects_to_app(owner_a):
    from tests.conftest import PASSWORD

    owner_a.set_password(PASSWORD)
    owner_a.save()

    c = get_browser()
    resp = login_client(c, owner_a.email, PASSWORD)
    assert resp.status_code == 302
    assert resp["Location"] == "/app/"

    home_resp = c.get("/app/")
    assert home_resp.status_code == 200


def test_newly_created_organization_owner_logs_in_immediately():
    org, owner_m = tenancy_services.create_organization(
        name="Apex Robotics",
        slug="apex-robotics",
        owner_name="Apex Owner",
        owner_email="owner@apexrobotics.test",
        owner_password=TEST_PASSWORD,
        timezone_name="UTC",
        country="US",
    )
    assert owner_m.status == "ACTIVE"
    assert owner_m.user.is_platform_admin is False

    c = get_browser()
    # Attempt login with next pointing to /platform/organizations/
    resp = login_client(c, "owner@apexrobotics.test", TEST_PASSWORD, next_url="/platform/organizations/")
    assert resp.status_code == 302
    assert resp["Location"] == "/app/"

    # Verify /app/ cockpit loads cleanly
    home_resp = c.get("/app/")
    assert home_resp.status_code == 200
    assert "Apex Robotics" in home_resp.content.decode()


def test_403_page_renders_clean_dashboard_link_for_tenant_user(owner_a):
    from tests.conftest import PASSWORD

    owner_a.set_password(PASSWORD)
    owner_a.save()

    c = get_browser()
    login_client(c, owner_a.email, PASSWORD)

    # Directly hit /platform/organizations/ as tenant owner -> 403
    resp = c.get("/platform/organizations/")
    assert resp.status_code == 403
    content = resp.content.decode()
    assert "Permission Required" in content
    # Ensure Return to Dashboard links to /app/
    assert 'href="/app/"' in content
