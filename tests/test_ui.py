import pytest

from apps.rbac.models import Role
from apps.tenancy.models import Membership

pytestmark = pytest.mark.django_db

OWNER_PAGES = [
    "/app/", "/app/organization/", "/app/users/", "/app/users/invite/", "/app/roles/",
    "/app/roles/new/", "/app/audit/", "/app/notifications/", "/app/notifications/bell/",
    "/app/search/?q=ow"
]

PUBLIC_PAGES = [
    "/",
    "/features/",
    "/solutions/",
    "/solutions/enterprise-operations/",
    "/modules/",
    "/modules/FON-M01/",
    "/resources/",
    "/about/",
    "/legal/privacy-policy/",
    "/legal/terms-and-conditions/",
]


@pytest.mark.parametrize("url", PUBLIC_PAGES)
def test_public_pages_render_for_anonymous_visitors(client, url):
    r = client.get(url)
    assert r.status_code == 200, f"Public page failed: {url}"
    assert "FieldOps Nexus" in r.content.decode()


def test_authenticated_user_redirected_from_root(client, owner_a):
    client.force_login(owner_a)
    r = client.get("/")
    assert r.status_code == 302
    assert r["Location"] == "/app/"


@pytest.mark.parametrize("url", OWNER_PAGES)
def test_owner_pages_render(client, owner_a, url):
    client.force_login(owner_a)
    r = client.get(url)
    assert r.status_code == 200, url


@pytest.mark.parametrize("url", ["/app/users/", "/app/users/invite/", "/app/roles/", "/app/roles/new/",
                                 "/app/audit/", "/app/organization/"])
def test_technician_forbidden_from_admin_pages(client, tech_a, url):
    client.force_login(tech_a)
    assert client.get(url).status_code == 403


def test_asset_manager_forbidden_from_admin_and_nav_filtered(client, org_a, make_member):
    asset_mgr = make_member(org_a, "asset.mgr.test@alpha.test", "asset_manager")
    client.force_login(asset_mgr.user)

    # 1. Admin endpoints strictly return 403 Forbidden
    for url in ("/app/organization/", "/app/users/", "/app/roles/", "/app/portal/accounts/", "/app/audit/"):
        assert client.get(url).status_code == 403, f"Expected 403 for {url}"

    # 2. Left sidebar excludes Administration and Compliance items
    html = client.get("/app/").content.decode()
    nav_html = html.split("fx-nav")[1] if "fx-nav" in html else html
    for forbidden_label in ("Organization", "Users", "Roles &amp; Permissions", "Portal Accounts", "Audit Trail"):
        assert forbidden_label not in nav_html

    # 3. Operational overview shows asset/site metrics, not administrative user/role counts
    assert "Master Assets" in html
    assert "Facility Sites" in html


def test_nav_is_permission_filtered(client, owner_a, tech_a):
    client.force_login(owner_a)
    html = client.get("/app/").content.decode()
    assert "Audit Trail" in html and "Roles &amp; Permissions" in html
    client.force_login(tech_a)
    html = client.get("/app/").content.decode()
    assert "Audit Trail" not in html and "Users" not in html.split("fx-nav")[1]


@pytest.mark.parametrize("url", ["/app/", "/app/users/", "/app/audit/"])
def test_anonymous_redirected_to_login(client, url):
    r = client.get(url)
    assert r.status_code == 302 and "/accounts/login/" in r["Location"]


def test_invite_form_persists_and_audits(client, owner_a, org_a):
    client.force_login(owner_a)
    rid = Role.objects.unscoped().get(organization=org_a, system_key="technician").pk
    r = client.post("/app/users/invite/", {"email": "new.tech@alpha.test", "full_name": "New Tech", "roles": [rid]})
    assert r.status_code == 302
    m = Membership.objects.unscoped().get(organization=org_a, user__email="new.tech@alpha.test")
    assert m.status == "INVITED"


def test_member_actions_via_ui_require_permission(client, tech_a, org_a, owner_a):
    m = Membership.objects.unscoped().get(organization=org_a, user=owner_a)
    client.force_login(tech_a)
    assert client.post(f"/app/users/{m.pk}/", {"action": "deactivate"}).status_code == 403


def test_logout_requires_post(client, owner_a):
    client.force_login(owner_a)
    assert client.get("/accounts/logout/").status_code == 405


def test_csrf_enforced_on_ui_posts(owner_a):
    from django.test import Client
    c = Client(enforce_csrf_checks=True)
    c.force_login(owner_a)
    assert c.post("/app/switch-organization/", {"organization": "x"}).status_code == 403


def test_security_headers(client):
    r = client.get("/accounts/login/")
    assert r["X-Frame-Options"] == "DENY" and r["X-Content-Type-Options"] == "nosniff"
    assert r["X-Request-ID"]


def test_login_page_renders_with_branded_identity(client):
    r = client.get("/accounts/login/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "FieldOps Nexus" in html
    assert "Sign in with your enterprise credentials" in html
    assert "Client Onboarding" in html or "Requester" in html


def test_client_registration_flow(client):
    from apps.audit.models import AuditLog

    # 1. GET page
    r = client.get("/register/")
    assert r.status_code == 200
    assert "Client Onboarding" in r.content.decode()

    # 2. Invalid POST (missing required fields)
    r_bad = client.post("/register/", {"full_name": "Incomplete Client"})
    assert r_bad.status_code == 200
    assert "This field is required" in r_bad.content.decode()

    # 3. Valid POST (onboarding request)
    data = {
        "full_name": "Test Client",
        "email": "requester@testclient.test",
        "phone": "+1 555 123 4567",
        "company_name": "Test Client Corp",
        "facility_address": "400 Industrial Parkway",
        "service_scope": "HVAC inspection and chiller maintenance",
        "terms_accepted": True,
    }
    r_ok = client.post("/register/", data)
    assert r_ok.status_code == 200
    html = r_ok.content.decode()
    assert "Onboarding Request Received" in html
    assert "Test Client Corp" in html

    # Verify audit record
    assert AuditLog.objects.filter(action="portal.client_onboarding_requested", actor_email="requester@testclient.test").exists()


def test_home_dashboard_renders_enhanced_kpi_cards(client, owner_a):
    client.force_login(owner_a)
    r = client.get("/app/")
    assert r.status_code == 200
    html = r.content.decode()
    assert "Active Users" in html
    assert "Pending Invitations" in html
    assert "RBAC Roles" in html
    assert "Operational Shortcuts" in html


@pytest.mark.parametrize("role_key,expected_badge,expected_kpi", [
    ("admin", "System Administration & Governance", "Active Users"),
    ("asset_manager", "Asset Lifecycle & Operations", "Master Assets"),
    ("maintenance_planner", "Maintenance Planning & PM", "Active PM Plans"),
    ("service_dispatcher", "Service Dispatch & Operations", "Open Incidents"),
    ("technician", "Field Mobility & Execution", "My Active Jobs"),
    ("supervisor", "Maintenance Supervision & Oversight", "Pending Review"),
    ("stores_manager", "Supply Chain & Warehouses", "Cataloged Parts"),
    ("service_manager", "Service Quality & Contract Management", "Open Service Requests"),
    ("auditor", "Governance, Risk & Compliance", "Immutable Audit Logs"),
])
def test_home_dashboard_role_tailoring(client, org_a, make_member, role_key, expected_badge, expected_kpi):
    member = make_member(org_a, f"{role_key}.test@alpha.test", role_key)
    client.force_login(member.user)
    r = client.get("/app/")
    assert r.status_code == 200
    assert r.context["persona"]["badge"] == expected_badge
    html = r.content.decode()
    assert expected_badge.replace("&", "&amp;") in html
    assert expected_kpi in html


def test_hub_dashboard_role_section_isolation(client, org_a, make_member):
    from apps.sites.models import Site
    from apps.inventory.models import Warehouse
    site = Site.objects.create(organization=org_a, name="Alpha Plant 1", code="ALP-01")
    Warehouse.objects.create(organization=org_a, site=site, name="Alpha Store 1")

    stores_mgr = make_member(org_a, "stores.hub.test@alpha.test", "stores_manager")
    client.force_login(stores_mgr.user)
    # Stores manager visits hub -> defaults directly to inventory
    r = client.get("/app/dashboards/")
    assert r.status_code == 200
    assert r.context["section"] == "inventory"
    # Attempting to access unauthorized section (e.g. operations or maintenance) returns 403
    assert client.get("/app/dashboards/?section=operations").status_code == 403
    assert client.get("/app/dashboards/?section=maintenance").status_code == 403

    planner = make_member(org_a, "planner.hub.test@alpha.test", "maintenance_planner")
    client.force_login(planner.user)
    r_planner = client.get("/app/dashboards/?section=maintenance")
    assert r_planner.status_code == 200
    assert client.get("/app/dashboards/?section=inventory").status_code == 403


def test_technician_dashboard_shortcuts_and_nav_enrichment(client, org_a, tech_a):
    client.force_login(tech_a)
    r = client.get("/app/")
    assert r.status_code == 200
    html = r.content.decode()

    # 1. Shortcuts include My Work Cockpit and Technician Workspace
    assert "My Work Cockpit" in html
    assert "Technician Workspace" in html
    assert "Scan Asset Label" in html

    # 2. Sidebar includes Field Execution and Field Tools
    assert "My Assigned Jobs" in html
    assert "All Work Orders" in html
    assert "/app/dashboards/my-work" in html
    assert "Scan Asset Label" in html

    # 3. Context contains technician data structures
    assert r.context["is_technician"] is True
    assert "capacity_summary" in r.context
    assert r.context["capacity_summary"]["standard_capacity_hours"] == 8.0


def test_technician_dashboard_active_clocked_in_banner_and_queue(client, org_a, tech_a):
    from apps.sites.models import Site
    from apps.assets.models import Asset, AssetCategory
    from apps.workorders.models import WorkOrder

    membership = Membership.objects.get(organization=org_a, user=tech_a)
    site = Site.objects.create(organization=org_a, name="Beta Processing Unit", code="BPU-01")
    cat = AssetCategory.objects.create(organization=org_a, name="Mechanical Pumps")
    asset = Asset.objects.create(organization=org_a, site=site, category=cat, name="Centrifugal Pump A1", asset_tag="PUMP-001")

    # In-progress job
    wo_active = WorkOrder.objects.create(
        organization=org_a,
        site=site,
        asset=asset,
        order_number="WO-TECH-001",
        title="Emergency Pump Seal Repair",
        status=WorkOrder.Status.IN_PROGRESS,
        priority=WorkOrder.Priority.CRITICAL,
        assigned_to=membership,
    )
    # Dispatched job
    wo_dispatched = WorkOrder.objects.create(
        organization=org_a,
        site=site,
        asset=asset,
        order_number="WO-TECH-002",
        title="Routine Chiller Inspection",
        status=WorkOrder.Status.DISPATCHED,
        priority=WorkOrder.Priority.HIGH,
        assigned_to=membership,
    )

    client.force_login(tech_a)
    r = client.get("/app/")
    assert r.status_code == 200
    html = r.content.decode()

    # 1. Prominent Clocked-In Banner
    assert "Currently Clocked In" in html
    assert "WO-TECH-001" in html
    assert "Emergency Pump Seal Repair" in html

    # 2. Assigned Work Order Queue Table
    assert "Assigned Work Order Queue" in html
    assert "WO-TECH-002" in html
    assert "Routine Chiller Inspection" in html
    assert "Start" in html

    # 3. Capacity utilization gauge
    assert "Today&#x27;s Shift Capacity" in html or "Today's Shift Capacity" in html
    assert "Shift Utilization" in html


def test_technician_dashboard_shows_only_assigned_and_no_unassigned(client, org_a, tech_a, owner_a):
    from apps.sites.models import Site
    from apps.assets.models import Asset, AssetCategory
    from apps.workorders.models import WorkOrder
    from django.urls import reverse

    membership = Membership.objects.get(organization=org_a, user=tech_a)
    site = Site.objects.create(organization=org_a, name="Test Plant Site", code="TPS-01")
    cat = AssetCategory.objects.create(organization=org_a, name="Turbines")
    asset = Asset.objects.create(organization=org_a, site=site, category=cat, name="Steam Turbine 1", asset_tag="TRB-001")

    # 1. Assigned job to technician
    wo_assigned = WorkOrder.objects.create(
        organization=org_a,
        site=site,
        asset=asset,
        order_number="WO-ASSIGNED-101",
        title="Assigned Turbine Maintenance",
        status=WorkOrder.Status.DISPATCHED,
        priority=WorkOrder.Priority.HIGH,
        assigned_to=membership,
    )
    # 2. Unassigned job
    wo_unassigned = WorkOrder.objects.create(
        organization=org_a,
        site=site,
        asset=asset,
        order_number="WO-UNASSIGNED-999",
        title="Unassigned Turbine Inspection",
        status=WorkOrder.Status.PLANNED,
        priority=WorkOrder.Priority.MEDIUM,
        assigned_to=None,
    )

    client.force_login(tech_a)

    # Check Technician Home (/app/)
    r_home = client.get("/app/")
    assert r_home.status_code == 200
    home_html = r_home.content.decode()
    assert "WO-ASSIGNED-101" in home_html
    assert "Assigned Turbine Maintenance" in home_html
    assert "WO-UNASSIGNED-999" not in home_html
    assert "Unassigned Turbine Inspection" not in home_html

    # Check Work Orders List (/app/work-orders/)
    r_list = client.get(reverse("workorders:list"))
    assert r_list.status_code == 200
    list_html = r_list.content.decode()
    assert "WO-ASSIGNED-101" in list_html
    assert "Assigned Turbine Maintenance" in list_html
    assert "WO-UNASSIGNED-999" not in list_html
    assert "Unassigned Turbine Inspection" not in list_html
    assert "My assigned work orders" in list_html
    # Status cards: PLANNED has 0 because the unassigned planned order is NOT visible to technician
    status_card_map = {c["code"]: c["count"] for c in r_list.context["status_cards"]}
    assert status_card_map.get(WorkOrder.Status.DISPATCHED, 0) == 1
    assert status_card_map.get(WorkOrder.Status.PLANNED, 0) == 0

    # Check Technician Workspace (/app/workspace/)
    r_workspace = client.get(reverse("workspace:my_jobs"))
    assert r_workspace.status_code == 200
    ws_html = r_workspace.content.decode()
    assert "WO-ASSIGNED-101" in ws_html
    assert "WO-UNASSIGNED-999" not in ws_html

    # Check My Work Cockpit (/app/dashboards/my-work/)
    r_cockpit = client.get(reverse("dashboards:my_work"))
    assert r_cockpit.status_code == 200
    cockpit_html = r_cockpit.content.decode()
    assert "WO-ASSIGNED-101" in cockpit_html
    assert "WO-UNASSIGNED-999" not in cockpit_html

    # Supervisor / Owner CAN see both assigned and unassigned work orders in /app/work-orders/
    client.force_login(owner_a)
    r_owner = client.get(reverse("workorders:list"))
    assert r_owner.status_code == 200
    owner_html = r_owner.content.decode()
    assert "WO-ASSIGNED-101" in owner_html
    assert "WO-UNASSIGNED-999" in owner_html
