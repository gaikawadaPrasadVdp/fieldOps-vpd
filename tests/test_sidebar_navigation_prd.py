"""Tests verifying Dashboard Left-Side Navigation compliance with HPE PRD (HPE-PRD-2026-FOPS02)."""
import pytest
from unittest.mock import MagicMock, patch
from django.test import RequestFactory
from apps.ui.context_processors import shell


def test_platform_super_admin_sidebar_isolation():
    """Platform Super Admin must only see Platform Governance navigation."""
    rf = RequestFactory()
    req = rf.get("/platform/organizations/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=True)

    ctx = shell(req)
    sections = ctx.get("shell_nav_sections", {})
    assert list(sections.keys()) == ["Platform Governance"]
    labels = [item["label"] for item in sections["Platform Governance"]]
    assert "Organizations" in labels
    assert "Platform Audit Trail" in labels


def test_client_portal_sidebar_isolation():
    """Client / Requester must only see Portal navigation."""
    rf = RequestFactory()
    req = rf.get("/app/portal/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)
    
    # Mock client membership
    membership = MagicMock()
    membership.is_active = True
    membership.portal_account = MagicMock(is_enabled=True)
    req.membership = membership
    req.active_memberships = []
    req.organization = MagicMock(name="Acme Client")
    req.tenant_error = None

    ctx = shell(req)
    sections = ctx.get("shell_nav_sections", {})
    assert list(sections.keys()) == ["Portal"]
    labels = [item["label"] for item in sections["Portal"]]
    assert "Client Portal" in labels
    assert "My Requests" in labels


def test_owner_admin_full_prd_navigation_sections():
    """Organization Owner or Admin must see all 9 PRD sections with exact labels."""
    rf = RequestFactory()
    req = rf.get("/app/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)
    
    membership = MagicMock()
    membership.is_active = True
    membership.portal_account = None
    membership.is_owner = True
    membership.roles = MagicMock()
    req.membership = membership
    req.active_memberships = []
    req.organization = MagicMock(name="Acme Corp")
    req.tenant_error = None

    from apps.rbac import services as rbac
    from apps.rbac.models import MembershipRole
    
    with patch.object(rbac, "is_owner", return_value=True), \
         patch("apps.ui.context_processors.is_client_membership", return_value=False), \
         patch.object(MembershipRole.objects, "filter") as mock_filter:
        mock_filter.return_value.values_list.return_value = ["admin"]
        ctx = shell(req)

    sections = ctx.get("shell_nav_sections", {})

    expected_sections = [
        "Overview",
        "Operations",
        "Maintenance Planning",
        "Inventory & Stores",
        "Assets & Locations",
        "Commercial & Contracts",
        "Service Level Agreements",
        "Compliance & Governance",
        "Administration",
    ]
    for sec in expected_sections:
        assert sec in sections, f"Missing PRD section: {sec}. Available: {list(sections.keys())}"

    # Verify specific items required by HPE PRD in each section
    overview_labels = [i["label"] for i in sections["Overview"]]
    assert "Operations Overview" in overview_labels
    assert "Analytics Hub" in overview_labels
    assert "KPI Snapshots" in overview_labels

    operations_labels = [i["label"] for i in sections["Operations"]]
    assert "Incidents & Requests" in operations_labels
    assert "Work Orders" in operations_labels
    assert "Checklists" in operations_labels
    assert "Inspections" in operations_labels
    assert "Technician Workspace" in operations_labels

    maintenance_labels = [i["label"] for i in sections["Maintenance Planning"]]
    assert "Maintenance Plans" in maintenance_labels
    assert "Due & Upcoming" in maintenance_labels
    assert "PM History" in maintenance_labels

    inventory_labels = [i["label"] for i in sections["Inventory & Stores"]]
    assert "Parts Catalog" in inventory_labels
    assert "Stock Balances" in inventory_labels
    assert "Warehouses" in inventory_labels
    assert "Reservations" in inventory_labels
    assert "Stock Movements" in inventory_labels

    asset_labels = [i["label"] for i in sections["Assets & Locations"]]
    assert "Sites & Locations" in asset_labels
    assert "Asset Registry" in asset_labels
    assert "Asset Hierarchy" in asset_labels
    assert "Scan QR / Barcode" in asset_labels

    commercial_labels = [i["label"] for i in sections["Commercial & Contracts"]]
    assert "Warranties & Contracts" in commercial_labels
    assert "Expiring Coverage" in commercial_labels
    assert "Service Providers" in commercial_labels

    sla_labels = [i["label"] for i in sections["Service Level Agreements"]]
    assert "SLA & Escalation" in sla_labels

    compliance_labels = [i["label"] for i in sections["Compliance & Governance"]]
    assert "Audit Trail" in compliance_labels
    assert "Compliance Reports" in compliance_labels

    admin_labels = [i["label"] for i in sections["Administration"]]
    assert "Organization Settings" in admin_labels
    assert "Users & Invitations" in admin_labels
    assert "Roles & Permissions" in admin_labels
    assert "Technicians & Shifts" in admin_labels
    assert "Portal Accounts" in admin_labels


def test_service_dispatcher_sidebar_mandatory_modules_only():
    """Service Dispatcher must see only PRD-mandated dispatch modules."""
    rf = RequestFactory()
    req = rf.get("/app/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)

    membership = MagicMock()
    membership.is_active = True
    membership.portal_account = None
    membership.is_owner = False
    req.membership = membership
    req.active_memberships = []
    req.organization = MagicMock(name="Acme Corp")
    req.tenant_error = None

    from apps.rbac import services as rbac
    from apps.rbac.models import MembershipRole

    allowed = {
        "incident.view", "work_order.view", "inspection.view",
        "asset.view", "qr.scan", "sla.view", "report.view",
    }
    with patch.object(rbac, "is_owner", return_value=False), \
         patch.object(rbac, "has_permission", return_value=False), \
         patch.object(rbac, "has_permission_anywhere", side_effect=lambda m, code: code in allowed), \
         patch("apps.ui.context_processors.is_client_membership", return_value=False), \
         patch.object(MembershipRole.objects, "filter") as mock_filter:
        mock_filter.return_value.values_list.return_value = ["service_dispatcher"]
        ctx = shell(req)

    sections = ctx.get("shell_nav_sections", {})
    assert list(sections.keys()) == [
        "Overview", "Operations", "Assets", "Service Level Agreements", "Analytics"
    ]
    assert [i["label"] for i in sections["Overview"]] == ["Operational Overview"]
    assert [i["label"] for i in sections["Operations"]] == [
        "Incidents & Requests", "Incident Dashboard", "Work Orders", "Inspections"
    ]
    assert [i["label"] for i in sections["Assets"]] in (["Assets", "Scan QR"], ["Asset Register", "Scan QR"])
    assert [i["label"] for i in sections["Service Level Agreements"]] == ["SLA & Escalation"]
    assert [i["label"] for i in sections["Analytics"]] == ["Analytics Hub"]


def test_service_dispatcher_sidebar_respects_permissions():
    """Service Dispatcher sidebar items are hidden when permissions are revoked."""
    rf = RequestFactory()
    req = rf.get("/app/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)

    membership = MagicMock()
    membership.is_active = True
    membership.portal_account = None
    membership.is_owner = False
    req.membership = membership
    req.active_memberships = []
    req.organization = MagicMock(name="Acme Corp")
    req.tenant_error = None

    from apps.rbac import services as rbac
    from apps.rbac.models import MembershipRole

    allowed = {"incident.view", "work_order.view"}
    with patch.object(rbac, "is_owner", return_value=False), \
         patch.object(rbac, "has_permission", return_value=False), \
         patch.object(rbac, "has_permission_anywhere", side_effect=lambda m, code: code in allowed), \
         patch("apps.ui.context_processors.is_client_membership", return_value=False), \
         patch.object(MembershipRole.objects, "filter") as mock_filter:
        mock_filter.return_value.values_list.return_value = ["service_dispatcher"]
        ctx = shell(req)

    sections = ctx.get("shell_nav_sections", {})
    assert list(sections.keys()) == ["Overview", "Operations"]
    assert [i["label"] for i in sections["Operations"]] == [
        "Incidents & Requests", "Incident Dashboard", "Work Orders"
    ]


def test_maintenance_planner_sidebar_mandatory_modules_only():
    """Maintenance Planner must see only PRD-mandated PM & planning modules."""
    rf = RequestFactory()
    req = rf.get("/app/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)

    membership = MagicMock()
    membership.is_active = True
    membership.portal_account = None
    membership.is_owner = False
    req.membership = membership
    req.active_memberships = []
    req.organization = MagicMock(name="Acme Corp")
    req.tenant_error = None

    from apps.rbac import services as rbac
    from apps.rbac.models import MembershipRole

    allowed = {
        "maintenance.view", "work_order.view", "checklist.view",
        "inspection.view", "asset.view", "qr.scan", "report.view",
    }
    with patch.object(rbac, "is_owner", return_value=False), \
         patch.object(rbac, "has_permission", return_value=False), \
         patch.object(rbac, "has_permission_anywhere", side_effect=lambda m, code: code in allowed), \
         patch("apps.ui.context_processors.is_client_membership", return_value=False), \
         patch.object(MembershipRole.objects, "filter") as mock_filter:
        mock_filter.return_value.values_list.return_value = ["maintenance_planner"]
        ctx = shell(req)

    sections = ctx.get("shell_nav_sections", {})
    assert list(sections.keys()) == [
        "Overview", "Maintenance Planning", "Operations", "Assets", "Analytics"
    ]
    assert [i["label"] for i in sections["Overview"]] == ["Operational Overview"]
    assert [i["label"] for i in sections["Maintenance Planning"]] == [
        "Maintenance Plans", "Due & Upcoming", "PM History"
    ]
    assert [i["label"] for i in sections["Operations"]] == [
        "Work Orders", "Checklists", "Inspections"
    ]
    assert [i["label"] for i in sections["Assets"]] in (["Assets", "Scan QR"], ["Asset Register", "Scan QR"])
    assert [i["label"] for i in sections["Analytics"]] == ["Analytics Hub"]


