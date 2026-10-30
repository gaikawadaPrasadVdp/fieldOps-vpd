"""M04 read side: everything starts from the caller's organization and is restricted to the sites where the caller
holds ``maintenance.view`` (the plan's site = its asset's site). The PM state of a cycle is DERIVED from the M06
work order, never stored twice."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from django.db.models import Q
from django.utils import timezone

from apps.rbac import services as rbac
from apps.sites.selectors import scoped_get

from . import services
from .models import MaintenanceCycle, MaintenancePlan, MaintenanceSchedule

CYCLE_STATES = {  # work-order status -> PM lifecycle state (HPE: GENERATED -> ASSIGNED -> COMPLETED -> VERIFIED)
    "DRAFT": "GENERATED", "PLANNED": "GENERATED", "ASSIGNED": "ASSIGNED", "DISPATCHED": "ASSIGNED",
    "IN_PROGRESS": "ASSIGNED", "ON_HOLD": "ASSIGNED", "COMPLETED": "COMPLETED", "SUPERVISOR_REVIEW": "COMPLETED",
    "CLOSED": "VERIFIED", "CANCELLED": "CANCELLED",
}


def cycle_state(cycle: MaintenanceCycle) -> str:
    return CYCLE_STATES.get(cycle.work_order.status, "GENERATED") if cycle.work_order_id else "GENERATED"


def _uuid_or_none(value):
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def _parse_date(val):
    if not val:
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return date.fromisoformat(str(val).strip())
    except ValueError:
        return None


def plans_for(membership, org):
    scope = rbac.site_scope(membership, "maintenance.view")
    return scope.filter(MaintenancePlan.objects.for_organization(org).select_related("asset", "site"), "site_id")


def get_plan(membership, org, pk) -> MaintenancePlan:
    return scoped_get(plans_for(membership, org), pk, "Maintenance plan")


def filter_plans(qs, params):
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(asset__asset_tag__icontains=q) | Q(asset__name__icontains=q))
    for param, field in (("site", "site_id"), ("asset", "asset_id")):
        value = (params.get(param) or "").strip()
        if value:
            parsed = _uuid_or_none(value)
            qs = qs.filter(**{field: parsed}) if parsed else qs.none()
    active = (params.get("active") or "").strip()
    if active in ("1", "true"):
        qs = qs.filter(is_active=True)
    elif active in ("0", "false"):
        qs = qs.filter(is_active=False)
    ordering = (params.get("ordering") or "").strip()
    ordering_map = {
        "-created_at": "-created_at",
        "created_at": "created_at",
        "name": "name",
        "-name": "-name",
    }
    return qs.order_by(ordering_map.get(ordering, "-created_at"))


def schedules_for(membership, org):
    scope = rbac.site_scope(membership, "maintenance.view")
    qs = MaintenanceSchedule.objects.for_organization(org).select_related("plan__asset", "plan__site", "meter")
    return scope.filter(qs, "plan__site_id")


def get_schedule(membership, org, pk) -> MaintenanceSchedule:
    return scoped_get(schedules_for(membership, org), pk, "Maintenance schedule")


def cycles_for(membership, org):
    scope = rbac.site_scope(membership, "maintenance.view")
    qs = MaintenanceCycle.objects.for_organization(org).select_related(
        "schedule__plan__asset", "schedule__plan__site", "schedule__meter", "work_order")
    return scope.filter(qs, "schedule__plan__site_id")


def filter_cycles(qs, params):
    for param, field in (("plan", "schedule__plan_id"), ("schedule", "schedule_id"), ("asset", "schedule__plan__asset_id")):
        value = (params.get(param) or "").strip()
        if value:
            parsed = _uuid_or_none(value)
            qs = qs.filter(**{field: parsed}) if parsed else qs.none()
    return qs.order_by("-created_at")


def schedule_state(sch: MaintenanceSchedule, now: datetime | None = None) -> str:
    """DISABLED / DUE (a due occurrence exists, incl. overdue) / SCHEDULED (waiting for the next occurrence)."""
    if services.blocked_reason(sch):
        return "DISABLED"
    return "DUE" if services.evaluate(sch, now) is not None else "SCHEDULED"


def describe_schedule_rows(schedules, now: datetime | None = None) -> list[dict]:
    rows = []
    for sch in schedules:
        rows.append({"schedule": sch, "state": schedule_state(sch, now), "blocked": services.blocked_reason(sch)})
    return rows


def pm_compliance_ratio(
    membership,
    org,
    *,
    site_id=None,
    plan_id=None,
    start_date=None,
    end_date=None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Calculates PM compliance ratio (scheduled vs on-time vs overdue vs skipped).

    - scheduled: total occurrences scheduled/generated plus skipped historical ones
    - on_time: completed on or before target due date
    - overdue: completed after due date, or open past due date
    - skipped: collapsed/missed occurrences (D-043/D-045)
    - compliance_ratio: on_time / (on_time + overdue + skipped) * 100
    """
    if now is None:
        now = timezone.now()
    today = now.date() if isinstance(now, datetime) else now

    qs = cycles_for(membership, org).select_related("work_order", "schedule__plan__site")
    if site_id:
        parsed_site = _uuid_or_none(site_id)
        qs = qs.filter(schedule__plan__site_id=parsed_site) if parsed_site else qs.none()
    if plan_id:
        parsed_plan = _uuid_or_none(plan_id)
        qs = qs.filter(schedule__plan_id=parsed_plan) if parsed_plan else qs.none()

    sd = _parse_date(start_date)
    if sd:
        qs = qs.filter(Q(due_date__gte=sd) | Q(due_date__isnull=True, created_at__date__gte=sd))
    ed = _parse_date(end_date)
    if ed:
        qs = qs.filter(Q(due_date__lte=ed) | Q(due_date__isnull=True, created_at__date__lte=ed))

    scheduled = 0
    on_time = 0
    overdue = 0
    skipped = 0

    for c in qs:
        c_skipped = c.skipped or 0
        skipped += c_skipped
        scheduled += (1 + c_skipped)

        wo = c.work_order
        target_due = c.due_date or (wo.due_at.date() if wo and wo.due_at else c.created_at.date())

        if wo:
            if wo.status in ("COMPLETED", "CLOSED", "SUPERVISOR_REVIEW"):
                effective_end = (wo.completed_at or wo.closed_at or wo.updated_at).date()
                if effective_end <= target_due:
                    on_time += 1
                else:
                    overdue += 1
            elif wo.status == "CANCELLED":
                overdue += 1
            else:
                if today > target_due:
                    overdue += 1
        else:
            if today > target_due:
                overdue += 1

    denominator = on_time + overdue + skipped
    rate = round((on_time / denominator) * 100.0, 1) if denominator > 0 else 100.0
    pending = max(0, scheduled - (on_time + overdue + skipped))

    return {
        "scheduled": scheduled,
        "on_time": on_time,
        "overdue": overdue,
        "skipped": skipped,
        "pending": pending,
        "compliance_ratio": rate,
        "value": f"{rate:.1f}%",
    }
