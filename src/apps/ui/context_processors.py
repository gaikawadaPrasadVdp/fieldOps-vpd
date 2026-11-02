from django.urls import NoReverseMatch, reverse

from apps.rbac import services as rbac
from apps.rbac.models import MembershipRole
from apps.tenancy import selectors

from . import navigation
from .utils import is_client_membership


def _resolve_active(sections, req_path):
    """Marks the single most specific matching nav item as active."""
    best_item = None
    best_len = -1
    for sec, items in sections.items():
        for item in items:
            mp = item.get("match_prefix", "") or item.get("url", "")
            if mp == "/app/" or mp == "/app":
                if req_path.rstrip("/") == "/app" and len(mp) > best_len:
                    best_len = len(mp)
                    best_item = item
            elif mp and req_path.startswith(mp):
                if len(mp) > best_len:
                    best_len = len(mp)
                    best_item = item
    if best_item:
        best_item["active"] = True



def _safe_reverse(viewname, *args, **kwargs):
    """Safely reverse a URL pattern, returning None on NoReverseMatch so broken links are omitted."""
    try:
        return reverse(viewname, *args, **kwargs)
    except NoReverseMatch:
        return None


def _filter_valid_nav_items(sections):
    """Filters out nav items whose URL could not be reversed to prevent dead links."""
    clean = {}
    for sec_name, items in sections.items():
        valid = [it for it in items if it.get("url")]
        if valid:
            clean[sec_name] = valid
    return clean


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    req_path = request.path
    membership = getattr(request, "membership", None)

    # 1. Platform Super Admin (NAV-01) - Dedicated Governance Navigation Only
    if getattr(user, "is_platform_admin", False):
        sections = {
            "Platform Governance": [
                {"label": "Organizations", "url": _safe_reverse("platform_admin:organizations"), "icon": "building", "match_prefix": "/platform/organizations"},
                {"label": "Platform Audit Trail", "url": _safe_reverse("platform_admin:audit"), "icon": "shield", "match_prefix": "/platform/audit"},
                {"label": "Incident Dashboard", "url": _safe_reverse("platform_admin:incident_dashboard"), "icon": "activity", "match_prefix": "/platform/incidents"},
            ]
        }
        sections = _filter_valid_nav_items(sections)
        _resolve_active(sections, req_path)
        return {
            "shell_org": None,
            "shell_membership": None,
            "shell_nav_sections": sections,
            "shell_memberships": [],
            "shell_tenant_error": None,
            "is_client": False,
        }

    if membership is None:
        return {
            "shell_org": None,
            "shell_membership": None,
            "shell_nav_sections": {},
            "shell_memberships": list(selectors.active_memberships(user)),
            "shell_tenant_error": getattr(request, "tenant_error", None),
            "is_client": False,
        }

    # 2. Client / Requester Navigation (M13)
    is_client = is_client_membership(membership)
    if is_client:
        sections = {
            "Portal": [
                {"label": "Client Portal", "url": _safe_reverse("portal:dashboard"), "icon": "grid", "match_prefix": "/app/portal/"},
                {"label": "My Requests", "url": _safe_reverse("portal:requests_list"), "icon": "list-check", "match_prefix": "/app/portal/requests"},
                {"label": "New Request", "url": _safe_reverse("portal:request_create"), "icon": "plus-circle", "match_prefix": "/app/portal/requests/new"},
            ]
        }
        sections = _filter_valid_nav_items(sections)
        _resolve_active(sections, req_path)
        return {
            "shell_org": getattr(request, "organization", None),
            "shell_membership": membership,
            "shell_nav_sections": sections,
            "shell_memberships": getattr(request, "active_memberships", None) or list(selectors.active_memberships(user)),
            "shell_tenant_error": getattr(request, "tenant_error", None),
            "is_client": True,
        }

    # 3. Internal Tenant Staff Roles - Clean Sidebar Allocation (Section H)
    role_keys = set(
        MembershipRole.objects.filter(membership=membership).values_list("role__system_key", flat=True)
    )
    is_owner = rbac.is_owner(membership)
    is_admin = "admin" in role_keys or rbac.has_permission(membership, "role.manage")
    sections = {}

    if is_owner or is_admin:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Operations"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"},
        ]
        sections["Maintenance Planning"] = [
            {"label": "Maintenance plans", "url": _safe_reverse("maintenance:plans"), "icon": "wrench", "match_prefix": "/app/maintenance/plans"},
            {"label": "Due & upcoming", "url": _safe_reverse("maintenance:due"), "icon": "clock", "match_prefix": "/app/maintenance/due"},
            {"label": "PM history", "url": _safe_reverse("maintenance:history"), "icon": "list-check", "match_prefix": "/app/maintenance/history"},
        ]
        sections["Inventory & Warehouses"] = [
            {"label": "Parts", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"},
            {"label": "Stock", "url": _safe_reverse("inventory:stock"), "icon": "grid", "match_prefix": "/app/inventory/stock"},
            {"label": "Warehouses", "url": _safe_reverse("inventory:warehouses"), "icon": "building", "match_prefix": "/app/inventory/warehouses"},
            {"label": "Reservations", "url": _safe_reverse("inventory:reservations"), "icon": "list-check", "match_prefix": "/app/inventory/reservations"},
            {"label": "Movements", "url": _safe_reverse("inventory:movements"), "icon": "clipboard", "match_prefix": "/app/inventory/movements"},
        ]
        sections["Asset Lifecycle"] = [
            {"label": "Sites & Locations", "url": _safe_reverse("sites:list"), "icon": "pin", "match_prefix": "/app/sites"},
            {"label": "Assets", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Hierarchy", "url": _safe_reverse("assets:hierarchy_hub"), "icon": "git-branch", "match_prefix": "/app/assets/hierarchy"},
        ]
        sections["Service Level Agreements"] = [
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
        ]
        sections["Commercial"] = [
            {"label": "Warranties & contracts", "url": reverse("contracts:agreements"), "icon": "shield", "match_prefix": "/app/contracts/agreements"},
            {"label": "Expiring coverage", "url": reverse("contracts:expiry"), "icon": "clock", "match_prefix": "/app/contracts/expiry"},
        ]
        sections["Administration"] = [
            {"label": "Organization", "url": _safe_reverse("tenancy:organization"), "icon": "building", "match_prefix": "/app/organization"},
            {"label": "Users", "url": _safe_reverse("tenancy:members"), "icon": "people", "match_prefix": "/app/users"},
            {"label": "Roles & Permissions", "url": _safe_reverse("rbac:roles"), "icon": "shield", "match_prefix": "/app/roles"},
            {"label": "Portal Accounts", "url": _safe_reverse("portal:accounts_list"), "icon": "people", "match_prefix": "/app/portal/accounts"},
        ]
        sections["Analytics & Governance"] = [
            {"label": "Operational Dashboards", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            {"label": "Audit Trail", "url": _safe_reverse("audit:list"), "icon": "clock", "match_prefix": "/app/audit"},
        ]


    elif "operations_manager" in role_keys:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Operations"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"},
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
        ]
        sections["Maintenance Planning"] = [
            {"label": "Maintenance plans", "url": _safe_reverse("maintenance:plans"), "icon": "wrench", "match_prefix": "/app/maintenance/plans"},
            {"label": "Due & upcoming", "url": _safe_reverse("maintenance:due"), "icon": "clock", "match_prefix": "/app/maintenance/due"},
            {"label": "PM history", "url": _safe_reverse("maintenance:history"), "icon": "list-check", "match_prefix": "/app/maintenance/history"},
        ]
        sections["Inventory & Warehouses"] = [
            {"label": "Parts", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"},
            {"label": "Stock", "url": _safe_reverse("inventory:stock"), "icon": "grid", "match_prefix": "/app/inventory/stock"},
            {"label": "Warehouses", "url": _safe_reverse("inventory:warehouses"), "icon": "building", "match_prefix": "/app/inventory/warehouses"},
            {"label": "Reservations", "url": _safe_reverse("inventory:reservations"), "icon": "list-check", "match_prefix": "/app/inventory/reservations"},
            {"label": "Movements", "url": _safe_reverse("inventory:movements"), "icon": "clipboard", "match_prefix": "/app/inventory/movements"},
        ]
        sections["Asset Lifecycle"] = [
            {"label": "Sites & Locations", "url": _safe_reverse("sites:list"), "icon": "pin", "match_prefix": "/app/sites"},
            {"label": "Assets", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Hierarchy", "url": _safe_reverse("assets:hierarchy_hub"), "icon": "git-branch", "match_prefix": "/app/assets/hierarchy"},
        ]
        sections["Service Level Agreements"] = [
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
        ]
        sections["Analytics"] = [
            {"label": "Operational Dashboards", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
        ]

    elif role_keys & {"technician", "field_technician"}:
        sections["Workspace"] = [
            {"label": "Technician Workspace", "url": _safe_reverse("workspace:my_jobs"), "icon": "wrench", "match_prefix": "/app/workspace"},
        ]
        sections["Service"] = [
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
        ]
        sections["Assets"] = [
            {"label": "Asset Register", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Scan QR", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"},
        ]
        sections["Operations & Assets"] = [
            {"label": "Facility Sites", "url": _safe_reverse("sites:list"), "icon": "pin", "match_prefix": "/app/sites"},
            {"label": "Asset Registry", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Incident & Defects", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
        ]
        field_tools = [
            {"label": "Scan Asset Label", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"},
        ]
        if rbac.has_permission_anywhere(membership, "inventory.part.view"):
            field_tools.append(
                {"label": "Cataloged Parts", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"}
            )
        sections["Field Tools"] = field_tools

    elif role_keys & {"stores_manager", "stores_inventory"}:
        sections["Inventory & Warehouses"] = [
            {"label": "Parts", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"},
            {"label": "Stock", "url": _safe_reverse("inventory:stock"), "icon": "grid", "match_prefix": "/app/inventory/stock"},
            {"label": "Warehouses", "url": _safe_reverse("inventory:warehouses"), "icon": "building", "match_prefix": "/app/inventory/warehouses"},
            {"label": "Reservations", "url": _safe_reverse("inventory:reservations"), "icon": "list-check", "match_prefix": "/app/inventory/reservations"},
            {"label": "Movements", "url": _safe_reverse("inventory:movements"), "icon": "clipboard", "match_prefix": "/app/inventory/movements"},
        ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "asset_manager" in role_keys:
        sections["Service"] = [
            {"label": "Service Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
        ]
        sections["Asset Lifecycle"] = [
            {"label": "Sites & Locations", "url": _safe_reverse("sites:list"), "icon": "pin", "match_prefix": "/app/sites"},
            {"label": "Assets", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Hierarchy", "url": _safe_reverse("assets:hierarchy_hub"), "icon": "git-branch", "match_prefix": "/app/assets/hierarchy"},
            {"label": "Scan Label", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"},
        ]
        sections["Commercial"] = [
            {"label": "Warranties & contracts", "url": _safe_reverse("contracts:agreements"), "icon": "shield", "match_prefix": "/app/contracts/agreements"},
            {"label": "Expiring coverage", "url": _safe_reverse("contracts:expiry"), "icon": "clock", "match_prefix": "/app/contracts/expiry"},
        ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "maintenance_planner" in role_keys:
        sections["Operations"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
        ]
        sections["Maintenance Planning"] = [
            {"label": "Maintenance plans", "url": _safe_reverse("maintenance:plans"), "icon": "wrench", "match_prefix": "/app/maintenance/plans"},
            {"label": "Due & upcoming", "url": _safe_reverse("maintenance:due"), "icon": "clock", "match_prefix": "/app/maintenance/due"},
            {"label": "PM history", "url": _safe_reverse("maintenance:history"), "icon": "list-check", "match_prefix": "/app/maintenance/history"},
        ]
        sections["Work Management"] = [
            {"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"},
        ]
        sections["Inventory & Warehouses"] = [
            {"label": "Parts", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"},
            {"label": "Stock", "url": _safe_reverse("inventory:stock"), "icon": "grid", "match_prefix": "/app/inventory/stock"},
            {"label": "Warehouses", "url": _safe_reverse("inventory:warehouses"), "icon": "building", "match_prefix": "/app/inventory/warehouses"},
            {"label": "Reservations", "url": _safe_reverse("inventory:reservations"), "icon": "list-check", "match_prefix": "/app/inventory/reservations"},
            {"label": "Movements", "url": _safe_reverse("inventory:movements"), "icon": "clipboard", "match_prefix": "/app/inventory/movements"},
        ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "supervisor" in role_keys:
        sections["Supervisory Operations"] = [
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
            {"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"},
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
        ]
        if rbac.has_permission_anywhere(membership, "sla.view"):
            sections["Service Level Agreements"] = [
                {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "service_dispatcher" in role_keys:
        sections["Operations"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
        ]
        sections["Assets"] = [
            {"label": "Asset Register", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Scan QR", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"},
        ]
        sections["Service Level Agreements"] = [
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
        ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "service_manager" in role_keys:
        sections["Service Assurance"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            {"label": "Warranties & contracts", "url": _safe_reverse("contracts:agreements"), "icon": "shield", "match_prefix": "/app/contracts/agreements"},
            {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
        ]

    elif role_keys & {"auditor", "compliance"}:
        sections["Audit & Compliance"] = [
            {"label": "Audit Trail", "url": _safe_reverse("audit:list"), "icon": "shield", "match_prefix": "/app/audit/"},
            {"label": "Compliance reports", "url": _safe_reverse("audit:reports"), "icon": "list-check", "match_prefix": "/app/audit/reports"},
            {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
        ]

    else:
        # Fallback for custom composite roles
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        if rbac.has_permission_anywhere(membership, "incident.view"):
            sections.setdefault("Operations", []).append(
                {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"}
            )
        if rbac.has_permission_anywhere(membership, "work_order.view"):
            sections.setdefault("Operations", []).append(
                {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"}
            )
        if rbac.has_permission_anywhere(membership, "asset.view"):
            sections.setdefault("Assets & Locations", []).append(
                {"label": "Sites & Locations", "url": _safe_reverse("sites:list"), "icon": "pin", "match_prefix": "/app/sites"}
            )
            sections.setdefault("Assets & Locations", []).append(
                {"label": "Assets", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"}
            )
            sections.setdefault("Assets & Locations", []).append(
                {"label": "Hierarchy", "url": _safe_reverse("assets:hierarchy_hub"), "icon": "git-branch", "match_prefix": "/app/assets/hierarchy"}
            )
        if rbac.has_permission_anywhere(membership, "sla.view"):
            sections["Service Level Agreements"] = [
                {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    sections = _filter_valid_nav_items(sections)
    _resolve_active(sections, req_path)

    return {
        "shell_org": getattr(request, "organization", None),
        "shell_membership": membership,
        "shell_nav_sections": sections,
        "shell_memberships": getattr(request, "active_memberships", None) or list(selectors.active_memberships(user)),
        "shell_tenant_error": getattr(request, "tenant_error", None),
        "is_client": is_client,
        "is_org_owner": is_owner,
    }
