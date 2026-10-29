import pytest
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

from apps.sla.models import SLAProfile, SLATarget, SLATracking, SLAPauseEvent
from apps.sla import services as sla_services
from apps.sla.forms import ProfileForm
from apps.workorders.models import WorkOrder
from apps.workorders import services as wo_services
from apps.incidents.models import ServiceRequest
from apps.incidents import services as incident_services

pytestmark = pytest.mark.django_db


def test_sla_profile_default_pause_states(org_a, owner_a):
    """Creating SLA profile without pause_states should default to WORK_ORDER:ON_HOLD."""
    # 1. ProfileForm initial value
    form = ProfileForm()
    assert form.fields["pause_states"].initial == ["WORK_ORDER:ON_HOLD"]

    # 2. Service creation defaults for WORK_ORDER
    wo_profile = sla_services.create_profile(
        org_a,
        name="Default WO Policy",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        actor=owner_a,
    )
    assert wo_profile.pause_states == ["WORK_ORDER:ON_HOLD"]

    # 3. Service creation defaults for REQUEST
    req_profile = sla_services.create_profile(
        org_a,
        name="Default Req Policy",
        applies_to=SLAProfile.AppliesTo.REQUEST,
        actor=owner_a,
    )
    assert req_profile.pause_states == ["WORK_ORDER:ON_HOLD"]


def test_standalone_work_order_hold_pauses_and_resumes_sla(org_a, site_a1, owner_a, tech_a, make_asset, make_member):
    """Holding a standalone work order pauses SLA tracking; resuming shifts due times."""
    owner_mem = owner_a.memberships.get(organization=org_a)
    tech_mem = tech_a.memberships.get(organization=org_a)
    planner = make_member(org_a, "planner.d8.sa@alpha.test", "maintenance_planner")
    asset = make_asset(org_a, site_a1, "AST-D8-1")

    profile = sla_services.create_profile(
        org_a,
        name="Plant WO SLA",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        actor=owner_a,
    )
    sla_services.set_target(profile, priority="HIGH", response_minutes=30, resolution_minutes=120, warning_percent=80, actor=owner_a)

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        title="Emergency Boiler Valve Inspection",
        priority="HIGH",
        actor=owner_a,
        work_type="CORRECTIVE",
    )

    tracking = SLATracking.objects.filter(work_order=wo).first()
    assert tracking is not None, "SLATracking must be created for standalone work order"
    assert tracking.status == SLATracking.Status.ACTIVE

    # Move DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN_PROGRESS
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type="CORRECTIVE",
        priority="HIGH",
    )
    wo = wo_services.assign_work_order(wo, assignee_id=tech_mem.pk, membership=planner, actor=planner.user)
    wo = wo_services.dispatch_work_order(wo, membership=planner, actor=planner.user)
    wo = wo_services.start_work_order(wo, membership=tech_mem, actor=tech_a)

    tracking.refresh_from_db()
    assert tracking.response_met_at is not None

    orig_resolution_due = tracking.resolution_due_at

    # Place on Hold
    wo_services.hold_work_order(wo, membership=tech_mem, actor=tech_a, reason="Waiting for spare parts delivery")

    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.PAUSED
    assert tracking.paused_at is not None

    pause_event = SLAPauseEvent.objects.filter(tracking=tracking).last()
    assert pause_event is not None
    assert pause_event.ended_at is None
    assert "Waiting for spare parts" in pause_event.reason

    # Resume Work Order
    wo_services.resume_work_order(wo, membership=tech_mem, actor=tech_a)

    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.ACTIVE
    assert tracking.paused_at is None
    pause_event.refresh_from_db()
    assert pause_event.ended_at is not None
    assert tracking.paused_seconds >= 0
    assert tracking.resolution_due_at >= orig_resolution_due


def test_incident_linked_work_order_hold_pauses_request_sla(org_a, site_a1, owner_a, tech_a, make_asset, make_member):
    """Holding a work order linked to an incident request pauses the request's SLA tracking."""
    owner_mem = owner_a.memberships.get(organization=org_a)
    tech_mem = tech_a.memberships.get(organization=org_a)
    ops_mgr = make_member(org_a, "ops.mgr.d8@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.d8@alpha.test", "maintenance_planner")
    asset = make_asset(org_a, site_a1, "AST-D8-2")

    profile = sla_services.create_profile(
        org_a,
        name="Plant Incident SLA",
        applies_to=SLAProfile.AppliesTo.REQUEST,
        actor=owner_a,
    )
    sla_services.set_target(profile, priority="CRITICAL", response_minutes=15, resolution_minutes=60, warning_percent=80, actor=owner_a)

    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=owner_mem,
        title="Critical Generator Failure",
        severity="CRITICAL",
        kind="INCIDENT",
        actor=owner_a,
    )
    sr = incident_services.transition(sr, action="triage", actor=ops_mgr.user)
    sr = incident_services.transition(sr, action="approve", actor=ops_mgr.user)
    assert sr.status == "APPROVED"

    tracking = SLATracking.objects.filter(request=sr).first()
    assert tracking is not None, "SLATracking must be created for incident request"
    assert tracking.status == SLATracking.Status.ACTIVE

    # Create linked work order for the request
    wo = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )

    # Move DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN_PROGRESS
    start = timezone.now() + timedelta(days=2)
    end = start + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type="CORRECTIVE",
        priority="CRITICAL",
    )
    wo = wo_services.assign_work_order(wo, assignee_id=tech_mem.pk, membership=planner, actor=planner.user)
    wo = wo_services.dispatch_work_order(wo, membership=planner, actor=planner.user)
    wo = wo_services.start_work_order(wo, membership=tech_mem, actor=tech_a)

    # Place linked work order on hold
    wo_services.hold_work_order(wo, membership=tech_mem, actor=tech_a, reason="Awaiting specialized technician")

    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.PAUSED
    assert tracking.paused_at is not None

    pause_event = SLAPauseEvent.objects.filter(tracking=tracking).last()
    assert pause_event is not None
    assert pause_event.ended_at is None
    assert "Awaiting specialized technician" in pause_event.reason

    # Resume linked work order
    wo_services.resume_work_order(wo, membership=tech_mem, actor=tech_a)

    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.ACTIVE
    assert tracking.paused_at is None
    pause_event.refresh_from_db()
    assert pause_event.ended_at is not None



def test_explicit_opt_out_does_not_pause_timer_on_hold(org_a, site_a1, owner_a, tech_a, make_asset, make_member):
    """When a profile explicitly configures pause_states=[], holding a work order does not pause the SLA."""
    tech_mem = tech_a.memberships.get(organization=org_a)
    planner = make_member(org_a, "planner.d8.optout@alpha.test", "maintenance_planner")
    asset = make_asset(org_a, site_a1, "AST-D8-OPTOUT")

    profile = sla_services.create_profile(
        org_a,
        name="No Pause SLA Policy",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        pause_states=[],  # explicit opt-out
        actor=owner_a,
    )
    assert profile.pause_states == []
    sla_services.set_target(profile, priority="HIGH", response_minutes=30, resolution_minutes=120, warning_percent=80, actor=owner_a)

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        title="Continuously Monitored Work",
        priority="HIGH",
        actor=owner_a,
        work_type="CORRECTIVE",
    )
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type="CORRECTIVE",
        priority="HIGH",
    )
    wo = wo_services.assign_work_order(wo, assignee_id=tech_mem.pk, membership=planner, actor=planner.user)
    wo = wo_services.dispatch_work_order(wo, membership=planner, actor=planner.user)
    wo = wo_services.start_work_order(wo, membership=tech_mem, actor=tech_a)

    tracking = SLATracking.objects.get(work_order=wo)
    assert tracking.status == SLATracking.Status.ACTIVE

    # Place on Hold
    wo_services.hold_work_order(wo, membership=tech_mem, actor=tech_a, reason="Waiting for tools")

    tracking.refresh_from_db()
    # SLA status must remain ACTIVE because hold state is not configured to pause
    assert tracking.status == SLATracking.Status.ACTIVE
    assert tracking.paused_at is None
    assert SLAPauseEvent.objects.filter(tracking=tracking).count() == 0


def test_invalid_pause_state_token_rejected_on_create_profile(org_a, owner_a):
    """Unknown pause state tokens must be rejected with code invalid_pause_state."""
    from apps.core.exceptions import ValidationFailed

    with pytest.raises(ValidationFailed) as exc_info:
        sla_services.create_profile(
            org_a,
            name="Bad Token Profile",
            applies_to=SLAProfile.AppliesTo.WORK_ORDER,
            pause_states=["WORK_ORDER:INVALID_STATE"],
            actor=owner_a,
        )
    assert exc_info.value.code == "invalid_pause_state"


def test_pause_reason_required_when_holding_work_order(org_a, site_a1, owner_a, tech_a, make_asset, make_member):
    """Putting a work order on hold without an adequate reason is rejected."""
    from apps.core.exceptions import ValidationFailed

    tech_mem = tech_a.memberships.get(organization=org_a)
    planner = make_member(org_a, "planner.d8.reason@alpha.test", "maintenance_planner")
    asset = make_asset(org_a, site_a1, "AST-D8-REASON")

    profile = sla_services.create_profile(
        org_a,
        name="Reason Enforced SLA",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        actor=owner_a,
    )
    sla_services.set_target(profile, priority="HIGH", response_minutes=30, resolution_minutes=120, warning_percent=80, actor=owner_a)

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        title="Check compressor",
        priority="HIGH",
        actor=owner_a,
        work_type="CORRECTIVE",
    )
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type="CORRECTIVE",
        priority="HIGH",
    )
    wo = wo_services.assign_work_order(wo, assignee_id=tech_mem.pk, membership=planner, actor=planner.user)
    wo = wo_services.dispatch_work_order(wo, membership=planner, actor=planner.user)
    wo = wo_services.start_work_order(wo, membership=tech_mem, actor=tech_a)

    # Empty reason
    with pytest.raises(ValidationFailed):
        wo_services.hold_work_order(wo, membership=tech_mem, actor=tech_a, reason="")

    # Short reason (< 3 chars)
    with pytest.raises(ValidationFailed):
        wo_services.hold_work_order(wo, membership=tech_mem, actor=tech_a, reason="no")

    tracking = SLATracking.objects.get(work_order=wo)
    assert tracking.status == SLATracking.Status.ACTIVE


def test_priority_update_retargets_work_order_sla(org_a, site_a1, owner_a, make_asset, make_member):
    """Updating work order priority retargets open SLA due dates."""
    planner = make_member(org_a, "planner.d8.retarget@alpha.test", "maintenance_planner")
    asset = make_asset(org_a, site_a1, "AST-D8-RETARGET")

    profile = sla_services.create_profile(
        org_a,
        name="Retargeting SLA",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        actor=owner_a,
    )
    sla_services.set_target(profile, priority="LOW", response_minutes=120, resolution_minutes=480, warning_percent=80, actor=owner_a)
    sla_services.set_target(profile, priority="HIGH", response_minutes=30, resolution_minutes=120, warning_percent=80, actor=owner_a)

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        title="General lubrication",
        priority="LOW",
        actor=owner_a,
        work_type="CORRECTIVE",
    )

    tracking = SLATracking.objects.get(work_order=wo)
    assert tracking.priority == "LOW"
    assert tracking.response_minutes == 120
    assert tracking.resolution_minutes == 480

    # Escalate priority to HIGH while in draft
    wo = wo_services.update_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        priority="HIGH",
    )

    tracking.refresh_from_db()
    assert tracking.priority == "HIGH"
    assert tracking.response_minutes == 30
    assert tracking.resolution_minutes == 120
