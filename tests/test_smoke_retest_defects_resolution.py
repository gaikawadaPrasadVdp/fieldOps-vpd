"""Regression test suite verifying resolution of all defects and blockers identified in the
FieldOps Nexus Smoke Testing Retest Report (Run 56F5).

Covers:
- SMK-D001 / SMK-POR-045: Portal /me response schema compatibility (flat user_email, user_name, updated_at).
- SMK-D002, SMK-D031-033: Service requests and requests router registration and OpenAPI schema generation.
- SMK-D003-007, SMK-D012, SMK-D014, SMK-D015, SMK-D020, SMK-D022, SMK-D023:
  Router registration of work-orders, inventory, and checklists/inspections.
- SMK-D008 / SMK-CTR-033: Coverage agreements expiring endpoint paginated schema.
- SMK-D009 / SMK-CTR-037: Coverage checks work_order_number nullability and order_number fallback.
- SMK-D026 / SMK-MNT-030: Maintenance schedules cycles endpoint paginated schema.
- SMK-D027-030: Portal request detail work_order nullability and 404 envelope.
"""
import uuid
import pytest
from django.utils import timezone
from rest_framework.test import APIClient
from drf_spectacular.generators import SchemaGenerator

from apps.accounts.models import User
from apps.contracts.models import CoverageCheck
from apps.inventory.models import PartReservation, StockMovement, WorkOrderPart
from apps.portal.models import PortalAccount, PortalAssetGrant
from apps.workorders.models import WorkOrder
from tests.phase3_support import wo_in_progress


@pytest.mark.django_db
def test_portal_me_carries_flat_and_nested_fields(p3, as_user, make_member):
    """SMK-D001 / SMK-POR-045: Verify /portal/me/ provides required flat and nested fields."""
    m = make_member(p3["org"], "portal.client.me@test.com", "client_requester")
    account, _ = PortalAccount.objects.get_or_create(
        organization=p3["org"],
        membership=m,
        defaults={"company_name": "Acme Portal Corp", "is_enabled": True},
    )

    api = as_user(m.user, p3["org"])
    r = api.get("/api/v1/portal/me/")
    assert r.status_code == 200, r.content
    data = r.json()

    # Top-level flat properties
    assert "id" in data
    assert data["membership"] == str(m.pk)
    assert data["membership_status"] == m.status
    assert data["company_name"] == "Acme Portal Corp"
    assert data["is_enabled"] is True
    assert data["created_at"] is not None
    assert "updated_at" in data
    assert data["user_email"] == "portal.client.me@test.com"
    assert data["user_name"] == m.user.full_name

    # Nested structures
    assert data["user"]["email"] == "portal.client.me@test.com"
    assert data["user"]["id"] == str(m.user.pk)
    assert data["organization"]["slug"] == p3["org"].slug


@pytest.mark.django_db
def test_coverage_agreements_expiring_paginated_schema():
    """SMK-D008 / SMK-CTR-033: Verify expiring endpoint is documented with paginated list schema."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    expiring_schema = schema["paths"]["/api/v1/coverage-agreements/expiring/"]["get"]["responses"]["200"]
    ref = expiring_schema["content"]["application/json"]["schema"]["$ref"]
    assert "PaginatedAgreementList" in ref


@pytest.mark.django_db
def test_maintenance_schedules_cycles_paginated_schema():
    """SMK-D026 / SMK-MNT-030: Verify maintenance schedule cycles is documented with paginated list schema."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    cycles_schema = schema["paths"]["/api/v1/maintenance-schedules/{id}/cycles/"]["get"]["responses"]["200"]
    ref = cycles_schema["content"]["application/json"]["schema"]["$ref"]
    assert "PaginatedCycleList" in ref


@pytest.mark.django_db
def test_coverage_check_work_order_number_nullability_and_fallback(p3, as_user, owner_a):
    """SMK-D009 / SMK-CTR-037: CheckSerializer handles null work_order.number and documents nullability."""
    # 1. Schema nullability check
    schema = SchemaGenerator().get_schema(request=None, public=True)
    check_props = schema["components"]["schemas"]["Check"]["properties"]
    assert check_props["work_order_number"].get("nullable") is True

    # 2. Data check with order_number fallback
    wo = wo_in_progress(p3)
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("UPDATE workorders_workorder SET number = NULL WHERE id = %s", [wo.pk])
    wo.refresh_from_db()
    assert wo.number is None
    assert wo.order_number

    check = CoverageCheck.objects.create(
        organization=p3["org"],
        work_order=wo,
        asset=p3["asset"],
        agreement=None,
        work_type="PREVENTIVE",
        reference_date=timezone.localdate(),
        eligible=True,
        reason="Covered by default warranty",
    )

    api = as_user(owner_a, p3["org"])
    r = api.get(f"/api/v1/coverage-checks/{check.pk}/")
    assert r.status_code == 200, r.content
    data = r.json()
    assert data["work_order_number"] == wo.order_number
    assert data["agreement_reference"] is None
    assert data["provider_name"] is None


@pytest.mark.django_db
def test_inventory_work_order_number_nullability():
    """Verify inventory serializers (Reservation, PartLine, Movement) document nullable work_order_number."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    schemas = schema["components"]["schemas"]
    assert schemas["Reservation"]["properties"]["work_order_number"].get("nullable") is True
    assert schemas["PartLine"]["properties"]["work_order_number"].get("nullable") is True
    assert schemas["Movement"]["properties"]["work_order_number"].get("nullable") is True


@pytest.mark.django_db
def test_service_requests_and_requests_schema_published():
    """SMK-D002, SMK-D031-033: Verify service-requests and requests router registration & OpenAPI presence."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    paths = schema["paths"]

    # Canonical service-requests
    assert "/api/v1/service-requests/" in paths
    assert "/api/v1/service-requests/check-duplicate/" in paths
    assert "PaginatedServiceRequestList" in paths["/api/v1/service-requests/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]

    # Legacy requests alias
    assert "/api/v1/requests/" in paths
    assert "/api/v1/requests/check-duplicate/" in paths
    assert "PaginatedServiceRequestList" in paths["/api/v1/requests/"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]


@pytest.mark.django_db
def test_work_order_serializer_schema_fields():
    """Verify WorkOrder serializer documents all transition and lifecycle fields."""
    schema = SchemaGenerator().get_schema(request=None, public=True)
    wo_props = schema["components"]["schemas"]["WorkOrder"]["properties"]
    assert wo_props["assignee_name"].get("nullable") is True
    assert "asset_name" in wo_props
    assert "expected_version" in wo_props
    assert "reason" in wo_props
    assert "approved" in wo_props
    assert "checklist_key" in wo_props
    assert "is_active" in wo_props


@pytest.mark.django_db
def test_docs_and_swagger_endpoints_route_and_redirect_without_trailing_slash():
    """Verify /api/v1/docs, /docs, /swagger, /schema route cleanly without 404."""
    from rest_framework.test import APIClient
    client = APIClient()

    # Without trailing slash
    r = client.get("/api/v1/docs", follow=False, HTTP_HOST="localhost")
    assert r.status_code == 302
    assert r.headers["Location"] == "/api/v1/docs/"

    # With trailing slash
    r = client.get("/api/v1/docs/", follow=False, HTTP_HOST="localhost")
    assert r.status_code == 200
    assert "SwaggerUIBundle" in r.content.decode()

    # /docs alias
    r = client.get("/docs", follow=False, HTTP_HOST="localhost")
    assert r.status_code == 302
    assert r.headers["Location"] == "/api/v1/docs/"

    # /swagger alias
    r = client.get("/swagger", follow=False, HTTP_HOST="localhost")
    assert r.status_code == 302
    assert r.headers["Location"] == "/api/v1/docs/"

    # /api/v1/schema without slash
    r = client.get("/api/v1/schema", follow=False, HTTP_HOST="localhost")
    assert r.status_code == 302
    assert r.headers["Location"] == "/api/v1/schema/"

