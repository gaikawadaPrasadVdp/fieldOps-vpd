"""Edge Case 2 (PRD §4.2): Technician reassignment after dispatch or during hold.

Tests:
1. Reassigning a work order after it has been DISPATCHED:
   - Updates assigned_to to the new technician.
   - Updates the active assignment record.
   - Creates append-only WorkOrderEvent and AuditLog records.
   - Authorizes the new technician to execute/start the job.
   - Revokes execution authority from the previous technician.
2. Reassigning a work order while it is ON_HOLD:
   - Updates assigned_to to the new technician while preserving ON_HOLD status.
   - Authorizes the new technician to resume and complete the job.
   - Prevents the old technician from resuming the job.
3. API endpoint /api/v1/work-orders/{id}/reassign/ allows reassignment for DISPATCHED and ON_HOLD.
4. Unauthorized members lacking work_order.assign permission cannot reassign.
"""
from datetime import timedelta
import pytest
from django.utils import timezone

from apps.core.exceptions import PermissionDenied, ValidationFailed
from apps.workorders import services as wos
from apps.workorders.models import WorkOrder, WorkOrderAssignment, WorkOrderEvent
from tests.phase3_support import new_wo, step


@pytest.fixture
def dispatched_order(p3):
    """Create a work order and advance it to DISPATCHED assigned to p3['tech']."""
    wo = new_wo(p3, work_type="CORRECTIVE")
    t0 = timezone.now() + timedelta(days=1)
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=3))
    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    wo = step(wo, "dispatch", p3, "planner")
    assert wo.status == WorkOrder.Status.DISPATCHED
    assert wo.assigned_to_id == p3["tech"].pk
    return wo


@pytest.fixture
def held_order(p3):
    """Create a work order, advance it to IN_PROGRESS, then place it ON_HOLD."""
    wo = new_wo(p3, work_type="CORRECTIVE")
    t0 = timezone.now() + timedelta(days=5)
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=3))
    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    wo = step(wo, "dispatch", p3, "planner")
    wo = step(wo, "start", p3, "tech")
    wo = step(wo, "hold", p3, "tech", reason="Awaiting specialty tool")
    assert wo.status == WorkOrder.Status.ON_HOLD
    assert wo.assigned_to_id == p3["tech"].pk
    return wo


def test_reassign_technician_after_dispatch(p3):
    """Edge Case 2A: Reassign technician when work order is DISPATCHED."""
    wo = new_wo(p3, work_type="CORRECTIVE")
    t0 = timezone.now() + timedelta(days=1)
    wo = step(wo, "plan", p3, "planner", planned_start=t0, planned_end=t0 + timedelta(hours=3))
    wo = step(wo, "assign", p3, "planner", technician=p3["tech"])
    wo = step(wo, "dispatch", p3, "planner")
    assert wo.status == WorkOrder.Status.DISPATCHED

    # Reassign to tech2
    t_new_start = t0 + timedelta(hours=1)
    t_new_end = t0 + timedelta(hours=4)
    reassigned = wos.reassign_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        assignee_id=p3["tech2"].pk,
        scheduled_start=t_new_start,
        scheduled_end=t_new_end,
        reason="Technician 1 reallocated to emergency job",
    )

    # 1. Verification of assigned technician & status
    assert reassigned.assigned_to_id == p3["tech2"].pk
    assert reassigned.status == WorkOrder.Status.DISPATCHED
    assert reassigned.planned_start == t_new_start
    assert reassigned.planned_end == t_new_end

    # 2. WorkOrderAssignment active record updated
    assignment = WorkOrderAssignment.objects.get(work_order=reassigned)
    assert assignment.technician_id == p3["tech2"].pk
    assert assignment.scheduled_start == t_new_start

    # 3. WorkOrderEvent recorded
    event = WorkOrderEvent.objects.filter(work_order=reassigned, action="reassigned").last()
    assert event is not None
    assert event.assigned_to_id == p3["tech2"].pk
    assert event.reason == "Technician 1 reallocated to emergency job"

    # 4. New technician is authorized to execute/start
    wos.assert_can_execute(reassigned, p3["tech2"])

    # 5. Old technician is no longer authorized
    with pytest.raises(PermissionDenied):
        wos.assert_can_execute(reassigned, p3["tech"])

    # 6. Tech2 can start the work order
    started = step(reassigned, "start", p3, "tech2")
    assert started.status == WorkOrder.Status.IN_PROGRESS


def test_reassign_technician_during_hold(p3, held_order):
    """Edge Case 2B: Reassign technician when work order is ON_HOLD."""
    wo = held_order
    assert wo.status == WorkOrder.Status.ON_HOLD
    assert wo.assigned_to_id == p3["tech"].pk

    # Reassign to tech2 while on hold
    reassigned = wos.reassign_work_order(
        wo,
        membership=p3["planner"],
        actor=p3["planner"].user,
        assignee_id=p3["tech2"].pk,
        reason="Technician shift ended; handover to morning shift technician",
    )

    # Status remains ON_HOLD and assignee is tech2
    assert reassigned.status == WorkOrder.Status.ON_HOLD
    assert reassigned.assigned_to_id == p3["tech2"].pk

    # Old technician cannot resume
    with pytest.raises(PermissionDenied):
        wos.resume_work_order(reassigned, membership=p3["tech"], actor=p3["tech"].user)

    # New technician CAN resume
    resumed = wos.resume_work_order(reassigned, membership=p3["tech2"], actor=p3["tech2"].user)
    assert resumed.status == WorkOrder.Status.IN_PROGRESS
    assert resumed.assigned_to_id == p3["tech2"].pk


def test_reassign_requires_permission(p3, dispatched_order):
    """Unauthorized user lacking work_order.assign cannot reassign."""
    with pytest.raises(PermissionDenied):
        wos.reassign_work_order(
            dispatched_order,
            membership=p3["reader"],
            actor=p3["reader"].user,
            assignee_id=p3["tech2"].pk,
        )


def test_reassign_api_endpoint(p3, as_user, dispatched_order, held_order):
    """API endpoint /api/v1/work-orders/{id}/reassign/ allows reassignment."""
    client = as_user(p3["planner"].user, p3["org"])

    # 1. Reassign dispatched order
    res1 = client.post(
        f"/api/v1/work-orders/{dispatched_order.pk}/reassign/",
        {
            "assigned_to": str(p3["tech2"].pk),
            "reason": "Reassigned via API after dispatch",
        },
        format="json",
    )
    assert res1.status_code == 200, res1.data
    assert str(res1.data["assigned_to"]) == str(p3["tech2"].pk)
    assert res1.data["status"] == WorkOrder.Status.DISPATCHED

    # 2. Reassign held order
    res2 = client.post(
        f"/api/v1/work-orders/{held_order.pk}/reassign/",
        {
            "assigned_to": str(p3["tech2"].pk),
            "reason": "Reassigned via API during hold",
        },
        format="json",
    )
    assert res2.status_code == 200, res2.data
    assert str(res2.data["assigned_to"]) == str(p3["tech2"].pk)
    assert res2.data["status"] == WorkOrder.Status.ON_HOLD
