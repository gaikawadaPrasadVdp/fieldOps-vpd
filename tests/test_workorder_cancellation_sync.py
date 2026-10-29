"""Regression tests for D2: Work Order cancellation must synchronize with linked incident/request.

Sequence under test:
1. Create a service request.
2. Move the request through triage -> approve -> WORK_ORDER_CREATED (linked to draft work order).
3. Cancel the linked work order (with mandatory reason).
4. Assert request returns to APPROVED status.
5. Assert request history contains an action named 'work_order_cancelled' with source 'work_order'.
6. Assert that an audit record exists for the request status reversion.

Negative tests (Phase 3):
- Cancelling a work order with no linked request still works.
- Cancelling from ASSIGNED or IN_PROGRESS remains refused.
- Cancelling with outstanding issued parts is refused.
- An unsuccessful cancellation leaves the request unchanged through atomic rollback.
"""
from decimal import Decimal
import pytest
from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, InvalidTransition, ValidationFailed
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.inventory import services as inventory_services
from apps.inventory.models import Part, Warehouse
from apps.workorders import services as workorder_services
from apps.workorders.models import WorkOrder

pytestmark = pytest.mark.django_db


def test_work_order_cancellation_synchronizes_linked_request(org_a, site_a1, make_asset, make_member):
    # Setup test asset and actor memberships
    asset = make_asset(org_a, site_a1, "CHILLER-01")
    reporter = make_member(org_a, "tech.reporter@alpha.test", "technician")
    ops = make_member(org_a, "ops.mgr@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.cancel@alpha.test", "maintenance_planner")

    # 1. Create service request
    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        actor=reporter.user,
        title="Chiller compressor failure",
        severity=ServiceRequest.Severity.HIGH,
        service_impact=ServiceRequest.Impact.PARTIAL,
    )
    assert sr.status == "NEW"

    # Triage and approve
    sr = incident_services.transition(sr, action="triage", actor=ops.user)
    sr = incident_services.transition(sr, action="approve", actor=ops.user)
    assert sr.status == "APPROVED"

    # 2. Convert to work order -> request moves to WORK_ORDER_CREATED
    wo = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    sr.refresh_from_db()
    assert wo.status == WorkOrder.Status.DRAFT
    assert sr.status == "WORK_ORDER_CREATED"

    # 3. Cancel the linked work order
    wo = workorder_services.cancel_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        reason="Duplicate work order issued by error",
    )
    assert wo.status == WorkOrder.Status.CANCELLED

    # 4. Assert that request status becomes APPROVED
    sr.refresh_from_db()
    assert sr.status == "APPROVED", f"Expected request status to revert to APPROVED, got: {sr.status}"

    # 5. Assert that history contains an action named work_order_cancelled with source work_order
    history_entry = sr.history.filter(action="work_order_cancelled").first()
    assert history_entry is not None, "Missing ServiceRequestHistory entry for 'work_order_cancelled'"
    assert history_entry.source == "work_order"
    assert history_entry.to_status == "APPROVED"

    # 6. Assert that an audit record exists
    audit_entry = AuditLog.objects.filter(
        organization=org_a,
        target_id=str(sr.pk),
        action="incident.status_changed",
    ).order_by("-occurred_at").first()
    assert audit_entry is not None, "Missing AuditLog record for request status change"
    assert audit_entry.before["status"] == "WORK_ORDER_CREATED"
    assert audit_entry.after["status"] == "APPROVED"
    assert audit_entry.metadata["action"] == "work_order_cancelled"


def test_cancel_work_order_without_linked_request_succeeds(org_a, site_a1, make_asset, make_member):
    """Cancelling a standalone work order (no source request) succeeds cleanly."""
    asset = make_asset(org_a, site_a1, "BOILER-01")
    planner = make_member(org_a, "planner.standalone@alpha.test", "maintenance_planner")

    wo = workorder_services.create_work_order(
        org_a,
        asset=asset,
        site=site_a1,
        title="Periodic routine check",
        actor=planner.user,
        membership=planner,
    )
    assert wo.status == WorkOrder.Status.DRAFT
    assert wo.source_request_id is None

    wo = workorder_services.cancel_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        reason="No longer required by plant schedule",
    )
    assert wo.status == WorkOrder.Status.CANCELLED


def test_cancel_work_order_from_in_progress_or_completed_is_refused(org_a, site_a1, make_asset, make_member):
    """Cancellation from IN_PROGRESS or COMPLETED must be rejected by workflow rules."""
    asset = make_asset(org_a, site_a1, "FAN-01")
    planner = make_member(org_a, "planner.assign@alpha.test", "maintenance_planner")

    wo = workorder_services.create_work_order(
        org_a,
        asset=asset,
        site=site_a1,
        title="Ventilation exhaust fan repair",
        actor=planner.user,
        membership=planner,
    )
    # Move to IN_PROGRESS directly in DB to test state machine boundary
    WorkOrder.objects.filter(pk=wo.pk).update(status=WorkOrder.Status.IN_PROGRESS)
    wo.refresh_from_db()
    assert wo.status == WorkOrder.Status.IN_PROGRESS

    # Attempting to cancel an IN_PROGRESS work order must be refused
    with pytest.raises(InvalidTransition):
        workorder_services.cancel_work_order(
            wo,
            membership=planner,
            actor=planner.user,
            reason="Attempting invalid cancellation from IN_PROGRESS",
        )

    # Move to COMPLETED and test cancellation is also refused
    WorkOrder.objects.filter(pk=wo.pk).update(status=WorkOrder.Status.COMPLETED)
    wo.refresh_from_db()
    assert wo.status == WorkOrder.Status.COMPLETED

    with pytest.raises(InvalidTransition):
        workorder_services.cancel_work_order(
            wo,
            membership=planner,
            actor=planner.user,
            reason="Attempting invalid cancellation from COMPLETED",
        )


def test_cancel_work_order_with_outstanding_issued_parts_is_refused(org_a, site_a1, make_asset, make_member):
    """Cancelling with parts issued to the work order must be blocked with outstanding_parts Conflict."""
    asset = make_asset(org_a, site_a1, "COMPRESSOR-02")
    planner = make_member(org_a, "planner.parts@alpha.test", "maintenance_planner")
    stores = make_member(org_a, "stores.parts@alpha.test", "stores_manager")

    warehouse = Warehouse.objects.create(
        organization=org_a,
        site=site_a1,
        code="WH-MAIN",
        name="Main Storage",
        is_active=True,
    )
    part = Part.objects.create(
        organization=org_a,
        part_number="FLTR-001",
        name="Oil Filter High Pressure",
        unit="EA",
        is_active=True,
    )
    # Receive initial stock
    inventory_services.receive(
        warehouse,
        part,
        Decimal("10"),
        actor=stores.user,
        reason="Initial stock count",
    )

    wo = workorder_services.create_work_order(
        org_a,
        asset=asset,
        site=site_a1,
        title="Filter overhaul",
        actor=planner.user,
        membership=planner,
    )
    # Move to PLANNED so parts can be issued
    WorkOrder.objects.filter(pk=wo.pk).update(status=WorkOrder.Status.PLANNED)
    wo.refresh_from_db()

    # Request and issue part
    line = inventory_services.request_part(
        wo,
        part=part,
        quantity=Decimal("2"),
        actor=stores.user,
        membership=stores,
    )
    inventory_services.issue(
        line,
        warehouse=warehouse,
        quantity=Decimal("2"),
        actor=stores.user,
    )

    # Attempt to cancel must raise Conflict with code 'outstanding_parts'
    with pytest.raises(Conflict) as exc_info:
        workorder_services.cancel_work_order(
            wo,
            membership=planner,
            actor=planner.user,
            reason="Cancelling order with issued parts",
        )
    assert exc_info.value.code == "outstanding_parts"


def test_unsuccessful_cancellation_rolls_back_atomically(org_a, site_a1, make_asset, make_member, monkeypatch):
    """If an error occurs during cancellation, atomic rollback leaves the linked request in WORK_ORDER_CREATED."""
    asset = make_asset(org_a, site_a1, "GENSET-01")
    reporter = make_member(org_a, "reporter.rb@alpha.test", "technician")
    ops = make_member(org_a, "ops.rb@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.rb@alpha.test", "maintenance_planner")

    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        actor=reporter.user,
        title="Generator failure",
        severity=ServiceRequest.Severity.HIGH,
        service_impact=ServiceRequest.Impact.FULL,
    )
    sr = incident_services.transition(sr, action="triage", actor=ops.user)
    sr = incident_services.transition(sr, action="approve", actor=ops.user)

    wo = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"

    # Simulate unexpected failure during sync
    def broken_sync(*args, **kwargs):
        raise RuntimeError("Simulated network or database failure")

    monkeypatch.setattr(workorder_services, "_sync_incident_request", broken_sync)

    with pytest.raises(RuntimeError):
        workorder_services.cancel_work_order(
            wo,
            membership=planner,
            actor=planner.user,
            reason="Attempted cancellation with failure",
        )

    # Both work order and request must remain uncancelled due to atomic rollback
    wo.refresh_from_db()
    sr.refresh_from_db()
    assert wo.status == WorkOrder.Status.DRAFT
    assert sr.status == "WORK_ORDER_CREATED"
