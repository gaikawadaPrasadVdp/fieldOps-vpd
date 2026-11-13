from __future__ import annotations

import uuid
from django.db.models import QuerySet

from apps.tenancy.models import Membership, Organization
from .models import PortalAccount


STAGE_MAP = {
    "NEW": "PENDING",
    "TRIAGED": "PENDING",
    "APPROVED": "PENDING",
    "WORK_ORDER_CREATED": "IN_PROGRESS",
    "IN_SERVICE": "IN_PROGRESS",
    "RESOLVED": "RESOLVED",
    "CONFIRMED": "CONFIRMED",
    "CLOSED": "CLOSED",
    "REJECTED": "REJECTED",
}

STATUS_LABELS = {
    "NEW": "Submitted",
    "TRIAGED": "Under Review",
    "APPROVED": "Approved",
    "WORK_ORDER_CREATED": "Scheduled",
    "IN_SERVICE": "In Service",
    "RESOLVED": "Resolved",
    "CONFIRMED": "Confirmed",
    "CLOSED": "Closed",
    "REJECTED": "Declined",
}

ACTION_LABELS = {
    "report": "Request submitted",
    "triage": "Triaged by operations",
    "approve": "Request approved",
    "reject": "Request declined",
    "link_work_order": "Work order scheduled",
    "work_order_cancelled": "Work order rescheduled",
    "start_service": "Technician commenced work",
    "resolve": "Work completed / Resolved",
    "resume_service": "Service resumed",
    "confirm": "Resolution confirmed",
    "reopen": "Request reopened",
    "close": "Request closed",
}


def get_status_stage(status: str) -> str:
    """Returns high-level lifecycle stage for an M05 status."""
    return STAGE_MAP.get(status, "PENDING")


def get_status_label(status: str) -> str:
    """Returns human-readable client-facing label for an M05 status."""
    return STATUS_LABELS.get(status, str(status).replace("_", " ").title())


def get_portal_account(membership: Membership | None) -> PortalAccount | None:
    """Returns the portal account for the given membership, if any."""
    if membership is None:
        return None
    return PortalAccount.objects.for_organization(membership.organization_id).filter(
        organization_id=membership.organization_id,
        membership=membership,
    ).select_related("membership", "membership__user", "organization").first()


def get_portal_account_by_id(organization: Organization, account_id: str | uuid.UUID) -> PortalAccount | None:
    """Returns a portal account by ID scoped to the given organization."""
    return PortalAccount.objects.for_organization(organization).filter(
        pk=account_id,
    ).select_related("membership", "membership__user").first()


def accounts_for_organization(organization: Organization) -> QuerySet[PortalAccount]:
    """Returns all portal accounts for an organization."""
    return PortalAccount.objects.for_organization(organization).select_related(
        "membership", "membership__user"
    ).order_by("company_name", "membership__user__full_name")


def is_portal_account_active(membership: Membership | None) -> bool:
    """Returns True if the membership has an active enabled portal account in its organization."""
    account = get_portal_account(membership)
    return bool(account and account.is_enabled and account.membership.is_active)


def client_requests_for(membership: Membership | None) -> QuerySet[ServiceRequest]:
    """Returns service requests visible to the client portal user.

    Scoped strictly to the caller's organization and reported_by=membership.
    """
    if membership is None:
        from apps.incidents.models import ServiceRequest
        return ServiceRequest.objects.none()
    from apps.incidents.models import ServiceRequest
    return (
        ServiceRequest.objects.for_organization(membership.organization)
        .filter(reported_by=membership)
        .select_related("asset", "site", "reported_by__user")
        .order_by("-created_at")
    )


def get_client_request(membership: Membership | None, request_id: str | uuid.UUID) -> ServiceRequest | None:
    """Returns a single service request scoped to the client portal user.

    Prevents cross-client and cross-tenant access. Returns None if not found or unauthorized.
    Supports lookup by UUID (pk) or reference number.
    """
    if membership is None:
        return None
    qs = client_requests_for(membership)
    try:
        val = uuid.UUID(str(request_id))
        obj = qs.filter(pk=val).first()
        if obj:
            return obj
    except (ValueError, TypeError):
        pass
    return qs.filter(number=str(request_id).strip()).first()


_INTERNAL_HISTORY_ACTIONS = (
    "work_order_update",
    "work_order_updated",
    "work_order_labor",
    "work_order_material",
    "work_order_evidence",
    "work_order_checklist",
)


def client_request_history_for(sr: ServiceRequest) -> QuerySet[ServiceRequestHistory]:
    """Returns the append-only status history for a service request in chronological order."""
    from apps.incidents.models import ServiceRequestHistory
    return (
        ServiceRequestHistory.objects.for_organization(sr.organization)
        .filter(request=sr)
        .exclude(action__in=_INTERNAL_HISTORY_ACTIONS)
        .order_by("created_at")
    )


def granted_assets_for(membership: Membership | None):
    """Returns non-terminal assets explicitly granted to the client's portal account."""
    if membership is None:
        from apps.assets.models import Asset
        return Asset.objects.none()
    account = get_portal_account(membership)
    if account is None or not account.is_enabled or not membership.is_active:
        from apps.assets.models import Asset
        return Asset.objects.none()
    from apps.assets.models import Asset
    return (
        Asset.objects.for_organization(membership.organization)
        .filter(portal_grants__portal_account=account)
        .exclude(status__in=["RETIRED", "DISPOSED"])
        .select_related("site")
        .order_by("asset_tag")
    )


def is_asset_granted_to_client(membership: Membership | None, asset_id: str | uuid.UUID) -> bool:
    """Returns True if the asset is explicitly granted and accessible to the membership."""
    if membership is None or not asset_id:
        return False
    try:
        val = uuid.UUID(str(asset_id))
    except (ValueError, TypeError):
        return False
    return granted_assets_for(membership).filter(pk=val).exists()


def get_linked_work_order(sr: ServiceRequest):
    """Returns the primary or latest linked work order for a service request with assigned technician."""
    from apps.workorders.models import WorkOrder
    return (
        WorkOrder.objects.for_organization(sr.organization)
        .filter(source_request=sr)
        .select_related("assigned_to__user")
        .order_by("-created_at")
        .first()
        or WorkOrder.objects.for_organization(sr.organization)
        .filter(source_reference=sr.number)
        .select_related("assigned_to__user")
        .order_by("-created_at")
        .first()
    )


def get_portal_dashboard_metrics(membership: Membership | None) -> dict:
    """Computes real-time client KPI summary and activity for the authenticated client.

    Derived directly from PostgreSQL records, strictly scoped to membership and organization.
    """
    if membership is None:
        return {
            "total": 0,
            "open": 0,
            "in_progress": 0,
            "awaiting_confirmation": 0,
            "resolved_closed": 0,
            "avg_rating": None,
            "rating_count": 0,
            "recent_activity": [],
            "granted_assets_count": 0,
        }

    from django.db.models import Avg, Count, Q
    from apps.incidents.models import ServiceRequest, ServiceRequestHistory
    from apps.portal.models import PortalClosureConfirmation

    org = membership.organization
    base_qs = ServiceRequest.objects.for_organization(org).filter(reported_by=membership)

    aggregates = base_qs.aggregate(
        total=Count("id"),
        open=Count("id", filter=Q(status__in=["NEW", "TRIAGED", "APPROVED"])),
        in_progress=Count("id", filter=Q(status__in=["WORK_ORDER_CREATED", "IN_SERVICE", "IN_PROGRESS"])),
        awaiting_confirmation=Count("id", filter=Q(status="RESOLVED")),
        resolved_closed=Count("id", filter=Q(status__in=["CONFIRMED", "CLOSED"])),
    )

    account = get_portal_account(membership)
    rating_data = {"avg": None, "count": 0}
    if account:
        rating_data = PortalClosureConfirmation.objects.for_organization(org).filter(
            portal_account=account,
            rating__isnull=False,
        ).aggregate(
            avg=Avg("rating"),
            count=Count("id"),
        )

    recent_activity = list(
        ServiceRequestHistory.objects.for_organization(org)
        .filter(request__reported_by=membership)
        .exclude(action__in=_INTERNAL_HISTORY_ACTIONS)
        .select_related("request", "changed_by")
        .order_by("-created_at")[:6]
    )

    granted_count = granted_assets_for(membership).count()

    return {
        "total": aggregates["total"] or 0,
        "open": aggregates["open"] or 0,
        "in_progress": aggregates["in_progress"] or 0,
        "awaiting_confirmation": aggregates["awaiting_confirmation"] or 0,
        "resolved_closed": aggregates["resolved_closed"] or 0,
        "avg_rating": round(rating_data["avg"], 1) if rating_data["avg"] is not None else None,
        "rating_count": rating_data["count"] or 0,
        "recent_activity": recent_activity,
        "granted_assets_count": granted_count,
    }



def get_client_sla_indicator(service_request) -> dict | None:
    """Return client-safe SLA commitment information for a ServiceRequest.

    Strictly exposes customer-facing indicators (within SLA, response achieved,
    expected resolution commitment, delayed indicator, status badge) while
    completely withholding internal escalation rules, notification recipients,
    or internal breach logs.
    """
    if not service_request:
        return None

    tracking_obj = getattr(service_request, "sla_trackings", None)
    if tracking_obj is not None and hasattr(tracking_obj, "first"):
        tracking_obj = tracking_obj.first()
    else:
        from apps.sla.models import SLATracking
        tracking_obj = SLATracking.objects.filter(request=service_request).first()

    if not tracking_obj:
        return None

    response_achieved = (
        tracking_obj.response_state in ("MET", "MET_LATE")
        or tracking_obj.response_met_at is not None
    )
    resolution_achieved = (
        tracking_obj.resolution_state in ("MET", "MET_LATE")
        or tracking_obj.resolution_met_at is not None
    )
    is_delayed = (
        tracking_obj.is_breached
        or tracking_obj.response_state in ("BREACHED", "MET_LATE")
        or tracking_obj.resolution_state in ("BREACHED", "MET_LATE")
    )
    is_paused = tracking_obj.is_paused

    if resolution_achieved:
        badge_class = "success" if not is_delayed else "warning"
        status_label = "Resolved within SLA" if not is_delayed else "Resolved (Delayed)"
        status_code = "COMPLETED"
    elif is_paused:
        badge_class = "secondary"
        status_label = "SLA Paused (Pending Information)"
        status_code = "PAUSED"
    elif is_delayed:
        badge_class = "danger"
        status_label = "Service Delayed"
        status_code = "DELAYED"
    elif tracking_obj.is_at_risk:
        badge_class = "warning"
        status_label = "Target Priority Attention"
        status_code = "AT_RISK"
    elif response_achieved:
        badge_class = "info"
        status_label = "Response Completed - In Progress"
        status_code = "RESPONSE_MET"
    else:
        badge_class = "primary"
        status_label = "Within SLA Commitment"
        status_code = "ON_TRACK"

    return {
        "has_sla": True,
        "is_within_sla": not is_delayed,
        "response_achieved": response_achieved,
        "resolution_achieved": resolution_achieved,
        "is_delayed": is_delayed,
        "is_paused": is_paused,
        "status": status_code,
        "status_label": status_label,
        "badge_class": badge_class,
        "response_due_at": tracking_obj.response_due_at.isoformat() if tracking_obj.response_due_at else None,
        "response_met_at": tracking_obj.response_met_at.isoformat() if tracking_obj.response_met_at else None,
        "expected_resolution_at": tracking_obj.resolution_due_at.isoformat() if tracking_obj.resolution_due_at else None,
        "resolution_met_at": tracking_obj.resolution_met_at.isoformat() if tracking_obj.resolution_met_at else None,
        "expected_resolution_datetime": tracking_obj.resolution_due_at,
        "response_due_datetime": tracking_obj.response_due_at,
    }
