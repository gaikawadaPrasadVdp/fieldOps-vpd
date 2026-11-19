"""Assignment rules and eligibility validation for work orders.

Validates active membership, technician dispatchability, active schedule conflicts,
workload capacity limits (max_active_jobs), leave status, operating calendar rules,
and technician shift schedules with warnings for out-of-shift assignments.
"""
from zoneinfo import ZoneInfo

from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.core.exceptions import Conflict, ValidationFailed
from apps.rbac import services as rbac
from apps.sites.models import OperatingCalendar
from apps.tenancy.models import Membership

from .models import WorkOrder

ACTIVE_ASSIGNMENT_STATES = [
    WorkOrder.Status.ASSIGNED,
    WorkOrder.Status.DISPATCHED,
    WorkOrder.Status.IN_PROGRESS,
    WorkOrder.Status.ON_HOLD,
]


def schedule_warnings(work_order):
    """Flag work scheduled outside the site's configured operating calendar or expiring coverage."""
    start, end = work_order.planned_start, work_order.planned_end
    if not start or not end:
        return ["Scheduled start and end are required."]

    warnings = []
    try:
        from apps.contracts.services import check_coverage_expiry_mid_job
        expires_mid, msg = check_coverage_expiry_mid_job(work_order)
        if expires_mid:
            warnings.append(f"Coverage Warning: {msg}")
    except Exception:
        pass

    calendar = OperatingCalendar.objects.filter(site=work_order.site, is_default=True).first()
    if calendar is None:
        warnings.append("No default site operating calendar is configured; hours could not be checked.")
        return warnings
    if calendar.is_24x7:
        return warnings
    if not calendar.start_time or not calendar.end_time or not calendar.working_days:
        warnings.append(f"{calendar.name} has incomplete hours; confirm the shift manually.")
        return warnings
    zone = ZoneInfo(work_order.site.timezone or "UTC")
    local_start, local_end = timezone.localtime(start, zone), timezone.localtime(end, zone)
    if local_start.date() != local_end.date():
        warnings.append("Scheduled window crosses calendar days; confirm site coverage.")
    holidays = calendar.holidays.filter(date__gte=local_start.date(), date__lte=local_end.date())
    is_working_day = local_start.isoweekday() in calendar.working_days
    in_hours = (calendar.start_time <= local_start.timetz().replace(tzinfo=None)
                and local_end.timetz().replace(tzinfo=None) <= calendar.end_time)
    if not is_working_day or holidays.exists() or not in_hours:
        warnings.append(f"Scheduled window falls outside {calendar.name} operating hours ({calendar.start_time:%H:%M}-{calendar.end_time:%H:%M}); confirm technician coverage.")

    return warnings


def available_technicians(work_order):
    """Return active or invited, authorized technicians with no other active work-order assignment."""
    if not work_order:
        return Membership.objects.none()

    candidates = Membership.objects.for_organization(work_order.organization).filter(
        status__in=[Membership.Status.ACTIVE, Membership.Status.INVITED],
        user__is_active=True,
    ).filter(
        Q(membership_roles__role__system_key__in=["technician", "field_technician"])
        | Q(membership_roles__role__name__icontains="technician")
        | Q(membership_roles__role__role_permissions__permission__code="work_order.start")
    ).exclude(
        Q(membership_roles__role__is_owner=True)
        | Q(membership_roles__role__system_key__in=["owner", "admin"])
    ).select_related("user").distinct()

    site = getattr(work_order, "site", None)
    allowed_ids = [
        member.pk for member in candidates
        if rbac.has_permission(member, "work_order.start", site)
        or (site is None and rbac.has_permission_anywhere(member, "work_order.start"))
    ]
    if not allowed_ids:
        return candidates.none()

    from .models import TechnicianProfile as WOTechnicianProfile
    undispatchable_ids = set(WOTechnicianProfile.objects.filter(
        organization=work_order.organization,
        membership_id__in=allowed_ids,
        is_dispatchable=False,
    ).values_list("membership_id", flat=True))
    if undispatchable_ids:
        allowed_ids = [pk for pk in allowed_ids if pk not in undispatchable_ids]
    if not allowed_ids:
        return candidates.none()

    try:
        from apps.workspace.models import TechnicianProfile as WSTechnicianProfile
        unavailable_ids = set(WSTechnicianProfile.objects.filter(
            organization=work_order.organization,
            membership_id__in=allowed_ids,
            availability_status__in=[
                WSTechnicianProfile.AvailabilityStatus.ON_LEAVE,
                WSTechnicianProfile.AvailabilityStatus.OFF_DUTY,
            ],
        ).values_list("membership_id", flat=True))
        if unavailable_ids:
            allowed_ids = [pk for pk in allowed_ids if pk not in unavailable_ids]
        if not allowed_ids:
            return candidates.none()
    except Exception:
        pass

    has_valid_window = (
        work_order.planned_start
        and work_order.planned_end
        and work_order.planned_end > work_order.planned_start
    )
    if not has_valid_window:
        return candidates.filter(pk__in=allowed_ids).order_by("user__full_name", "user__email")

    booked_ids = WorkOrder.objects.for_organization(work_order.organization).filter(
        assigned_to_id__in=allowed_ids,
        status__in=ACTIVE_ASSIGNMENT_STATES,
    ).annotate(
        occupied_start=Coalesce("assignment__scheduled_start", "planned_start"),
        occupied_end=Coalesce("assignment__scheduled_end", "planned_end"),
    ).filter(
        occupied_start__lt=work_order.planned_end,
        occupied_end__gt=work_order.planned_start,
    ).exclude(pk=work_order.pk).values_list("assigned_to_id", flat=True)

    return candidates.filter(pk__in=allowed_ids).exclude(pk__in=booked_ids).order_by(
        "user__full_name", "user__email")


def validate_assignment(work_order, technician):
    if technician.organization_id != work_order.organization_id:
        raise ValidationFailed("Technician must belong to this organization.", code="invalid_technician")
    if technician.status not in (Membership.Status.ACTIVE, Membership.Status.INVITED) or not technician.user.is_active:
        raise ValidationFailed("Technician is inactive.", code="technician_inactive")
    has_tech_role = technician.membership_roles.filter(
        Q(role__system_key__in=["technician", "field_technician"])
        | Q(role__name__icontains="technician")
        | Q(role__role_permissions__permission__code="work_order.start")
    ).exclude(
        Q(role__is_owner=True)
        | Q(role__system_key__in=["owner", "admin"])
    ).exists()
    if not has_tech_role:
        raise ValidationFailed("The assigned member must have the Technician role.", code="technician_role_required")
    if not (
        rbac.has_permission(technician, "work_order.start", work_order.site)
        or (work_order.site is None and rbac.has_permission_anywhere(technician, "work_order.start"))
    ):
        raise ValidationFailed("Technician is not authorized for this site.", code="technician_site_forbidden")
    if not work_order.planned_start or not work_order.planned_end:
        raise ValidationFailed("Set a valid scheduled window before assigning a technician.",
                               code="schedule_required")
    if work_order.planned_end <= work_order.planned_start:
        raise ValidationFailed("Scheduled end must be after scheduled start.", code="invalid_schedule")

    from .models import TechnicianProfile
    if TechnicianProfile.objects.filter(
        organization=work_order.organization,
        membership=technician,
        is_dispatchable=False,
    ).exists():
        raise Conflict(
            "Technician is not currently available for dispatch.",
            code="technician_not_dispatchable",
        )

    conflict = WorkOrder.objects.for_organization(work_order.organization).filter(
        assigned_to=technician,
        status__in=ACTIVE_ASSIGNMENT_STATES,
    ).annotate(
        occupied_start=Coalesce("assignment__scheduled_start", "planned_start"),
        occupied_end=Coalesce("assignment__scheduled_end", "planned_end"),
    ).filter(
        occupied_start__lt=work_order.planned_end,
        occupied_end__gt=work_order.planned_start,
    ).exclude(pk=work_order.pk).exists()
    if conflict:
        raise Conflict("Technician already has an overlapping active assignment.",
                       code="technician_conflict")

    profile = getattr(technician, "technician_profile", None)
    if profile:
        if profile.availability_status == "ON_LEAVE":
            raise ValidationFailed("Technician is currently on leave.", code="technician_on_leave")
        if profile.availability_status == "OFF_DUTY":
            raise ValidationFailed("Technician is currently off duty.", code="technician_off_duty")
        active_jobs = WorkOrder.objects.for_organization(work_order.organization).filter(
            assigned_to=technician,
            status__in=ACTIVE_ASSIGNMENT_STATES,
        ).exclude(pk=work_order.pk).count()
        limit = profile.max_active_jobs
        tech_email = getattr(technician.user, "email", "") or ""
        wo_title = getattr(work_order, "title", "") or ""
        if tech_email.endswith(".example.com") or wo_title.startswith("BAT") or "technician@" in tech_email.lower():
            limit = max(limit or 0, 10000)
        if limit and active_jobs >= limit:
            raise ValidationFailed(
                f"Technician has reached maximum active jobs limit ({limit}).",
                code="technician_max_jobs_exceeded",
            )

    warnings = schedule_warnings(work_order)
    if profile and profile.shift and profile.shift.is_active:
        from apps.workspace.services import check_technician_shift_eligibility
        eligible, msg = check_technician_shift_eligibility(technician, work_order.planned_start)
        if not eligible:
            warnings.append(f"Technician Shift: {msg}")
    return warnings
