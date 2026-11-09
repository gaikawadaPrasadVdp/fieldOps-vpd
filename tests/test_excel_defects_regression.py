"""Regression test suite for all functional testing defects DEF-001 through DEF-015
and defect-blocked M04 / M14 workflows from the QA Functional Testing I-R report."""
from datetime import date, timedelta
from pathlib import Path
import re
import uuid

from django.conf import settings
from django.db import IntegrityError
from django.test import Client, override_settings
from django.utils import timezone
import pytest
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.forms import AssetForm
from apps.assets.models import Asset
from apps.core.exceptions import Conflict
from apps.inventory import services as inv
from apps.inventory.models import Part
from apps.maintenance import services as pm
from apps.portal.models import PortalAccount
from apps.rbac import services as rbac
from apps.sites.models import Site
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership, Organization
from apps.workspace import services as ws_services
from tests.phase3_support import wo_in_progress
from tests.pm_support import make_plan


# --- DEF-001 + M04 unblocked lifecycle -------------------------------------------------------------------------------


@pytest.mark.django_db
def test_def001_schedule_error_discrimination_and_full_lifecycle(pm_, as_user):
    # 1. _is_duplicate_schedule_error only treats unique schedule constraints as duplicate_schedule
    assert pm._is_duplicate_schedule_error(IntegrityError('duplicate key value violates unique constraint "uniq_time_schedule_per_plan"'))
    assert not pm._is_duplicate_schedule_error(IntegrityError('null value in column "legacy_req_col" violates not-null constraint'))

    plan = make_plan(pm_)
    c = as_user(pm_["planner"].user, pm_["org"])

    # Create TIME schedule -> 201
    sched_payload = {"trigger_type": "TIME", "frequency": "MONTHLY", "interval_count": 1, "start_date": "2026-03-10"}
    r_create = c.post(f"/api/v1/maintenance-plans/{plan.pk}/schedules/", sched_payload, format="json")
    assert r_create.status_code == 201, r_create.content
    sid = r_create.json()["id"]

    # Real duplicate schedule STILL returns 409 duplicate_schedule
    r_dup = c.post(f"/api/v1/maintenance-plans/{plan.pk}/schedules/", sched_payload, format="json")
    assert r_dup.status_code == 409
    assert r_dup.json()["error"]["code"] == "duplicate_schedule"

    # Unblocked M04 cases: TC_M04_072 PATCH, TC_M04_082 disable, TC_M04_087 enable, TC_M04_092/093 generate,
    # plus TC_M04_013/067/077 GET detail/cycles
    assert c.get(f"/api/v1/maintenance-schedules/{sid}/").status_code == 200
    r_patch = c.patch(f"/api/v1/maintenance-schedules/{sid}/", {"interval_count": 2}, format="json")
    assert r_patch.status_code == 200
    assert r_patch.json()["interval_count"] == 2

    r_dis = c.post(f"/api/v1/maintenance-schedules/{sid}/disable/")
    assert r_dis.status_code == 200 and r_dis.json()["is_active"] is False

    r_en = c.post(f"/api/v1/maintenance-schedules/{sid}/enable/")
    assert r_en.status_code == 200 and r_en.json()["is_active"] is True

    r_gen = c.post(f"/api/v1/maintenance-schedules/{sid}/generate/")
    assert r_gen.status_code == 201, r_gen.content
    assert r_gen.json()["work_order"] is not None
    cycle_id = r_gen.json()["id"]
    assert c.get(f"/api/v1/maintenance-cycles/{cycle_id}/").status_code == 200

    r_cycles = c.get(f"/api/v1/maintenance-schedules/{sid}/cycles/")
    assert r_cycles.status_code == 200
    assert r_cycles.json()["count"] >= 1


# --- DEF-002: invite / resend / platform user creation & Celery resilience -------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_def002_invites_and_platform_users_survive_broker_failure(monkeypatch, make_org, platform_admin, as_user):
    org = make_org("Broker Down Org", "owner@brokerdown.test")
    owner = User.objects.get(email="owner@brokerdown.test")
    tech_role = rbac.system_role_by_key(org, "technician")

    def boom(*args, **kwargs):
        raise RuntimeError("Redis broker unavailable")

    monkeypatch.setattr("apps.accounts.tasks.send_invitation_email.delay", boom)
    monkeypatch.setattr("apps.notifications.tasks.send_notification_email.delay", boom)

    c_owner = as_user(owner, org)
    # 1. POST /members/
    r1 = c_owner.post(
        "/api/v1/members/",
        {"email": "m1@brokerdown.test", "full_name": "M1 User", "role_ids": [str(tech_role.pk)]},
        format="json",
    )
    assert r1.status_code == 201, r1.content
    m1_id = r1.json()["id"]

    # 2. POST /users/ (alias) with long first_name + last_name (> 150 chars sliced cleanly)
    r2 = c_owner.post(
        "/api/v1/users/",
        {
            "email": "m2@brokerdown.test",
            "first_name": "A" * 100,
            "last_name": "B" * 100,
            "role_ids": [str(tech_role.pk)],
        },
        format="json",
    )
    assert r2.status_code == 201, r2.content
    assert len(r2.json()["full_name"]) <= 150
    m2_id = r2.json()["id"]

    # 3. POST /members/{id}/resend/ & /users/{id}/resend/
    assert c_owner.post(f"/api/v1/members/{m1_id}/resend/").status_code == 202
    assert c_owner.post(f"/api/v1/users/{m2_id}/resend/").status_code == 202

    # 4. Invalid email raises clean 400 validation error instead of NameError
    r_bad_email = c_owner.post(
        "/api/v1/members/",
        {"email": "not-an-email", "full_name": "Bad", "role_ids": [str(tech_role.pk)]},
        format="json",
    )
    assert r_bad_email.status_code == 400

    # 5. Platform admin POST /platform/organizations/{id}/users/ & /platform/users/
    c_admin = as_user(platform_admin)
    r_org_user = c_admin.post(
        f"/api/v1/platform/organizations/{org.pk}/users/",
        {"email": "porg@brokerdown.test", "full_name": "P Org User", "role": "technician"},
        format="json",
    )
    assert r_org_user.status_code == 201, r_org_user.content

    r_plat_user = c_admin.post(
        "/api/v1/platform/users/",
        {"email": "puser@brokerdown.test", "full_name": "P User", "organization": str(org.pk), "role": "technician"},
        format="json",
    )
    assert r_plat_user.status_code == 201, r_plat_user.content

    # Malformed organization UUID on /platform/users/ -> 400 (not 500)
    r_bad_org = c_admin.post(
        "/api/v1/platform/users/",
        {"email": "badorg@brokerdown.test", "full_name": "Bad Org", "organization": "not-a-uuid"},
        format="json",
    )
    assert r_bad_org.status_code == 400


# --- DEF-003 & DEF-004: Dashboard snapshots & organization permanent deletion ----------------------------------------


@pytest.mark.django_db
def test_def003_def004_snapshots_and_org_deletion(p3, make_org, platform_admin, as_user):
    org = p3["org"]
    c_ops = as_user(p3["ops"].user, org)
    c_tech = as_user(p3["tech"].user, org)

    # DEF-004: GET list, POST generate, GET detail, 404 on unknown ID, 403 on unpermitted user (TC_M14_016/018/019)
    assert c_ops.get("/api/v1/dashboards/snapshots/").status_code == 200
    today = timezone.localdate()
    payload = {
        "snapshot_type": "DAILY",
        "section": "OPERATIONS",
        "period_start": (today - timedelta(days=2)).isoformat(),
        "period_end": (today - timedelta(days=1)).isoformat(),
    }
    r_post = c_ops.post("/api/v1/dashboards/snapshots/", payload, format="json")
    assert r_post.status_code == 201, r_post.content
    snap_id = r_post.json()["id"]

    assert c_ops.get(f"/api/v1/dashboards/snapshots/{snap_id}/").status_code == 200
    assert c_ops.get(f"/api/v1/dashboards/snapshots/{uuid.uuid4()}/").status_code == 404
    assert c_tech.post("/api/v1/dashboards/snapshots/", payload, format="json").status_code == 403

    # DEF-003: Workspace shift/profile + SR + snapshots exist; permanent delete + DELETE /platform/organizations/{id}/ work
    ws_services.get_or_create_technician_profile(p3["tech"])
    target_org = make_org("Disposable QA Org", "dispose@qa.test")
    disp_owner = Membership.objects.unscoped().get(organization=target_org)
    ws_services.get_or_create_technician_profile(disp_owner)

    c_admin = as_user(platform_admin)
    r_del = c_admin.delete(f"/api/v1/platform/organizations/{target_org.pk}/")
    assert r_del.status_code == 200

    target_id = target_org.pk
    tenancy.permanently_delete_organization(target_org, actor=platform_admin)
    assert not Organization.objects.filter(pk=target_id).exists()


# --- DEF-005 & DEF-006: Auth long email & client-IP login throttling -------------------------------------------------


@pytest.mark.django_db
def test_def005_def006_auth_long_email_400_and_login_throttle_429(client):
    # DEF-005: 5000-char email must return 400 cleanly, never 500 DataError
    api = APIClient()
    r_long = api.post(
        "/api/v1/auth/token/",
        {"email": ("a" * 4990) + "@example.com", "password": "wrong-password"},
        format="json",
    )
    assert r_long.status_code == 400

    # DEF-006: burst from same client IP triggers 429 regardless of locmem rate config
    new_rf = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "login": "5/min",
        },
    }
    try:
        with override_settings(REST_FRAMEWORK=new_rf, TRUSTED_PROXY_COUNT=1):
            api_settings.reload()
            statuses = []
            for _ in range(7):
                r = api.post(
                    "/api/v1/auth/token/",
                    {"email": "nonexistent@example.com", "password": "wrong-password"},
                    format="json",
                    HTTP_X_FORWARDED_FOR="198.51.100.77",
                )
                statuses.append(r.status_code)
            assert 401 in statuses and 429 in statuses, statuses
    finally:
        api_settings.reload()


# --- DEF-007: Inventory UI accepts alphanumeric part numbers and EA unit ----------------------------------------------


@pytest.mark.django_db
def test_def007_part_ui_accepts_alphanumeric_part_number_and_ea_unit(inv_):
    stores = inv_["stores"]
    c = Client()
    c.force_login(stores.user)

    r_get = c.get("/app/inventory/parts/new/")
    assert r_get.status_code == 200
    assert "Part number must contain only numbers" not in r_get.content.decode()

    r_post = c.post(
        "/app/inventory/parts/new/",
        {
            "part_number": "FT-UI-100",
            "name": "Filter Cartridge",
            "unit": "EA",
            "min_stock": "2",
            "max_stock": "10",
            "reorder_quantity": "4",
        },
    )
    assert r_post.status_code == 302
    assert Part.objects.filter(organization=inv_["org"], part_number="FT-UI-100", unit="EA").exists()


# --- DEF-008 & DEF-009: Workspace defects & technician lookup ---------------------------------------------------------


@pytest.mark.django_db
def test_def008_def009_workspace_defects_and_technician_lookup(p3, owner_a, as_user):
    wo = wo_in_progress(p3)
    c_tech = as_user(p3["tech"].user, p3["org"])
    c_ops = as_user(p3["ops"].user, p3["org"])
    c_owner = as_user(owner_a, p3["org"])

    # DEF-008: POST defect succeeds 201 and duplicate returns 409 with details + duplicates + request_id
    payload = {
        "title": "Auxiliary fan bearing overheating defect",
        "asset_id": str(p3["asset2"].pk),
        "kind": "INCIDENT",
        "severity": "HIGH",
        "service_impact": "DEGRADED",
        "description": "Bearing temperature above threshold during inspection.",
        "failure_category": "Mechanical",
    }
    r1 = c_tech.post(f"/api/v1/workspace/jobs/{wo.pk}/defects/", payload, format="json")
    assert r1.status_code == 201, r1.content

    r2 = c_tech.post(f"/api/v1/workspace/jobs/{wo.pk}/defects/", payload, format="json")
    assert r2.status_code == 409
    err_body = r2.json()["error"]
    assert err_body["code"] == "duplicate_incident_detected"
    assert isinstance(err_body["details"], dict)
    assert len(err_body["duplicates"]) >= 1
    assert "request_id" in err_body

    # DEF-009: ID returned by GET /workspace/technicians/ works on detail, PATCH, and availability
    r_list = c_ops.get("/api/v1/workspace/technicians/")
    assert r_list.status_code == 200
    items = r_list.json()
    assert len(items) >= 1
    tech_id = items[0]["id"]

    assert c_ops.get(f"/api/v1/workspace/technicians/{tech_id}/").status_code == 200
    r_patch = c_owner.patch(
        f"/api/v1/workspace/technicians/{tech_id}/",
        {"notes": "Certified HVAC tech"},
        format="json",
    )
    assert r_patch.status_code == 200 and r_patch.json()["notes"] == "Certified HVAC tech"

    r_avail = c_tech.post(
        f"/api/v1/workspace/technicians/{tech_id}/availability/",
        {"availability_status": "ON_LEAVE"},
        format="json",
    )
    assert r_avail.status_code == 200 and r_avail.json()["availability_status"] == "ON_LEAVE"

    assert c_ops.get("/api/v1/workspace/technicians/not-a-uuid/").status_code == 404


# --- DEF-010: Asset UI long name (> 200 chars) not truncated & rejected -----------------------------------------------


@pytest.mark.django_db
def test_def010_asset_ui_does_not_truncate_over_200_char_name(p3, owner_a):
    form = AssetForm(sites=Site.objects.filter(organization=p3["org"]), org=p3["org"])
    assert "maxlength" not in form.fields["name"].widget.attrs

    c = Client()
    c.force_login(owner_a)
    assert 'name="name"' in c.get("/app/assets/new/").content.decode()
    long_name = "CentrifugalPump" * 30  # > 400 chars
    before = Asset.objects.filter(organization=p3["org"]).count()
    r = c.post(
        "/app/assets/new/",
        {
            "asset_tag": "AST-LONG-400",
            "name": long_name,
            "category": str(p3["asset"].category_id),
            "site": str(p3["site"].pk),
        },
    )
    assert r.status_code == 400
    assert Asset.objects.filter(organization=p3["org"]).count() == before

    app_js = Path(settings.BASE_DIR, "static", "js", "app.js").read_text(encoding="utf-8")
    assert "Asset name cannot exceed 200 characters." in app_js


# --- DEF-011: Undocumented HTTP methods return 405 before 403 --------------------------------------------------------


@pytest.mark.django_db
def test_def011_method_not_allowed_returns_405_before_permission_denied(p3, make_member, as_user):
    org = p3["org"]
    wo = wo_in_progress(p3)
    client_role_m = make_member(org, "client_def011@alpha.test", "client_requester")
    PortalAccount.objects.get_or_create(
        organization=org,
        membership=client_role_m,
        defaults={"company_name": "Client Co", "is_enabled": True},
    )
    shift = ws_services.create_shift(
        org,
        code="D11-SHIFT",
        name="Day Shift",
        start_time="08:00",
        end_time="16:00",
        actor=p3["ops"].user,
    )
    prof, _ = ws_services.get_or_create_technician_profile(p3["tech"])

    # Authenticated users (even unpermitted auditors) MUST receive 405 for unsupported PUT
    c_reader = as_user(p3["reader"].user, org)
    c_ops = as_user(p3["ops"].user, org)
    c_client = as_user(client_role_m.user, org)

    for api_client, path in [
        (c_reader, "/api/v1/workspace/capacity/"),
        (c_reader, "/api/v1/workspace/jobs/"),
        (c_reader, f"/api/v1/workspace/jobs/{wo.pk}/"),
        (c_reader, f"/api/v1/workspace/jobs/{wo.pk}/defects/"),
        (c_reader, "/api/v1/workspace/profile/availability/"),
        (c_reader, "/api/v1/workspace/shifts/"),
        (c_reader, f"/api/v1/workspace/shifts/{shift.pk}/"),
        (c_reader, "/api/v1/workspace/technicians/"),
        (c_reader, f"/api/v1/workspace/technicians/{prof.pk}/"),
        (c_reader, f"/api/v1/workspace/technicians/{prof.pk}/availability/"),
        (c_reader, "/api/v1/sla-metrics/"),
        (c_reader, "/api/v1/dashboards/"),
        (c_reader, "/api/v1/dashboards/snapshots/"),
        (c_reader, "/api/v1/dashboards/operations/"),
        (c_client, "/api/v1/portal/me/"),
        (c_client, "/api/v1/portal/assets/"),
        (c_client, "/api/v1/portal/requests/"),
        (c_ops, "/api/v1/sla-metrics/"),
    ]:
        r = api_client.put(path, {}, format="json")
        assert r.status_code == 405, f"PUT {path} returned {r.status_code}: {r.content}"


# --- DEF-012, DEF-013 & DEF-014: OpenAPI schema fidelity & binary error responses -------------------------------------


@pytest.mark.django_db
def test_def012_def013_def014_schema_contracts_and_binary_auth_errors(p3, make_member, as_user):
    from drf_spectacular.generators import SchemaGenerator
    from apps.contracts import services as contract_services

    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    # DEF-014: no undocumented path parameters anywhere
    for path, path_item in paths.items():
        placeholders = set(re.findall(r"\{([^}]+)\}", path))
        for prm in path_item.get("parameters", []):
            if prm.get("in") == "path":
                assert prm.get("name") in placeholders, (path, prm)
        for method, op in path_item.items():
            if isinstance(op, dict):
                for prm in op.get("parameters", []):
                    if prm.get("in") == "path":
                        assert prm.get("name") in placeholders, (path, method, prm)

    # DEF-012: spot-check fixed response schemas
    assert paths["/api/v1/sites/{id}/tree/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    assert paths["/api/v1/work-orders/{id}/events/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    assert paths["/api/v1/coverage/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/CoverageResult")
    assert paths["/api/v1/portal/me/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/PortalMe")
    assert paths["/api/v1/work-orders/{id}/closure/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith("/WorkOrderClosureResponse")
    assert "text/csv" in paths["/api/v1/coverage-agreements/export/"]["get"]["responses"]["200"]["content"]
    assert "application/pdf" in paths["/api/v1/coverage-agreements/{id}/download/"]["get"]["responses"]["200"]["content"]
    assert "application/zip" in paths["/api/v1/audit-logs/evidence/"]["get"]["responses"]["200"]["content"]
    for documented_get_path in (
        "/api/v1/requests/check-duplicate/",
        "/api/v1/service-requests/check-duplicate/",
        "/api/v1/work-orders/{id}/materials/",
        "/api/v1/workspace/jobs/",
        "/api/v1/workspace/shifts/",
        "/api/v1/workspace/technicians/",
        "/api/v1/dashboards/snapshots/",
        "/api/v1/dashboards/snapshots/{id}/",
    ):
        get_resp = paths[documented_get_path]["get"]["responses"]["200"]
        assert "application/json" in get_resp.get("content", {}), documented_get_path

    schemas = schema["components"]["schemas"]
    assert schemas["Asset"]["properties"]["zone_name"]["nullable"] is True
    assert schemas["Inspection"]["properties"]["work_order_number"]["nullable"] is True
    assert schemas["Finding"]["properties"]["work_order_number"]["nullable"] is True
    assert schemas["Cycle"]["properties"]["work_order_number"]["nullable"] is True
    assert schemas["Cycle"]["properties"]["work_order_status"]["nullable"] is True

    # DEF-013: Unauthenticated export/download endpoints return JSON 401 (never "error" text/html)
    provider = contract_services.create_provider(p3["org"], name="Acme OEM", actor=p3["ops"].user)
    ag = contract_services.create_agreement(
        p3["org"],
        kind="WARRANTY",
        reference="WAR-DEF013",
        title="Pump Warranty",
        provider=provider,
        site=p3["site"],
        start_date=date.today() - timedelta(days=1),
        end_date=date.today() + timedelta(days=30),
        assets=[p3["asset"]],
        actor=p3["ops"].user,
    )
    anon = APIClient()
    for url in (
        "/api/v1/coverage-agreements/export/",
        f"/api/v1/coverage-agreements/{ag.pk}/download/",
        "/api/v1/warranties/export/",
        f"/api/v1/warranties/{ag.pk}/download/",
    ):
        r = anon.get(url)
        assert r.status_code == 401
        assert "application/json" in r["Content-Type"]
        body = r.json()
        assert "error" in body

    # Real runtime checks on DEF-012 endpoints match schemas
    c_ops = as_user(p3["ops"].user, p3["org"])
    assert isinstance(c_ops.get(f"/api/v1/sites/{p3['site'].pk}/tree/").json(), list)
    r_tree = c_ops.get(f"/api/v1/assets/{p3['asset'].pk}/tree/").json()
    assert "path" in r_tree and "tree" in r_tree
    r_cov = c_ops.get(f"/api/v1/coverage/?asset={p3['asset'].pk}").json()
    assert isinstance(r_cov, dict) and r_cov["covered"] is True

    client_m = make_member(p3["org"], "portal_me@alpha.test", "client_requester")
    PortalAccount.objects.get_or_create(
        organization=p3["org"],
        membership=client_m,
        defaults={"company_name": "Portal Client", "is_enabled": True},
    )
    r_me = as_user(client_m.user, p3["org"]).get("/api/v1/portal/me/")
    assert r_me.status_code == 200
    me_json = r_me.json()
    assert "user" in me_json and "organization" in me_json


# --- DEF-015: Work-order part must be RESERVED before ISSUED ----------------------------------------------------------


@pytest.mark.django_db
def test_def015_issue_requires_reservation_before_issue(inv_, as_user):
    inv.receive(inv_["wh"], inv_["part"], 10, actor=inv_["stores"].user)
    wo = wo_in_progress(inv_)
    line = inv.request_part(wo, inv_["part"], 3, actor=inv_["tech"].user, membership=inv_["tech"])

    # UI does not show Issue button while REQUESTED
    c_ui = Client()
    c_ui.force_login(inv_["stores"].user)
    html = c_ui.get(f"/app/work-orders/{wo.pk}/parts/").content.decode()
    assert "Reserve" in html
    assert 'btn-primary">Issue<' not in html

    # Direct API POST /issue/ on REQUESTED line returns 409 reservation_required
    c_stores = as_user(inv_["stores"].user, inv_["org"])
    r_bad = c_stores.post(
        f"/api/v1/work-order-parts/{line.pk}/issue/",
        {"warehouse": str(inv_["wh"].pk), "quantity": "2"},
        format="json",
    )
    assert r_bad.status_code == 409
    assert r_bad.json()["error"]["code"] == "reservation_required"

    # After reserving -> ISSUED succeeds
    r_res = c_stores.post(
        f"/api/v1/work-order-parts/{line.pk}/reserve/",
        {"warehouse": str(inv_["wh"].pk), "quantity": "2"},
        format="json",
    )
    assert r_res.status_code == 200 and r_res.json()["status"] == "RESERVED"

    r_ok = c_stores.post(
        f"/api/v1/work-order-parts/{line.pk}/issue/",
        {"warehouse": str(inv_["wh"].pk), "quantity": "2"},
        format="json",
    )
    assert r_ok.status_code == 200 and r_ok.json()["status"] == "ISSUED"
