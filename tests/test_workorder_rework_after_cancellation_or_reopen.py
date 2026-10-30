"""Regression tests for D1: Allow creating a new work order after reopening or cancellation.

Workflow under test:
Case A: Service request -> approved -> work order created -> work order cancelled
        -> request returns to APPROVED -> planner creates replacement work order.
Case B: Service request -> approved -> work order completed/closed -> request resolved
        -> client/supervisor reopens request for rework (status returns to APPROVED)
        -> planner creates replacement work order.

Negative tests:
1. Cannot create duplicate work order while a live work order is still active (DRAFT, etc.).
2. Database constraint uniq_live_work_order_per_request blocks concurrent live work orders.
3. Cannot create work order when request status is not APPROVED.
4. Linked duplicate requests cannot create work orders.
"""
import pytest
from django.db import IntegrityError
from apps.core.exceptions import Conflict, InvalidTransition
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.workorders import services as workorder_services
from apps.workorders.models import WorkOrder

pytestmark = pytest.mark.django_db


def test_create_new_work_order_after_cancellation_of_previous_work_order(org_a, site_a1, make_asset, make_member):
    """After a work order is cancelled, creating a replacement work order for the approved request must succeed."""
    asset = make_asset(org_a, site_a1, "CHILLER-01")
    reporter = make_member(org_a, "tech.reporter@alpha.test", "technician")
    ops = make_member(org_a, "ops.mgr@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.d1@alpha.test", "maintenance_planner")

    # 1. Create and approve service request
    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="Chiller leak",
        description="Coolant dripping from valve",
        severity="HIGH",
        service_impact=ServiceRequest.Impact.PARTIAL,
        actor=reporter.user,
    )
    sr = incident_services.transition(sr, action="triage", actor=ops.user)
    sr = incident_services.transition(sr, action="approve", actor=ops.user)
    assert sr.status == "APPROVED"

    # 2. Create first work order
    wo1 = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"
    assert wo1.status == WorkOrder.Status.DRAFT

    # 3. Cancel first work order
    workorder_services.cancel_work_order(
        wo1,
        membership=planner,
        actor=planner.user,
        reason="Mistakenly planned wrong scope",
    )
    wo1.refresh_from_db()
    assert wo1.status == WorkOrder.Status.CANCELLED
    sr.refresh_from_db()
    assert sr.status == "APPROVED"

    # 4. Attempt to create replacement work order (Defect D1 Case A)
    wo2 = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    assert wo2 is not None
    assert wo2.pk != wo1.pk
    assert wo2.status == WorkOrder.Status.DRAFT
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"


def test_create_new_work_order_after_request_reopened_for_rework(org_a, site_a1, make_asset, make_member):
    """When a service request is reopened for rework after work order resolution, creating a new work order must succeed."""
    asset = make_asset(org_a, site_a1, "CONVEYOR-02")
    reporter = make_member(org_a, "reporter.rwk@alpha.test", "technician")
    ops = make_member(org_a, "ops.rwk@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.rwk@alpha.test", "maintenance_planner")

    # 1. Create, triage, approve request
    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="Belt alignment off",
        description="Conveyor belt slipping off tracks",
        severity="MEDIUM",
        service_impact=ServiceRequest.Impact.DEGRADED,
        actor=reporter.user,
    )
    sr = incident_services.transition(sr, action="triage", actor=ops.user)
    sr = incident_services.transition(sr, action="approve", actor=ops.user)

    # 2. Create initial work order
    wo1 = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"

    # Simulate work order lifecycle: started -> completed -> closed
    incident_services.on_work_order_started(sr, actor=ops.user)
    sr.refresh_from_db()
    assert sr.status == "IN_SERVICE"

    incident_services.on_work_order_completed(sr, actor=ops.user)
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"

    WorkOrder.objects.filter(pk=wo1.pk).update(status=WorkOrder.Status.CLOSED)
    wo1.refresh_from_db()
    assert wo1.status == WorkOrder.Status.CLOSED

    # 3. Client / supervisor reopens request for rework
    sr = incident_services.transition(
        sr,
        action="reopen",
        reason="Belt slipping recurred during shift B testing",
        actor=ops.user,
    )
    assert sr.status == "APPROVED"

    # 4. Attempt to create second work order for rework (Defect D1 Case B)
    wo2 = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    assert wo2 is not None
    assert wo2.pk != wo1.pk
    assert wo2.status == WorkOrder.Status.DRAFT
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"


def test_duplicate_live_work_order_creation_remains_blocked(org_a, site_a1, make_asset, make_member):
    """While an active work order exists for a request, creating another must be strictly blocked."""
    asset = make_asset(org_a, site_a1, "PUMP-01")
    reporter = make_member(org_a, "rep.dup@alpha.test", "technician")
    ops = make_member(org_a, "ops.dup@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.dup@alpha.test", "maintenance_planner")

    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="Pump seal failure",
        description="Liquid leaking around casing",
        severity="HIGH",
        service_impact=ServiceRequest.Impact.PARTIAL,
        actor=reporter.user,
    )
    sr = incident_services.transition(sr, action="triage", actor=ops.user)
    sr = incident_services.transition(sr, action="approve", actor=ops.user)

    wo1 = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    assert wo1.status == WorkOrder.Status.DRAFT

    # Force request status back to APPROVED to test the duplicate work order guard directly
    sr.status = "APPROVED"
    sr.save(update_fields=["status"])

    # Attempting to create second work order while first is still live (DRAFT) must fail with Conflict
    with pytest.raises(Conflict) as exc:
        incident_services.create_work_order_for_request(
            sr,
            actor=planner.user,
            membership=planner,
        )
    assert exc.value.code == "duplicate_work_order"


def test_db_partial_unique_constraint_blocks_concurrent_live_work_orders(org_a, site_a1, make_asset, make_member):
    """Database constraint uniq_live_work_order_per_request must reject two live work orders referencing the same source_request."""
    asset = make_asset(org_a, site_a1, "BOILER-01")
    planner = make_member(org_a, "planner.db@alpha.test", "maintenance_planner")
    reporter = make_member(org_a, "rep.db@alpha.test", "technician")
    ops = make_member(org_a, "ops.db@alpha.test", "operations_manager")

    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="Pressure relief valve stuck",
        severity="CRITICAL",
        service_impact=ServiceRequest.Impact.PARTIAL,
        actor=reporter.user,
    )
    sr = incident_services.transition(sr, action="triage", actor=ops.user)
    sr = incident_services.transition(sr, action="approve", actor=ops.user)

    wo1 = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    assert wo1.status == WorkOrder.Status.DRAFT

    # Attempt direct DB insertion of a second live work order with the same source_request
    with pytest.raises(IntegrityError):
        WorkOrder.objects.create(
            organization=org_a,
            site=site_a1,
            asset=asset,
            source_request=sr,
            source_type=WorkOrder.SourceType.INCIDENT,
            source_reference=sr.number,
            title="Duplicate live work order",
            status=WorkOrder.Status.DRAFT,
            created_by=planner.user,
        )


def test_cannot_create_work_order_when_request_not_approved(org_a, site_a1, make_asset, make_member):
    """Attempting create_work_order_for_request when status is not APPROVED raises InvalidTransition."""
    asset = make_asset(org_a, site_a1, "HVAC-01")
    reporter = make_member(org_a, "rep.na@alpha.test", "technician")
    planner = make_member(org_a, "planner.na@alpha.test", "maintenance_planner")

    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="HVAC filter clogged",
        severity="LOW",
        service_impact=ServiceRequest.Impact.NONE,
        actor=reporter.user,
    )
    assert sr.status == "NEW"

    with pytest.raises(InvalidTransition):
        incident_services.create_work_order_for_request(
            sr,
            actor=planner.user,
            membership=planner,
        )


def test_cannot_create_work_order_for_linked_duplicate_request(org_a, site_a1, make_asset, make_member):
    """Attempting to create a work order for a duplicate-linked request is rejected."""
    asset = make_asset(org_a, site_a1, "MOTOR-01")
    reporter = make_member(org_a, "rep.dup2@alpha.test", "technician")
    ops = make_member(org_a, "ops.dup2@alpha.test", "operations_manager")
    planner = make_member(org_a, "planner.dup2@alpha.test", "maintenance_planner")

    parent = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="Motor bearing noise",
        severity="HIGH",
        service_impact=ServiceRequest.Impact.PARTIAL,
        actor=reporter.user,
    )
    parent = incident_services.transition(parent, action="triage", actor=ops.user)
    parent = incident_services.transition(parent, action="approve", actor=ops.user)

    duplicate = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=reporter,
        title="Motor bearing noise",
        severity="HIGH",
        service_impact=ServiceRequest.Impact.PARTIAL,
        duplicate_of=parent,
        actor=reporter.user,
    )
    duplicate.status = "APPROVED"
    duplicate.save(update_fields=["status"])

    with pytest.raises(Conflict) as exc:
        incident_services.create_work_order_for_request(
            duplicate,
            actor=planner.user,
            membership=planner,
        )
    assert exc.value.code == "duplicate_incident_work_order"
