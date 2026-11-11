"""Regression tests for the 2026-11-10 QA functional testing round I-R (3,644 cases).

Source report: FieldOps_Nexus_Complete_Functional_Testing_I-R.xlsx (8 failed TCs, 4 defects).

* DEF-001  Render DB schema drift made every dashboard snapshot endpoint 500
           -> idempotent repair migration ``dashboards/0003_fix_snapshot_schema``.
* DEF-002  the documented 10/min login throttle did not engage without Redis
           -> shared ``login_throttle`` counter cache (Redis or ``core_login_throttle``
              database table) with a per-process fallback that degrades open.
* DEF-003  OpenAPI contract drift: request downtime returned 200 + null body instead
           of 404 (TC_M05_050/131) and the portal request detail dropped ``work_order``
           while the request was unlinked (TC_M13_083/089).
* DEF-004  ``GET /api/v1/inspections/requirements/`` 500'd on ``PermissionDenied``
           (missing import, TC_M08_085).
* E2E_023  "complete work order" 500 looked QA-precondition-blocked, but was a real
           code defect: the documented ``summary`` alias reached the service layer as
           an unexpected kwarg (TypeError -> 500) -> popped after mapping.
"""
import importlib
import uuid
from datetime import timedelta

import pytest
from django.conf import settings
from django.core.cache import caches
from django.db import connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from apps.accounts.api import ClientIPScopedRateThrottle
from apps.accounts.models import User
from apps.incidents import services as incident_services
from apps.portal.models import PortalAccount, PortalAssetGrant
from apps.tenancy.models import Membership
from tests.conftest import PASSWORD
from tests.phase3_support import wo_in_progress

pytestmark = pytest.mark.django_db

_LOCMEM = "django.core.cache.backends.locmem.LocMemCache"
_DBCACHE = "django.core.cache.backends.db.DatabaseCache"


# --- DEF-001: snapshot schema repair migration is idempotent on a healthy schema ------------------------------

EXPECTED_SNAPSHOT_COLUMNS = {
    "id", "created_at", "updated_at", "snapshot_type", "section",
    "period_start", "period_end", "metrics", "notes",
    "created_by_id", "organization_id", "site_id",
}


@pytest.fixture
def snapshot_repair():
    mod = importlib.import_module("apps.dashboards.migrations.0003_fix_snapshot_schema")
    return mod.repair_reportsnapshot_schema


def _table_columns(table):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s", [table])
        return {row[0] for row in cursor.fetchall()}


def _has_constraint(table, name):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM pg_constraint WHERE conname = %s AND conrelid = %s::regclass",
                       [name, table])
        return cursor.fetchone() is not None


def test_def001_snapshot_repair_is_noop_on_healthy_schema(snapshot_repair, p3, as_user, owner_a):
    # The test database was built straight from the migration chain (healthy schema).
    # Re-applying the DEF-001 repair twice must succeed and change nothing observable.
    for _ in range(2):
        with connection.schema_editor() as editor:
            snapshot_repair(None, editor)

    assert EXPECTED_SNAPSHOT_COLUMNS <= _table_columns("dashboards_reportsnapshot")
    assert _has_constraint("dashboards_reportsnapshot", "uniq_report_snapshot_period")

    # Endpoints stay healthy after the repair re-ran (TC_M14_013 / TC_M14_033).
    c = as_user(owner_a, p3["org"])
    assert c.get("/api/v1/dashboards/snapshots/").status_code == 200
    payload = {
        "snapshot_type": "DAILY",
        "section": "OPERATIONS",
        "period_start": timezone.localdate().isoformat(),
        "period_end": timezone.localdate().isoformat(),
    }
    r = c.post("/api/v1/dashboards/snapshots/", payload, format="json")
    assert r.status_code == 201, r.content
    assert c.get(f"/api/v1/dashboards/snapshots/{r.json()['id']}/").status_code == 200


def test_def001_snapshot_repair_restores_missing_pieces(snapshot_repair, p3, owner_a):
    # Simulate the drifted Render state: drop the unique constraint and one column.
    with connection.cursor() as cursor:
        cursor.execute("ALTER TABLE dashboards_reportsnapshot DROP CONSTRAINT uniq_report_snapshot_period")
        cursor.execute("ALTER TABLE dashboards_reportsnapshot DROP COLUMN notes")
    assert "notes" not in _table_columns("dashboards_reportsnapshot")

    with connection.schema_editor() as editor:
        snapshot_repair(None, editor)

    assert "notes" in _table_columns("dashboards_reportsnapshot")
    assert _has_constraint("dashboards_reportsnapshot", "uniq_report_snapshot_period")
    # The model layer can still write through the repaired schema.
    from apps.dashboards import services as dashboard_services
    snap = dashboard_services.create_report_snapshot(
        p3["org"], snapshot_type="DAILY", section="OPERATIONS",
        period_start=timezone.localdate() - timedelta(days=1),
        period_end=timezone.localdate(), actor=owner_a)
    assert snap.pk is not None


# --- DEF-002: shared login-throttle counter cache ------------------------------------------------------------


def test_def002_login_throttle_cache_wiring():
    # Base settings always define the shared alias (Redis when configured, else the
    # database table created by core/0006_create_login_throttle_cache).
    from config.settings import base

    assert "login_throttle" in base.CACHES
    assert base.CACHES["login_throttle"]["BACKEND"] in (
        "django.core.cache.backends.redis.RedisCache", _DBCACHE)

    # The fallback table exists on any database the full migration chain ran on.
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'core_login_throttle'")
        assert cursor.fetchone() is not None

    # Test settings strip the alias: the throttle must notice and fall back, not crash.
    assert "login_throttle" not in settings.CACHES
    assert ClientIPScopedRateThrottle._shared_cache() is None


def test_def002_throttle_uses_shared_cache_when_configured():
    with override_settings(CACHES={
        "default": {"BACKEND": _LOCMEM},
        "login_throttle": {"BACKEND": _LOCMEM, "LOCATION": "shared-login-throttle"},
    }):
        shared = caches["login_throttle"]
        assert ClientIPScopedRateThrottle._shared_cache() is shared


def test_def002_throttle_enforces_limit_via_shared_database_cache():
    # The deployed configuration without Redis: login_throttle on the core_login_throttle
    # table. A burst from one client IP must hit 429 and the counter must live in the
    # shared backend (proving it is not the per-process fallback doing the work).
    new_rf = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "login": "5/min",
        },
    }
    api = APIClient(REMOTE_ADDR="203.0.113.201")
    try:
        with override_settings(
            REST_FRAMEWORK=new_rf,
            CACHES={
                "default": {"BACKEND": _LOCMEM},
                "login_throttle": {"BACKEND": _DBCACHE, "LOCATION": "core_login_throttle"},
            },
        ):
            api_settings.reload()
            statuses = [
                api.post(
                    "/api/v1/auth/token/",
                    {"email": "nonexistent@ir.test", "password": "wrong-password"},
                    format="json",
                ).status_code
                for _ in range(7)
            ]
            assert statuses == [401] * 5 + [429] * 2, statuses
            # DRF's SimpleRateThrottle key: throttle_<scope>_<ident>.
            assert caches["login_throttle"].get("throttle_login_203.0.113.201") is not None
    finally:
        api_settings.reload()


class _BrokenCache:
    """Cache backend whose every operation fails (shared store AND fallback down)."""

    def get(self, key, default=None):
        raise RuntimeError("cache backend down")

    def set(self, key, value, timeout=None):
        raise RuntimeError("cache backend down")


def test_def002_login_survives_total_counter_store_outage(make_org, monkeypatch):
    # A cache outage must never take authentication down: with both the shared store
    # and the in-process fallback failing, login degrades open instead of erroring.
    make_org("Throttle Outage Org", "owner@throttle-outage.test")
    owner = User.objects.get(email="owner@throttle-outage.test")
    broken = _BrokenCache()
    monkeypatch.setattr(ClientIPScopedRateThrottle, "_shared_cache", staticmethod(lambda: broken))
    monkeypatch.setattr("apps.accounts.api._FALLBACK_THROTTLE_CACHE", broken)

    r = APIClient().post(
        "/api/v1/auth/token/", {"email": owner.email, "password": PASSWORD}, format="json")
    assert r.status_code == 200, r.content
    assert "access" in r.json()


# --- DEF-003a: request downtime returns 404 while no record exists --------------------------------------------


def _new_request(p3):
    return {"asset": str(p3["asset"].pk), "title": "Round two downtime contract",
            "severity": "LOW", "service_impact": "NONE"}


def test_def003a_downtime_missing_record_returns_404_envelope(p3, as_user, owner_a):
    c = as_user(owner_a, p3["org"])
    r = c.post("/api/v1/service-requests/", _new_request(p3), format="json")
    assert r.status_code == 201, r.content
    sr_id = r.json()["id"]

    # No downtime record yet: 404 with the standard error envelope on both routes.
    for path in (f"/api/v1/requests/{sr_id}/downtime/", f"/api/v1/service-requests/{sr_id}/downtime/"):
        resp = c.get(path)
        assert resp.status_code == 404, (path, resp.status_code, resp.content)
        error = resp.json()["error"]
        assert error["code"] == "not_found"
        assert error["message"] == "No downtime record exists for this request."
        assert "request_id" in error

    # With a record the endpoint returns 200 and the documented body.
    from apps.incidents.models import ServiceRequest
    sr = ServiceRequest.objects.get(pk=sr_id)
    incident_services.set_downtime(sr, started_at=timezone.now(), ended_at=None,
                                   actor=owner_a, request=None)
    resp = c.get(f"/api/v1/requests/{sr.pk}/downtime/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["started_at"] is not None and body["ended_at"] is None

    # The OpenAPI contract documents the 404 (it used to promise only 200 + object).
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator().get_schema(request=None, public=True)
    responses = schema["paths"]["/api/v1/requests/{id}/downtime/"]["get"]["responses"]
    assert "200" in responses and "404" in responses


# --- DEF-003b: portal request detail always carries work_order -------------------------------------------------


def _portal_client(p3, make_member, email):
    m = make_member(p3["org"], email, "client_requester")
    account, _ = PortalAccount.objects.get_or_create(
        organization=p3["org"], membership=m,
        defaults={"company_name": "Round Two Client", "is_enabled": True})
    PortalAssetGrant.objects.get_or_create(
        organization=p3["org"], portal_account=account, asset=p3["asset"])
    return m, account


def test_def003b_portal_request_detail_always_includes_work_order(p3, as_user, owner_a, make_member):
    client_m, _account = _portal_client(p3, make_member, "round2.portal@alpha.test")
    papi = as_user(client_m.user, p3["org"])

    r = papi.post("/api/v1/portal/requests/",
                  {"title": "Round two portal contract", "asset": str(p3["asset"].pk),
                   "severity": "MEDIUM"}, format="json")
    assert r.status_code == 201, r.content
    sr_id = r.json()["id"]

    # Unlinked request: work_order must still be present (null), not absent.
    r = papi.get(f"/api/v1/portal/requests/{sr_id}/")
    assert r.status_code == 200, r.content
    body = r.json()
    assert "work_order" in body
    assert body["work_order"] is None

    # Link a work order: triage -> approve -> convert, then re-read the detail.
    from apps.incidents.models import ServiceRequest
    sr = ServiceRequest.objects.get(pk=sr_id)
    incident_services.transition(sr, action="triage", actor=owner_a, request=None)
    incident_services.transition(sr, action="approve", actor=owner_a, request=None)
    owner_m = Membership.objects.unscoped().get(organization=p3["org"], user=owner_a)
    wo = incident_services.create_work_order_for_request(
        sr, actor=owner_a, membership=owner_m, request=None)

    r = papi.get(f"/api/v1/portal/requests/{sr_id}/")
    assert r.status_code == 200, r.content
    detail = r.json()["work_order"]
    assert detail is not None
    assert detail["order_number"] == wo.order_number

    # The OpenAPI schema documents work_order on the detail serializer as nullable.
    from drf_spectacular.generators import SchemaGenerator
    schema = SchemaGenerator().get_schema(request=None, public=True)
    props = schema["components"]["schemas"]["PortalServiceRequestDetail"]["properties"]
    assert "work_order" in props


# --- DEF-004: inspection requirements endpoint contract -------------------------------------------------------


def test_def004_inspection_requirements_contract(p3, as_user, owner_a, make_member):
    wo = wo_in_progress(p3)
    c = as_user(owner_a, p3["org"])

    # Happy path (TC_M08_085 owner flow): documented object shape, never a 500.
    r = c.get(f"/api/v1/inspections/requirements/?work_order={wo.pk}")
    assert r.status_code == 200, r.content
    body = r.json()
    assert body["work_order"] == str(wo.pk)
    assert isinstance(body["blockers"], list) and isinstance(body["checklists"], list)

    # Missing parameter -> clean 400 envelope.
    r = c.get("/api/v1/inspections/requirements/")
    assert r.status_code == 400, r.content
    assert r.json()["error"]["code"] == "validation_failed"

    # Malformed parameter -> clean 400 envelope.
    r = c.get("/api/v1/inspections/requirements/?work_order=not-a-uuid")
    assert r.status_code == 400, r.content
    assert r.json()["error"]["code"] == "validation_failed"

    # Unknown work order -> clean 404 envelope.
    r = c.get(f"/api/v1/inspections/requirements/?work_order={uuid.uuid4()}")
    assert r.status_code == 404, r.content

    # Portal client -> 403 envelope (used to 500 with a NameError).
    client_m, _account = _portal_client(p3, make_member, "round2.requirements@alpha.test")
    papi = as_user(client_m.user, p3["org"])
    r = papi.get(f"/api/v1/inspections/requirements/?work_order={wo.pk}")
    assert r.status_code == 403, r.content
    error = r.json()["error"]
    assert error["code"] == "permission_denied"
    assert "Portal clients cannot access inspection requirements." in error["message"]


# --- E2E_023: completing an in-progress work order ------------------------------------------------------------


def test_e2e_023_complete_in_progress_work_order_with_summary(p3, as_user):
    from apps.workorders import services as wos
    from apps.workorders.checklist_adapter import record_external_validation

    wo = wo_in_progress(p3)
    api = as_user(p3["tech"].user, p3["org"])

    # Preconditions not met: documented 409 envelope, never the 500 E2E_023 saw.
    r = api.post(f"/api/v1/work-orders/{wo.pk}/complete/",
                 {"summary": "Replaced the belt and verified alignment"}, format="json")
    assert r.status_code == 409, r.content
    assert r.json()["error"]["code"] == "checklist_incomplete"

    # Satisfy the documented preconditions (checklist validation, then labor)...
    if wo.checklist_required and wo.checklist_status != "COMPLETED":
        wo.checklist_instance_ref = f"round2-e2e-023:{wo.pk}"
        record_external_validation(wo, status="COMPLETED", validation_state="VALID",
                                   completed_at=timezone.now())
        wo.save(update_fields=["checklist_instance_ref", "checklist_status",
                               "checklist_validation_state", "checklist_completed_at",
                               "checklist_validated_at", "updated_at"])
    wos.record_labor(wo, membership=p3["tech"], actor=p3["tech"].user,
                     work_date=timezone.localdate(), hours="1.5",
                     description="Completed servicing")

    # ...and the QA payload (the documented summary field) completes the work order.
    r = api.post(f"/api/v1/work-orders/{wo.pk}/complete/",
                 {"summary": "Replaced the belt and verified alignment"}, format="json")
    assert r.status_code == 200, r.content
    assert r.json()["status"] == "COMPLETED"
    assert r.json()["resolution_notes"] == "Replaced the belt and verified alignment"
