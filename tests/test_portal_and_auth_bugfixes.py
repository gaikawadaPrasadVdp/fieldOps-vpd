from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.assets import services as asset_services
from apps.portal.forms import PortalServiceRequestForm
from apps.portal.models import PortalAccount
from apps.rbac.models import Role
from apps.sites import services as site_services
from apps.tenancy import services as tenancy_services

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Correct-Horse-Battery-9"


def test_bug001_new_sites_and_assets_sync_to_client_portal_dropdowns(
    client, as_user, org_a, org_b, owner_a, owner_b, make_category
):
    """BUG-001: Newly created sites and assets in management console immediately appear in client portal."""
    client_role = Role.objects.unscoped().get(organization=org_a, system_key="client_requester")
    client_mem = tenancy_services.invite_member(
        org_a,
        email="bug001.client@alpha.test",
        full_name="Bug One Client",
        role_ids=[client_role.pk],
        actor=owner_a,
        password=PASSWORD,
    )
    account = PortalAccount.objects.get(organization=org_a, membership=client_mem)
    assert account.auto_grant_assets is True

    category_a = make_category(org_a, "HVAC")
    created_sites = []
    created_assets = []
    for idx in range(1, 4):
        site = site_services.create_site(
            org_a,
            actor=owner_a,
            code=f"NEW-S{idx}",
            name=f"New Facility {idx}",
        )
        asset = asset_services.create_asset(
            org_a,
            site=site,
            category=category_a,
            actor=owner_a,
            asset_tag=f"NEW-TAG-{idx:02d}",
            name=f"New Equipment {idx}",
        )
        created_sites.append(site)
        created_assets.append(asset)

    # Foreign org site/asset must never leak into org_a client portal
    foreign_site = site_services.create_site(org_b, actor=owner_b, code="ORG-B-S1", name="Foreign Site")
    foreign_cat = make_category(org_b, "Boiler")
    foreign_asset = asset_services.create_asset(
        org_b,
        site=foreign_site,
        category=foreign_cat,
        actor=owner_b,
        asset_tag="FOREIGN-99",
        name="Foreign Boiler",
    )

    form = PortalServiceRequestForm(organization=org_a, membership=client_mem)
    site_ids = set(form.fields["site"].queryset.values_list("pk", flat=True))
    asset_ids = set(form.fields["asset"].queryset.values_list("pk", flat=True))

    for s in created_sites:
        assert s.pk in site_ids
    for a in created_assets:
        assert a.pk in asset_ids
    assert foreign_site.pk not in site_ids
    assert foreign_asset.pk not in asset_ids

    # Verify UI dropdown rendering & API payload
    client.force_login(client_mem.user)
    res_ui = client.get("/app/portal/requests/new/")
    assert res_ui.status_code == 200
    html = res_ui.content.decode("utf-8")
    for s in created_sites:
        assert s.name in html
    for a in created_assets:
        assert a.asset_tag in html
    assert foreign_asset.asset_tag not in html

    api = as_user(client_mem.user, org_a)
    res_api = api.get("/api/v1/portal/assets/")
    assert res_api.status_code == 200
    api_tags = {item["asset_tag"] for item in res_api.json()["results"]}
    assert {"NEW-TAG-01", "NEW-TAG-02", "NEW-TAG-03"}.issubset(api_tags)
    assert "FOREIGN-99" not in api_tags


def test_bug001_site_scoped_client_only_receives_new_assets_in_assigned_site(
    org_a, owner_a, site_a1, site_a2, make_category
):
    client_role = Role.objects.unscoped().get(organization=org_a, system_key="client_requester")
    scoped_mem = tenancy_services.invite_member(
        org_a,
        email="bug001.scoped@alpha.test",
        full_name="Scoped Client",
        role_ids=[client_role.pk],
        site_ids=[site_a1.pk],
        actor=owner_a,
        password=PASSWORD,
    )

    cat = make_category(org_a, "Pump")
    a_in_scope = asset_services.create_asset(
        org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="SCOPED-A1", name="In Scope Pump"
    )
    a_out_scope = asset_services.create_asset(
        org_a, site=site_a2, category=cat, actor=owner_a, asset_tag="SCOPED-A2", name="Out Scope Pump"
    )

    form = PortalServiceRequestForm(organization=org_a, membership=scoped_mem)
    asset_ids = set(form.fields["asset"].queryset.values_list("pk", flat=True))
    assert a_in_scope.pk in asset_ids
    assert a_out_scope.pk not in asset_ids

    # Moving a_out_scope into site_a1 syncs it to scoped client
    asset_services.update_asset(a_out_scope, actor=owner_a, site=site_a1, reason="Relocated to site one")
    form_after = PortalServiceRequestForm(organization=org_a, membership=scoped_mem)
    assert a_out_scope.pk in set(form_after.fields["asset"].queryset.values_list("pk", flat=True))


def test_bug002_portal_request_create_client_and_server_validation(
    client, org_a, site_a1, make_asset, make_portal_client
):
    """BUG-002: Create Service Request form renders robust client-side validation & rejects invalid data."""
    user, membership, account = make_portal_client(org_a, "bug002.client@alpha.test")
    asset = make_asset(org_a, site_a1, "PUMP-VAL-01")
    from apps.portal.services import grant_portal_asset
    grant_portal_asset(account, asset)

    client.force_login(user)
    res_get = client.get("/app/portal/requests/new/")
    assert res_get.status_code == 200
    html = res_get.content.decode("utf-8")

    for el_id in (
        'id="title-error"',
        'id="site-error"',
        'id="asset-error"',
        'id="description-error"',
        'id="severity-error"',
        'id="service_impact-error"',
        'id="impact_notes-error"',
        'id="attachment-error"',
        'id="portal-no-site-assets-msg"',
    ):
        assert el_id in html

    assert "Please select a related asset." in html
    assert "validateTitle()" in html
    assert "validateAsset()" in html
    assert "validateAttachment()" in html

    # Empty fields & unselected asset rejected by server
    res_empty = client.post("/app/portal/requests/new/", {"title": "   ", "asset": ""})
    assert res_empty.status_code == 400
    assert "title" in res_empty.context["form"].errors
    assert "asset" in res_empty.context["form"].errors

    # Special character strings rejected
    res_special = client.post(
        "/app/portal/requests/new/",
        {
            "title": "@@@###$$$",
            "asset": str(asset.pk),
            "description": "--- !!!",
            "severity": "MEDIUM",
            "service_impact": "NONE",
        },
    )
    assert res_special.status_code == 400
    assert "title" in res_special.context["form"].errors
    assert "description" in res_special.context["form"].errors


def test_bug003_login_after_logout_redirect_succeeds_with_csrf_enforcement(owner_a):
    """BUG-003: Logout -> /accounts/login/?logged_out=1&next=... -> credential POST succeeds under CSRF."""
    owner_a.set_password(PASSWORD)
    owner_a.save(update_fields=["password"])

    browser = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")

    # 1. Initial login
    get_login = browser.get("/accounts/login/")
    assert get_login.status_code == 200
    assert "csrftoken" in get_login.cookies
    token_1 = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', get_login.content.decode()).group(1)

    post_login = browser.post(
        "/accounts/login/",
        {"csrfmiddlewaretoken": token_1, "username": owner_a.email, "password": PASSWORD},
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER="http://localhost/accounts/login/",
    )
    assert post_login.status_code == 302
    assert post_login["Location"] == "/app/"

    # 2. Logout via AJAX (mirrors app.js logout flow)
    csrf_cookie = browser.cookies["csrftoken"].value
    logout_resp = browser.post(
        "/accounts/logout/",
        {"csrfmiddlewaretoken": csrf_cookie},
        HTTP_X_CSRFTOKEN=csrf_cookie,
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        HTTP_ACCEPT="application/json",
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER="http://localhost/app/",
    )
    assert logout_resp.status_code == 200
    # Must NOT wipe csrftoken or send Clear-Site-Data: "cookies"
    assert '"cookies"' not in logout_resp.headers.get("Clear-Site-Data", "")
    assert "csrftoken" not in logout_resp.cookies or logout_resp.cookies["csrftoken"].value != ""

    # 3. Redirected to /accounts/login/?logged_out=1&next=/app/portal/
    get_redirected = browser.get("/accounts/login/?logged_out=1&next=%2Fapp%2Fportal%2F")
    assert get_redirected.status_code == 200
    html = get_redirected.content.decode("utf-8")
    assert 'action="/accounts/login/"' in html
    assert 'name="next" value="/app/portal/"' in html
    assert "csrftoken" in browser.cookies

    token_2 = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', html).group(1)

    # 4. Submit login form (both clean action="/accounts/login/" and direct query-param URL)
    post_relogin = browser.post(
        "/accounts/login/",
        {
            "csrfmiddlewaretoken": token_2,
            "username": owner_a.email,
            "password": PASSWORD,
            "next": "/app/portal/",
        },
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER="http://localhost/accounts/login/?logged_out=1&next=%2Fapp%2Fportal%2F",
    )
    assert post_relogin.status_code == 302
    assert post_relogin["Location"] == "/app/portal/"

    # 5. Submitting with ?logged_out=1&next=... in POST URL also succeeds cleanly
    browser.post(
        "/accounts/logout/",
        {"csrfmiddlewaretoken": browser.cookies["csrftoken"].value},
        HTTP_X_CSRFTOKEN=browser.cookies["csrftoken"].value,
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER="http://localhost/app/portal/",
    )
    r3 = browser.get("/accounts/login/?logged_out=1&next=%2Fapp%2F")
    token_3 = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', r3.content.decode()).group(1)
    post_qp = browser.post(
        "/accounts/login/?logged_out=1&next=%2Fapp%2F",
        {"csrfmiddlewaretoken": token_3, "username": owner_a.email, "password": PASSWORD, "next": "/app/"},
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER="http://localhost/accounts/login/?logged_out=1&next=%2Fapp%2F",
    )
    assert post_qp.status_code == 302
    assert post_qp["Location"] == "/app/"

    # 6. CSRF enforcement still blocks forged/missing token POSTs
    anon = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
    forged = anon.post(
        "/accounts/login/",
        {"username": owner_a.email, "password": PASSWORD},
        HTTP_ORIGIN="http://localhost",
        HTTP_REFERER="http://localhost/accounts/login/",
    )
    assert forged.status_code == 403
