from __future__ import annotations

import time
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.core.exceptions import ValidationFailed
from apps.incidents import services as incident_services
from apps.workorders import services as wo_services
from apps.workorders.models import WorkOrder, WorkOrderLabor
from apps.workspace import services as ws_services

pytestmark = pytest.mark.django_db
PASSWORD = "Correct-Horse-Battery-9"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _setup_started_work_order(org_a, site_a1, make_asset, make_member):
    asset = make_asset(org_a, site_a1, "LAB-PUMP-01")
    planner = make_member(org_a, "labor-planner@alpha.test", "maintenance_planner")
    tech = make_member(org_a, "labor-tech@alpha.test", "technician")

    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        actor=planner.user,
        title="Inspect main pump seals",
        work_type="CORRECTIVE",
        priority=WorkOrder.Priority.MEDIUM,
        membership=planner,
    )
    t0 = timezone.now() + timedelta(hours=2)
    wo = wo_services.plan_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        planned_start=t0,
        planned_end=t0 + timedelta(hours=2),
        estimated_hours=Decimal("2.0"),
        due_at=t0 + timedelta(days=1),
    )
    wo = wo_services.assign_work_order(
        wo,
        membership=planner,
        actor=planner.user,
        assignee_id=tech.pk,
        scheduled_start=t0,
        scheduled_end=t0 + timedelta(hours=2),
    )
    wo = wo_services.dispatch_work_order(wo, membership=planner, actor=planner.user)
    wo = ws_services.start_job(wo, membership=tech, actor=tech.user)
    return wo, tech


# ---------------------------------------------------------------------------
# BUG-001: Service Dispatcher Portal Overview Renders Complete Multi-Widget Layout
# ---------------------------------------------------------------------------

def test_bug001_service_dispatcher_home_overview_renders_all_widgets_and_site_stats(
    org_a, site_a1, site_a2, make_asset, make_member
):
    asset1 = make_asset(org_a, site_a1, "DISP-A1")
    asset2 = make_asset(org_a, site_a2, "DISP-A2")
    dispatcher = make_member(org_a, "disp-overview@alpha.test", "service_dispatcher")

    incident_services.create_request(
        org_a,
        asset=asset1,
        reporter=dispatcher,
        actor=dispatcher.user,
        title="Chiller compressor fault",
    )
    wo_services.create_work_order(
        org_a,
        site_id=site_a2.pk,
        asset=asset2,
        actor=dispatcher.user,
        title="Inspect rooftop damper",
        work_type="CORRECTIVE",
        priority=WorkOrder.Priority.MEDIUM,
        membership=dispatcher,
    )

    client = Client()
    client.force_login(dispatcher.user)
    resp = client.get(reverse("ui:home"))

    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "Service Dispatch" in html
    assert "Facility Sites" in html
    assert "Facility Site Statistics" in html
    assert site_a1.name in html
    assert site_a2.name in html
    assert "Recent Incident" in html
    assert "Operational Shortcuts" in html
    assert "Work Order Board" in html


def test_bug001_service_dispatcher_incidents_dashboard_renders_full_overview_sections(
    org_a, site_a1, make_asset, make_member
):
    make_asset(org_a, site_a1, "DISP-DASH-01")
    dispatcher = make_member(org_a, "disp-inc@alpha.test", "service_dispatcher")

    client = Client()
    client.force_login(dispatcher.user)
    resp = client.get(reverse("incidents:dashboard"))

    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "Active related work orders" in html
    assert "Service impact summary" in html
    assert "Open incidents by asset type" in html
    assert "Incidents approaching an SLA deadline" in html


def test_bug001_css_app_shell_allows_full_page_scroll_not_clipped_to_100vh():
    css_text = (REPO_ROOT / "src" / "static" / "css" / "app.css").read_text(encoding="utf-8")
    assert "body.fx-app" in css_text
    assert "overflow-y: auto;" in css_text
    assert "min-height: 100vh;" in css_text
    assert "height: 100vh;\n  overflow: hidden;\n}" not in css_text


# ---------------------------------------------------------------------------
# BUG-002: Field Execution On-Site Labor Description Alphabetical Validation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_description",
    [
        "644444444",
        "12345",
        "Replaced 2 bolts",
        "Work order #123",
        "@@@###",
        "   ",
        "",
    ],
)
def test_bug002_record_job_labor_rejects_numeric_and_non_alphabetical_descriptions(
    org_a, site_a1, make_asset, make_member, bad_description
):
    wo, tech = _setup_started_work_order(org_a, site_a1, make_asset, make_member)

    with pytest.raises(ValidationFailed) as exc_info:
        ws_services.record_job_labor(
            wo,
            hours=Decimal("1.50"),
            description=bad_description,
            membership=tech,
            actor=tech.user,
        )

    assert exc_info.value.code == "invalid_description"
    assert WorkOrderLabor.objects.filter(work_order=wo).count() == 0


def test_bug002_workspace_labor_view_and_api_reject_numeric_and_accept_alphabetical(
    org_a, site_a1, make_asset, make_member
):
    wo, tech = _setup_started_work_order(org_a, site_a1, make_asset, make_member)

    # 1. HTML workspace labor form POST rejects numeric-only input
    web_client = Client()
    web_client.force_login(tech.user)
    resp = web_client.post(
        reverse("workspace:labor", args=[wo.pk]),
        {"hours": "2.00", "description": "644444444"},
        follow=True,
    )
    assert resp.status_code == 200
    assert WorkOrderLabor.objects.filter(work_order=wo).count() == 0
    msgs = [m.message for m in resp.context["messages"]]
    assert any("letters" in msg.lower() or "alphabet" in msg.lower() or "numbers" in msg.lower() for msg in msgs)

    # 2. API endpoint also enforces the rule
    api_client = APIClient()
    api_client.force_authenticate(user=tech.user)
    api_resp = api_client.post(
        f"/api/v1/workspace/jobs/{wo.pk}/labor/",
        {"hours": "2.00", "description": "644444444"},
        format="json",
    )
    assert api_resp.status_code == 400
    assert api_resp.json()["error"]["code"] == "invalid_description"
    assert WorkOrderLabor.objects.filter(work_order=wo).count() == 0

    # 3. Valid alphabetical description succeeds
    ok_resp = web_client.post(
        reverse("workspace:labor", args=[wo.pk]),
        {"hours": "2.00", "description": "Replaced faulty gasket and pressure tested"},
        follow=True,
    )
    assert ok_resp.status_code == 200
    assert WorkOrderLabor.objects.filter(work_order=wo).count() == 1


def test_bug002_job_detail_template_has_client_validation_and_csp_nonce(
    org_a, site_a1, make_asset, make_member
):
    wo, tech = _setup_started_work_order(org_a, site_a1, make_asset, make_member)
    client = Client()
    client.force_login(tech.user)
    resp = client.get(reverse("workspace:job_detail", args=[wo.pk]))

    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert 'id="onSiteLaborForm"' in html
    assert 'id="id_labor_description"' in html
    assert 'id="labor-description-error"' in html
    assert "<script nonce=" in html


# ---------------------------------------------------------------------------
# BUG-003: Automatic Session Idle Timeout & Auto Sign-Out
# ---------------------------------------------------------------------------

def test_bug003_idle_timeout_expires_session_and_redirects_to_login(
    client, org_a, make_member, settings
):
    settings.SESSION_IDLE_TIMEOUT_SECONDS = 300
    dispatcher = make_member(org_a, "idle-disp@alpha.test", "service_dispatcher")
    client.force_login(dispatcher.user)

    ok_resp = client.get("/app/")
    assert ok_resp.status_code == 200
    assert b'data-idle-timeout-ms="300000"' in ok_resp.content
    assert "_last_activity_ts" in client.session

    # Simulate user inactivity beyond timeout threshold
    session = client.session
    session["_last_activity_ts"] = int(time.time()) - 400
    session.save()

    expired_resp = client.get("/app/")
    assert expired_resp.status_code == 302
    assert expired_resp["Location"] == "/accounts/login/?logged_out=1&next=%2Fapp%2F"

    # Session must now be unauthenticated
    assert "_auth_user_id" not in client.session


def test_bug003_idle_timeout_returns_401_json_for_api_requests(
    client, org_a, make_member, settings
):
    settings.SESSION_IDLE_TIMEOUT_SECONDS = 300
    dispatcher = make_member(org_a, "idle-api@alpha.test", "service_dispatcher")
    client.force_login(dispatcher.user)

    session = client.session
    session["_last_activity_ts"] = int(time.time()) - 400
    session.save()

    resp = client.get("/api/v1/workorders/", HTTP_ACCEPT="application/json")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "session_expired"


def test_bug003_active_session_stays_authenticated_and_login_initializes_timestamp(
    client, org_a, make_member, settings
):
    settings.SESSION_IDLE_TIMEOUT_SECONDS = 300
    dispatcher = make_member(org_a, "active-disp@alpha.test", "service_dispatcher")
    dispatcher.user.set_password(PASSWORD)
    dispatcher.user.save(update_fields=["password"])

    login_get = client.get("/accounts/login/")
    assert login_get.status_code == 200
    login_post = client.post(
        "/accounts/login/",
        {"username": dispatcher.user.email, "password": PASSWORD},
    )
    assert login_post.status_code == 302
    assert "_last_activity_ts" in client.session

    # Activity within timeout window keeps user signed in and refreshes timestamp
    stale_ok_ts = int(time.time()) - 60
    session = client.session
    session["_last_activity_ts"] = stale_ok_ts
    session.save()

    resp = client.get("/app/")
    assert resp.status_code == 200
    assert client.session["_last_activity_ts"] > stale_ok_ts


def test_bug003_app_js_contains_idle_timer_and_auto_signout():
    js_text = (REPO_ROOT / "src" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "nexus_last_activity_at" in js_text
    assert "data-idle-timeout-ms" in js_text
    assert "performIdleSignOut" in js_text
    assert "checkIdleExpiration" in js_text
    assert "setInterval(checkIdleExpiration" in js_text
