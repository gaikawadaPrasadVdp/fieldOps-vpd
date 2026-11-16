"""Regression tests for Bug-003:
Requested parts by technician in Field Dashboard do not reflect in Stores/Inventory Dashboard.
"""
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory import services as inv_services
from apps.inventory import selectors as inv_selectors
from apps.inventory.models import WorkOrderPart
from tests.phase3_support import wo_in_progress

pytestmark = pytest.mark.django_db


def test_bug_003_technician_part_request_syncs_to_stores_dashboard_and_queue(inv_):
    org = inv_["org"]
    tech = inv_["tech"]
    stores = inv_["stores"]
    wh = inv_["wh"]

    # 1. Create part PRT-8842-FLT as described in Bug-003
    part = inv_services.create_part(
        org,
        part_number="PRT-8842-FLT",
        name="Fleet Hydraulic Filter",
        unit="pcs",
        actor=stores.user,
    )

    # 2. Active work order assigned to technician in progress
    wo = wo_in_progress(inv_)

    # 3. Technician requests replacement part (PRT-8842-FLT)
    line = inv_services.request_part(
        wo,
        part,
        Decimal("3"),
        actor=tech.user,
        membership=tech,
        notes="Urgent replacement for leaking line",
    )
    assert line.status == WorkOrderPart.Status.REQUESTED
    assert line.quantity_requested == Decimal("3")
    assert line.requested_by == tech.user

    # 4. Verify selectors.lines_visible for stores manager
    stores_lines = inv_selectors.lines_visible(stores, org)
    assert line in stores_lines

    # 5. API Test: Stores manager GET /api/v1/work-order-parts/
    client = Client()
    client.force_login(stores.user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    api_resp = client.get(
        "/api/v1/work-order-parts/",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert api_resp.status_code == 200, f"Stores manager API was forbidden or error: {api_resp.status_code}"
    data = api_resp.json()
    items = data.get("results", data)
    part_numbers = [item.get("part_number") for item in items]
    assert "PRT-8842-FLT" in part_numbers

    # Verify status filtering works for pending_fulfillment and REQUESTED
    filter_resp = client.get(
        "/api/v1/work-order-parts/?status=pending_fulfillment",
        HTTP_X_ORGANIZATION_ID=str(org.id),
    )
    assert filter_resp.status_code == 200
    filtered_items = filter_resp.json().get("results", filter_resp.json())
    assert any(item.get("part_number") == "PRT-8842-FLT" for item in filtered_items)
    matched_item = next(item for item in filtered_items if item.get("part_number") == "PRT-8842-FLT")
    assert matched_item.get("status_display") == "Pending Fulfillment"
    assert matched_item.get("fulfillment_status") == "Pending Fulfillment"

    # 6. Stores / Inventory Home Dashboard (/app/)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    home_resp = client.get(reverse("ui:home"))
    assert home_resp.status_code == 200
    assert home_resp.context["is_stores_manager"] is True
    pending_list = home_resp.context.get("stores_pending_requests", [])
    assert any(req.part.part_number == "PRT-8842-FLT" for req in pending_list)
    home_html = home_resp.content.decode()
    assert "Pending Parts Requests Queue" in home_html
    assert "PRT-8842-FLT" in home_html
    assert "Pending Fulfillment" in home_html

    # 7. Dedicated Part Requests Queue (/app/inventory/requests/)
    queue_resp = client.get(reverse("inventory:requests"))
    assert queue_resp.status_code == 200
    queue_html = queue_resp.content.decode()
    assert "PRT-8842-FLT" in queue_html
    assert "Pending Fulfillment" in queue_html
    assert "Fleet Hydraulic Filter" in queue_html

    # 8. Operational Dashboards Hub (/app/dashboards/hub/?section=inventory)
    hub_resp = client.get(reverse("dashboards:hub") + "?section=inventory")
    assert hub_resp.status_code == 200
    hub_html = hub_resp.content.decode()
    assert "Pending Requests" in hub_html
    assert "PRT-8842-FLT" in hub_html
