"""Regression tests for Bug-004:
Action buttons and input fields under the Actions column are misaligned and overflowing in the parts table.
"""
from decimal import Decimal
import pytest
from django.test import Client
from django.urls import reverse

from apps.inventory import services as inv_services
from apps.inventory.models import WorkOrderPart
from tests.phase3_support import wo_in_progress

pytestmark = pytest.mark.django_db


def test_bug_004_parts_table_actions_alignment_classes_and_structure(inv_):
    org = inv_["org"]
    stores = inv_["stores"]
    tech = inv_["tech"]

    part = inv_services.create_part(
        org,
        part_number="PRT-8842-FLT",
        name="Fleet Hydraulic Filter",
        unit="pcs",
        actor=stores.user,
    )

    wo = wo_in_progress(inv_)

    line = inv_services.request_part(
        wo,
        part,
        Decimal("2"),
        actor=tech.user,
        membership=tech,
        notes="Urgent filter change",
    )

    client = Client()
    client.force_login(stores.user)
    session = client.session
    session["active_org_id"] = str(org.id)
    session.save()

    resp = client.get(reverse("inventory:wo_parts", kwargs={"pk": wo.pk}))
    assert resp.status_code == 200
    html = resp.content.decode()

    # 1. Verify table layout constraints
    assert "fx-parts-table" in html
    assert "fx-parts-actions-col" in html

    # 2. Verify action button container and control alignment classes
    assert "fx-parts-action-group" in html
    assert "fx-parts-action-form" in html
    assert "fx-parts-wh-select" in html
    assert "fx-parts-qty-input" in html
    assert "fx-parts-btn" in html

    # 3. Verify Reserve and Cancel buttons render with proper styling
    assert "Reserve" in html
    assert "Cancel" in html
