"""Regression tests for Bug-006:
Missing back navigation buttons / breadcrumb navigation across dashboard and sub-screens.
"""
import pytest
from django.test import Client, RequestFactory

from apps.inventory import services as inv_services
from apps.ui.context_processors import _build_breadcrumbs, shell
from tests.phase3_support import wo_in_progress

pytestmark = pytest.mark.django_db


def test_bug_006_build_breadcrumbs_hierarchy_and_back_urls(inv_):
    """Verify _build_breadcrumbs constructs proper hierarchy and back_url across sub-screens."""
    wo = wo_in_progress(inv_)
    part = inv_["part"]

    rf = RequestFactory()

    # 1. Module root: /app/work-orders/
    req = rf.get("/app/work-orders/")
    req.user = inv_["tech"].user
    req.membership = inv_["tech"]
    crumbs, back_url = _build_breadcrumbs(req)
    assert len(crumbs) == 2
    assert crumbs[0]["label"] == "Home" and crumbs[0]["url"] == "/app/"
    assert crumbs[1]["label"] == "Work Orders" and crumbs[1]["url"] is None
    assert back_url == "/app/"

    # 2. Detail screen: /app/work-orders/<uuid>/
    req = rf.get(f"/app/work-orders/{wo.pk}/")
    req.user = inv_["tech"].user
    req.membership = inv_["tech"]
    crumbs, back_url = _build_breadcrumbs(req)
    assert len(crumbs) == 3
    assert crumbs[0]["label"] == "Home" and crumbs[0]["url"] == "/app/"
    assert crumbs[1]["label"] == "Work Orders" and crumbs[1]["url"] == "/app/work-orders/"
    assert crumbs[2]["label"] == "Detail" and crumbs[2]["url"] is None
    assert back_url == "/app/work-orders/"

    # 3. Nested sub-screen: /app/work-orders/<uuid>/parts/
    req = rf.get(f"/app/work-orders/{wo.pk}/parts/")
    req.user = inv_["tech"].user
    req.membership = inv_["tech"]
    crumbs, back_url = _build_breadcrumbs(req)
    assert len(crumbs) == 4
    assert crumbs[0]["label"] == "Home" and crumbs[0]["url"] == "/app/"
    assert crumbs[1]["label"] == "Work Orders" and crumbs[1]["url"] == "/app/work-orders/"
    assert crumbs[2]["label"] == "Detail" and crumbs[2]["url"] == f"/app/work-orders/{wo.pk}/"
    assert crumbs[3]["label"] == "Parts" and crumbs[3]["url"] is None
    assert back_url == f"/app/work-orders/{wo.pk}/"

    # 4. Inventory module sub-screens
    req = rf.get("/app/inventory/parts/")
    req.user = inv_["stores"].user
    req.membership = inv_["stores"]
    crumbs, back_url = _build_breadcrumbs(req)
    assert len(crumbs) == 2
    assert crumbs[1]["label"] == "Parts Inventory"
    assert back_url == "/app/"

    req = rf.get(f"/app/inventory/parts/{part.pk}/")
    req.user = inv_["stores"].user
    req.membership = inv_["stores"]
    crumbs, back_url = _build_breadcrumbs(req)
    assert len(crumbs) == 3
    assert crumbs[1]["label"] == "Parts Inventory" and crumbs[1]["url"] == "/app/inventory/parts/"
    assert crumbs[2]["label"] == "Detail" and crumbs[2]["url"] is None
    assert back_url == "/app/inventory/parts/"

    req = rf.get("/app/inventory/requests/")
    req.user = inv_["stores"].user
    req.membership = inv_["stores"]
    crumbs, back_url = _build_breadcrumbs(req)
    assert len(crumbs) == 2
    assert crumbs[1]["label"] == "Part Requests"
    assert back_url == "/app/"


def test_bug_006_rendered_html_includes_header_and_content_back_buttons(inv_):
    """Verify rendered HTML for work orders list, detail, and parts contains Back buttons & breadcrumbs."""
    wo = wo_in_progress(inv_)
    org = inv_["org"]
    user = inv_["stores"].user

    client = Client()
    client.force_login(user)
    s = client.session
    s["active_org_id"] = str(org.id)
    s.save()

    # A. Work Orders List (/app/work-orders/)
    resp_list = client.get("/app/work-orders/")
    assert resp_list.status_code == 200
    html_list = resp_list.content.decode("utf-8")
    assert 'data-action="go-back"' in html_list
    assert 'data-fallback="/app/"' in html_list
    assert "Back" in html_list
    assert "fx-topbar-back-btn" in html_list

    # B. Work Order Detail (/app/work-orders/<uuid>/)
    resp_detail = client.get(f"/app/work-orders/{wo.pk}/")
    assert resp_detail.status_code == 200
    html_detail = resp_detail.content.decode("utf-8")
    assert 'data-action="go-back"' in html_detail
    assert f'data-fallback="/app/work-orders/"' in html_detail
    assert "Work Orders" in html_detail
    assert "fx-topbar-back-btn" in html_detail

    # C. Work Order Parts Sub-screen (/app/work-orders/<uuid>/parts/)
    resp_parts = client.get(f"/app/work-orders/{wo.pk}/parts/")
    assert resp_parts.status_code == 200
    html_parts = resp_parts.content.decode("utf-8")
    assert 'data-action="go-back"' in html_parts
    assert f'data-fallback="/app/work-orders/{wo.pk}/"' in html_parts
    assert f'href="/app/work-orders/{wo.pk}/"' in html_parts
    assert "Parts" in html_parts
    assert "fx-topbar-back-btn" in html_parts
