from django.conf import settings
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
    for _sec, items in sections.items():
        for item in items:
            prefixes = item.get("match_prefixes") or [item.get("match_prefix", "") or item.get("url", "")]
            for mp in prefixes:
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


def _build_tenant_nav(membership, is_owner):
    role_keys = set(
        MembershipRole.objects.filter(membership=membership).values_list("role__system_key", flat=True)
    )
    is_admin = "admin" in role_keys or rbac.has_permission(membership, "role.manage")
    sections = {}

    if is_owner or is_admin:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
            {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "activity", "match_prefix": "/app/dashboards"},
            {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "clock", "match_prefix": "/app/dashboards/snapshots"},
        ]
        sections["Analytics & Governance"] = sections["Overview"]
        sections["Operations"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"},
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
            {"label": "Technician Workspace", "url": _safe_reverse("workspace:my_jobs"), "icon": "wrench", "match_prefix": "/app/workspace"},
        ]
        sections["Maintenance Planning"] = [
            {"label": "Maintenance Plans", "url": _safe_reverse("maintenance:plans"), "icon": "wrench", "match_prefix": "/app/maintenance/plans"},
            {"label": "Due & Upcoming", "url": _safe_reverse("maintenance:due"), "icon": "clock", "match_prefix": "/app/maintenance/due"},
            {"label": "PM History", "url": _safe_reverse("maintenance:history"), "icon": "list-check", "match_prefix": "/app/maintenance/history"},
        ]
        sections["Inventory & Stores"] = [
            {"label": "Parts Catalog", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"},
            {"label": "Stock Balances", "url": _safe_reverse("inventory:stock"), "icon": "grid", "match_prefix": "/app/inventory/stock"},
            {"label": "Warehouses", "url": _safe_reverse("inventory:warehouses"), "icon": "building", "match_prefix": "/app/inventory/warehouses"},
            {"label": "Reservations", "url": _safe_reverse("inventory:reservations"), "icon": "list-check", "match_prefix": "/app/inventory/reservations"},
            {"label": "Stock Movements", "url": _safe_reverse("inventory:movements"), "icon": "clipboard", "match_prefix": "/app/inventory/movements"},
        ]
        sections["Assets & Locations"] = [
            {"label": "Sites & Locations", "url": _safe_reverse("sites:list"), "icon": "pin", "match_prefix": "/app/sites"},
            {"label": "Asset Registry", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"},
            {"label": "Asset Hierarchy", "url": _safe_reverse("assets:hierarchy_hub"), "icon": "git-branch", "match_prefix": "/app/assets/hierarchy"},
            {"label": "Scan QR / Barcode", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"},
        ]
        sections["Commercial & Contracts"] = [
            {"label": "Warranties & Contracts", "url": _safe_reverse("contracts:agreements"), "icon": "shield", "match_prefix": "/app/contracts/agreements"},
            {"label": "Expiring Coverage", "url": _safe_reverse("contracts:expiry"), "icon": "clock", "match_prefix": "/app/contracts/expiry"},
            {"label": "Service Providers", "url": _safe_reverse("contracts:providers"), "icon": "building", "match_prefix": "/app/contracts/providers"},
        ]
        sections["Commercial"] = sections["Commercial & Contracts"]
        sections["Service Level Agreements"] = [
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
        ]
        sections["Compliance & Governance"] = [
            {"label": "Audit Trail", "url": _safe_reverse("audit:list"), "icon": "shield", "match_prefix": "/app/audit"},
            {"label": "Compliance Reports", "url": _safe_reverse("audit:reports"), "icon": "list-check", "match_prefix": "/app/audit/reports"},
        ]
        sections["Administration"] = [
            {"label": "Organization Settings", "url": _safe_reverse("tenancy:organization"), "icon": "building", "match_prefix": "/app/organization"},
            {"label": "Users & Invitations", "url": _safe_reverse("tenancy:members"), "icon": "people", "match_prefix": "/app/users"},
            {"label": "Roles & Permissions", "url": _safe_reverse("rbac:roles"), "icon": "shield", "match_prefix": "/app/roles"},
            {"label": "Technicians & Shifts", "url": _safe_reverse("workspace:technician_list"), "icon": "wrench", "match_prefix": "/app/workspace/technicians"},
            {"label": "Portal Accounts", "url": _safe_reverse("portal:accounts_list"), "icon": "people", "match_prefix": "/app/portal/accounts"},
        ]


    elif "operations_manager" in role_keys:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Operations"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"},
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Technicians & Shifts", "url": _safe_reverse("workspace:technician_list"), "icon": "people", "match_prefix": "/app/workspace/technicians"},
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
            {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
        ]

    elif role_keys & {"technician", "field_technician"}:
        sections["Field Execution"] = [
            {"label": "My Assigned Jobs", "url": _safe_reverse("workspace:my_jobs"), "icon": "wrench", "match_prefix": "/app/workspace"},
            {"label": "All Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "My Work Cockpit", "url": _safe_reverse("dashboards:my_work"), "icon": "activity", "match_prefix": "/app/dashboards/my-work"},
            {"label": "My Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "list-check", "match_prefix": "/app/inspections"},
            {"label": "My Profile & Shift", "url": _safe_reverse("workspace:my_profile"), "icon": "user", "match_prefix": "/app/workspace/profile"},
        ]
        field_tools = [
            {"label": "Scan Asset Label", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"},
        ]
        if rbac.has_permission_anywhere(membership, "checklist.view") or rbac.has_permission_anywhere(membership, "checklist.execute"):
            field_tools.append(
                {"label": "Checklist Templates", "url": _safe_reverse("checklists:list"), "icon": "file-text", "match_prefix": "/app/checklists"}
            )
        if rbac.has_permission_anywhere(membership, "inventory.part.view"):
            field_tools.append(
                {"label": "Cataloged Parts", "url": _safe_reverse("inventory:parts"), "icon": "box", "match_prefix": "/app/inventory/parts"}
            )
        sections["Field Tools"] = field_tools

    elif role_keys & {"stores_manager", "stores_inventory"}:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
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
                {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
            ]

    elif "asset_manager" in role_keys:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
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
            {"label": "Providers", "url": _safe_reverse("contracts:providers"), "icon": "building", "match_prefix": "/app/contracts/providers"},
        ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
                {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
            ]

    elif "maintenance_planner" in role_keys:
        sections["Overview"] = [
            {"label": "Operational Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        if rbac.has_permission_anywhere(membership, "maintenance.view"):
            sections["Maintenance Planning"] = [
                {"label": "Maintenance Plans", "url": _safe_reverse("maintenance:plans"), "icon": "wrench", "match_prefix": "/app/maintenance/plans"},
                {"label": "Due & Upcoming", "url": _safe_reverse("maintenance:due"), "icon": "clock", "match_prefix": "/app/maintenance/due"},
                {"label": "PM History", "url": _safe_reverse("maintenance:history"), "icon": "list-check", "match_prefix": "/app/maintenance/history"},
            ]
        ops_items = []
        if rbac.has_permission_anywhere(membership, "work_order.view"):
            ops_items.append({"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"})
        if rbac.has_permission_anywhere(membership, "checklist.view"):
            ops_items.append({"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"})
        if rbac.has_permission_anywhere(membership, "inspection.view"):
            ops_items.append({"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"})
        if ops_items:
            sections["Operations"] = ops_items

        asset_items = []
        if rbac.has_permission_anywhere(membership, "asset.view"):
            asset_items.append({"label": "Asset Register", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"})
        if rbac.has_permission_anywhere(membership, "qr.scan"):
            asset_items.append({"label": "Scan QR", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"})
        if asset_items:
            sections["Assets"] = asset_items

        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "supervisor" in role_keys:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Supervisory Operations"] = [
            {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"},
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
            {"label": "Checklists", "url": _safe_reverse("checklists:list"), "icon": "list-check", "match_prefix": "/app/checklists"},
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"},
        ]
        if rbac.has_permission_anywhere(membership, "sla.view"):
            sections["Service Level Agreements"] = [
                {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
                {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
            ]

    elif "service_dispatcher" in role_keys:
        sections["Overview"] = [
            {"label": "Operational Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        ops_items = []
        if rbac.has_permission_anywhere(membership, "incident.view"):
            ops_items.append({"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"})
            ops_items.append({"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"})
        if rbac.has_permission_anywhere(membership, "work_order.view"):
            ops_items.append({"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"})
        if rbac.has_permission_anywhere(membership, "inspection.view"):
            ops_items.append({"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"})
        if ops_items:
            sections["Operations"] = ops_items

        asset_items = []
        if rbac.has_permission_anywhere(membership, "asset.view"):
            asset_items.append({"label": "Asset Register", "url": _safe_reverse("assets:list"), "icon": "box", "match_prefix": "/app/assets"})
        if rbac.has_permission_anywhere(membership, "qr.scan"):
            asset_items.append({"label": "Scan QR", "url": _safe_reverse("identification:scan"), "icon": "qr", "match_prefix": "/app/scan"})
        if asset_items:
            sections["Assets"] = asset_items

        if rbac.has_permission_anywhere(membership, "sla.view"):
            sections["Service Level Agreements"] = [
                {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            ]

    elif "service_manager" in role_keys:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Service Assurance"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"},
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            {"label": "Portal Accounts", "url": _safe_reverse("portal:accounts_list"), "icon": "people", "match_prefix": "/app/portal/accounts"},
        ]
        sections["Commercial"] = [
            {"label": "Warranties & contracts", "url": _safe_reverse("contracts:agreements"), "icon": "shield", "match_prefix": "/app/contracts/agreements"},
            {"label": "Expiring coverage", "url": _safe_reverse("contracts:expiry"), "icon": "clock", "match_prefix": "/app/contracts/expiry"},
            {"label": "Providers", "url": _safe_reverse("contracts:providers"), "icon": "building", "match_prefix": "/app/contracts/providers"},
        ]
        sections["Analytics"] = [
            {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
        ]

    elif role_keys & {"auditor", "compliance"}:
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Audit & Compliance"] = [
            {"label": "Audit Trail", "url": _safe_reverse("audit:list"), "icon": "shield", "match_prefix": "/app/audit/"},
            {"label": "Compliance reports", "url": _safe_reverse("audit:reports"), "icon": "list-check", "match_prefix": "/app/audit/reports"},
            {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
            {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
        ]

    else:
        # Fallback for custom composite roles - dynamically populated by verified permissions
        sections["Overview"] = [
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]

        # Operations
        ops_items = []
        if rbac.has_permission_anywhere(membership, "incident.view"):
            sections.setdefault("Operations", []).append(
                {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"}
            )
            sections.setdefault("Operations", []).append(
                {"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"}
            )
        if rbac.has_permission_anywhere(membership, "work_order.view"):
            sections.setdefault("Operations", []).append(
                {"label": "Work Orders", "url": _safe_reverse("workorders:list"), "icon": "clipboard-check", "match_prefix": "/app/work-orders"}
            )
        if rbac.has_permission_anywhere(membership, "user.view"):
            sections.setdefault("Operations", []).append(
                {"label": "Technicians & Shifts", "url": _safe_reverse("workspace:technician_list"), "icon": "people", "match_prefix": "/app/workspace/technicians"}
            )
        

        # Service Level Agreements
        if rbac.has_permission_anywhere(membership, "sla.view"):
            sections["Service Level Agreements"] = [
                {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
            ]
        if rbac.has_permission_anywhere(membership, "contract.view"):
            sections["Commercial"] = [
                {"label": "Warranties & contracts", "url": _safe_reverse("contracts:agreements"), "icon": "shield", "match_prefix": "/app/contracts/agreements"},
                {"label": "Expiring coverage", "url": _safe_reverse("contracts:expiry"), "icon": "clock", "match_prefix": "/app/contracts/expiry"},
                {"label": "Providers", "url": _safe_reverse("contracts:providers"), "icon": "building", "match_prefix": "/app/contracts/providers"},
            ]
        if rbac.has_permission_anywhere(membership, "report.view"):
            sections["Analytics"] = [
                {"label": "Analytics Hub", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"},
                {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
            ]

        # Analytics
        analytics_items = []
        if rbac.has_permission_anywhere(membership, "report.view"):
            analytics_items.append({"label": "Operational Dashboards", "url": _safe_reverse("dashboards:hub"), "icon": "grid", "match_prefix": "/app/dashboards"})
            analytics_items.append({"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "clock", "match_prefix": "/app/dashboards/snapshots"})
        if analytics_items:
            sections["Analytics"] = analytics_items

        # Compliance & Governance
        audit_items = []
        if rbac.has_permission_anywhere(membership, "audit.view"):
            audit_items.append({"label": "Audit Trail", "url": _safe_reverse("audit:list"), "icon": "clock", "match_prefix": "/app/audit"},)
            audit_items.append({"label": "Compliance reports", "url": _safe_reverse("audit:reports"), "icon": "list-check", "match_prefix": "/app/audit/reports"})
        if audit_items:
            sections["Compliance & Governance"] = audit_items

        # Administration
        admin_items = []
        if rbac.has_permission_anywhere(membership, "organization.update"):
            admin_items.append({"label": "Organization", "url": _safe_reverse("tenancy:organization"), "icon": "building", "match_prefix": "/app/organization"})
        if rbac.has_permission_anywhere(membership, "user.invite") or rbac.has_permission_anywhere(membership, "user.view"):
            admin_items.append({"label": "Users", "url": _safe_reverse("tenancy:members"), "icon": "people", "match_prefix": "/app/users"})
        if rbac.has_permission_anywhere(membership, "role.manage") or rbac.has_permission_anywhere(membership, "role.view"):
            admin_items.append({"label": "Roles & Permissions", "url": _safe_reverse("rbac:roles"), "icon": "shield", "match_prefix": "/app/roles"})
        if rbac.has_permission_anywhere(membership, "user.view") and rbac.has_permission_anywhere(membership, "work_order.view"):
            admin_items.append({"label": "Technicians & Shifts", "url": _safe_reverse("workspace:technician_list"), "icon": "people", "match_prefix": "/app/workspace/technicians"})
        if rbac.has_permission_anywhere(membership, "portal.manage"):
            admin_items.append({"label": "Portal Accounts", "url": _safe_reverse("portal:accounts_list"), "icon": "people", "match_prefix": "/app/portal/accounts"})
        if admin_items:
            sections["Administration"] = admin_items

    return _filter_valid_nav_items(sections)


def _build_breadcrumbs(request):
    """Generates structured breadcrumbs and back URL for sub-screens across all modules."""
    path = getattr(request, "path", "").rstrip("/")
    if not path or path in ("/app", "/platform", "/platform/organizations"):
        return [], None

    crumbs = []
    user = getattr(request, "user", None)
    if getattr(user, "is_platform_admin", False) and not getattr(request, "membership", None):
        crumbs.append({"label": "Platform", "url": _safe_reverse("platform_admin:organizations")})
    elif getattr(request, "membership", None) and is_client_membership(request.membership):
        crumbs.append({"label": "Portal", "url": _safe_reverse("portal:dashboard")})
    else:
        crumbs.append({"label": "Home", "url": _safe_reverse("ui:home")})

    MODULE_MAP = [
        ("/app/work-orders", "Work Orders", "workorders:list"),
        ("/app/incidents/dashboard", "Incident Dashboard", "incidents:dashboard"),
        ("/app/incidents", "Incidents & Requests", "incidents:list"),
        ("/app/assets/categories", "Categories", "assets:categories"),
        ("/app/assets/hierarchy", "Hierarchy", "assets:hierarchy"),
        ("/app/assets", "Assets", "assets:list"),
        ("/app/sites", "Sites & Locations", "sites:list"),
        ("/app/inventory/parts", "Parts Inventory", "inventory:parts_list"),
        ("/app/inventory/stock", "Stock Overview", "inventory:stock_list"),
        ("/app/inventory/transactions", "Transactions", "inventory:transactions_list"),
        ("/app/inventory/warehouses", "Warehouses", "inventory:warehouses_list"),
        ("/app/contracts/agreements", "Warranties & Contracts", "contracts:agreements"),
        ("/app/contracts/expiry", "Expiring Coverage", "contracts:expiry"),
        ("/app/contracts/providers", "Providers", "contracts:providers"),
        ("/app/sla/trackings", "SLA & Escalation", "sla:trackings"),
        ("/app/sla/breaches", "Breaches", "sla:breaches"),
        ("/app/sla/profiles", "SLA Profiles", "sla:profiles"),
        ("/app/dashboards/snapshots", "KPI Snapshots", "dashboards:snapshot_list"),
        ("/app/dashboards", "Analytics Hub", "dashboards:hub"),
        ("/app/audit/reports", "Compliance Reports", "audit:reports"),
        ("/app/audit", "Audit Trail", "audit:list"),
        ("/app/workspace/technicians", "Technicians & Shifts", "workspace:technician_list"),
        ("/app/workspace/shifts", "Shifts", "workspace:shift_list"),
        ("/app/workspace/my-jobs", "My Jobs", "workspace:my_jobs"),
        ("/app/workspace/profile", "My Profile", "workspace:my_profile"),
        ("/app/organization", "Organization", "tenancy:organization"),
        ("/app/users", "Users Directory", "tenancy:members"),
        ("/app/roles", "Roles & Permissions", "rbac:roles"),
        ("/app/notifications", "Notifications", "notifications:list"),
        ("/app/checklists", "Checklists & Inspections", "checklists:list"),
        ("/app/pm", "Preventive Maintenance", "pm:plan_list"),
    ]

    matched_mod = None
    for prefix, label, viewname in MODULE_MAP:
        if path == prefix or path.startswith(prefix + "/"):
            matched_mod = (prefix, label, viewname)
            break

    if matched_mod:
        prefix, label, viewname = matched_mod
        url = _safe_reverse(viewname)
        if path == prefix:
            crumbs.append({"label": label, "url": None})
        else:
            crumbs.append({"label": label, "url": url})
            remainder = path[len(prefix):].strip("/").split("/")
            for i, seg in enumerate(remainder):
                is_last = (i == len(remainder) - 1)
                if len(seg) >= 32 and (seg.replace("-", "").isalnum()):
                    seg_label = "Detail"
                elif seg in ("action",):
                    continue
                elif seg in ("new", "create"):
                    seg_label = "New"
                elif seg in ("assign",):
                    seg_label = "Assign Technician"
                elif seg in ("reassign",):
                    seg_label = "Reassign"
                elif seg in ("plan",):
                    seg_label = "Plan"
                elif seg in ("dispatch",):
                    seg_label = "Dispatch"
                elif seg in ("complete",):
                    seg_label = "Complete"
                elif seg in ("review",):
                    seg_label = "Review"
                elif seg in ("close",):
                    seg_label = "Close"
                elif seg in ("parts",):
                    seg_label = "Parts"
                elif seg in ("labor",):
                    seg_label = "Labor"
                elif seg in ("evidence",):
                    seg_label = "Evidence"
                elif seg in ("notes",):
                    seg_label = "Notes"
                elif seg in ("timeline",):
                    seg_label = "Timeline"
                elif seg in ("reports",):
                    seg_label = "Reports"
                else:
                    seg_label = seg.replace("-", " ").replace("_", " ").title()

                sub_path = prefix + "/" + "/".join(remainder[:i+1])
                crumbs.append({"label": seg_label, "url": None if is_last else sub_path})
    else:
        segments = [s for s in path.replace("/app/", "").split("/") if s]
        for i, seg in enumerate(segments):
            is_last = (i == len(segments) - 1)
            seg_label = "Detail" if len(seg) >= 32 else seg.replace("-", " ").replace("_", " ").title()
            sub_path = "/app/" + "/".join(segments[:i+1])
            crumbs.append({"label": seg_label, "url": None if is_last else sub_path})

    back_url = None
    if len(crumbs) > 1:
        for c in reversed(crumbs[:-1]):
            if c.get("url"):
                back_url = c["url"]
                break

    return crumbs, back_url


def shell(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}

    from django.conf import settings
    idle_timeout_seconds = getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800)
    idle_timeout_ms = int(idle_timeout_seconds) * 1000

    req_path = request.path
    membership = getattr(request, "membership", None)
    crumbs, back_url = _build_breadcrumbs(request)
    idle_timeout_ms = max(60, int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800))) * 1000

    # 1. Platform Super Admin (NAV-01) - Dedicated Governance Navigation Only
    if getattr(user, "is_platform_admin", False):
        sections = {
            "Platform Governance": [
                {"label": "Overview", "url": _safe_reverse("platform_admin:overview"), "icon": "grid", "match_prefix": "/platform/overview", "match_prefixes": ["/platform/overview", "/app"]},
                {"label": "Organizations", "url": _safe_reverse("platform_admin:organizations"), "icon": "building", "match_prefix": "/platform/organizations"},
                {"label": "Platform Audit Trail", "url": _safe_reverse("platform_admin:audit"), "icon": "shield", "match_prefix": "/platform/audit"},
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
            "shell_breadcrumbs": crumbs,
            "shell_back_url": back_url,
            "session_idle_timeout_ms": idle_timeout_ms,
        }

    if membership is None:
        return {
            "shell_org": None,
            "shell_membership": None,
            "shell_nav_sections": {},
            "shell_memberships": list(selectors.active_memberships(user)),
            "shell_tenant_error": getattr(request, "tenant_error", None),
            "is_client": False,
            "shell_breadcrumbs": crumbs,
            "shell_back_url": back_url,
            "session_idle_timeout_ms": idle_timeout_ms,
        }

    # 2. Client / Requester Navigation (M13)
    is_client = is_client_membership(membership)
    if is_client:
        portal_items = [
            {"label": "Client Portal", "url": _safe_reverse("portal:dashboard"), "icon": "grid", "match_prefix": "/app/portal/"},
            {"label": "My Requests", "url": _safe_reverse("portal:requests_list"), "icon": "list-check", "match_prefix": "/app/portal/requests"},
            {"label": "New Request", "url": _safe_reverse("portal:request_create"), "icon": "plus-circle", "match_prefix": "/app/portal/requests/new"},
        ]
        if rbac.has_permission_anywhere(membership, "qr.scan"):
            portal_items.append({"label": "Scan QR", "url": _safe_reverse("portal:scan"), "icon": "qr", "match_prefix": "/app/portal/scan", "match_prefixes": ["/app/portal/scan", "/app/portal/s/"]})
        sections = {"Portal": portal_items}
        sections = _filter_valid_nav_items(sections)
        _resolve_active(sections, req_path)
        return {
            "shell_org": getattr(request, "organization", None),
            "shell_membership": membership,
            "shell_nav_sections": sections,
            "shell_memberships": request.active_memberships if hasattr(request, "active_memberships") and request.active_memberships is not None else list(selectors.active_memberships(user)),
            "shell_tenant_error": getattr(request, "tenant_error", None),
            "is_client": True,
            "shell_breadcrumbs": crumbs,
            "shell_back_url": back_url,
            "session_idle_timeout_ms": idle_timeout_ms,
        }

        # 3. Internal Tenant Staff Roles - Clean Sidebar Allocation (Section H)
    import copy
    import uuid
    from django.core.cache import cache

    is_owner = rbac.is_owner(membership)
    nav_cache_key = f"shell_nav_raw:{membership.pk}" if isinstance(getattr(membership, "pk", None), (uuid.UUID, int, str)) else None
    raw_sections = cache.get(nav_cache_key) if nav_cache_key else None

    if raw_sections is None:
        raw_sections = _build_tenant_nav(membership, is_owner)
        if nav_cache_key:
            cache.set(nav_cache_key, raw_sections, timeout=300)

    sections = copy.deepcopy(raw_sections)
    _resolve_active(sections, req_path)

    return {
        "shell_org": getattr(request, "organization", None),
        "shell_membership": membership,
        "shell_nav_sections": sections,
        "shell_memberships": request.active_memberships if hasattr(request, "active_memberships") and request.active_memberships is not None else list(selectors.active_memberships(user)),
        "shell_tenant_error": getattr(request, "tenant_error", None),
        "is_client": is_client,
        "is_org_owner": is_owner,
        "shell_breadcrumbs": crumbs,
        "shell_back_url": back_url,
        "session_idle_timeout_ms": idle_timeout_ms,
    }
