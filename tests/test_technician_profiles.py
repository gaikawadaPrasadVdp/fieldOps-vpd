import pytest
from datetime import timedelta
from django.utils import timezone
from apps.core.exceptions import Conflict, ValidationFailed
from apps.workorders.models import TechnicianProfile, WorkOrder
from apps.workorders import services as wo_services
from apps.sites.models import Shift

@pytest.mark.django_db
def test_technician_profile_creation_and_relations(org_a, make_member, site_a1):
    tech = make_member(org_a, "tech-profile-test@alpha.test", "technician")
    profile = TechnicianProfile.objects.create(
        organization=org_a,
        membership=tech,
        skills=["HVAC", "Electrical"],
        certifications=["EPA-608", "OSHA-10"],
        daily_capacity_hours=8.0,
        is_dispatchable=True,
        notes="Senior Lead Technician"
    )
    assert profile.pk is not None
    assert profile.membership == tech
    assert profile.organization == org_a
    assert profile.is_dispatchable is True
    assert "HVAC" in profile.skills

@pytest.mark.django_db
def test_undispatchable_technician_assignment_blocked(org_a, site_a1, make_member, make_asset):
    planner = make_member(org_a, "planner-techprof@alpha.test", "maintenance_planner")
    tech = make_member(org_a, "tech-undispatchable@alpha.test", "technician")
    asset = make_asset(org_a, site_a1, "AST-TECH-01")
    
    # Create profile marked not dispatchable
    profile = TechnicianProfile.objects.create(
        organization=org_a,
        membership=tech,
        skills=["HVAC"],
        is_dispatchable=False,
    )

    start = timezone.now() + timedelta(days=2)
    end = start + timedelta(hours=2)

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        title="Emergency Valve Repair",
        asset=asset,
        membership=planner,
        actor=planner.user,
        source_type=WorkOrder.SourceType.MANUAL,
    )
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.HIGH,
    )

    with pytest.raises((Conflict, ValidationFailed)) as exc:
        wo_services.assign_work_order(
            wo,
            membership=planner,
            actor=planner.user,
            assignee_id=tech.pk,
            scheduled_start=start,
            scheduled_end=end,
        )
    assert "not currently available for dispatch" in str(exc.value)

@pytest.mark.django_db
def test_dispatchable_technician_assignment_succeeds(org_a, site_a1, make_member, make_asset):
    planner = make_member(org_a, "planner-techprof2@alpha.test", "maintenance_planner")
    tech = make_member(org_a, "tech-dispatchable@alpha.test", "technician")
    asset = make_asset(org_a, site_a1, "AST-TECH-02")
    
    TechnicianProfile.objects.create(
        organization=org_a,
        membership=tech,
        skills=["Electrical"],
        is_dispatchable=True,
    )

    start = timezone.now() + timedelta(days=3)
    end = start + timedelta(hours=2)

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        title="Routine Motor Inspection",
        asset=asset,
        membership=planner,
        actor=planner.user,
        source_type=WorkOrder.SourceType.MANUAL,
    )
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type=WorkOrder.WorkType.PREVENTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )

    assigned = wo_services.assign_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        assignee_id=tech.pk,
        scheduled_start=start,
        scheduled_end=end,
    )
    assert assigned.status == WorkOrder.Status.ASSIGNED
    assert assigned.assigned_to == tech
