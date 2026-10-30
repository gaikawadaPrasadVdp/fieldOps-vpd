"""Component & Asset Health Engine.

Evaluates operational equipment health by correlating asset lifecycle status with
active breakdown tickets and incidents (M05 ServiceRequest).

Health States:
- HEALTHY: Asset is ACTIVE and has 0 unresolved breakdown tickets.
- DEGRADED: Asset has active tickets with LOW/MEDIUM severity, DEGRADED service impact,
            or is administratively UNDER_MAINTENANCE without full outage.
- CRITICAL: Asset has active tickets with HIGH/CRITICAL severity, PARTIAL/FULL outage,
            or is OUT_OF_SERVICE.
- OFFLINE: Asset is INACTIVE, RETIRED, or DISPOSED.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Iterable

if TYPE_CHECKING:
    from apps.assets.models import Asset

HEALTH_HEALTHY = "HEALTHY"
HEALTH_DEGRADED = "DEGRADED"
HEALTH_CRITICAL = "CRITICAL"
HEALTH_OFFLINE = "OFFLINE"

CRITICAL_SEVERITIES = {"CRITICAL", "HIGH"}
CRITICAL_IMPACTS = {"FULL_OUTAGE", "PARTIAL_OUTAGE"}


def evaluate_asset_health(asset: Asset, active_tickets: list[Any]) -> dict[str, Any]:
    """Pure evaluation of asset health based on asset status and its active breakdown tickets."""
    status_upper = str(getattr(asset, "status", "ACTIVE")).upper()
    ticket_count = len(active_tickets)

    # 1. Lifecycle terminal / inactive states
    if status_upper in ("RETIRED", "DISPOSED"):
        return {
            "status": HEALTH_OFFLINE,
            "tone": "secondary",
            "label": "Retired" if status_upper == "RETIRED" else "Disposed",
            "breakdown_count": ticket_count,
            "highest_severity": None,
            "tickets": _format_tickets(active_tickets),
            "has_active_breakdown": False,
        }

    if status_upper == "INACTIVE":
        return {
            "status": HEALTH_OFFLINE,
            "tone": "secondary",
            "label": "Inactive",
            "breakdown_count": ticket_count,
            "highest_severity": None,
            "tickets": _format_tickets(active_tickets),
            "has_active_breakdown": False,
        }

    # 2. Out of service lifecycle
    if status_upper == "OUT_OF_SERVICE":
        return {
            "status": HEALTH_CRITICAL,
            "tone": "danger",
            "label": f"Breakdown Active ({ticket_count})" if ticket_count > 0 else "Out of Service",
            "breakdown_count": ticket_count,
            "highest_severity": _highest_severity(active_tickets) or "CRITICAL",
            "tickets": _format_tickets(active_tickets),
            "has_active_breakdown": ticket_count > 0,
        }

    # 3. Active breakdown tickets present
    if ticket_count > 0:
        has_critical = any(
            getattr(t, "severity", None) in CRITICAL_SEVERITIES
            or getattr(t, "service_impact", None) in CRITICAL_IMPACTS
            for t in active_tickets
        )
        highest_sev = _highest_severity(active_tickets)

        if has_critical:
            label = f"Breakdown Active ({ticket_count})" if ticket_count > 1 else "Breakdown Active"
            return {
                "status": HEALTH_CRITICAL,
                "tone": "danger",
                "label": label,
                "breakdown_count": ticket_count,
                "highest_severity": highest_sev,
                "tickets": _format_tickets(active_tickets),
                "has_active_breakdown": True,
            }
        else:
            label = f"Degraded ({ticket_count})" if ticket_count > 1 else "Degraded"
            return {
                "status": HEALTH_DEGRADED,
                "tone": "warning",
                "label": label,
                "breakdown_count": ticket_count,
                "highest_severity": highest_sev,
                "tickets": _format_tickets(active_tickets),
                "has_active_breakdown": True,
            }

    # 4. Under maintenance without active breakdown tickets
    if status_upper == "UNDER_MAINTENANCE":
        return {
            "status": HEALTH_DEGRADED,
            "tone": "warning",
            "label": "Under Maintenance",
            "breakdown_count": 0,
            "highest_severity": None,
            "tickets": [],
            "has_active_breakdown": False,
        }

    # 5. Healthy operational equipment
    return {
        "status": HEALTH_HEALTHY,
        "tone": "success",
        "label": "Healthy",
        "breakdown_count": 0,
        "highest_severity": None,
        "tickets": [],
        "has_active_breakdown": False,
    }


def _highest_severity(tickets: list[Any]) -> str | None:
    order = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
    highest = None
    max_val = 0
    for t in tickets:
        sev = getattr(t, "severity", "MEDIUM")
        val = order.get(sev, 0)
        if val > max_val:
            max_val = val
            highest = sev
    return highest


def _format_tickets(tickets: list[Any]) -> list[dict[str, Any]]:
    formatted = []
    for t in tickets:
        formatted.append({
            "id": str(getattr(t, "pk", getattr(t, "id", ""))),
            "number": getattr(t, "number", ""),
            "title": getattr(t, "title", ""),
            "severity": getattr(t, "severity", "MEDIUM"),
            "service_impact": getattr(t, "service_impact", "NONE"),
            "status": getattr(t, "status", "NEW"),
            "occurred_at": getattr(t, "occurred_at", None),
        })
    return formatted


def get_asset_health(asset: Asset) -> dict[str, Any]:
    """Computes health for a single asset (fetches active ServiceRequest tickets)."""
    if hasattr(asset, "_health_info"):
        return asset._health_info

    from apps.incidents.models import ServiceRequest
    from apps.incidents.workflow import ACTIVE_INCIDENT_STATUSES

    tickets = list(
        ServiceRequest.objects.filter(
            asset=asset,
            status__in=ACTIVE_INCIDENT_STATUSES,
        ).order_by("-occurred_at")
    )
    health = evaluate_asset_health(asset, tickets)
    asset._health_info = health
    return health


def batch_annotate_assets_health(assets: Iterable[Asset], organization=None) -> dict[uuid.UUID, dict[str, Any]]:
    """Batch annotates a collection of Asset instances with health info in a single SQL query."""
    asset_list = list(assets)
    if not asset_list:
        return {}

    from apps.incidents.models import ServiceRequest
    from apps.incidents.workflow import ACTIVE_INCIDENT_STATUSES

    pks = [a.pk for a in asset_list]
    org = organization or getattr(asset_list[0], "organization", None)

    qs = ServiceRequest.objects.filter(
        asset_id__in=pks,
        status__in=ACTIVE_INCIDENT_STATUSES,
    )
    if org:
        qs = qs.filter(organization=org)

    tickets_by_asset: dict[uuid.UUID, list[ServiceRequest]] = {pk: [] for pk in pks}
    for t in qs.order_by("-occurred_at"):
        if t.asset_id in tickets_by_asset:
            tickets_by_asset[t.asset_id].append(t)

    result = {}
    for a in asset_list:
        tickets = tickets_by_asset.get(a.pk, [])
        info = evaluate_asset_health(a, tickets)
        a._health_info = info
        result[a.pk] = info

    return result


def annotate_tree_health(tree_node: dict[str, Any], organization=None) -> dict[str, Any]:
    """Annotates all nodes in a build_tree() structure in 1 single query.
    
    Also rolls up sub-component breakdown counts to parent assemblies.
    """
    if not tree_node:
        return tree_node

    from apps.assets import hierarchy

    nodes = hierarchy.flatten(tree_node)
    assets = [n["asset"] for n in nodes if "asset" in n]
    batch_annotate_assets_health(assets, organization=organization)

    # Post-order rollout of subtree breakdowns
    def _rollup(node: dict[str, Any]) -> int:
        direct_count = node["asset"]._health_info.get("breakdown_count", 0)
        sub_count = 0
        for child in node.get("children", []):
            sub_count += _rollup(child)
        
        node["child_breakdown_count"] = sub_count
        node["subtree_breakdown_count"] = direct_count + sub_count
        node["health"] = node["asset"]._health_info
        if sub_count > 0 and direct_count == 0:
            node["health"]["subcomponent_alert"] = f"{sub_count} sub-item{'s' if sub_count > 1 else ''} in breakdown"
            node["health"]["has_child_breakdown"] = True
        return direct_count + sub_count

    _rollup(tree_node)
    return tree_node
