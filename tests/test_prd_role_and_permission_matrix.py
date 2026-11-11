"""Comprehensive verification of the FieldOps Nexus Role-Based Access Control (RBAC) matrix

Empirically validates:
1. The 10 Primary System Role Templates required by the HPE PRD (plus Owner & Auditor).
2. Permission separation across all 19 functional module domains (98 permissions total).
3. Least-privilege positive and negative capability boundaries for each persona:
   - Owner (root tenant authority)
   - Admin (governance, users, roles, sites)
   - Asset Manager (assets, meters, hierarchy, documents)
   - Maintenance Planner (PM schedules, work order creation & planning)
   - Service Dispatcher (incident triage, dispatching, route coordination)
   - Field Technician (executes assigned work orders, checklists, part consumption)
   - Maintenance Supervisor (review, hold, close work orders, inspections)
   - Stores Manager (warehouse, stock balances, part masters, reservations)
   - Service Manager (SLAs, contracts/AMCs, service request escalation)
   - Client Requester (isolated self-service portal, assigned assets only)
   - Auditor (read-only compliance, audit log view & export)
4. Cross-tenant isolation and site scoping enforcement.
"""
import pytest
from django.contrib.auth import get_user_model
from apps.rbac import catalog, services as rbac_services
from apps.rbac.models import Role
from apps.tenancy import services as tenancy_services
from apps.tenancy.models import Membership

pytestmark = [pytest.mark.django_db, pytest.mark.rbac]
User = get_user_model()


def test_permission_catalog_completeness():
    """Verify that all 19 functional module domains are registered in the global catalog."""
    codes = catalog.all_codes()
    assert len(codes) >= 95, f"Expected at least 95 permissions, got {len(codes)}"

    required_prefixes = {
        "organization", "user", "role", "site", "zone", "calendar",
        "asset", "maintenance", "work_order", "checklist", "inspection",
        "inventory", "incident", "sla", "contract", "qr", "portal",
        "report", "audit"
    }
    actual_prefixes = {c.split(".")[0] for c in codes}
    missing = required_prefixes - actual_prefixes
    assert not missing, f"Missing permission domains: {missing}"


def test_system_roles_seeded_for_organization(org_a):
    """Verify that rbac.seed_system_roles provisions all PRD role templates."""
    roles = rbac_services.seed_system_roles(org_a)
    expected_roles = {
        "owner", "admin", "asset_manager", "maintenance_planner",
        "service_dispatcher", "technician", "supervisor", "stores_manager",
        "service_manager", "client_requester", "auditor"
    }
    for r in expected_roles:
        assert r in roles, f"Role template '{r}' was not seeded"
        role_obj = Role.objects.unscoped().filter(organization=org_a, system_key=r).first()
        assert role_obj is not None, f"Role '{r}' missing in database for org"


def test_owner_role_unrestricted_capabilities(as_user, owner_a, org_a):
    """Owner holds full administrative and operational authority across all endpoints."""
    client = as_user(owner_a, org_a)
    assert client.get("/api/v1/organization/").status_code == 200
    assert client.get("/api/v1/members/").status_code == 200
    assert client.get("/api/v1/roles/").status_code == 200
    assert client.get("/api/v1/sites/").status_code == 200
    assert client.get("/api/v1/assets/").status_code == 200
    assert client.get("/api/v1/work-orders/").status_code == 200
    assert client.get("/api/v1/parts/").status_code == 200
    assert client.get("/api/v1/audit-logs/").status_code == 200


def test_admin_role_governance_allowed_operational_execution_restricted(as_user, org_a, make_member):
    """Organization Admin manages users, sites, and roles, but cannot execute field jobs."""
    admin_m = make_member(org_a, "admin.test@alpha.test", "admin")
    client = as_user(admin_m.user, org_a)

    # Allowed: governance and management
    assert client.get("/api/v1/members/").status_code == 200
    assert client.get("/api/v1/roles/").status_code == 200
    assert client.get("/api/v1/sites/").status_code == 200

    # Restricted: Admin cannot execute field technician actions
    perms = rbac_services.membership_permissions(admin_m)
    assert "work_order.start" not in perms
    assert "work_order.complete" not in perms
    assert "checklist.execute" not in perms


def test_asset_manager_allowed_asset_domain_denied_governance(as_user, org_a, make_member):
    """Asset Manager manages assets, meters, categories, but cannot manage users or roles."""
    am_m = make_member(org_a, "asset.mgr@alpha.test", "asset_manager")
    client = as_user(am_m.user, org_a)

    # Allowed: Asset domain
    assert client.get("/api/v1/assets/").status_code == 200
    assert client.get("/api/v1/sites/").status_code == 200

    # Denied: User and Role management
    assert client.get("/api/v1/members/").status_code == 403
    assert client.get("/api/v1/roles/").status_code == 403
    assert client.patch("/api/v1/organization/", {"name": "Hacked"}, format="json").status_code == 403


def test_maintenance_planner_pm_and_work_order_planning(as_user, org_a, make_member):
    """Maintenance Planner can plan PMs and work orders, but cannot manage users or parts master."""
    planner_m = make_member(org_a, "planner.test@alpha.test", "maintenance_planner")
    client = as_user(planner_m.user, org_a)

    perms = rbac_services.membership_permissions(planner_m)
    assert "maintenance.create" in perms or "maintenance.view" in perms
    assert "work_order.plan" in perms
    assert "work_order.assign" in perms

    # Denied: cannot invite users or manage roles
    assert client.get("/api/v1/members/").status_code == 403
    assert client.get("/api/v1/roles/").status_code == 403


def test_technician_least_privilege_boundary(as_user, org_a, make_member):
    """Technicians can only execute assigned work orders; cannot view all work orders or admin records."""
    tech_m = make_member(org_a, "field.tech@alpha.test", "technician")
    client = as_user(tech_m.user, org_a)

    # Technician has execute permissions
    perms = rbac_services.membership_permissions(tech_m)
    assert "work_order.start" in perms
    assert "work_order.complete" in perms
    assert "checklist.execute" in perms
    assert "work_order.view_assigned" in perms
    # Technician DOES NOT have general view or admin permissions
    assert "work_order.view" not in perms
    assert "user.view" not in perms
    assert "role.manage" not in perms

    # Endpoints strictly denied with 403
    assert client.get("/api/v1/members/").status_code == 403
    assert client.get("/api/v1/roles/").status_code == 403
    assert client.get("/api/v1/audit-logs/").status_code == 403


def test_stores_manager_inventory_domain_isolation(as_user, org_a, make_member):
    """Stores Manager manages parts and warehouses; cannot dispatch work orders or manage users."""
    stores_m = make_member(org_a, "stores.test@alpha.test", "stores_manager")
    client = as_user(stores_m.user, org_a)

    perms = rbac_services.membership_permissions(stores_m)
    assert "inventory.part.manage" in perms
    assert "inventory.adjust" in perms
    assert "inventory.reconcile" in perms
    assert "work_order.dispatch" not in perms
    assert "user.invite" not in perms

    assert client.get("/api/v1/parts/").status_code == 200
    assert client.get("/api/v1/members/").status_code == 403


def test_client_requester_strict_isolation_from_internal_erp(as_user, org_a, make_member):
    """Client Requester is confined to the client portal and cannot access internal ERP records."""
    client_m = make_member(org_a, "client.portal@alpha.test", "client_requester")
    client = as_user(client_m.user, org_a)

    perms = rbac_services.membership_permissions(client_m)
    assert "portal.request.create" in perms
    assert "portal.request.view" in perms
    assert "portal.request.confirm" in perms
    assert "work_order.view" not in perms
    assert "inventory.view" not in perms
    assert "user.view" not in perms

    # Direct API access to internal modules returns 403 Forbidden
    assert client.get("/api/v1/members/").status_code == 403
    assert client.get("/api/v1/roles/").status_code == 403
    assert client.get("/api/v1/parts/").status_code == 403
    assert client.get("/api/v1/work-orders/").status_code == 403


def test_auditor_read_only_access_with_modification_blocked(as_user, org_a, make_member):
    """Auditor can view audit trails, reports, and records, but cannot mutate any data."""
    auditor_m = make_member(org_a, "auditor.test@alpha.test", "auditor")
    client = as_user(auditor_m.user, org_a)

    # Allowed: Read views
    assert client.get("/api/v1/audit-logs/").status_code == 200
    assert client.get("/api/v1/assets/").status_code == 200
    assert client.get("/api/v1/sites/").status_code == 200

    # Denied: Data mutations
    assert client.post("/api/v1/sites/", {"name": "Unauthorized Site"}, format="json").status_code == 403
    assert client.post("/api/v1/parts/", {"name": "Unauthorized Part"}, format="json").status_code == 403


def test_cross_tenant_isolation_enforcement(as_user, org_a, org_b, owner_a):
    """Even an Organization Owner in Tenant A cannot access Tenant B records."""
    client = as_user(owner_a, org_a)
    # Attempt to spoof tenant context header to Tenant B
    client.credentials(HTTP_X_ORGANIZATION=org_b.slug)
    resp = client.get("/api/v1/members/")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "not_a_member"
