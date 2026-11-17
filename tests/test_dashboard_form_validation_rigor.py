from apps.sites.models import Site
import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse
from apps.assets.forms import AssetForm
from apps.assets.models import Asset, AssetCategory
from apps.dashboards.models import ReportSnapshot
from apps.incidents.forms import RequestForm
from apps.inventory.forms import PartForm, RequestPartForm
from apps.inventory.models import Part
from apps.portal.forms import PortalServiceRequestForm
from apps.tenancy.forms import InviteForm, RoleForm
from apps.workorders.forms import CreateWorkOrderForm
from apps.workorders.models import WorkOrder
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_phase1_snapshot_form_validation(client, owner_a, org_a):
    """Phase 1: Test validation of snapshot creation form."""
    client.force_login(owner_a)

    # 1. Invalid start date / missing dates
    r_bad = client.post(reverse("dashboards:snapshot_list"), {
        "section": "OPERATIONS",
        "snapshot_type": "DAILY",
        "period_start": "invalid-date",
        "period_end": "invalid-date",
    })
    # Should handle gracefully without 500 error
    assert r_bad.status_code in (200, 302, 400)

    # 2. Valid generation
    today = timezone.localdate().isoformat()
    r_good = client.post(reverse("dashboards:snapshot_list"), {
        "section": "OPERATIONS",
        "snapshot_type": "DAILY",
        "period_start": today,
        "period_end": today,
        "notes": "Verified snapshot creation",
    })
    assert r_good.status_code == 302
    assert ReportSnapshot.objects.filter(organization=org_a, notes="Verified snapshot creation").exists()


def test_phase2_asset_form_validation(org_a, site_a1):
    """Phase 2: Test validation of AssetForm."""
    cat = AssetCategory.objects.create(organization=org_a, name="Motors")

    # 1. Missing mandatory fields
    blank_form = AssetForm(data={}, org=org_a, sites=Site.objects.filter(pk=site_a1.pk))
    assert not blank_form.is_valid()
    assert "asset_tag" in blank_form.errors
    assert "name" in blank_form.errors
    assert "site" in blank_form.errors

    # 2. Name with invalid numbers rejected by alphabetical validator
    num_name_form = AssetForm(data={
        "asset_tag": "PUMP-001",
        "name": "Pump 2500 X",
        "site": str(site_a1.pk),
        "category": str(cat.pk),
        "criticality": "HIGH",
    }, org=org_a, sites=Site.objects.filter(pk=site_a1.pk))
    assert not num_name_form.is_valid()
    assert "name" in num_name_form.errors

    # 3. Clean alphabetical name accepted
    clean_form = AssetForm(data={
        "asset_tag": "PUMP-001",
        "name": "Primary Water Feed Pump",
        "site": str(site_a1.pk),
        "category": str(cat.pk),
        "criticality": "HIGH",
    }, org=org_a, sites=Site.objects.filter(pk=site_a1.pk))
    assert clean_form.is_valid(), clean_form.errors


def test_phase3_work_order_and_incident_form_validation(org_a, site_a1, make_member, make_asset):
    """Phase 3: Test validation of CreateWorkOrderForm and RequestForm."""
    planner = make_member(org_a, "planner.val@alpha.test", "maintenance_planner")
    asset = make_asset(org_a, site_a1, "VAL-PUMP")

    # 1. CreateWorkOrderForm missing required fields
    wo_blank = CreateWorkOrderForm({}, membership=planner)
    assert not wo_blank.is_valid()
    assert "title" in wo_blank.errors
    assert "site" in wo_blank.errors
    assert "asset" in wo_blank.errors

    # 2. Title with industrial number accepted
    wo_valid = CreateWorkOrderForm({
        "source_type": WorkOrder.SourceType.MANUAL,
        "site": str(site_a1.pk),
        "asset": str(asset.pk),
        "title": "Pump 2 seal replacement",
    }, membership=planner)
    assert wo_valid.is_valid(), wo_valid.errors

    # 3. Incident RequestForm validation
    inc_blank = RequestForm(data={})
    assert not inc_blank.is_valid()
    assert "title" in inc_blank.errors
    assert "asset" in inc_blank.errors


def test_phase4_inventory_and_portal_form_validation(org_a, site_a1, make_asset, make_portal_client):
    """Phase 4: Test validation of PartForm, RequestPartForm, and PortalServiceRequestForm."""
    # 1. PartForm: rejects negative stock values
    part_bad = PartForm(data={
        "part_number": "SKU-100",
        "name": "Oil Seal",
        "unit": "pcs",
        "min_stock": -5,
    })
    assert not part_bad.is_valid()
    assert "min_stock" in part_bad.errors

    # 2. RequestPartForm: rejects non-numeric quantities
    req_bad = RequestPartForm(data={"quantity": "five", "notes": "Emergency part"})
    assert not req_bad.is_valid()
    assert "quantity" in req_bad.errors

    # 3. PortalServiceRequestForm: validates client form
    user, membership, account = make_portal_client(org_a, "client.fval@acme.test")
    portal_blank = PortalServiceRequestForm(data={}, organization=org_a, membership=membership)
    assert not portal_blank.is_valid()
    assert "title" in portal_blank.errors
    assert "asset" in portal_blank.errors


def test_phase5_invite_and_role_form_validation(org_a):
    """Phase 5: Test validation of InviteForm and RoleForm."""
    # 1. InviteForm rejects invalid email domain
    invite_bad_email = InviteForm(data={
        "email": "user@gmail.123",
        "full_name": "Jane Doe",
        "password": "FieldOps@2026!",
    }, org=org_a)
    assert not invite_bad_email.is_valid()
    assert "email" in invite_bad_email.errors

    # 2. InviteForm rejects numbers in full name
    invite_bad_name = InviteForm(data={
        "email": "jane.doe@validcompany.com",
        "full_name": "Jane Doe 2nd",
        "password": "FieldOps@2026!",
    }, org=org_a)
    assert not invite_bad_name.is_valid()
    assert "full_name" in invite_bad_name.errors
