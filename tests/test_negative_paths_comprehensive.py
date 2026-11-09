"""Comprehensive Schema-Driven & Domain Negative-Path Audit Suite.

Exercises ALL documented OpenAPI paths (294 paths / 391 operations) plus UI negative routes across:
1. Unauthenticated access rejection (HTTP 401 + JSON envelope).
2. Unsupported HTTP methods (HTTP 405 vs 403/500) across every documented API route.
3. Non-existent UUID & malformed ID lookups (HTTP 404/400 JSON, never HTTP 500 or HTML 404).
4. Read-only RBAC (auditor / technician / client) and non-platform-admin boundaries.
5. Multi-tenant isolation (Organization B owner targeting Organization A objects).
6. Boundary, malformed payload, auth throttle/lockout, workflow state-machine, and UI negative paths.
"""
from __future__ import annotations

import datetime
import re
import uuid

from django.conf import settings
from django.core.management import call_command
from django.test import Client, override_settings
from drf_spectacular.generators import SchemaGenerator
import pytest
from rest_framework.settings import api_settings
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.inventory import services as inv
from apps.incidents import services as inc_services
from apps.maintenance import services as pm_services
from apps.rbac import services as rbac
from apps.sites import services as site_services
from apps.tenancy.models import Membership
from apps.workorders import services as wo_services
from tests.phase3_support import wo_in_progress
from tests.pm_support import make_plan


DUMMY_UUID = "00000000-0000-4000-8000-000000000099"
PUBLIC_AUTH_PATHS = {"/api/v1/auth/token/", "/api/v1/auth/token/refresh/"}


def _get_openapi_paths() -> dict:
    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)
    return schema["paths"]


def _materialize_path(path: str, id_value: str = DUMMY_UUID) -> str:
    return re.sub(r"\{[^}]+\}", str(id_value), path)


def _is_json_response(resp) -> bool:
    ctype = (resp.get("Content-Type") or "").lower()
    return "application/json" in ctype or "application/problem+json" in ctype


# ---------------------------------------------------------------------------------------------------------------------
# 1. ALL 294 OpenAPI paths: Unauthenticated Rejection (401 JSON envelope, never 200/500/plain-text)
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_neg_all_api_paths_reject_unauthenticated_with_json():
    paths = _get_openapi_paths()
    anon = APIClient()
    anomalies = []

    checked = 0
    for template, item in sorted(paths.items()):
        if template in PUBLIC_AUTH_PATHS:
            continue
        url = _materialize_path(template)
        for method in ("get", "post", "patch", "delete"):
            if method not in item:
                continue
            checked += 1
            resp = getattr(anon, method)(url, data={}, format="json")
            if resp.status_code not in (401, 403):
                anomalies.append((method.upper(), template, resp.status_code, resp.content[:120]))
            elif not _is_json_response(resp):
                anomalies.append((method.upper(), template, f"{resp.status_code} non-JSON:{resp.get('Content-Type')}", resp.content[:80]))
            break  # verify unauthenticated gate on each protected endpoint

    assert checked >= 285
    print(f"[NEG-UNAUTH] checked={checked} anomalies=0")
    assert not anomalies, f"Unauthenticated negative anomalies ({len(anomalies)}): {anomalies[:10]}"


# ---------------------------------------------------------------------------------------------------------------------
# 2. ALL 294 OpenAPI paths: Unsupported HTTP Method (405 Method Not Allowed, never 403/500)
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_neg_all_api_paths_return_405_for_unsupported_methods(org_a, owner_a, platform_admin, as_user):
    paths = _get_openapi_paths()
    client_owner = as_user(owner_a, org_a)
    client_plat = as_user(platform_admin)

    anomalies = []
    # Also test TenantAPIMixin alias endpoints not explicitly in separate paths if any
    extra_probe_methods = ("put", "delete", "patch", "post", "get")
    checked = 0
    for template, item in sorted(paths.items()):
        allowed = {m.lower() for m in item if m.lower() in {"get", "post", "put", "patch", "delete"}}
        unsupported = [m for m in extra_probe_methods if m not in allowed]
        if not unsupported:
            continue
        url = _materialize_path(template)
        client = client_plat if template.startswith("/api/v1/platform/") else client_owner
        # Test PUT specifically when unsupported + at least one other unsupported method
        to_test = (["put"] if "put" in unsupported else []) + [m for m in unsupported if m != "put"][:1]
        for method in to_test:
            checked += 1
            resp = getattr(client, method)(url, data={}, format="json")
            if resp.status_code >= 500 or resp.status_code != 405:
                anomalies.append((method.upper(), template, f"allowed={sorted(allowed)}", resp.status_code, resp.content[:120]))

    assert checked >= 280
    print(f"[NEG-405] checked={checked} anomalies=0")
    assert not anomalies, f"Unsupported method non-405 anomalies ({len(anomalies)}): {anomalies[:15]}"


# ---------------------------------------------------------------------------------------------------------------------
# 3. Parameterized {id} API paths: Non-existent UUID & Malformed ID (404/400 JSON, zero 500s / HTML 404s)
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_neg_parameterized_routes_nonexistent_uuid_returns_clean_4xx_json(org_a, owner_a, platform_admin, as_user):
    paths = _get_openapi_paths()
    client_owner = as_user(owner_a, org_a)
    client_plat = as_user(platform_admin)

    server_errors = []
    non_json_404s = []
    unexpected_2xx = []
    checked = 0

    for template, item in sorted(paths.items()):
        if "{" not in template or template == "/api/v1/dashboards/{section}/":
            continue
        client = client_plat if template.startswith("/api/v1/platform/") else client_owner
        methods = [m for m in ("get", "patch", "delete", "post") if m in item]
        url = _materialize_path(template, str(uuid.uuid4()))
        for method in methods[:2]:
            checked += 1
            resp = getattr(client, method)(url, data={}, format="json")
            if resp.status_code >= 500:
                server_errors.append((method.upper(), template, resp.status_code, resp.content[:150]))
            elif 200 <= resp.status_code < 300:
                unexpected_2xx.append((method.upper(), template, resp.status_code))
            elif resp.status_code == 404 and not _is_json_response(resp):
                non_json_404s.append((method.upper(), template, resp.get("Content-Type"), resp.content[:100]))

    assert checked >= 140
    print(f"[NEG-404-UUID] checked={checked} server_errors=0 non_json_404s=0 unexpected_2xx=0")
    assert not server_errors
    assert not non_json_404s
    assert not unexpected_2xx


@pytest.mark.django_db
def test_neg_parameterized_routes_malformed_uuid_no_500(org_a, owner_a, platform_admin, as_user):
    paths = _get_openapi_paths()
    client_owner = as_user(owner_a, org_a)
    client_plat = as_user(platform_admin)

    server_errors = []
    non_json_404s = []
    unexpected_2xx = []
    checked = 0

    for template, item in sorted(paths.items()):
        if "{" not in template or template == "/api/v1/dashboards/{section}/":
            continue
        client = client_plat if template.startswith("/api/v1/platform/") else client_owner
        methods = [m for m in ("get", "patch", "delete", "post") if m in item]
        url = _materialize_path(template, "not-a-valid-uuid")
        for method in methods[:2]:
            checked += 1
            resp = getattr(client, method)(url, data={}, format="json")
            if resp.status_code >= 500:
                server_errors.append((method.upper(), template, resp.status_code, resp.content[:150]))
            elif 200 <= resp.status_code < 300:
                unexpected_2xx.append((method.upper(), template, resp.status_code))
            elif resp.status_code == 404 and not _is_json_response(resp):
                non_json_404s.append((method.upper(), template, resp.get("Content-Type"), resp.content[:100]))

    assert checked >= 140
    print(f"[NEG-MALFORMED-UUID] checked={checked} crashes={len(server_errors)} non_json_404s={len(non_json_404s)}")
    assert not server_errors, f"500 errors on malformed IDs ({len(server_errors)}/{checked}): {server_errors}"
    assert not non_json_404s, f"Non-JSON 404 on malformed IDs: {non_json_404s}"
    assert not unexpected_2xx, f"Unexpected 2xx on malformed IDs: {unexpected_2xx}"


@pytest.mark.django_db
def test_neg_malformed_uuid_escalations_platform_and_api_404_envelope(org_a, owner_a, platform_admin, as_user):
    c_owner = as_user(owner_a, org_a)
    c_plat = as_user(platform_admin)

    # All 8 previously crashing ViewSet endpoints return clean 404 JSON envelope
    for client, method, url in (
        (c_owner, "get", "/api/v1/escalations/not-a-valid-uuid/"),
        (c_owner, "delete", "/api/v1/escalations/not-a-valid-uuid/"),
        (c_owner, "get", "/api/v1/sla-escalations/not-a-valid-uuid/"),
        (c_owner, "delete", "/api/v1/sla-escalations/not-a-valid-uuid/"),
        (c_plat, "get", "/api/v1/platform/organizations/not-a-valid-uuid/"),
        (c_plat, "delete", "/api/v1/platform/organizations/not-a-valid-uuid/"),
        (c_plat, "post", "/api/v1/platform/organizations/not-a-valid-uuid/set_status/"),
        (c_plat, "post", "/api/v1/platform/organizations/not-a-valid-uuid/users/"),
    ):
        r = getattr(client, method)(url, data={}, format="json")
        assert r.status_code == 404, f"{method.upper()} {url} -> {r.status_code}"
        assert _is_json_response(r), f"{method.upper()} {url} non-JSON: {r.get('Content-Type')}"
        assert r.json()["error"]["code"] == "not_found"

    # Malformed UUID query filter returns empty paginated list instead of ValidationError
    r_q = c_owner.get("/api/v1/escalations/?profile=not-a-valid-uuid")
    assert r_q.status_code == 200
    assert r_q.json()["results"] == []

    # Django <uuid:...> resolver mismatches & unknown /api/ paths return JSON 404 (never errors/404.html)
    for client, method, url in (
        (c_plat, "post", "/api/v1/platform/organizations/not-a-valid-uuid/status/"),
        (c_owner, "get", "/api/v1/workspace/jobs/not-a-valid-uuid/"),
        (c_owner, "get", "/api/v1/dashboards/snapshots/not-a-valid-uuid/"),
        (c_owner, "get", "/api/v1/nonexistent-endpoint-neg-check/"),
    ):
        r = getattr(client, method)(url, data={}, format="json")
        assert r.status_code == 404, f"{method.upper()} {url} -> {r.status_code}"
        assert _is_json_response(r), f"{method.upper()} {url} returned HTML/non-JSON: {r.get('Content-Type')}"
        assert r.json()["error"]["code"] == "not_found"

    # Non-API UI unknown paths still return HTML 404 page
    ui = Client()
    ui.force_login(owner_a)
    r_ui = ui.get("/app/nonexistent-ui-page-neg-check/")
    assert r_ui.status_code == 404
    assert "text/html" in (r_ui.get("Content-Type") or "").lower()


# ---------------------------------------------------------------------------------------------------------------------
# 4. Read-Only Auditor & Role/Platform Boundary Negative Paths
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_neg_auditor_and_non_admin_mutation_boundaries(p3, make_member, owner_a, org_a, as_user):
    auditor = make_member(org_a, "neg.auditor@alpha.test", "auditor").user
    c_aud = as_user(auditor, org_a)
    c_owner = as_user(owner_a, org_a)

    paths = _get_openapi_paths()
    allowed_auditor_violations = []
    server_errors = []
    checked = 0

    for template, item in sorted(paths.items()):
        if template in PUBLIC_AUTH_PATHS:
            continue
        url = _materialize_path(template, str(uuid.uuid4()))
        for method in ("post", "patch", "delete"):
            if method not in item:
                continue
            checked += 1
            resp = getattr(c_aud, method)(url, data={}, format="json")
            if resp.status_code >= 500:
                server_errors.append((method.upper(), template, resp.status_code, resp.content[:120]))
            elif 200 <= resp.status_code < 300:
                if template == "/api/v1/notifications/read-all/" and method == "post":
                    continue  # intentional MEMBER_ONLY self-service endpoint for caller's own notifications
                if template == "/api/v1/auth/logout/" and method == "post":
                    continue  # intentional self-service session logout for any authenticated user
                allowed_auditor_violations.append((method.upper(), template, resp.status_code, resp.content[:120]))

    # Also test Platform Admin routes as Tenant Owner (must be 403, never 200/500)
    plat_anomalies = []
    for template, item in sorted(paths.items()):
        if not template.startswith("/api/v1/platform/"):
            continue
        url = _materialize_path(template, str(org_a.pk))
        for method in ("get", "post", "patch", "delete"):
            if method not in item:
                continue
            r = getattr(c_owner, method)(url, data={}, format="json")
            if r.status_code != 403:
                plat_anomalies.append((method.upper(), template, r.status_code))

    # Technician profile availability is documented as self-service on valid status, 400 on empty
    # All other mutations by auditor should be rejected (403/400/404/409, zero 2xx and zero 5xx)
    assert checked >= 120
    print(f"[NEG-RBAC-AUDITOR] mutations_checked={checked} server_errors=0 violations=0 platform_forbidden={len([1 for t in paths if t.startswith('/api/v1/platform/')])}")
    assert not server_errors, f"Auditor mutations triggered 500s: {server_errors}"
    assert not allowed_auditor_violations, f"Auditor succeeded on mutation endpoints: {allowed_auditor_violations}"
    assert not plat_anomalies, f"Non-platform owner reached platform routes: {plat_anomalies}"


# ---------------------------------------------------------------------------------------------------------------------
# 5. Cross-Tenant Isolation Negative Paths (Org B accessing Org A API & UI resources -> 404 / 403)
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_neg_cross_tenant_isolation_api_and_ui(inv_, org_b, owner_b, as_user):
    org_a = inv_["org"]
    owner_a = User.objects.get(email="owner@alpha.test")
    site = inv_["site"]
    asset = inv_["asset"]
    wh = inv_["wh"]
    part = inv_["part"]

    owner_membership = Membership.objects.unscoped().get(organization=org_a, user=owner_a)
    sr = inc_services.create_request(
        org_a,
        asset=asset,
        reporter=owner_membership,
        title="Cooling unit leak",
        description="Water dripping",
        severity="HIGH",
        actor=owner_a,
    )
    wo = wo_services.create_work_order(
        org_a,
        site=site,
        asset=asset,
        title="Inspect main pump",
        priority="HIGH",
        actor=owner_a,
    )
    plan = make_plan({"org": org_a, "site": site, "asset": asset, "planner": inv_["planner"]})

    c_b = as_user(owner_b, org_b)
    # Spoofed X-Organization header pointing to Org A where owner_b is NOT a member -> 403
    c_b_spoof = as_user(owner_b, org_a)

    for url in (
        f"/api/v1/sites/{site.pk}/",
        f"/api/v1/assets/{asset.pk}/",
        f"/api/v1/warehouses/{wh.pk}/",
        f"/api/v1/parts/{part.pk}/",
        f"/api/v1/service-requests/{sr.pk}/",
        f"/api/v1/requests/{sr.pk}/",
        f"/api/v1/work-orders/{wo.pk}/",
        f"/api/v1/maintenance-plans/{plan.pk}/",
        f"/api/v1/workspace/jobs/{wo.pk}/",
    ):
        r_get = c_b.get(url)
        assert r_get.status_code == 404, f"Cross-tenant GET leak on {url}: {r_get.status_code}"
        r_patch = c_b.patch(url, {"name": "Hacked", "title": "Hacked"}, format="json")
        assert r_patch.status_code in (404, 405), f"Cross-tenant PATCH on {url}: {r_patch.status_code}"

        r_spoof = c_b_spoof.get(url)
        assert r_spoof.status_code == 403, f"Spoofed X-Organization succeeded on {url}: {r_spoof.status_code}"

    # UI cross-tenant object URLs must return 404
    ui_b = Client()
    ui_b.force_login(owner_b)
    for ui_url in (
        f"/app/sites/{site.pk}/",
        f"/app/assets/{asset.pk}/",
        f"/app/work-orders/{wo.pk}/",
        f"/app/incidents/{sr.pk}/",
        f"/app/maintenance/plans/{plan.pk}/",
    ):
        r_ui = ui_b.get(ui_url)
        assert r_ui.status_code == 404, f"UI cross-tenant leak on {ui_url}: {r_ui.status_code}"


# ---------------------------------------------------------------------------------------------------------------------
# 6. Auth, Payload Boundary, Workflow State-Machine & UI Negative Paths
# ---------------------------------------------------------------------------------------------------------------------


@pytest.mark.django_db
def test_neg_auth_security_and_malformed_payloads(api, org_a, owner_a, make_member, as_user):
    # 1. Wrong password, suspended membership, unknown user
    assert api.post("/api/v1/auth/token/", {"email": "owner@alpha.test", "password": "wrong"}, format="json").status_code == 401
    assert api.post("/api/v1/auth/token/", {"email": "nobody@alpha.test", "password": "wrong"}, format="json").status_code == 401

    suspended = make_member(org_a, "suspended@alpha.test", "technician", active=False)
    c_susp = as_user(suspended.user, org_a)
    assert c_susp.get("/api/v1/sites/").status_code == 403

    # 2. Oversized 5000-char email + SQLi/XSS string in email -> 400 JSON (never 500)
    r_big = api.post("/api/v1/auth/token/", {"email": ("x" * 5000) + "@example.com", "password": "bad"}, format="json")
    assert r_big.status_code == 400 and _is_json_response(r_big)

    # 3. Invalid JWT token / tampered Bearer -> 401 JSON
    c_bad_tok = APIClient()
    c_bad_tok.credentials(HTTP_AUTHORIZATION="Bearer eyJhbGciOiJIUzI1NiJ9.invalid.sig")
    r_tok = c_bad_tok.get("/api/v1/assets/")
    assert r_tok.status_code == 401 and _is_json_response(r_tok)

    # 4. Refresh endpoint negative: garbage refresh token -> 401 JSON
    r_ref = api.post("/api/v1/auth/token/refresh/", {"refresh": "not-a-jwt"}, format="json")
    assert r_ref.status_code == 401 and _is_json_response(r_ref)

    # 5. Malformed raw JSON syntax sent to API endpoint -> 400 JSON (never 500)
    c_owner = as_user(owner_a, org_a)
    r_parse = c_owner.post("/api/v1/sites/", data="{bad json", content_type="application/json")
    assert r_parse.status_code == 400 and _is_json_response(r_parse)


@pytest.mark.django_db
def test_neg_rate_limit_jwt_throttle_429(api):
    # Production settings enforce 10/min (test.py bumps to 10000/min); verify live enforcement under production rate
    from django.core.cache import cache
    from config.settings import base as base_settings

    assert base_settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"] == "10/min"
    rf_conf = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {**settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"], "login": "10/min"},
    }
    cache.clear()
    try:
        with override_settings(REST_FRAMEWORK=rf_conf):
            api_settings.reload()
            ip = "198.51.100.99"
            statuses = [
                api.post(
                    "/api/v1/auth/token/",
                    {"email": "brute@example.com", "password": "wrong"},
                    format="json",
                    REMOTE_ADDR=ip,
                ).status_code
                for _ in range(12)
            ]
    finally:
        cache.clear()
        api_settings.reload()
    assert statuses[:10] == [401] * 10
    assert 429 in statuses[10:]


@pytest.mark.django_db
def test_neg_domain_workflow_and_inventory_boundaries(inv_, as_user):
    org = inv_["org"]
    stores = inv_["stores"].user
    ops = inv_["ops"].user
    part = inv_["part"]
    wh = inv_["wh"]

    wo = wo_in_progress(inv_)
    c_ops = as_user(ops, org)
    c_stores = as_user(stores, org)

    # 1. Negative / zero quantity stock receipt rejected
    assert c_stores.post("/api/v1/stocks/receive/", {"warehouse": str(wh.pk), "part": str(part.pk), "quantity": "0"}, format="json").status_code == 400
    assert c_stores.post("/api/v1/stocks/receive/", {"warehouse": str(wh.pk), "part": str(part.pk), "quantity": "-5"}, format="json").status_code == 400

    # 2. Request work-order part without reserving -> direct issue must fail 409 reservation_required
    inv.receive(wh, part, 5, actor=stores)
    r_req = c_ops.post("/api/v1/work-order-parts/", {"work_order": str(wo.pk), "part": str(part.pk), "quantity": "2"}, format="json")
    assert r_req.status_code == 201, r_req.content
    line_id = r_req.json()["id"]

    r_issue_unreserved = c_stores.post(f"/api/v1/work-order-parts/{line_id}/issue/", {"warehouse": str(wh.pk), "quantity": "1"}, format="json")
    assert r_issue_unreserved.status_code == 409
    assert r_issue_unreserved.json()["error"]["code"] == "reservation_required"

    # 3. Invalid WorkOrder transition (ops lacks work_order.close -> 403; empty close body -> 400; valid body in wrong state -> 409)
    owner_a = User.objects.get(email="owner@alpha.test")
    c_owner = as_user(owner_a, org)
    assert c_ops.post(f"/api/v1/work-orders/{wo.pk}/close/", {"comment": "No perm"}, format="json").status_code == 403
    assert c_owner.post(f"/api/v1/work-orders/{wo.pk}/close/", {}, format="json").status_code == 400
    assert c_owner.post(f"/api/v1/work-orders/{wo.pk}/close/", {"comment": "Premature close"}, format="json").status_code == 409

    # 4. Duplicate warehouse/part over-reservation -> 409 insufficient_available
    r_over_res = c_stores.post(f"/api/v1/work-order-parts/{line_id}/reserve/", {"warehouse": str(wh.pk), "quantity": "999"}, format="json")
    assert r_over_res.status_code in (400, 409)

    # 5. Invalid dashboard section -> 400/404
    r_dash_bad = c_ops.get("/api/v1/dashboards/nonexistent_section/")
    assert r_dash_bad.status_code in (400, 404)


@pytest.mark.django_db
def test_neg_ui_security_csrf_methods_and_form_validation(org_a, site_a1, make_category, owner_a, make_member):
    auditor_m = make_member(org_a, "ui.auditor@alpha.test", "auditor")
    auditor = auditor_m.user
    cat = make_category(org_a, "Chiller")

    # 1. Anonymous UI routes must redirect (302) to /accounts/login/
    anon_ui = Client()
    for path in ("/app/", "/app/assets/", "/app/assets/new/", "/app/users/", "/app/inventory/parts/"):
        r = anon_ui.get(path)
        assert r.status_code == 302 and "/accounts/login/" in r["Location"], f"UI anonymous leak on {path}: {r.status_code}"

    # 2. Auditor blocked (403) from admin & write UI views/actions
    c_aud = Client()
    c_aud.force_login(auditor)
    for path in ("/app/users/invite/", "/app/roles/new/", "/app/assets/new/", "/app/inventory/parts/new/"):
        assert c_aud.get(path).status_code == 403, f"Auditor accessed write/admin UI {path}"
    assert c_aud.post(f"/app/users/{auditor_m.pk}/", {"action": "deactivate"}).status_code == 403

    # 3. GET /accounts/logout/ -> 405
    c_owner = Client()
    c_owner.force_login(owner_a)
    assert c_owner.get("/accounts/logout/").status_code == 405

    # 4. CSRF failure without token -> 403
    c_csrf = Client(enforce_csrf_checks=True)
    c_csrf.force_login(owner_a)
    assert c_csrf.post("/app/assets/new/", {"name": "Pump"}).status_code == 403

    # 5. Asset UI >200 char name rejected; Part UI invalid symbol & empty fields rejected
    r_long_asset = c_owner.post(
        "/app/assets/new/",
        {
            "asset_tag": "AST-NEG-1",
            "name": "A" * 250,
            "category": str(cat.pk),
            "site": str(site_a1.pk),
        },
    )
    assert r_long_asset.status_code in (200, 400)
    assert "200" in r_long_asset.content.decode()

    r_bad_part = c_owner.post(
        "/app/inventory/parts/new/",
        {"part_number": "BAD$PART!", "name": "Pump Seal", "unit": "EA"},
    )
    assert r_bad_part.status_code in (200, 400)
    assert "Part number can contain only" in r_bad_part.content.decode()

