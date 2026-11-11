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
        sections["Service Level Agreements"] = [
            {"label": "SLA & Escalation", "url": _safe_reverse("sla:trackings"), "icon": "clock", "match_prefix": "/app/sla/trackings"},
        ]
        sections["Compliance & Governance"] = [
            {"label": "Audit Trail", "url": _safe_reverse("audit:list"), "icon": "clock", "match_prefix": "/app/audit"},
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
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
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
            {"label": "Inspections", "url": _safe_reverse("checklists:inspections"), "icon": "clipboard", "match_prefix": "/app/inspections"},
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
            {"label": "Operations Overview", "url": _safe_reverse("ui:home"), "icon": "grid", "match_prefix": "/app/"},
        ]
        sections["Operations"] = [
            {"label": "Incidents & Requests", "url": _safe_reverse("incidents:list"), "icon": "bell", "match_prefix": "/app/incidents"},
            {"label": "Incident Dashboard", "url": _safe_reverse("incidents:dashboard"), "icon": "activity", "match_prefix": "/app/incidents/dashboard"},
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
                {"label": "KPI Snapshots", "url": _safe_reverse("dashboards:snapshot_list"), "icon": "archive", "match_prefix": "/app/dashboards/snapshots"},
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
        if rbac.has_permission_anywhere(membership, "work_order.view"):
            admin_items.append({"label": "Technicians & Shifts", "url": _safe_reverse("workspace:technician_list"), "icon": "people", "match_prefix": "/app/workspace/technicians"})
        if rbac.has_permission_anywhere(membership, "portal.manage"):
            admin_items.append({"label": "Portal Accounts", "url": _safe_reverse("portal:accounts_list"), "icon": "people", "match_prefix": "/app/portal/accounts"})
        if admin_items:
            sections["Administration"] = admin_items

    return _filter_valid_nav_items(sections)


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
            "session_idle_timeout_ms": max(60, int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800))) * 1000,
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
                {"label": "Scan QR", "url": _safe_reverse("portal:scan"), "icon": "qr", "match_prefix": "/app/portal/scan", "match_prefixes": ["/app/portal/scan", "/app/portal/s/"]},
            ]
        }
        sections = _filter_valid_nav_items(sections)
        _resolve_active(sections, req_path)
        return {
            "shell_org": getattr(request, "organization", None),
            "shell_membership": membership,
            "shell_nav_sections": sections,
            "shell_memberships": request.active_memberships if hasattr(request, "active_memberships") and request.active_memberships is not None else list(selectors.active_memberships(user)),
            "shell_tenant_error": getattr(request, "tenant_error", None),
            "is_client": True,
            "session_idle_timeout_ms": max(60, int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800))) * 1000,
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
        "session_idle_timeout_ms": max(60, int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800))) * 1000,
    }
