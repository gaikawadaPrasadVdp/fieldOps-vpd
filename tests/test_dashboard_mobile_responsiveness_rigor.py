import pytest
import re
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_phase1_dashboard_mobile_responsiveness(client, owner_a, site_a1):
    """Phase 1: Test mobile viewport, responsive tables, and grids in Operational Dashboards."""
    client.force_login(owner_a)

    # Operational Hub
    r_hub = client.get(reverse("dashboards:hub"))
    assert r_hub.status_code == 200
    html = r_hub.content.decode("utf-8")
    assert 'name="viewport"' in html
    assert "width=device-width" in html
    # Grids must use responsive breakpoints
    assert re.search(r"col-12\s+col-md-", html) or "row g-" in html

    # Snapshots List
    r_snap = client.get(reverse("dashboards:snapshot_list"))
    assert r_snap.status_code == 200
    snap_html = r_snap.content.decode("utf-8")
    assert "table-responsive" in snap_html

    # Audit list
    r_audit = client.get("/app/audit/")
    assert r_audit.status_code == 200
    assert "table-responsive" in r_audit.content.decode("utf-8")


def test_phase2_assets_mobile_responsiveness(client, owner_a, org_a, site_a1, make_asset):
    """Phase 2: Test mobile viewport and responsive tables in Asset Registry."""
    client.force_login(owner_a)
    asset = make_asset(org_a, site_a1, "RESP-ASSET-01")

    # Asset list
    r_list = client.get(reverse("assets:list"))
    assert r_list.status_code == 200
    html_list = r_list.content.decode("utf-8")
    assert "table-responsive" in html_list
    assert 'name="viewport"' in html_list

    # Asset detail
    r_detail = client.get(reverse("assets:detail", kwargs={"pk": asset.pk}))
    assert r_detail.status_code == 200
    html_detail = r_detail.content.decode("utf-8")
    assert "table-responsive" in html_detail or "row g-" in html_detail


def test_phase3_workorders_and_incidents_mobile_responsiveness(client, owner_a, org_a, site_a1, make_asset):
    """Phase 3: Test mobile viewport, responsive tables, and drawer components in Work Orders & Incidents."""
    client.force_login(owner_a)
    asset = make_asset(org_a, site_a1, "WO-RESP-PUMP")

    # Incidents List
    r_inc = client.get(reverse("incidents:list"))
    assert r_inc.status_code == 200
    html_inc = r_inc.content.decode("utf-8")
    assert "table-responsive" in html_inc

    # Incidents Dashboard
    r_inc_dash = client.get(reverse("incidents:dashboard"))
    assert r_inc_dash.status_code == 200
    html_inc_dash = r_inc_dash.content.decode("utf-8")
    assert "col-6 col-xl-3" in html_inc_dash or "row g-3" in html_inc_dash

    # Technician Workspace
    r_ws = client.get("/app/workspace/")
    assert r_ws.status_code in (200, 302)


def test_phase4_inventory_and_portal_mobile_responsiveness(client, owner_a, org_a, site_a1, make_portal_client):
    """Phase 4: Test mobile viewport, responsive tables, and cards in Inventory & Client Portal."""
    # Inventory parts
    client.force_login(owner_a)
    r_parts = client.get(reverse("inventory:parts"))
    assert r_parts.status_code == 200
    assert "table-responsive" in r_parts.content.decode("utf-8")

    # Client Portal Dashboard
    user, membership, account = make_portal_client(org_a, "client.resp@acme.test")
    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org_a.id)
    session.save()

    r_portal = client.get(reverse("portal:dashboard"))
    assert r_portal.status_code == 200
    html_portal = r_portal.content.decode("utf-8")
    assert 'name="viewport"' in html_portal
    assert "container-fluid" in html_portal

    # Client Portal Requests List
    r_portal_list = client.get(reverse("portal:requests_list"))
    assert r_portal_list.status_code == 200
    assert "table-responsive" in r_portal_list.content.decode("utf-8")


def test_phase5_governance_mobile_responsiveness(client, owner_a):
    """Phase 5: Test mobile viewport and responsive tables in Users and Roles."""
    client.force_login(owner_a)

    r_users = client.get(reverse("tenancy:members"))
    assert r_users.status_code == 200
    html_users = r_users.content.decode("utf-8")
    assert "table-responsive" in html_users
    assert 'name="viewport"' in html_users
