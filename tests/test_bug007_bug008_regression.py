import pytest
from django.urls import reverse
from django.utils import timezone
from apps.dashboards.models import ReportSnapshot

pytestmark = pytest.mark.django_db


def test_bug007_mtbf_card_and_modal_present(client, owner_a, org_a, site_a1):
    """BUG-007: MTBF KPI card is interactive with modal and tooltip."""
    client.force_login(owner_a)
    resp = client.get(reverse("dashboards:hub"), {"section": "assets"})
    assert resp.status_code == 200
    html = resp.content.decode("utf-8")
    assert "mtbfModal" in html
    assert "Mean Time Between Failures (MTBF) Details" in html
    assert "Why does this show n/a?" in html


def test_bug008_snapshot_form_requires_dates(client, owner_a, org_a):
    """BUG-008: Snapshot creation enforces required period dates and order."""
    client.force_login(owner_a)
    
    # 1. Missing dates should fail and redirect with error message
    resp_empty = client.post(reverse("dashboards:snapshot_list"), {
        "section": "OPERATIONS",
        "snapshot_type": "DAILY",
        "period_start": "",
        "period_end": "",
    }, follow=True)
    assert resp_empty.status_code == 200
    messages = [m.message for m in resp_empty.context["messages"]]
    assert any("Period Start and Period End dates are required." in m for m in messages)
    
    # 2. Start date after end date should fail
    resp_inverted = client.post(reverse("dashboards:snapshot_list"), {
        "section": "OPERATIONS",
        "snapshot_type": "DAILY",
        "period_start": "2026-11-20",
        "period_end": "2026-11-10",
    }, follow=True)
    assert resp_inverted.status_code == 200
    messages_inv = [m.message for m in resp_inverted.context["messages"]]
    assert any("Period Start cannot be after Period End." in m for m in messages_inv)
    
    # 3. Valid dates should succeed
    resp_valid = client.post(reverse("dashboards:snapshot_list"), {
        "section": "OPERATIONS",
        "snapshot_type": "DAILY",
        "period_start": "2026-11-10",
        "period_end": "2026-11-10",
        "notes": "Valid snapshot test",
    }, follow=True)
    assert resp_valid.status_code == 200
    assert ReportSnapshot.objects.filter(organization=org_a, notes="Valid snapshot test").exists()
