"""Comprehensive Automated Regression Suite for All 36 Failed API Test Cases across 9 Defect IDs.

Defects covered:
- DEF-010 (6 cases): MTH-163, MTH-164, MTH-165, MTH-166, MTH-167, MTH-168
- DEF-099 (15 cases): API-100-NEG, API-159-POS, API-160-NEG, API-161-NEG, API-162-NEG,
                     API-163-NEG, API-164-NEG, API-165-NEG, API-166-NEG, API-170-POS,
                     API-507-POS, API-510-POS, AUTH-018, AUTH-019, AUTH-031
- DEF-024 (4 cases): RBM-196, RBM-197, RBM-203, RBM-204
- DEF-015 (3 cases): API-131-POS, API-133-POS, API-134-POS
- DEF-020 (2 cases): AUTH-071, AUTH-072
- DEF-005 (1 case): AUTH-050
- DEF-023 (1 case): CMT-004
- DEF-013 (3 cases): PERF-003, PERF-008, PERF-012
- DEF-012 (1 case): DB-010
"""
import time
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.maintenance.models import MaintenancePlan, MaintenanceSchedule
from apps.portal.models import PortalAccount
from apps.rbac.models import MembershipRole, Permission, Role, RolePermission
from apps.rbac.services import seed_system_roles
from apps.sites.models import Site
from apps.tenancy.models import Membership, Organization
from axes.models import AccessAttempt

pytestmark = pytest.mark.django_db


# ==============================================================================
# DEF-010 & DEF-099 Platform Endpoints
# ==============================================================================
def test_def_010_and_def_099_platform_endpoints():
    """Verify DEF-010 (MTH-163..MTH-168 return 405 Method Not Allowed)
    and DEF-099 Platform Admin endpoints (API-159..API-166)."""
    admin_user = User.objects.create_user(
        email=f"platform-admin-{uuid.uuid4().hex[:6]}@example.com",
        password="AdminPassword123!",
        is_staff=True,
        is_platform_admin=True,
    )
    client = APIClient()
    client.force_authenticate(user=admin_user)
    random_id = str(uuid.uuid4())

    # --- DEF-010: Unsupported PUT returns 405 Method Not Allowed ---
    # MTH-163: PUT /api/v1/platform/organizations/
    assert client.put("/api/v1/platform/organizations/").status_code == 405

    # MTH-164: PUT /api/v1/platform/organizations/{id}/
    assert client.put(f"/api/v1/platform/organizations/{random_id}/").status_code == 405

    # MTH-165: PUT /api/v1/platform/organizations/{id}/set_status/
    assert client.put(f"/api/v1/platform/organizations/{random_id}/set_status/").status_code == 405

    # MTH-166: PUT /api/v1/platform/organizations/{id}/status/
    assert client.put(f"/api/v1/platform/organizations/{random_id}/status/").status_code == 405

    # MTH-167: PUT /api/v1/platform/organizations/{id}/users/
    assert client.put(f"/api/v1/platform/organizations/{random_id}/users/").status_code == 405

    # MTH-168: PUT /api/v1/platform/users/
    assert client.put("/api/v1/platform/users/").status_code == 405

    # --- DEF-099: Platform Super Admin operations & validation ---
    # API-159-POS: GET /api/v1/platform/organizations/ -> 200
    resp_orgs = client.get("/api/v1/platform/organizations/")
    assert resp_orgs.status_code == 200

    # API-160-NEG: POST /api/v1/platform/organizations/ empty body -> 400
    resp_empty_org = client.post("/api/v1/platform/organizations/", {}, format="json")
    assert resp_empty_org.status_code == 400

    # API-161-NEG: DELETE /api/v1/platform/organizations/{id}/ non-existent -> 404
    assert client.delete(f"/api/v1/platform/organizations/{random_id}/").status_code == 404

    # API-162-NEG: GET /api/v1/platform/organizations/{id}/ non-existent -> 404
    assert client.get(f"/api/v1/platform/organizations/{random_id}/").status_code == 404

    # API-163-NEG: POST /api/v1/platform/organizations/{id}/set_status/ non-existent -> 404
    assert client.post(f"/api/v1/platform/organizations/{random_id}/set_status/", {"status": "ACTIVE"}, format="json").status_code == 404

    # API-164-NEG: POST /api/v1/platform/organizations/{id}/status/ non-existent -> 404
    assert client.post(f"/api/v1/platform/organizations/{random_id}/status/", {"status": "ACTIVE"}, format="json").status_code == 404

    # API-165-NEG: POST /api/v1/platform/organizations/{id}/users/ non-existent -> 404
    assert client.post(f"/api/v1/platform/organizations/{random_id}/users/", {"email": "u@test.com"}, format="json").status_code == 404

    # API-166-NEG: POST /api/v1/platform/users/ empty body -> 400
    assert client.post("/api/v1/platform/users/", {}, format="json").status_code == 400


# ==============================================================================
# DEF-099 Dashboard Section Validation
# ==============================================================================
def test_def_099_api_100_neg_dashboard_section_validation():
    """API-100-NEG: GET /api/v1/dashboards/{section}/ with unknown section returns 404 not_found."""
    org = Organization.objects.create(name=f"Dash Org {uuid.uuid4().hex[:6]}", slug=f"dash-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"dash-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Dash Admin", is_owner=True)
    MembershipRole.objects.create(membership=membership, role=role)

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    resp = client.get("/api/v1/dashboards/nonexistent-section/")
    assert resp.status_code == 404
    assert resp.data.get("error", {}).get("code") == "not_found"


# ==============================================================================
# DEF-099 Portal Account Resolution
# ==============================================================================
def test_def_099_portal_account_resolution():
    """API-170-POS, API-507-POS, API-510-POS: Portal account retrieval by id/user/membership."""
    org = Organization.objects.create(name=f"Portal Org {uuid.uuid4().hex[:6]}", slug=f"portal-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"client-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    portal_acc = PortalAccount.objects.create(
        organization=org, membership=membership, company_name="Portal Corp", is_enabled=True
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # API-170-POS: GET /api/v1/portal-accounts/{id}/
    resp1 = client.get(f"/api/v1/portal-accounts/{portal_acc.pk}/")
    assert resp1.status_code == 200
    assert resp1.data.get("company_name") == "Portal Corp"

    # API-507-POS: GET /api/v1/portal/accounts/{id} (without trailing slash)
    resp2 = client.get(f"/api/v1/portal/accounts/{portal_acc.pk}")
    assert resp2.status_code in (200, 301, 302)

    # API-510-POS: GET /api/v1/portal/accounts/{id}/
    resp3 = client.get(f"/api/v1/portal/accounts/{portal_acc.pk}/")
    assert resp3.status_code == 200


# ==============================================================================
# DEF-099 & DEF-005 Authentication & Lockout
# ==============================================================================
def test_def_099_and_def_005_authentication():
    """Verify AUTH-018, AUTH-019, AUTH-031, and AUTH-050."""
    from django.core.cache import caches, cache
    try:
        caches["login_throttle"].clear()
    except Exception:
        pass
    cache.clear()
    AccessAttempt.objects.all().delete()
    email = f"auth-user-{uuid.uuid4().hex[:6]}@example.com"
    user = User.objects.create_user(email=email, password="Password123!")
    client = APIClient()

    # AUTH-019: Uppercase email -> HTTP 200
    resp_upper = client.post("/api/v1/auth/token/", {"email": email.upper(), "password": "Password123!"}, format="json")
    assert resp_upper.status_code == 200
    refresh_token = resp_upper.data.get("refresh")
    assert refresh_token is not None

    # AUTH-031: Token rotation on refresh -> HTTP 200, new refresh != old refresh
    resp_refresh = client.post("/api/v1/auth/token/refresh/", {"refresh": refresh_token}, format="json")
    assert resp_refresh.status_code == 200
    new_refresh = resp_refresh.data.get("refresh")
    assert new_refresh is not None
    assert new_refresh != refresh_token

    # AUTH-018: Unicode email -> HTTP 401 (not 429 or 500)
    resp_unicode = client.post("/api/v1/auth/token/", {"email": "tëst@ünicöde.com", "password": "Password123!"}, format="json")
    assert resp_unicode.status_code in (400, 401)

    # AUTH-050: Seven consecutive failed logins trigger lockout (429) after 5 failures
    AccessAttempt.objects.all().delete()
    target_email = f"lockout-{uuid.uuid4().hex[:6]}@example.com"
    User.objects.create_user(email=target_email, password="ValidPassword123!")
    statuses = []
    for _ in range(7):
        r = client.post("/api/v1/auth/token/", {"email": target_email, "password": "BadPassword!"}, format="json")
        statuses.append(r.status_code)

    # First 5 return 401; attempts 6 and 7 must be locked out with 429
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5:] == [429, 429]


# ==============================================================================
# DEF-020 Logout & JWT Token Invalidation
# ==============================================================================
def test_def_020_logout_token_invalidation():
    """AUTH-071 & AUTH-072: Logout rejects invalid or missing refresh token with HTTP 400."""
    from django.core.cache import caches, cache
    try:
        caches["login_throttle"].clear()
    except Exception:
        pass
    cache.clear()
    AccessAttempt.objects.all().delete()
    user = User.objects.create_user(email=f"logout-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    client = APIClient()

    # Obtain valid tokens
    login_resp = client.post("/api/v1/auth/token/", {"email": user.email, "password": "Password123!"}, format="json")
    access_token = login_resp.data["access"]
    refresh_token = login_resp.data["refresh"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # AUTH-071: Invalid refresh token -> HTTP 400
    resp_invalid = client.post("/api/v1/auth/logout/", {"refresh": "invalid.jwt.token"}, format="json")
    assert resp_invalid.status_code == 400

    # AUTH-072: Missing refresh token -> HTTP 400
    resp_missing = client.post("/api/v1/auth/logout/", {}, format="json")
    assert resp_missing.status_code == 400

    # Valid logout succeeds
    resp_valid = client.post("/api/v1/auth/logout/", {"refresh": refresh_token}, format="json")
    assert resp_valid.status_code == 200

    # Trying to reuse blacklisted refresh token on refresh -> HTTP 401
    resp_reuse = client.post("/api/v1/auth/token/refresh/", {"refresh": refresh_token}, format="json")
    assert resp_reuse.status_code == 401


# ==============================================================================
# DEF-024 RBAC Site-Scoped Custom Role Org Permissions
# ==============================================================================
def test_def_024_rbac_site_scoped_custom_role():
    """RBM-196, RBM-197, RBM-203, RBM-204:
    Site-scoped role assignments honour organization-level permissions granted through custom role."""
    org = Organization.objects.create(name=f"RBAC Org {uuid.uuid4().hex[:6]}", slug=f"rbac-{uuid.uuid4().hex[:6]}")
    site = Site.objects.create(organization=org, name="Site Beta", code=f"s-{uuid.uuid4().hex[:4]}")
    user = User.objects.create_user(email=f"scoped-{uuid.uuid4().hex[:6]}@client.test", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    PortalAccount.objects.create(organization=org, membership=membership, company_name="Scoped Client Corp")

    custom_role = Role.objects.create(
        organization=org,
        name="Custom Raveen Role",
        system_key=f"custom_raveen_{uuid.uuid4().hex[:6]}",
    )
    for code in ["user.view", "role.view", "checklist.view", "organization.view"]:
        perm = Permission.objects.get(code=code)
        RolePermission.objects.create(role=custom_role, permission=perm)

    MembershipRole.objects.create(membership=membership, role=custom_role, site=site)

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # RBM-196: GET /api/v1/users/ -> HTTP 200
    assert client.get("/api/v1/users/").status_code == 200

    # RBM-197: GET /api/v1/roles/ -> HTTP 200
    assert client.get("/api/v1/roles/").status_code == 200

    # RBM-203: GET /api/v1/checklist-templates/ -> HTTP 200
    assert client.get("/api/v1/checklist-templates/").status_code == 200

    # RBM-204: GET /api/v1/organization/ -> HTTP 200
    assert client.get("/api/v1/organization/").status_code == 200


# ==============================================================================
# DEF-015 Maintenance Schedules Lifecycle & Duplication
# ==============================================================================
def test_def_015_maintenance_schedules_lifecycle():
    """API-131-POS, API-133-POS, API-134-POS:
    Create maintenance schedule, update (PATCH), disable, enable, and duplicate detection."""
    org = Organization.objects.create(name=f"PM Org {uuid.uuid4().hex[:6]}", slug=f"pm-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"planner-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Planner Role", system_key=f"planner_{uuid.uuid4().hex[:4]}")
    for code in ["maintenance.view", "maintenance.create", "maintenance.update", "asset.view", "site.view"]:
        p = Permission.objects.get(code=code)
        RolePermission.objects.create(role=role, permission=p)
    MembershipRole.objects.create(membership=membership, role=role)

    site = Site.objects.create(organization=org, name="Test Site", code=f"s-{uuid.uuid4().hex[:4]}")
    cat = AssetCategory.objects.create(organization=org, name="Pumps")
    asset = Asset.objects.create(organization=org, site=site, category=cat, name="Pump 1", asset_tag=f"P-{uuid.uuid4().hex[:4]}")

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # 1. Create plan
    plan_resp = client.post("/api/v1/maintenance-plans/", {
        "name": "Overhaul Plan", "asset": str(asset.pk), "site": str(site.pk), "priority": "HIGH"
    }, format="json")
    assert plan_resp.status_code == 201
    plan_id = plan_resp.data["id"]

    # 2. Create schedule
    sch_resp = client.post(f"/api/v1/maintenance-plans/{plan_id}/schedules/", {
        "trigger_type": "TIME", "frequency": "MONTHLY", "interval_count": 1,
        "start_date": str(date.today()), "lead_days": 5
    }, format="json")
    assert sch_resp.status_code == 201
    sch_id = sch_resp.data["id"]

    # 3. Duplicate schedule rejected with HTTP 409 duplicate_schedule
    dup_resp = client.post(f"/api/v1/maintenance-plans/{plan_id}/schedules/", {
        "trigger_type": "TIME", "frequency": "MONTHLY", "interval_count": 1,
        "start_date": str(date.today())
    }, format="json")
    assert dup_resp.status_code == 409
    assert dup_resp.data.get("error", {}).get("code") == "duplicate_schedule"

    # 4. API-131-POS: PATCH /api/v1/maintenance-schedules/{id}/
    patch_resp = client.patch(f"/api/v1/maintenance-schedules/{sch_id}/", {"lead_days": 12}, format="json")
    assert patch_resp.status_code == 200
    assert patch_resp.data.get("lead_days") == 12

    # 5. API-133-POS: POST /api/v1/maintenance-schedules/{id}/disable/
    dis_resp = client.post(f"/api/v1/maintenance-schedules/{sch_id}/disable/")
    assert dis_resp.status_code == 200
    assert dis_resp.data.get("is_active") is False

    # 6. API-134-POS: POST /api/v1/maintenance-schedules/{id}/enable/
    en_resp = client.post(f"/api/v1/maintenance-schedules/{sch_id}/enable/")
    assert en_resp.status_code == 200
    assert en_resp.data.get("is_active") is True


# ==============================================================================
# DEF-023 Service Request Comment Permissions
# ==============================================================================
def test_def_023_service_request_comment_permissions():
    """CMT-004: Auditor (read-only) receives HTTP 403 when creating comments;
    Authorized roles receive HTTP 201; Auditor can read comments (HTTP 200)."""
    org = Organization.objects.create(name=f"SR Org {uuid.uuid4().hex[:6]}", slug=f"sr-{uuid.uuid4().hex[:6]}")
    seed_system_roles(org)

    auditor_user = User.objects.create_user(email=f"auditor-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    auditor_mem = Membership.objects.create(organization=org, user=auditor_user, status=Membership.Status.ACTIVE)
    MembershipRole.objects.create(membership=auditor_mem, role=Role.objects.get(organization=org, system_key="auditor"))

    tech_user = User.objects.create_user(email=f"tech-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    tech_mem = Membership.objects.create(organization=org, user=tech_user, status=Membership.Status.ACTIVE)
    MembershipRole.objects.create(membership=tech_mem, role=Role.objects.get(organization=org, system_key="technician"))

    site = Site.objects.create(organization=org, name="SR Site", code=f"s-{uuid.uuid4().hex[:4]}")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    asset = Asset.objects.create(organization=org, site=site, category=cat, name="Unit 1", asset_tag=f"U-{uuid.uuid4().hex[:4]}")
    sr = incident_services.create_request(
        org, asset=asset, reporter=tech_mem, title="AC leak", occurred_at=timezone.now(),
        actor=tech_user, kind="INCIDENT", severity="MEDIUM"
    )

    # Auditor attempts to post comment -> HTTP 403 Forbidden
    client_auditor = APIClient()
    client_auditor.force_authenticate(user=auditor_user)
    client_auditor.defaults["HTTP_X_ORGANIZATION"] = org.slug
    assert client_auditor.post(f"/api/v1/service-requests/{sr.pk}/comments/", {"body": "Audit comment"}, format="json").status_code == 403

    # Technician posts comment -> HTTP 201 Created
    client_tech = APIClient()
    client_tech.force_authenticate(user=tech_user)
    client_tech.defaults["HTTP_X_ORGANIZATION"] = org.slug
    assert client_tech.post(f"/api/v1/service-requests/{sr.pk}/comments/", {"body": "Tech comment"}, format="json").status_code == 201

    # Auditor reads comments -> HTTP 200 OK
    assert client_auditor.get(f"/api/v1/service-requests/{sr.pk}/comments/").status_code == 200


# ==============================================================================
# DEF-013 API Performance & DEF-012 Pagination
# ==============================================================================
def test_def_013_performance_and_def_012_pagination():
    """PERF-003, PERF-008, PERF-012 (Response time < 5s) and DB-010 (Pagination page_size=200)."""
    org = Organization.objects.create(name=f"Perf Org {uuid.uuid4().hex[:6]}", slug=f"perf-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"perf-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Owner Role", is_owner=True)
    MembershipRole.objects.create(membership=membership, role=role)

    # Create sites to test DB-010 pagination
    for i in range(15):
        Site.objects.create(organization=org, name=f"Site {i}", code=f"S-{uuid.uuid4().hex[:4]}")

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # DB-010: GET /api/v1/sites/?page_size=200 -> HTTP 200
    resp_sites = client.get("/api/v1/sites/?page_size=200")
    assert resp_sites.status_code == 200
    assert "count" in resp_sites.data
    assert "results" in resp_sites.data

    # PERF-003, PERF-008, PERF-012: 5 sequential calls responding under 5s
    for ep in ["/api/v1/work-orders/", "/api/v1/members/", "/api/v1/dashboards/operations/"]:
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            r = client.get(ep)
            elapsed = time.perf_counter() - t0
            assert r.status_code == 200
            times.append(elapsed)
        assert max(times) < 5.0, f"{ep} exceeded 5s threshold: {max(times)}s"
