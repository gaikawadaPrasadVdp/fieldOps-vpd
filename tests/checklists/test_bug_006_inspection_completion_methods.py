"""Regression test suite for Bug-006:
Submitting inspection form triggers a server cold start/redeploy and returns HTTP Error 405 (Method Not Allowed).
Verifies:
1. GET /app/inspections/<id>/complete/ returns 200 OK and renders the Inspection Completion / Submit Page.
2. Routing handles both trailing slash and non-trailing slash (/complete and /complete/) without 405 or loss of method.
3. POST /app/inspections/<id>/complete/ completes inspection successfully and redirects to detail view.
4. GET /app/inspections/<id>/complete/ on an already-completed inspection safely redirects with an informative notice.
5. API endpoint GET /api/v1/inspections/<id>/complete/ returns HTTP 200 with completion readiness status (not 405).
"""
import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.checklists import selectors
from apps.checklists import services as cl
from apps.checklists.models import Inspection
from tests.phase3_support import make_template, wo_in_progress

pytestmark = pytest.mark.django_db


SIMPLE_ITEMS = [{"prompt": "Visual inspection passed", "item_type": "BOOLEAN"}]


def test_bug_006_inspection_complete_get_renders_page_not_405(p3, client):
    """GET /app/inspections/<pk>/complete/ must return 200 OK (not 405 Method Not Allowed)."""
    tech = p3["tech"]
    client.force_login(tech.user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session["organization_id"] = str(p3["org"].pk)
    session.save()

    t = make_template(p3, name="Pump Reliability Inspection", items=SIMPLE_ITEMS)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=tech, actor=tech.user, work_order=wo)

    # 1. GET with trailing slash must return HTTP 200, not 405
    resp = client.get(f"/app/inspections/{insp.pk}/complete/")
    assert resp.status_code == 200, f"Expected 200 OK but got {resp.status_code} (Method Not Allowed bug)"
    content = resp.content.decode()
    assert "Complete Inspection" in content
    assert "Technician Summary" in content
    assert f"/app/inspections/{insp.pk}/complete/" in content

    # 2. GET without trailing slash must also return HTTP 200, not 405
    resp_no_slash = client.get(f"/app/inspections/{insp.pk}/complete")
    assert resp_no_slash.status_code in (200, 302, 301)
    if resp_no_slash.status_code != 200:
        follow_resp = client.get(resp_no_slash.url)
        assert follow_resp.status_code == 200


def test_bug_006_inspection_complete_post_successful(p3, client):
    """POST /app/inspections/<pk>/complete/ successfully completes inspection and redirects."""
    tech = p3["tech"]
    client.force_login(tech.user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session["organization_id"] = str(p3["org"].pk)
    session.save()

    t = make_template(p3, name="Pump Weekly Inspection", items=SIMPLE_ITEMS)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=tech, actor=tech.user, work_order=wo)

    # Answer all items to fulfill quality gate
    items = list(selectors.items_for(p3["org"], t))
    answers = {str(it.pk): True for it in items}
    cl.save_responses(insp, answers, membership=tech, actor=tech.user)

    # Submit completion
    resp = client.post(
        f"/app/inspections/{insp.pk}/complete/",
        data={"summary": "All checks completed and verified on site"},
    )
    assert resp.status_code == 302
    assert resp.url == f"/app/inspections/{insp.pk}/"

    insp.refresh_from_db()
    assert insp.status == "COMPLETED"
    assert insp.completed_at is not None
    assert insp.summary == "All checks completed and verified on site"


def test_bug_006_inspection_complete_post_without_trailing_slash(p3, client):
    """POST /app/inspections/<pk>/complete (no slash) must not fail with 405."""
    tech = p3["tech"]
    client.force_login(tech.user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session["organization_id"] = str(p3["org"].pk)
    session.save()

    t = make_template(p3, name="Compressor Inspection", items=SIMPLE_ITEMS)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=tech, actor=tech.user, work_order=wo)

    items = list(selectors.items_for(p3["org"], t))
    answers = {str(it.pk): True for it in items}
    cl.save_responses(insp, answers, membership=tech, actor=tech.user)

    resp = client.post(
        f"/app/inspections/{insp.pk}/complete",
        data={"summary": "Compressor checks verified successfully"},
    )
    assert resp.status_code in (200, 302)
    insp.refresh_from_db()
    assert insp.status == "COMPLETED"


def test_bug_006_completed_inspection_get_redirects_with_notice(p3, client):
    """Navigating to /complete/ on an already-completed inspection redirects safely without 405."""
    tech = p3["tech"]
    client.force_login(tech.user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session["organization_id"] = str(p3["org"].pk)
    session.save()

    t = make_template(p3, name="Turbine Inspection", items=SIMPLE_ITEMS)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=tech, actor=tech.user, work_order=wo)

    items = list(selectors.items_for(p3["org"], t))
    answers = {str(it.pk): True for it in items}
    cl.save_responses(insp, answers, membership=tech, actor=tech.user)
    cl.complete_inspection(insp, membership=tech, actor=tech.user, summary="Finished inspection")

    # Visiting /complete/ on a completed inspection
    resp = client.get(f"/app/inspections/{insp.pk}/complete/")
    assert resp.status_code == 302
    assert resp.url == f"/app/inspections/{insp.pk}/"


def test_bug_006_api_inspection_complete_get_and_post(p3):
    """API endpoint /api/v1/inspections/<id>/complete/ allows GET and POST without 405."""
    tech = p3["tech"]
    api = APIClient()
    api.force_authenticate(user=tech.user)
    session = api.session
    session["active_org_id"] = str(p3["org"].pk)
    session["organization_id"] = str(p3["org"].pk)
    session.save()

    t = make_template(p3, name="Chiller Inspection", items=SIMPLE_ITEMS)
    wo = wo_in_progress(p3)
    insp = cl.start_inspection(p3["org"], template=t, membership=tech, actor=tech.user, work_order=wo)

    # 1. API GET /complete/ returns status 200, not 405
    get_resp = api.get(
        f"/api/v1/inspections/{insp.pk}/complete/",
        HTTP_X_ORGANIZATION_ID=str(p3["org"].pk),
    )
    assert get_resp.status_code == 200, f"Expected 200 OK from API GET but got {get_resp.status_code}"
    data = get_resp.json()
    assert "completion_issues" in data
    assert "can_complete" in data

    # 2. Answer items and POST completion via API
    items = list(selectors.items_for(p3["org"], t))
    answers = {str(it.pk): True for it in items}
    cl.save_responses(insp, answers, membership=tech, actor=tech.user)

    post_resp = api.post(
        f"/api/v1/inspections/{insp.pk}/complete/",
        data={"summary": "API completion verified"},
        format="json",
        HTTP_X_ORGANIZATION_ID=str(p3["org"].pk),
    )
    assert post_resp.status_code == 200
    insp.refresh_from_db()
    assert insp.status == "COMPLETED"
