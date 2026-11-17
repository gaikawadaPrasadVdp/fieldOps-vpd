"""Tests for Asset Detail Inspection Trigger (PRD §3.3 M08).
Verifies that inspections can be initiated directly from the Asset Detail UI,
enforcing RBAC permissions, lifecycle rules, template selection, and execution redirect.
"""
import uuid
from django.urls import reverse
import pytest

from apps.assets.models import Asset
from apps.checklists.models import ChecklistTemplate, Inspection
from apps.checklists import services as checklist_services


@pytest.fixture
def active_template(p3):
    t = ChecklistTemplate.objects.create(
        organization=p3["org"],
        key=uuid.uuid4(),
        name="Pump Visual Inspection",
        version=1,
        status="ACTIVE",
    )
    return t


def test_asset_detail_shows_start_inspection_button(p3, client, active_template):
    """Asset detail displays 'Start inspection' button for authorized users."""
    client.force_login(p3["tech"].user)
    # Switch active org in session
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session.save()

    resp = client.get(reverse("assets:detail", args=[p3["asset"].pk]))
    assert resp.status_code == 200
    assert b"Start inspection" in resp.content
    assert reverse("assets:start_inspection", args=[p3["asset"].pk]).encode() in resp.content


def test_asset_start_inspection_get_and_post(p3, client, active_template):
    """GET shows template selection; POST starts inspection and redirects to runner."""
    client.force_login(p3["tech"].user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session.save()

    # 1. GET selection form
    url = reverse("assets:start_inspection", args=[p3["asset"].pk])
    get_res = client.get(url)
    assert get_res.status_code == 200
    assert active_template.name.encode() in get_res.content

    # 2. POST to start inspection
    post_res = client.post(url, {"template_id": str(active_template.pk)}, follow=False)
    assert post_res.status_code == 302

    # Verify inspection was created with no work_order
    insp = Inspection.objects.filter(asset=p3["asset"]).latest("started_at")
    assert insp.template_id == active_template.pk
    assert insp.work_order is None
    assert insp.started_by_id == p3["tech"].pk
    assert post_res["Location"] == reverse("checklists:inspection_run", args=[insp.pk])


def test_asset_start_inspection_permission_denied(p3, client, active_template):
    """User lacking inspection.execute cannot start an inspection."""
    client.force_login(p3["reader"].user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session.save()

    url = reverse("assets:start_inspection", args=[p3["asset"].pk])
    res = client.get(url)
    assert res.status_code == 403


def test_asset_start_inspection_terminal_blocked(p3, client, active_template):
    """Retired or disposed assets cannot be inspected."""
    client.force_login(p3["tech"].user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session.save()

    p3["asset"].status = Asset.Status.RETIRED
    p3["asset"].save(update_fields=["status"])

    url = reverse("assets:start_inspection", args=[p3["asset"].pk])
    res = client.post(url, {"template_id": str(active_template.pk)}, follow=True)
    assert b"Cannot inspect asset in RETIRED status" in res.content


def test_asset_detail_inspections_tab(p3, client, active_template):
    """Asset detail tab=inspections lists previous standalone and linked inspections."""
    insp = checklist_services.start_inspection(
        p3["org"],
        template=active_template,
        membership=p3["tech"],
        actor=p3["tech"].user,
        asset=p3["asset"],
    )

    client.force_login(p3["tech"].user)
    session = client.session
    session["active_org_id"] = str(p3["org"].pk)
    session.save()

    res = client.get(reverse("assets:detail", args=[p3["asset"].pk]) + "?tab=inspections")
    assert res.status_code == 200
    assert active_template.name.encode() in res.content
    assert b"Inspection History" in res.content
