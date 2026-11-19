"""Comprehensive regression suite for all defects and test cases reported by QA."""
import datetime
import uuid
import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.checklists.models import ChecklistTemplate
from apps.core.models import WebhookEndpoint
from apps.incidents import services as incident_services
from apps.inventory.forms import PartForm
from apps.rbac.models import MembershipRole, Permission, Role, RolePermission
from apps.rbac.services import seed_system_roles
from apps.sites.models import Shift, Site
from apps.tenancy.models import Membership, Organization
from apps.workorders.models import TechnicianProfile, WorkOrder
from apps.workorders import services as wo_services

pytestmark = pytest.mark.django_db


def test_def_005_work_order_cancel_api():
    """DEF-005: A work order can be cancelled via POST /work-orders/{id}/transition/
    with action 'cancel' or directly via POST /work-orders/{id}/cancel/."""
    org = Organization.objects.create(name=f"Cancel Org {uuid.uuid4().hex[:6]}", slug=f"co-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    mem = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Owner Role", is_owner=True)
    MembershipRole.objects.create(membership=mem, role=role)

    site = Site.objects.create(organization=org, name="Cancel Site", code=f"s-{uuid.uuid4().hex[:4]}")
    cat = AssetCategory.objects.create(organization=org, name="Motors")
    asset = Asset.objects.create(organization=org, site=site, category=cat, name="Motor 1", asset_tag=f"M-{uuid.uuid4().hex[:4]}")

    wo = wo_services.create_work_order(
        org, site=site, asset=asset, title="Inspection motor",
        priority=WorkOrder.Priority.MEDIUM, actor=user, membership=mem,
    )
    assert wo.status == WorkOrder.Status.DRAFT

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # 1. Transition with action 'cancel'
    resp_transition = client.post(
        f"/api/v1/work-orders/{wo.pk}/transition/",
        {"action": "cancel", "reason": "QA cancel test"},
        format="json",
    )
    assert resp_transition.status_code == 200, resp_transition.data
    assert resp_transition.data["status"] == "CANCELLED"

    # 2. Another work order cancelled directly via /cancel/ endpoint
    wo2 = wo_services.create_work_order(
        org, site=site, asset=asset, title="Inspection motor 2",
        priority=WorkOrder.Priority.MEDIUM, actor=user, membership=mem,
    )
    resp_cancel = client.post(
        f"/api/v1/work-orders/{wo2.pk}/cancel/",
        {"reason": "Direct cancel test"},
        format="json",
    )
    assert resp_cancel.status_code == 200, resp_cancel.data
    assert resp_cancel.data["status"] == "CANCELLED"


def test_def_006_part_name_alphanumeric_validation():
    """DEF-006: The spare-part web form accepts names containing digits ('Bearing 6205')
    while rejecting numeric-only names ('123456789')."""
    # Alphanumeric name accepted
    f_valid = PartForm(data={"part_number": "BRG-6205", "name": "Bearing 6205", "unit": "1"})
    assert f_valid.is_valid(), f_valid.errors

    # Pure digits in name rejected
    f_bad = PartForm(data={"part_number": "BRG-6205", "name": "231115656665654", "unit": "1"})
    assert not f_bad.is_valid()
    assert "name" in f_bad.errors


def test_def_008_technician_profile_duplicate_conflict_409():
    """DEF-008: POST /api/v1/technician-profiles/ for an existing member returns HTTP 409 conflict."""
    org = Organization.objects.create(name=f"Tech Org {uuid.uuid4().hex[:6]}", slug=f"to-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    mem = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Owner Role", is_owner=True)
    MembershipRole.objects.create(membership=mem, role=role)

    tech_user = User.objects.create_user(email=f"tech-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    tech_mem = Membership.objects.create(organization=org, user=tech_user, status=Membership.Status.ACTIVE)

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # First POST -> 201 Created
    r1 = client.post("/api/v1/technician-profiles/", {"membership": str(tech_mem.pk), "skills": ["HVAC"]}, format="json")
    assert r1.status_code == 201

    # Second POST for same membership -> 409 Conflict
    r2 = client.post("/api/v1/technician-profiles/", {"membership": str(tech_mem.pk), "skills": ["HVAC", "Plumbing"]}, format="json")
    assert r2.status_code == 409
    assert r2.data["error"]["code"] == "duplicate_technician_profile"


def test_shf_001_shift_end_before_start_validation():
    """SHF-001: Shift with end_time before start_time (when not overnight) rejected with HTTP 400."""
    org = Organization.objects.create(name=f"Shift Org {uuid.uuid4().hex[:6]}", slug=f"so-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    mem = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Owner Role", is_owner=True)
    MembershipRole.objects.create(membership=mem, role=role)

    site = Site.objects.create(organization=org, name="Shift Site", code=f"s-{uuid.uuid4().hex[:4]}")

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # Non-overnight shift ending before start -> HTTP 400
    r_bad = client.post("/api/v1/shifts/", {
        "site": str(site.pk), "name": "Invalid Shift", "code": "SH-BAD",
        "start_time": "16:00:00", "end_time": "08:00:00", "is_overnight": False
    }, format="json")
    assert r_bad.status_code == 400
    assert "end_time" in str(r_bad.data)

    # Overnight shift ending before start -> HTTP 201
    r_good = client.post("/api/v1/shifts/", {
        "site": str(site.pk), "name": "Overnight Shift", "code": "SH-OVERNIGHT",
        "start_time": "16:00:00", "end_time": "08:00:00", "is_overnight": True
    }, format="json")
    assert r_good.status_code == 201


def test_api_110_pos_inspection_requirements_authorized_user():
    """API-110-POS: Checklists a work order needs and their state retrieved by authorized user."""
    org = Organization.objects.create(name=f"Insp Org {uuid.uuid4().hex[:6]}", slug=f"io-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    mem = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Owner Role", is_owner=True)
    MembershipRole.objects.create(membership=mem, role=role)

    site = Site.objects.create(organization=org, name="Insp Site", code=f"s-{uuid.uuid4().hex[:4]}")
    cat = AssetCategory.objects.create(organization=org, name="Generators")
    asset = Asset.objects.create(organization=org, site=site, category=cat, name="Gen 1", asset_tag=f"G-{uuid.uuid4().hex[:4]}")

    wo = wo_services.create_work_order(
        org, site=site, asset=asset, title="Generator check",
        priority=WorkOrder.Priority.MEDIUM, actor=user, membership=mem,
    )

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    r = client.get(f"/api/v1/inspections/requirements/?work_order={wo.pk}")
    assert r.status_code == 200, r.data
    assert "work_order" in r.data
    assert "blockers" in r.data
    assert "checklists" in r.data


def test_api_362_rbac_auditor_cannot_create_dashboard_snapshots():
    """API-362-RBAC: Read-only Auditor role receives HTTP 403 when attempting to generate snapshots."""
    org = Organization.objects.create(name=f"Dash Org {uuid.uuid4().hex[:6]}", slug=f"do-{uuid.uuid4().hex[:6]}")
    seed_system_roles(org)

    auditor_user = User.objects.create_user(email=f"auditor-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    auditor_mem = Membership.objects.create(organization=org, user=auditor_user, status=Membership.Status.ACTIVE)
    MembershipRole.objects.create(membership=auditor_mem, role=Role.objects.get(organization=org, system_key="auditor"))

    client = APIClient()
    client.force_authenticate(user=auditor_user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    r = client.post("/api/v1/dashboards/snapshots/", {}, format="json")
    assert r.status_code == 403


def test_webhooks_ssrf_protection():
    """Webhooks reject loopback and cloud metadata URLs with HTTP 400."""
    org = Organization.objects.create(name=f"WH Org {uuid.uuid4().hex[:6]}", slug=f"wh-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"owner-{uuid.uuid4().hex[:6]}@example.com", password="Password123!")
    mem = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    role = Role.objects.create(organization=org, name="Owner Role", is_owner=True)
    MembershipRole.objects.create(membership=mem, role=role)

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # Loopback URL
    r_loopback = client.post("/api/v1/webhooks/", {
        "name": "Loopback WH",
        "target_url": "http://127.0.0.1:8000/x",
        "event_pattern": "*",
    }, format="json")
    assert r_loopback.status_code == 400

    # Cloud metadata URL
    r_metadata = client.post("/api/v1/webhooks/", {
        "name": "Metadata WH",
        "target_url": "http://169.254.169.254/latest/meta-data/",
        "event_pattern": "*",
    }, format="json")
    assert r_metadata.status_code == 400
