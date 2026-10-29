"""Regression tests for D7: Enforce technician labor hours on completion and closure.

Defect D7:
In apps/workorders/services.py:
- _check_completion
- closure_blockers
Labor hours are never required before completion or closure, despite decision D-036:
"Closure rules: resolution notes (>= 10 chars, set at completion), at least one labor entry,
and for CORRECTIVE/INSTALLATION work at least one evidence file (checked at completion and at closure)."
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.core.exceptions import Conflict
from apps.workorders import services
from apps.workorders.checklist_adapter import record_external_validation
from apps.workorders.models import WorkOrder

pytestmark = pytest.mark.django_db


def _make_in_progress_order(org, site, planner, tech, work_type=WorkOrder.WorkType.PREVENTIVE):
    from apps.assets import services as asset_services
    from apps.assets.models import AssetCategory

    category = AssetCategory.objects.for_organization(org).filter(name="Labor Test Category").first()
    if category is None:
        category = asset_services.create_category(org, name="Labor Test Category", actor=planner.user)
    asset = asset_services.create_asset(
        org,
        site=site,
        category=category,
        actor=planner.user,
        asset_tag=f"WO-LABOR-{uuid4().hex[:8].upper()}",
        name="Labor Test Asset",
    )

    wo = services.create_work_order(
        org,
        site_id=site.pk,
        membership=planner,
        actor=planner.user,
        title="Check pump bearings",
        asset=asset,
        work_type=work_type,
        priority=WorkOrder.Priority.MEDIUM,
        source_type=WorkOrder.SourceType.MANUAL,
    )

    start = timezone.now() + timedelta(days=5)
    end = start + timedelta(hours=2)
    wo = services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type=work_type,
        priority=WorkOrder.Priority.MEDIUM,
    )
    wo = services.assign_work_order(wo, membership=planner, actor=planner.user, assignee_id=tech.pk)
    wo = services.dispatch_work_order(wo, membership=planner, actor=planner.user)
    wo = services.start_work_order(wo, membership=tech, actor=tech.user)

    # Valid checklist
    wo.checklist_instance_ref = f"test-m08:{wo.pk}"
    record_external_validation(wo, status="COMPLETED", validation_state="VALID", completed_at=timezone.now())
    wo.save(update_fields=[
        "checklist_instance_ref", "checklist_status", "checklist_validation_state",
        "checklist_completed_at", "checklist_validated_at", "updated_at"
    ])
    return wo


def test_complete_work_order_without_labor_is_refused(org_a, site_a1, make_member):
    """Attempting to complete a work order without any logged labor must be refused with Conflict."""
    planner = make_member(org_a, "planner.labor.d7@test.com", "maintenance_planner")
    tech = make_member(org_a, "tech.labor.d7@test.com", "technician")

    wo = _make_in_progress_order(org_a, site_a1, planner, tech)
    assert not wo.labor_entries.exists()

    with pytest.raises(Conflict) as exc_info:
        services.complete_work_order(
            wo,
            membership=tech,
            actor=tech.user,
            resolution_notes="Bearings greased and aligned according to spec.",
        )

    assert "labor" in str(exc_info.value).lower()
    assert getattr(exc_info.value, "code", "") == "labor_required"
    wo.refresh_from_db()
    assert wo.status == WorkOrder.Status.IN_PROGRESS


def test_closure_blockers_includes_labor_when_missing(org_a, site_a1, make_member):
    """closure_blockers must report missing labor entries as a blocker."""
    planner = make_member(org_a, "planner.blocker.d7@test.com", "maintenance_planner")
    tech = make_member(org_a, "tech.blocker.d7@test.com", "technician")

    wo = _make_in_progress_order(org_a, site_a1, planner, tech)
    wo.resolution_notes = "Bearings greased and aligned according to spec."
    wo.save(update_fields=["resolution_notes", "updated_at"])

    blockers = services.closure_blockers(wo)
    assert any("labor" in b.lower() for b in blockers), f"Expected labor blocker in {blockers}"


def test_complete_work_order_with_labor_succeeds(org_a, site_a1, make_member):
    """When labor is recorded, completion succeeds."""
    planner = make_member(org_a, "planner.ok.d7@test.com", "maintenance_planner")
    tech = make_member(org_a, "tech.ok.d7@test.com", "technician")

    wo = _make_in_progress_order(org_a, site_a1, planner, tech)

    services.record_labor(
        wo,
        membership=tech,
        actor=tech.user,
        work_date=timezone.localdate(),
        hours="1.50",
        description="Greased bearings and checked alignment",
    )
    assert wo.labor_entries.exists()

    completed_wo = services.complete_work_order(
        wo,
        membership=tech,
        actor=tech.user,
        resolution_notes="Bearings greased and aligned according to spec.",
    )
    assert completed_wo.status == WorkOrder.Status.COMPLETED


def test_close_work_order_without_labor_is_refused(org_a, site_a1, make_member):
    """Supervisor closure must be blocked if a work order has no labor recorded."""
    planner = make_member(org_a, "planner.close.d7@test.com", "maintenance_planner")
    tech = make_member(org_a, "tech.close.d7@test.com", "technician")
    supervisor = make_member(org_a, "sup.close.d7@test.com", "supervisor")

    wo = _make_in_progress_order(org_a, site_a1, planner, tech)
    services.record_labor(
        wo,
        membership=tech,
        actor=tech.user,
        work_date=timezone.localdate(),
        hours="2.00",
        description="Initial labor",
    )
    wo = services.complete_work_order(
        wo,
        membership=tech,
        actor=tech.user,
        resolution_notes="Bearings greased and aligned according to spec.",
    )
    wo = services.submit_for_review(wo, membership=tech, actor=tech.user)
    assert wo.status == WorkOrder.Status.SUPERVISOR_REVIEW

    # Simulate missing labor at review time
    wo.labor_entries.all().delete()
    assert not wo.labor_entries.exists()

    with pytest.raises(Conflict) as exc_info:
        services.close_work_order(
            wo,
            membership=supervisor,
            actor=supervisor.user,
            comment="Approved and verified.",
        )
    assert "labor" in str(exc_info.value).lower()
    assert getattr(exc_info.value, "code", "") == "closure_blocked"


@pytest.mark.parametrize("work_type", [
    WorkOrder.WorkType.PREVENTIVE,
    WorkOrder.WorkType.CORRECTIVE,
    WorkOrder.WorkType.INSPECTION,
    WorkOrder.WorkType.INSTALLATION,
])
def test_all_work_types_enforce_labor_requirement(org_a, site_a1, make_member, work_type):
    """Every work type requires at least one labor entry before completion."""
    planner = make_member(org_a, f"planner.{work_type.lower()}.d7@test.com", "maintenance_planner")
    tech = make_member(org_a, f"tech.{work_type.lower()}.d7@test.com", "technician")

    wo = _make_in_progress_order(org_a, site_a1, planner, tech, work_type=work_type)
    if work_type in (WorkOrder.WorkType.CORRECTIVE, WorkOrder.WorkType.INSTALLATION):
        # Attach required evidence so we test labor blocker independently
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.files import services as file_services
        att = file_services.attach(
            SimpleUploadedFile("evidence.txt", b"photo evidence content"),
            target=wo,
            organization=org_a,
            user=tech.user,
            description="Completion photo",
        )
        services.add_evidence(wo, membership=tech, actor=tech.user, attachment_id=att.pk)

    with pytest.raises(Conflict) as exc_info:
        services.complete_work_order(
            wo,
            membership=tech,
            actor=tech.user,
            resolution_notes="Work completed thoroughly according to SOP.",
        )
    assert getattr(exc_info.value, "code", "") == "labor_required"


def test_invalid_labor_recording_is_refused(org_a, site_a1, make_member):
    """Negative tests for labor entry bounds:
    - Zero or negative hours rejected
    - Future dates rejected
    - Labor logged outside IN_PROGRESS / ON_HOLD rejected
    """
    planner = make_member(org_a, "planner.neg.d7@test.com", "maintenance_planner")
    tech = make_member(org_a, "tech.neg.d7@test.com", "technician")

    wo = _make_in_progress_order(org_a, site_a1, planner, tech)

    # 1. Zero hours
    from apps.core.exceptions import ValidationFailed
    with pytest.raises(ValidationFailed):
        services.record_labor(
            wo,
            membership=tech,
            actor=tech.user,
            work_date=timezone.localdate(),
            hours="0.00",
            description="Did nothing",
        )

    # 2. Future date
    with pytest.raises(ValidationFailed):
        services.record_labor(
            wo,
            membership=tech,
            actor=tech.user,
            work_date=timezone.localdate() + timedelta(days=2),
            hours="2.00",
            description="Future work",
        )

    # 3. Work order in ASSIGNED status (not started yet)
    from apps.assets import services as asset_services
    draft_asset = asset_services.create_asset(
        org_a,
        site=site_a1,
        category=wo.asset.category,
        actor=planner.user,
        asset_tag=f"WO-DRAFT-{uuid4().hex[:8].upper()}",
        name="Draft Test Asset",
    )
    draft_wo = services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        membership=planner,
        actor=planner.user,
        title="Draft work order",
        source_type=WorkOrder.SourceType.MANUAL,
        asset=draft_asset,
    )
    start = timezone.now() + timedelta(days=10)
    end = start + timedelta(hours=2)
    planned_wo = services.plan_work_order(
        draft_wo,
        membership=planner,
        actor=planner.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=1),
        estimated_hours=2,
        work_type=WorkOrder.WorkType.PREVENTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    assigned_wo = services.assign_work_order(
        planned_wo,
        membership=planner,
        actor=planner.user,
        assignee_id=tech.pk,
    )
    with pytest.raises(Conflict, match="Labor can only be recorded during active work"):
        services.record_labor(
            assigned_wo,
            membership=tech,
            actor=tech.user,
            work_date=timezone.localdate(),
            hours="1.00",
            description="Premature labor",
        )
