import pytest
from django.urls import reverse
from apps.tenancy.models import Membership, Organization
from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_platform_admin_can_create_user_for_organization_api(as_user, platform_admin, org_a):
    """Gap 3 Fix: Platform Admin can create users / Super Admins through REST API."""
    client = as_user(platform_admin)

    # 1. Via nested endpoint: /api/v1/platform/organizations/{id}/users/
    payload = {
        "email": "first.superadmin@example.test",
        "first_name": "John",
        "last_name": "Doe",
        "role": "SUPER_ADMIN",
        "password": "SuperStrongPassword123!",
        "phone": "+1-555-0100",
    }
    res = client.post(f"/api/v1/platform/organizations/{org_a.id}/users/", payload, format="json")
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "first.superadmin@example.test"
    assert data["full_name"] == "John Doe"

    user = User.objects.get(email="first.superadmin@example.test")
    assert user.check_password("SuperStrongPassword123!")
    assert user.is_staff is True
    assert user.phone == "+1-555-0100"

    m = Membership.objects.unscoped().get(user=user, organization=org_a)
    assert m.status == Membership.Status.ACTIVE
    role_names = [r["name"] for r in data["roles"]]
    assert any("Admin" in r or "Owner" in r for r in role_names)

    # 2. Via root platform endpoint: /api/v1/platform/users/
    payload2 = {
        "organization": str(org_a.id),
        "email": "technician.api@example.test",
        "first_name": "Tech",
        "last_name": "One",
        "role": "FIELD_TECHNICIAN",
        "password": "SuperStrongPassword123!",
    }
    res2 = client.post("/api/v1/platform/users/", payload2, format="json")
    assert res2.status_code == 201
    assert res2.json()["email"] == "technician.api@example.test"


def test_users_api_alias_and_role_workflow_payload(as_user, owner_a, org_a):
    """Step 2 in ROLE_WORKFLOWS.md: POST /api/v1/users/ with role string & name components."""
    client = as_user(owner_a, org_a)

    # POST /api/v1/users/
    payload = {
        "email": "ravi.workflow@acme.test",
        "password": "a-strong-password-123",
        "first_name": "Ravi",
        "last_name": "Kumar",
        "phone": "+91 90000 00000",
        "role": "FIELD_TECHNICIAN",
    }
    res = client.post("/api/v1/users/", payload, format="json")
    assert res.status_code == 201
    data = res.json()
    assert data["email"] == "ravi.workflow@acme.test"
    assert data["full_name"] == "Ravi Kumar"
    member_id = data["id"]

    # PATCH /api/v1/users/{id}/ with role change
    patch_role_res = client.patch(f"/api/v1/users/{member_id}/", {"role": "SUPERVISOR"}, format="json")
    assert patch_role_res.status_code == 200
    roles = [r["name"] for r in patch_role_res.json()["roles"]]
    assert any("Supervisor" in r for r in roles)

    # PATCH /api/v1/users/{id}/ with is_active deactivation
    patch_deact_res = client.patch(f"/api/v1/users/{member_id}/", {"is_active": False}, format="json")
    assert patch_deact_res.status_code == 200
    m = Membership.objects.unscoped().get(id=member_id)
    assert m.status == Membership.Status.SUSPENDED


def test_contacts_api_alias(as_user, owner_a, org_a, site_a1):
    """Step 1 in ROLE_WORKFLOWS.md: /api/v1/contacts/ endpoint alias."""
    client = as_user(owner_a, org_a)
    res = client.get("/api/v1/contacts/")
    assert res.status_code == 200


def test_admin_landing_redirects_prevent_dead_ends(client, platform_admin, owner_a):
    """Gap 2 Fix: /admin/ landing redirects gracefully depending on role."""
    # 1. Anonymous user redirected to login
    res_anon = client.get("/admin/")
    assert res_anon.status_code == 302
    assert "/accounts/login/" in res_anon.url

    # 2. Platform Admin redirected to platform console
    client.force_login(platform_admin)
    res_plat = client.get("/admin/")
    assert res_plat.status_code == 302
    assert res_plat.url == reverse("platform_admin:organizations")

    # 3. Tenant Admin redirected to tenant home dashboard
    client.force_login(owner_a)
    res_tenant = client.get("/admin/")
    assert res_tenant.status_code == 302
    assert res_tenant.url == reverse("ui:home")


def test_technician_landing_dashboard_redirect(client, tech_a):
    """ROLE_WORKFLOWS.md Section 1 & 4.5: /technician/dashboard/ lands on workspace."""
    client.force_login(tech_a)
    
    # 1. Root-level /technician/dashboard/
    res1 = client.get("/technician/dashboard/")
    assert res1.status_code == 302
    assert res1.url == "/app/workspace/"
    
    # 2. App-level /app/technician/dashboard/
    res2 = client.get("/app/technician/dashboard/")
    assert res2.status_code == 302
    assert res2.url == "/app/workspace/"


def test_technician_sidebar_navigation_sections(rf, org_a, make_member):
    """ROLE_WORKFLOWS.md Section 4.5: Field Technician sidebar navigation."""
    from apps.ui.context_processors import shell
    
    tech = make_member(org_a, "tech.sidebar@alpha.test", "technician")
    request = rf.get("/app/workspace/")
    request.user = tech.user
    request.organization = org_a
    request.membership = tech
    
    ctx = shell(request)
    sections = ctx["shell_nav_sections"]
    
    assert "Workspace" in sections
    assert any(item["label"] == "Technician Workspace" for item in sections["Workspace"])
    
    assert "Service" in sections
    assert any(item["label"] == "Work Orders" for item in sections["Service"])
    assert any(item["label"] == "Inspections" for item in sections["Service"])
    
    assert "Assets" in sections
    assert any(item["label"] == "Asset Register" for item in sections["Assets"])
    assert any(item["label"] == "Scan QR" for item in sections["Assets"])


def test_dispatcher_supervisor_portal_landing_redirects(client, make_member, org_a):
    """ROLE_WORKFLOWS.md Section 1: Landing URLs for Dispatcher, Supervisor, and Portal."""
    disp = make_member(org_a, "disp.land@alpha.test", "service_dispatcher")
    client.force_login(disp.user)
    
    # 1. /dispatcher/dashboard/
    res_disp = client.get("/dispatcher/dashboard/")
    assert res_disp.status_code == 302
    assert res_disp.url == "/app/"
    
    # 2. /supervisor/dashboard/
    res_sup = client.get("/supervisor/dashboard/")
    assert res_sup.status_code == 302
    assert res_sup.url == "/app/"
    
    # 3. /portal/view/
    res_portal = client.get("/portal/view/")
    assert res_portal.status_code == 302
    assert res_portal.url == "/app/portal/"


def test_service_dispatcher_sidebar_navigation_sections(rf, org_a, make_member):
    """ROLE_WORKFLOWS.md Section 4.4 & 6: Dispatcher navigation includes Analytics Hub."""
    from apps.ui.context_processors import shell
    
    disp = make_member(org_a, "disp.nav@alpha.test", "service_dispatcher")
    request = rf.get("/app/")
    request.user = disp.user
    request.organization = org_a
    request.membership = disp
    
    ctx = shell(request)
    sections = ctx["shell_nav_sections"]
    
    assert "Operations" in sections
    assert any(item["label"] == "Work Orders" for item in sections["Operations"])
    assert any(item["label"] == "Inspections" for item in sections["Operations"])
    
    assert "Assets" in sections
    assert any(item["label"] == "Asset Register" for item in sections["Assets"])
    assert any(item["label"] == "Scan QR" for item in sections["Assets"])
    
    assert "Analytics" in sections
    assert any(item["label"] == "Analytics Hub" for item in sections["Analytics"])


def test_module_14_dashboards_hub_and_api(client, as_user, org_a, site_a1, make_member):
    """M14 Operational Dashboards: UI Hub and REST API endpoints."""
    disp = make_member(org_a, "disp.m14@alpha.test", "service_dispatcher")
    
    # UI Hub /app/dashboards/
    client.force_login(disp.user)
    session = client.session
    session["active_org_id"] = str(org_a.pk)
    session.save()
    
    res_ui = client.get("/app/dashboards/")
    assert res_ui.status_code == 200
    assert "Operational Dashboards" in res_ui.content.decode() or "Analytics" in res_ui.content.decode()
    
    # REST API /api/v1/dashboards/
    api_client = as_user(disp.user, org_a)
    res_api = api_client.get("/api/v1/dashboards/")
    assert res_api.status_code == 200
    data = res_api.json()
    assert "kpis" in data
    assert "operations" in data["sections"]
    assert "assets" in data["sections"]
    assert "maintenance" in data["sections"]
    assert "service" in data["sections"]
    assert "inventory" in data["sections"]
