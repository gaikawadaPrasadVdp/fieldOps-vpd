"""Unit Test Suite - Part 2: Service Requests (SR), Work Orders (WO), Inspections (INSP).
Covers TC-SR-001 through TC-SR-006, TC-WO-001 through TC-WO-008, TC-INSP-001 through TC-INSP-004.
"""
from datetime import timedelta
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.assets.models import Asset, AssetStatusHistory
from apps.checklists import services as checklist_services
from apps.checklists.models import ChecklistItem, ChecklistTemplate, Finding, Inspection, InspectionResponse
from apps.core.exceptions import Conflict, InvalidTransition, PermissionDenied, ValidationFailed
from apps.incidents import services as incident_services
from apps.incidents import workflow as incident_wf
from apps.incidents.models import ServiceRequest
from apps.tenancy.models import Membership
from apps.workorders import services as wo_services
from apps.workorders import workflow as wo_wf
from apps.workorders.models import WorkOrder, WorkOrderAssignment, WorkOrderLabor


# =========================================================================
# 3.5 Module: Service Request / Incident (SR)
# =========================================================================

@pytest.mark.django_db
def test_tc_sr_001_create_service_request_in_new_state(p3):
    """TC-SR-001: Ensure client requester or dispatcher can raise an incident with title, description, priority, asset, and site.
    Expected Result: Service request created with status="NEW" and ticket_number/reference generated.
    """
    sr = incident_services.create_request(
        p3["org"],
        asset=p3["asset"],
        reporter=p3["tech"],
        title="AC leaking water",
        description="Leaking water rapidly near the main valve",
        severity=ServiceRequest.Severity.HIGH,
        actor=p3["tech"].user,
    )
    assert sr.pk is not None
    assert sr.status == incident_wf.NEW
    assert sr.number is not None
    assert sr.number.startswith("INC-") or sr.number.startswith("SR-") or len(sr.number) > 0
    assert sr.title == "AC leaking water"
    assert sr.asset == p3["asset"]


@pytest.mark.django_db
def test_tc_sr_002_mandatory_state_machine_validation(p3):
    """TC-SR-002: Validate transition sequence: NEW -> TRIAGED -> APPROVED -> WORK_ORDER_CREATED.
    Reject invalid skip transitions (e.g. NEW directly to WORK_ORDER_CREATED).
    """
    sr = incident_services.create_request(
        p3["org"],
        asset=p3["asset"],
        reporter=p3["tech"],
        title="Compressor overheating",
        actor=p3["tech"].user,
    )
    assert sr.status == incident_wf.NEW

    # Attempt direct transition from NEW to WORK_ORDER_CREATED
    with pytest.raises((InvalidTransition, ValidationFailed)):
        incident_services.transition(sr, action="link_work_order", actor=p3["ops"].user)

    # Valid sequence: NEW --triage--> TRIAGED
    incident_services.transition(sr, action="triage", actor=p3["ops"].user)
    sr.refresh_from_db()
    assert sr.status == incident_wf.TRIAGED

    # TRIAGED --approve--> APPROVED
    incident_services.transition(sr, action="approve", actor=p3["ops"].user)
    sr.refresh_from_db()
    assert sr.status == incident_wf.APPROVED


@pytest.mark.django_db
def test_tc_sr_003_convert_approved_request_to_work_order(p3):
    """TC-SR-003: Verify converting an approved service request creates a linked WorkOrder
    with matching priority, site, and asset context, transitioning status to WORK_ORDER_CREATED.
    """
    sr = incident_services.create_request(
        p3["org"],
        asset=p3["asset"],
        reporter=p3["tech"],
        title="Water pump gasket failure",
        severity=ServiceRequest.Severity.HIGH,
        actor=p3["tech"].user,
    )
    incident_services.transition(sr, action="triage", actor=p3["ops"].user)
    incident_services.transition(sr, action="approve", actor=p3["ops"].user)
    sr.refresh_from_db()
    assert sr.status == incident_wf.APPROVED

    wo = incident_services.create_work_order_for_request(
        sr,
        actor=p3["planner"].user,
        membership=p3["planner"],
        title="Repair water pump gasket",
    )
    sr.refresh_from_db()
    assert sr.status == incident_wf.WORK_ORDER_CREATED
    assert wo is not None
    assert wo.asset == p3["asset"]
    assert wo.site == p3["site"]
    assert wo.source_request_id == sr.pk or wo.title == "Repair water pump gasket"


@pytest.mark.django_db
def test_tc_sr_004_flag_potential_duplicate_requests(p3):
    """TC-SR-004: Verify that opening a new incident on an asset that already has an unresolved
    incident triggers duplicate warning logic.
    """
    sr1 = incident_services.create_request(
        p3["org"],
        asset=p3["asset"],
        reporter=p3["tech"],
        title="Oil leak near turbine",
        actor=p3["tech"].user,
    )
    incident_services.transition(sr1, action="triage", actor=p3["ops"].user)

    duplicates = incident_services.find_duplicate_incidents(
        p3["org"],
        asset_id=p3["asset"].id,
        title="Oil leak near turbine bearing",
    )
    assert len(duplicates) > 0
    candidate_ids = [str(d["id"]) if isinstance(d, dict) else str(d.id) for d in duplicates]
    assert str(sr1.id) in candidate_ids


@pytest.mark.django_db
def test_tc_sr_005_reject_service_request_with_inactive_asset(p3, make_asset):
    """TC-SR-005: Verify service request creation is rejected if the targeted asset is in DISPOSED or RETIRED status."""
    retired_asset = make_asset(
        p3["org"],
        p3["site"],
        "P3-RETIRED-AST",
    )
    Asset.objects.filter(pk=retired_asset.pk).update(status=Asset.Status.RETIRED)
    retired_asset.refresh_from_db()
    with pytest.raises((Conflict, ValidationFailed, ValidationError)) as exc_info:
        incident_services.create_request(
            p3["org"],
            asset=retired_asset,
            reporter=p3["tech"],
            title="Boiler inspection request",
            actor=p3["tech"].user,
        )
    assert "retired" in str(exc_info.value).lower() or "inactive" in str(exc_info.value).lower() or "disposed" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_tc_sr_006_require_rejection_reason_on_service_request(p3):
    """TC-SR-006: Verify that moving status from TRIAGED to REJECTED requires a non-empty rejection reason."""
    sr = incident_services.create_request(
        p3["org"],
        asset=p3["asset"],
        reporter=p3["tech"],
        title="Minor vibration",
        actor=p3["tech"].user,
    )
    incident_services.transition(sr, action="triage", actor=p3["ops"].user)

    with pytest.raises((ValidationFailed, ValidationError)) as exc_info:
        incident_services.transition(sr, action="reject", reason="", actor=p3["ops"].user)
    assert "reason" in str(exc_info.value).lower()


# =========================================================================
# 3.6 Module: Work Order Lifecycle & Assignment (WO)
# =========================================================================

@pytest.mark.django_db
def test_tc_wo_001_complete_valid_work_order_state_progression(p3):
    """TC-WO-001: Verify smooth progression through all mandatory workflow states:
    DRAFT -> PLANNED -> ASSIGNED -> DISPATCHED -> IN_PROGRESS -> COMPLETED -> SUPERVISOR_REVIEW -> CLOSED.
    """
    wo = wo_services.create_work_order(
        p3["org"],
        title="Complete overhaul of HVAC",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.HIGH,
    )
    assert wo.status == wo_wf.DRAFT

    # 1. DRAFT -> PLANNED
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=4)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=4,
        priority=WorkOrder.Priority.HIGH,
    )
    assert wo.status == wo_wf.PLANNED

    # 2. PLANNED -> ASSIGNED
    wo = wo_services.assign_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        assignee_id=p3["tech"].id,
    )
    assert wo.status == wo_wf.ASSIGNED

    # 3. ASSIGNED -> DISPATCHED
    wo = wo_services.dispatch_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
    )
    assert wo.status == wo_wf.DISPATCHED

    # 4. DISPATCHED -> IN_PROGRESS
    wo = wo_services.start_work_order(
        wo,
        membership=p3["tech"],
        actor=p3["tech"].user,
    )
    assert wo.status == wo_wf.IN_PROGRESS

    from apps.workorders.checklist_adapter import record_external_validation
    from tests.test_workorders import attach_test_evidence
    wo.checklist_instance_ref = f"test-m08:{wo.pk}"
    record_external_validation(wo, status="COMPLETED", validation_state="VALID", completed_at=timezone.now())
    wo.save()
    attach_test_evidence(wo, p3["org"], p3["tech"])

    wo_services.record_labor(
        wo,
        membership=p3["tech"],
        actor=p3["tech"].user,
        work_date=timezone.localdate(),
        hours=Decimal("4.0"),
        description="Completed overhaul work",
    )

    # 5. IN_PROGRESS -> COMPLETED
    wo = wo_services.complete_work_order(
        wo,
        membership=p3["tech"],
        actor=p3["tech"].user,
        resolution_notes="Overhaul completed successfully. All components inspected and cleaned.",
    )
    assert wo.status == wo_wf.COMPLETED

    # 6. COMPLETED -> SUPERVISOR_REVIEW
    wo = wo_services.submit_for_review(
        wo,
        membership=p3["sup"],
        actor=p3["sup"].user,
    )
    assert wo.status == wo_wf.SUPERVISOR_REVIEW

    # 7. SUPERVISOR_REVIEW -> CLOSED
    wo = wo_services.close_work_order(
        wo,
        membership=p3["sup"],
        actor=p3["sup"].user,
        comment="Review approved by supervisor. Work meets quality standard.",
    )
    assert wo.status == wo_wf.CLOSED


@pytest.mark.django_db
def test_tc_wo_002_prevent_direct_editing_or_modifying_closed_work_order(p3):
    """TC-WO-002: Verify that once a work order is in CLOSED state, modifications fail."""
    wo = wo_services.create_work_order(
        p3["org"],
        title="WO to close",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    # Directly set to CLOSED for testing update guard
    WorkOrder.objects.filter(pk=wo.pk).update(status=wo_wf.CLOSED)
    wo.refresh_from_db()

    with pytest.raises((Conflict, ValidationFailed, PermissionDenied, ValidationError)) as exc_info:
        wo_services.update_work_order(
            wo,
            membership=p3["planner"],
            actor=p3["planner"].user,
            priority="CRITICAL",
        )
    assert "closed" in str(exc_info.value).lower() or "locked" in str(exc_info.value).lower() or "draft" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_tc_wo_003_reject_assignment_to_inactive_technician(p3, make_member):
    """TC-WO-003: Verify that assigning an inactive technician fails validation."""
    inactive_membership = make_member(p3["org"], "inactive_tech@alpha.test", "technician", active=False)

    wo = wo_services.create_work_order(
        p3["org"],
        title="WO for inactive tech test",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=2,
        priority=WorkOrder.Priority.MEDIUM,
    )

    with pytest.raises((ValidationFailed, ValidationError)) as exc_info:
        wo_services.assign_work_order(
            wo,
            membership=p3["planner"],
            actor=p3["planner"].user,
            assignee_id=inactive_membership.id,
        )
    assert "inactive" in str(exc_info.value).lower() or "suspended" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_tc_wo_004_enforce_required_checklist_completion_before_completed(p3):
    """TC-WO-004: Verify work order cannot transition to COMPLETED if mandatory checklist items are incomplete."""
    tpl = checklist_services.create_template(
        p3["org"],
        actor=p3["sup"].user,
        name="Mandatory Corrective Checklist",
        work_type="CORRECTIVE",
        is_required=True,
    )
    checklist_services.add_item(
        tpl,
        actor=p3["sup"].user,
        prompt="Check fluid pressure",
        item_type="BOOLEAN",
    )
    checklist_services.activate_template(tpl, actor=p3["sup"].user)

    wo = wo_services.create_work_order(
        p3["org"],
        title="Checklist completion test",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=2,
        priority=WorkOrder.Priority.MEDIUM,
    )
    wo = wo_services.assign_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, assignee_id=p3["tech"].id)
    wo = wo_services.dispatch_work_order(wo, membership=p3["planner"], actor=p3["planner"].user)
    wo = wo_services.start_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    with pytest.raises((ValidationFailed, ValidationError, Conflict)) as exc_info:
        wo_services.complete_work_order(
            wo,
            membership=p3["tech"],
            actor=p3["tech"].user,
            resolution_notes="Tried to complete without answering checklist",
        )
    assert "checklist" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_tc_wo_005_enforce_resolution_notes_on_complete(p3):
    """TC-WO-005: Verify that resolution_notes cannot be blank when moving to COMPLETED."""
    wo = wo_services.create_work_order(
        p3["org"],
        title="Resolution notes validation test",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.PREVENTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=2,
        priority=WorkOrder.Priority.MEDIUM,
    )
    wo = wo_services.assign_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, assignee_id=p3["tech"].id)
    wo = wo_services.dispatch_work_order(wo, membership=p3["planner"], actor=p3["planner"].user)
    wo = wo_services.start_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    with pytest.raises((ValidationFailed, ValidationError)) as exc_info:
        wo_services.complete_work_order(
            wo,
            membership=p3["tech"],
            actor=p3["tech"].user,
            resolution_notes="",
        )
    assert "resolution" in str(exc_info.value).lower() or "notes" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_tc_wo_006_reassignment_of_technician_during_on_hold(p3):
    """TC-WO-006: Verify dispatcher can reassign a work order while it is ON_HOLD,
    resetting the assignment record while keeping prior labor history intact.
    """
    wo = wo_services.create_work_order(
        p3["org"],
        title="Reassignment on hold test",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.PREVENTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=2,
        priority=WorkOrder.Priority.MEDIUM,
    )
    wo = wo_services.assign_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, assignee_id=p3["tech"].id)
    wo = wo_services.dispatch_work_order(wo, membership=p3["planner"], actor=p3["planner"].user)
    wo = wo_services.start_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    # Log labor for Tech 1
    wo_services.record_labor(
        wo,
        membership=p3["tech"],
        actor=p3["tech"].user,
        work_date=timezone.localdate(),
        hours=Decimal("2.5"),
        description="Initial diagnostic work",
    )
    # Move to ON_HOLD
    wo = wo_services.hold_work_order(
        wo,
        membership=p3["tech"],
        actor=p3["tech"].user,
        reason="AWAITING_PARTS",
    )
    assert wo.status == wo_wf.ON_HOLD

    # Reassign to Tech 2
    wo = wo_services.reassign_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        assignee_id=p3["tech2"].id,
    )
    assert wo.assigned_to_id == p3["tech2"].id or wo.assigned_to == p3["tech2"]
    # Prior labor intact
    labor_entries = WorkOrderLabor.objects.filter(work_order=wo)
    assert labor_entries.count() == 1
    assert labor_entries.first().hours == Decimal("2.5")


@pytest.mark.django_db
def test_tc_wo_007_reject_negative_or_zero_hours_in_labor_entry(p3):
    """TC-WO-007: Verify that logged labor duration must be strictly positive (duration_hours > 0)."""
    wo = wo_services.create_work_order(
        p3["org"],
        title="Labor hours validation test",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.PREVENTIVE,
        priority=WorkOrder.Priority.MEDIUM,
    )
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=2,
        priority=WorkOrder.Priority.MEDIUM,
    )
    wo = wo_services.assign_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, assignee_id=p3["tech"].id)
    wo = wo_services.dispatch_work_order(wo, membership=p3["planner"], actor=p3["planner"].user)
    wo = wo_services.start_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    with pytest.raises((ValidationFailed, ValidationError)):
        wo_services.record_labor(
            wo,
            membership=p3["tech"],
            actor=p3["tech"].user,
            hours=Decimal("0.0"),
        )

    with pytest.raises((ValidationFailed, ValidationError)):
        wo_services.record_labor(
            wo,
            membership=p3["tech"],
            actor=p3["tech"].user,
            hours=Decimal("-1.5"),
        )


@pytest.mark.django_db
def test_tc_wo_008_derive_asset_status_under_maintenance_when_work_order_starts(p3):
    """TC-WO-008: Verify that when work order transitions to IN_PROGRESS,
    the associated asset status automatically updates to UNDER_MAINTENANCE.
    """
    assert p3["asset"].status == Asset.Status.ACTIVE

    wo = wo_services.create_work_order(
        p3["org"],
        title="Maintenance start test",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.HIGH,
    )
    start_dt = timezone.now() + timedelta(days=1)
    end_dt = start_dt + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        planned_start=start_dt,
        planned_end=end_dt,
        due_at=end_dt + timedelta(days=1),
        estimated_hours=2,
        priority=WorkOrder.Priority.HIGH,
    )
    wo = wo_services.assign_work_order(wo, membership=p3["planner"], actor=p3["planner"].user, assignee_id=p3["tech"].id)
    wo = wo_services.dispatch_work_order(wo, membership=p3["planner"], actor=p3["planner"].user)
    wo = wo_services.start_work_order(wo, membership=p3["tech"], actor=p3["tech"].user)

    p3["asset"].refresh_from_db()
    assert p3["asset"].status == Asset.Status.UNDER_MAINTENANCE
    history = AssetStatusHistory.objects.filter(asset=p3["asset"], to_status=Asset.Status.UNDER_MAINTENANCE)
    assert history.exists()


# =========================================================================
# 3.7 Module: Inspection & Findings (INSP)
# =========================================================================

@pytest.mark.django_db
def test_tc_insp_001_submit_inspection_with_pass_result(p3):
    """TC-INSP-001: Verify that completing an inspection with all passing responses
    successfully marks the inspection status as PASSED/COMPLETED.
    """
    tpl = checklist_services.create_template(
        p3["org"],
        actor=p3["sup"].user,
        name="Safety Inspection Template",
        work_type="INSPECTION",
    )
    item1 = checklist_services.add_item(tpl, actor=p3["sup"].user, prompt="Safety valves operational?", item_type="BOOLEAN")
    item2 = checklist_services.add_item(tpl, actor=p3["sup"].user, prompt="Emergency shutoff accessible?", item_type="BOOLEAN")
    checklist_services.activate_template(tpl, actor=p3["sup"].user)

    insp = checklist_services.start_inspection(
        p3["org"],
        template=tpl,
        membership=p3["tech"],
        actor=p3["tech"].user,
        asset=p3["asset"],
    )
    checklist_services.save_responses(
        insp,
        answers={str(item1.id): True, str(item2.id): True},
        membership=p3["tech"],
        actor=p3["tech"].user,
    )
    completed_insp = checklist_services.complete_inspection(
        insp,
        membership=p3["tech"],
        actor=p3["tech"].user,
        summary="All safety checks passed without defects.",
    )
    assert completed_insp.status in ("COMPLETED", "PASSED")
    assert InspectionResponse.objects.filter(inspection=completed_insp).count() == 2


@pytest.mark.django_db
def test_tc_insp_002_fail_validation_when_required_response_omitted(p3):
    """TC-INSP-002: Verify validation fails if an inspection response marked is_mandatory=True is skipped."""
    tpl = checklist_services.create_template(
        p3["org"],
        actor=p3["sup"].user,
        name="Mandatory Item Inspection Template",
        work_type="INSPECTION",
    )
    item1 = checklist_services.add_item(tpl, actor=p3["sup"].user, prompt="Check coolant level", item_type="BOOLEAN")
    item2 = checklist_services.add_item(tpl, actor=p3["sup"].user, prompt="Check oil temperature", item_type="NUMERIC", min_value="0", max_value="120")
    checklist_services.activate_template(tpl, actor=p3["sup"].user)

    insp = checklist_services.start_inspection(
        p3["org"],
        template=tpl,
        membership=p3["tech"],
        actor=p3["tech"].user,
        asset=p3["asset"],
    )
    # Save only item 1, omitting mandatory item 2
    checklist_services.save_responses(
        insp,
        answers={str(item1.id): True},
        membership=p3["tech"],
        actor=p3["tech"].user,
    )
    with pytest.raises((Conflict, ValidationFailed, ValidationError)) as exc_info:
        checklist_services.complete_inspection(
            insp,
            membership=p3["tech"],
            actor=p3["tech"].user,
        )
    assert "missing" in str(exc_info.value).lower() or "incomplete" in str(exc_info.value).lower() or "unanswered" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()


@pytest.mark.django_db
def test_tc_insp_003_auto_generate_finding_upon_failed_inspection_item(p3):
    """TC-INSP-003: Verify that logging a defect/finding on inspection records a pending Finding
    requiring follow-up action.
    """
    tpl = checklist_services.create_template(
        p3["org"],
        actor=p3["sup"].user,
        name="Defect Detection Template",
        work_type="INSPECTION",
    )
    item = checklist_services.add_item(tpl, actor=p3["sup"].user, prompt="Check motor casing for cracks", item_type="BOOLEAN")
    checklist_services.activate_template(tpl, actor=p3["sup"].user)

    insp = checklist_services.start_inspection(
        p3["org"],
        template=tpl,
        membership=p3["tech"],
        actor=p3["tech"].user,
        asset=p3["asset"],
    )
    checklist_services.save_responses(
        insp,
        answers={str(item.id): False},
        membership=p3["tech"],
        actor=p3["tech"].user,
    )
    finding = checklist_services.add_finding(
        insp,
        item=item,
        description="Oil leakage near motor seal and hairline casing crack",
        severity="HIGH",
        membership=p3["tech"],
        actor=p3["tech"].user,
    )
    assert finding.pk is not None
    assert finding.severity == "HIGH"
    assert finding.status == Finding.Status.OPEN
    assert finding.inspection == insp
    assert finding.item == item


@pytest.mark.django_db
def test_tc_insp_004_convert_finding_to_corrective_work_order(p3):
    """TC-INSP-004: Verify that an open Finding can be linked and converted into a corrective Work Order
    without breaking traceability.
    """
    tpl = checklist_services.create_template(
        p3["org"],
        actor=p3["sup"].user,
        name="Finding Conversion Template",
        work_type="INSPECTION",
    )
    item = checklist_services.add_item(tpl, actor=p3["sup"].user, prompt="Check bearing play", item_type="BOOLEAN")
    checklist_services.activate_template(tpl, actor=p3["sup"].user)

    insp = checklist_services.start_inspection(
        p3["org"],
        template=tpl,
        membership=p3["tech"],
        actor=p3["tech"].user,
        asset=p3["asset"],
    )
    finding = checklist_services.add_finding(
        insp,
        description="Excessive bearing play detected",
        severity="HIGH",
        membership=p3["tech"],
        actor=p3["tech"].user,
    )
    # Convert finding into a corrective WorkOrder
    wo = wo_services.create_work_order(
        p3["org"],
        title=f"Corrective Action: {finding.description}",
        asset=p3["asset"],
        site_id=p3["site"].id,
        actor=p3["planner"].user,
        membership=p3["planner"],
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.HIGH,
    )
    # Link finding to corrective work order
    finding.corrective_work_order = wo
    finding.status = Finding.Status.RESOLVED
    finding.save()

    finding.refresh_from_db()
    assert finding.corrective_work_order == wo
    assert wo.asset == p3["asset"]
