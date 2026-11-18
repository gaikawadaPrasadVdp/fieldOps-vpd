"""Regression tests for BUG-006:
Unused spare part line item ("asd srf") incorrectly displays a "Cancelled" status
despite never being requested or consumed on a closed or active work order.
"""
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory import services as inv_services
from apps.inventory.models import WorkOrderPart
from apps.workorders import services as wo_services
from apps.workorders.models import WorkOrder
from tests.phase3_support import wo_in_progress

pytestmark = pytest.mark.django_db


def test_bug_006_active_work_order_unused_part_shows_requested_status(inv_):
    org = inv_["org"]
    tech = inv_["tech"]
    stores = inv_["stores"]

    # 1. Create part "asd srf" as reported in BUG-006
    part = inv_services.create_part(
        org,
        part_number="ASD-SRF-001",
        name="asd srf",
        unit="pcs",
        actor=stores.user,
    )

    # 2. Active work order assigned to technician
    wo = wo_in_progress(inv_)

    # 3. Request 10 pcs (Requested: 10 pcs, Issued: 0, Consumed: 0)
    line = inv_services.request_part(
        wo,
        part,
        Decimal("10"),
        actor=tech.user,
        membership=tech,
        notes="Spare requirement",
    )
    assert line.status == WorkOrderPart.Status.REQUESTED
    assert line.quantity_requested == Decimal("10")
    assert line.quantity_issued == Decimal("0")
    assert line.quantity_consumed == Decimal("0")
    assert line.display_status == WorkOrderPart.Status.REQUESTED

    # 4. View Parts tab on the work order (/app/work-orders/<uuid>/?tab=parts)
    client = Client()
    client.force_login(tech.user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    resp = client.get(f"/app/work-orders/{wo.pk}/?tab=parts")
    assert resp.status_code == 200
    html = resp.content.decode()

    # Verify part name and requested status badge are rendered
    assert "asd srf" in html
    assert "ASD-SRF-001" in html
    assert "Warehouse Spare Parts (Inventory M09)" in html
    # Ensure badge reflects Requested and does NOT reflect Cancelled
    assert "Requested" in html
    # The line row for asd srf must not have Cancelled status badge
    assert '<span class="badge fx-badge fx-badge-secondary">Cancelled</span>' not in html


def test_bug_006_closed_work_order_unused_part_retains_requested_status(inv_):
    org = inv_["org"]
    tech = inv_["tech"]
    stores = inv_["stores"]

    part = inv_services.create_part(
        org,
        part_number="ASD-SRF-002",
        name="asd srf",
        unit="pcs",
        actor=stores.user,
    )

    wo = wo_in_progress(inv_)

    line = inv_services.request_part(
        wo,
        part,
        Decimal("10"),
        actor=tech.user,
        membership=tech,
    )
    assert line.status == WorkOrderPart.Status.REQUESTED

    # Close the work order (closure reconciliation)
    inv_services.on_work_order_closed(wo, actor=stores.user)

    line.refresh_from_db()
    # BUG-006: Unused part line displays Requested status rather than Cancelled
    assert line.display_status == WorkOrderPart.Status.REQUESTED

    # View Parts tab on the closed work order
    WorkOrder.objects.filter(pk=wo.pk).update(status=WorkOrder.Status.CLOSED)
    wo.refresh_from_db()

    client = Client()
    client.force_login(tech.user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    resp = client.get(f"/app/work-orders/{wo.pk}/?tab=parts")
    assert resp.status_code == 200
    html = resp.content.decode()

    assert "asd srf" in html
    assert '<span class="badge fx-badge fx-badge-info">Requested</span>' in html
    assert '<span class="badge fx-badge fx-badge-secondary">Cancelled</span>' not in html


def test_bug_006_reopened_work_order_retains_active_status_on_rework(inv_):
    org = inv_["org"]
    tech = inv_["tech"]
    stores = inv_["stores"]

    part = inv_services.create_part(
        org,
        part_number="ASD-SRF-003",
        name="asd srf",
        unit="pcs",
        actor=stores.user,
    )

    wo = wo_in_progress(inv_)

    line = inv_services.request_part(
        wo,
        part,
        Decimal("10"),
        actor=tech.user,
        membership=tech,
    )

    # Simulate a legacy or wound-down line with CANCELLED on a closed order
    WorkOrderPart.objects.filter(pk=line.pk).update(status="CANCELLED")
    line.refresh_from_db()
    assert line.status == "CANCELLED"

    # Reopen work order for rework
    inv_services.on_work_order_reopened(wo, actor=stores.user)

    line.refresh_from_db()
    assert line.status == WorkOrderPart.Status.REQUESTED
    assert line.display_status == WorkOrderPart.Status.REQUESTED


def test_bug_006_explicit_user_cancellation_still_cancels_line(inv_):
    org = inv_["org"]
    tech = inv_["tech"]
    stores = inv_["stores"]

    part = inv_services.create_part(
        org,
        part_number="ASD-SRF-004",
        name="asd srf",
        unit="pcs",
        actor=stores.user,
    )

    wo = wo_in_progress(inv_)

    line = inv_services.request_part(
        wo,
        part,
        Decimal("10"),
        actor=tech.user,
        membership=tech,
    )

    # When user explicitly cancels the line
    inv_services.cancel_line(line, actor=tech.user, membership=tech)
    line.refresh_from_db()
    assert line.status == WorkOrderPart.Status.CANCELLED


def test_bug_006_cancelled_work_order_cancels_unfulfilled_lines(inv_):
    org = inv_["org"]
    tech = inv_["tech"]
    stores = inv_["stores"]

    part = inv_services.create_part(
        org,
        part_number="ASD-SRF-005",
        name="asd srf",
        unit="pcs",
        actor=stores.user,
    )

    wo = wo_in_progress(inv_)

    line = inv_services.request_part(
        wo,
        part,
        Decimal("10"),
        actor=tech.user,
        membership=tech,
    )

    # When the whole work order is cancelled
    inv_services.on_work_order_cancelled(wo, actor=stores.user)
    line.refresh_from_db()
    assert line.status == WorkOrderPart.Status.CANCELLED
