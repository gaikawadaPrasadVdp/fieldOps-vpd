import pytest
from django.urls import reverse

from apps.tenancy.models import Membership, Organization
from apps.tenancy import services

pytestmark = pytest.mark.django_db


def test_platform_admin_can_view_organizations_ui(client, platform_admin, org_a):
    client.force_login(platform_admin)
    response = client.get(reverse("platform_admin:organizations"))
    assert response.status_code == 200
    assert org_a.name in response.content.decode()


def test_non_platform_admin_blocked_from_organizations_ui(client, owner_a):
    client.force_login(owner_a)
    response = client.get(reverse("platform_admin:organizations"))
    assert response.status_code == 403


def test_platform_admin_can_create_organization_ui(client, platform_admin):
    client.force_login(platform_admin)
    # GET form
    get_res = client.get(reverse("platform_admin:organization_create"))
    assert get_res.status_code == 200

    # POST create
    payload = {
        "name": "New Enterprise Org",
        "slug": "new-enterprise-org",
        "owner_name": "Edward Owner",
        "owner_email": "edward@newenterprise.test",
        "timezone": "America/New_York",
        "country": "US",
    }
    response = client.post(reverse("platform_admin:organization_create"), payload)
    assert response.status_code == 302
    assert response.url == reverse("platform_admin:organizations")

    org = Organization.objects.get(slug="new-enterprise-org")
    assert org.name == "New Enterprise Org"
    assert org.country == "US"
    assert org.timezone == "America/New_York"
    assert Membership.objects.unscoped().filter(organization=org, user__email="edward@newenterprise.test").exists()


def test_non_platform_admin_blocked_from_create_organization_ui(client, owner_a):
    client.force_login(owner_a)
    response = client.get(reverse("platform_admin:organization_create"))
    assert response.status_code == 403

    payload = {
        "name": "Malicious Org",
        "owner_name": "Hacker",
        "owner_email": "hacker@evil.test",
        "timezone": "UTC",
    }
    post_res = client.post(reverse("platform_admin:organization_create"), payload)
    assert post_res.status_code == 403


def test_platform_admin_can_delete_organization_ui(client, platform_admin, org_b):
    client.force_login(platform_admin)
    delete_url = reverse("platform_admin:organization_delete", kwargs={"org_id": org_b.pk})
    response = client.post(delete_url)
    assert response.status_code == 302
    assert response.url == reverse("platform_admin:organizations")

    # Due to seeded roles/audit, it should be safely decommissioned
    org_b.refresh_from_db()
    assert org_b.status == Organization.Status.SUSPENDED
    assert "Deleted/Decommissioned" in org_b.suspended_reason


def test_non_platform_admin_blocked_from_delete_organization_ui(client, owner_a, org_b):
    client.force_login(owner_a)
    delete_url = reverse("platform_admin:organization_delete", kwargs={"org_id": org_b.pk})
    response = client.post(delete_url)
    assert response.status_code == 403


def test_platform_admin_api_list_and_retrieve(as_user, platform_admin, org_a):
    client = as_user(platform_admin)
    res = client.get("/api/v1/platform/organizations/")
    assert res.status_code == 200
    data = res.json()
    assert any(item["id"] == str(org_a.id) for item in data)

    detail_res = client.get(f"/api/v1/platform/organizations/{org_a.id}/")
    assert detail_res.status_code == 200
    assert detail_res.json()["name"] == org_a.name


def test_platform_admin_api_create_organization(as_user, platform_admin):
    client = as_user(platform_admin)
    payload = {
        "name": "API Created Org",
        "slug": "api-created-org",
        "owner_name": "API Owner",
        "owner_email": "api.owner@example.test",
        "timezone": "Europe/London",
        "country": "GB",
    }
    res = client.post("/api/v1/platform/organizations/", payload, format="json")
    assert res.status_code == 201
    created_id = res.json()["id"]
    org = Organization.objects.get(id=created_id)
    assert org.slug == "api-created-org"
    assert org.timezone == "Europe/London"


def test_platform_admin_api_delete_organization(as_user, platform_admin, org_b):
    client = as_user(platform_admin)
    res = client.delete(f"/api/v1/platform/organizations/{org_b.id}/")
    assert res.status_code == 200
    assert res.json()["success"] is True

    org_b.refresh_from_db()
    assert org_b.status == Organization.Status.SUSPENDED


def test_org_admin_blocked_from_platform_api(as_user, owner_a, org_a, org_b):
    client = as_user(owner_a, org_a)

    # Cannot list
    assert client.get("/api/v1/platform/organizations/").status_code == 403

    # Cannot retrieve
    assert client.get(f"/api/v1/platform/organizations/{org_a.id}/").status_code == 403

    # Cannot create
    assert client.post("/api/v1/platform/organizations/", {
        "name": "Unauthorized Org",
        "owner_name": "Nobody",
        "owner_email": "nobody@test.com",
    }, format="json").status_code == 403

    # Cannot delete
    assert client.delete(f"/api/v1/platform/organizations/{org_b.id}/").status_code == 403


def test_org_admin_cannot_create_or_delete_via_tenant_api(as_user, owner_a, org_a):
    client = as_user(owner_a, org_a)

    # POST to tenant /api/v1/organization/ is blocked (403 Forbidden or 405 Method Not Allowed)
    post_res = client.post("/api/v1/organization/", {"name": "Changed Name"}, format="json")
    assert post_res.status_code in (403, 405)

    # DELETE to tenant /api/v1/organization/ is blocked (403 Forbidden or 405 Method Not Allowed)
    del_res = client.delete("/api/v1/organization/")
    assert del_res.status_code in (403, 405)

def test_platform_admin_toggle_organization_status_ui(client, platform_admin, org_a):
    client.force_login(platform_admin)
    status_url = reverse("platform_admin:organization_toggle_status", kwargs={"org_id": org_a.pk})

    # Deactivate
    res = client.post(status_url, {"reason": "Maintenance window"})
    assert res.status_code == 302
    org_a.refresh_from_db()
    assert org_a.status == Organization.Status.SUSPENDED
    assert org_a.suspended_reason == "Maintenance window"

    # Re-activate
    res2 = client.post(status_url)
    assert res2.status_code == 302
    org_a.refresh_from_db()
    assert org_a.status == Organization.Status.ACTIVE


def test_platform_admin_set_status_api(as_user, platform_admin, org_a):
    client = as_user(platform_admin)

    # Deactivate via API
    res = client.post(f"/api/v1/platform/organizations/{org_a.id}/status/", {
        "active": False,
        "reason": "Payment overdue",
    }, format="json")
    assert res.status_code == 200
    assert res.json()["status"] == "SUSPENDED"

    org_a.refresh_from_db()
    assert org_a.status == Organization.Status.SUSPENDED

    # Reactivate via API
    res2 = client.post(f"/api/v1/platform/organizations/{org_a.id}/status/", {
        "active": True,
    }, format="json")
    assert res2.status_code == 200
    assert res2.json()["status"] == "ACTIVE"


def test_platform_admin_redirected_away_from_tenant_app_url(client, platform_admin):
    client.force_login(platform_admin)
    res = client.get("/app/", follow=False)
    assert res.status_code == 302
    assert res["Location"] == reverse("platform_admin:organizations")


def test_platform_admin_sidebar_has_no_tenant_modules(client, platform_admin):
    client.force_login(platform_admin)
    res = client.get(reverse("platform_admin:organizations"))
    assert res.status_code == 200
    content = res.content.decode()

    # Must contain platform governance items
    assert "Organizations" in content
    assert "Platform audit" in content

    # Must NOT contain tenant operational modules in the sidebar
    assert "Work Orders" not in content
    assert "Incident &amp; Requests" not in content
    assert "Asset Lifecycle" not in content

