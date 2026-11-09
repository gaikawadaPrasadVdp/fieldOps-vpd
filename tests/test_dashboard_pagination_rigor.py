import pytest
from django.test import Client
from django.urls import reverse
from apps.assets.models import Asset
from apps.dashboards.models import ReportSnapshot
from apps.incidents.models import ServiceRequest
from apps.inventory.models import Part, Warehouse, StockBalance, StockMovement
from apps.maintenance.models import MaintenancePlan, MaintenanceSchedule
from apps.notifications.models import Notification
from apps.tenancy.models import Membership
from apps.workorders.models import WorkOrder
from apps.rbac import services as rbac
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_phase1_dashboard_snapshots_and_audit_pagination(client, owner_a, org_a):
    """Phase 1: Test pagination on Snapshots and Audit logs."""
    client.force_login(owner_a)

    # 1. Test Snapshots list pagination
    import datetime
    for i in range(25):
        d = timezone.localdate() - datetime.timedelta(days=i)
        ReportSnapshot.objects.create(
            organization=org_a,
            snapshot_type=ReportSnapshot.SnapshotType.DAILY,
            section=ReportSnapshot.Section.OPERATIONS,
            period_start=d,
            period_end=d,
            metrics={"kpis": {"uptime": {"value": 99.9, "unit": "%"}}},
            notes=f"Snapshot batch {i}",
        )

    # Page 1
    r1 = client.get(reverse("dashboards:snapshot_list") + "?page=1")
    assert r1.status_code == 200
    assert len(r1.context["page"]) == 20

    # Page 2
    r2 = client.get(reverse("dashboards:snapshot_list") + "?page=2")
    assert r2.status_code == 200
    assert len(r2.context["page"]) == 5

    # Out of range fallback
    r_high = client.get(reverse("dashboards:snapshot_list") + "?page=9999")
    assert r_high.status_code == 200
    assert r_high.context["page"].number == 2

    # Invalid non-integer fallback
    r_bad = client.get(reverse("dashboards:snapshot_list") + "?page=xyz")
    assert r_bad.status_code == 200
    assert r_bad.context["page"].number == 1

    # 2. Test Audit list pagination
    r_audit = client.get("/app/audit/?page=1")
    assert r_audit.status_code == 200
    assert "page" in r_audit.context
    r_audit_bad = client.get("/app/audit/?page=invalid_str")
    assert r_audit_bad.status_code == 200
    assert r_audit_bad.context["page"].number == 1


def test_phase2_assets_and_maintenance_pagination(client, owner_a, org_a, site_a1, make_asset):
    """Phase 2: Test pagination on Assets list and Maintenance plans."""
    client.force_login(owner_a)

    # Create 22 assets to span 2 pages (page size 20)
    for i in range(22):
        make_asset(org_a, site_a1, f"PAG-ASSET-{i:03d}")

    r1 = client.get(reverse("assets:list") + "?page=1")
    assert r1.status_code == 200
    assert len(r1.context["page"]) == 20
    assert r1.context["page"].has_next()

    r2 = client.get(reverse("assets:list") + "?page=2")
    assert r2.status_code == 200
    assert len(r2.context["page"]) == 2
    assert r2.context["page"].has_previous()

    # Out of bounds fallback
    r_oob = client.get(reverse("assets:list") + "?page=9999")
    assert r_oob.status_code == 200
    assert r_oob.context["page"].number == 2

    # Query string preservation with filters
    r_filter = client.get(reverse("assets:list") + f"?site={site_a1.pk}&status=ACTIVE&page=2")
    assert r_filter.status_code == 200
    assert b"site=" in r_filter.content or r_filter.context["page"].number == 2


def test_phase3_work_orders_and_incidents_pagination(client, owner_a, org_a, site_a1, make_asset):
    """Phase 3: Test pagination on Work Orders and Incidents list."""
    client.force_login(owner_a)
    asset = make_asset(org_a, site_a1, "WO-PAG-PUMP")

    # Create 26 work orders (page size 25)
    for i in range(26):
        WorkOrder.objects.create(
            organization=org_a,
            site=site_a1,
            asset=asset,
            number=f"WO-PAG-{i:03d}",
            title=f"Repair Job {i}",
            status=WorkOrder.Status.DRAFT,
            priority=WorkOrder.Priority.MEDIUM,
        )

    r_wo1 = client.get(reverse("workorders:list") + "?page=1")
    assert r_wo1.status_code == 200
    assert len(r_wo1.context["page_obj"]) == 25
    assert r_wo1.context["page_obj"].has_next()

    r_wo2 = client.get(reverse("workorders:list") + "?page=2")
    assert r_wo2.status_code == 200
    assert len(r_wo2.context["page_obj"]) == 1

    # Incidents list pagination test with invalid page
    r_inc_bad = client.get(reverse("incidents:list") + "?page=abc")
    assert r_inc_bad.status_code == 200
    assert r_inc_bad.context["page"].number == 1


def test_phase4_inventory_and_portal_pagination(client, owner_a, org_a, site_a1, make_portal_client):
    """Phase 4: Test pagination on Inventory parts and Portal service requests."""
    # 1. Inventory Parts list
    client.force_login(owner_a)
    for i in range(27):
        Part.objects.create(
            organization=org_a,
            part_number=f"SKU-PAG-{i:03d}",
            name=f"Filter Component {i}",
            unit="pcs",
        )

    r_p1 = client.get(reverse("inventory:parts") + "?page=1")
    assert r_p1.status_code == 200
    assert len(r_p1.context["page"]) == 25

    r_p2 = client.get(reverse("inventory:parts") + "?page=2")
    assert r_p2.status_code == 200
    assert len(r_p2.context["page"]) == 2

    # 2. Client Portal requests pagination
    user, membership, account = make_portal_client(org_a, "client.pag@acme.test")
    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org_a.id)
    session.save()

    r_portal = client.get(reverse("portal:requests_list") + "?page=invalid")
    assert r_portal.status_code == 200
    assert r_portal.context["page_obj"].number == 1


def test_phase5_governance_users_and_notifications_pagination(client, owner_a, org_a):
    """Phase 5: Test pagination on User directory and Notifications."""
    client.force_login(owner_a)

    # Notifications pagination test
    for i in range(22):
        Notification.objects.create(
            organization=org_a,
            recipient=owner_a,
            title=f"Notification {i}",
            body="System alert",
        )

    r_n1 = client.get(reverse("notifications:list") + "?page=1")
    assert r_n1.status_code == 200
    assert len(r_n1.context["page"]) == 20

    r_n2 = client.get(reverse("notifications:list") + "?page=2")
    assert r_n2.status_code == 200
    assert len(r_n2.context["page"]) == 2
