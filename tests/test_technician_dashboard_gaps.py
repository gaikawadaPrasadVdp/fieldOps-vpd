"""Tests covering Phase 1-3 PRD gap fixes for Technician Dashboard & Navigation."""
from __future__ import annotations

import datetime
import uuid

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Asset, AssetCategory
from apps.checklists.models import ChecklistItem, ChecklistTemplate, Finding, Inspection
from apps.dashboards import metrics
from apps.rbac import services as rbac
from apps.rbac.models import Role, RolePermission
from apps.sites.models import Site
from apps.tenancy.models import Membership
from apps.ui.utils import is_client_membership
from apps.workorders.models import WorkOrder


def _login_client(user) -> Client:
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_my_work_cockpit_hides_operational_hub_link_for_technician_without_report_view(
    org_a, make_member, owner_a
):
    tech_m = make_member(org_a, "gap.tech1@alpha.test", "technician")
    tech_client = _login_client(tech_m.user)

    r_tech = tech_client.get(reverse("dashboards:my_work"))
    assert r_tech.status_code == 200
    assert r_tech.context["can_view_hub"] is False
    assert b"Operational Hub" not in r_tech.content
    assert b"Technician Workspace" in r_tech.content

    owner_client = _login_client(owner_a)
    r_owner = owner_client.get(reverse("dashboards:my_work"))
    assert r_owner.status_code == 200
    assert r_owner.context["can_view_hub"] is True
    assert b"Operational Hub" in r_owner.content


@pytest.mark.django_db
def test_my_work_cockpit_excludes_review_and_closed_from_active_queue(org_a, make_member, owner_a):
    site = Site.objects.create(organization=org_a, code="GAP-S1", name="Gap Site 1")
    tech_m = make_member(org_a, "gap.tech2@alpha.test", "technician")

    def _wo(title, status):
        return WorkOrder.objects.create(
            organization=org_a,
            site=site,
            title=title,
            order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
            status=status,
            assigned_to=tech_m,
            created_by=owner_a,
        )

    active_wo = _wo("Active Dispatched Job", WorkOrder.Status.DISPATCHED)
    _wo("Pending Review Job", WorkOrder.Status.SUPERVISOR_REVIEW)
    _wo("Already Closed Job", WorkOrder.Status.CLOSED)
    _wo("Already Completed Job", WorkOrder.Status.COMPLETED)

    client = _login_client(tech_m.user)
    r = client.get(reverse("dashboards:my_work"))
    assert r.status_code == 200
    open_ids = {wo.pk for wo in r.context["open_jobs"]}
    assert open_ids == {active_wo.pk}


@pytest.mark.django_db
def test_field_technician_role_parity_in_ui_and_metrics(org_a, owner_a):
    from apps.accounts.models import User
    from apps.rbac.models import Permission
    from apps.rbac.role_templates import BY_KEY
    from apps.rbac.services import _template_codes

    # Provision a role with explicit system_key="field_technician"
    ft_tpl = BY_KEY["field_technician"]
    ft_role = Role.objects.create(
        organization=org_a,
        name="Field Technician Alias",
        description=ft_tpl.description,
        system_key="field_technician",
        is_owner=False,
    )
    perm_by_code = {p.code: p for p in Permission.objects.all()}
    for code in _template_codes(ft_tpl):
        if code in perm_by_code:
            RolePermission.objects.create(role=ft_role, permission=perm_by_code[code])

    user = User.objects.create_user(
        email="field.tech.alias@alpha.test",
        password="Password123!",
        full_name="Alias Field Tech",
    )
    ft_member = Membership.objects.create(
        organization=org_a, user=user, status=Membership.Status.ACTIVE
    )
    rbac.set_membership_roles(ft_member, [ft_role], actor=None, system=True)

    from apps.ui.utils import is_technician_membership

    assert is_client_membership(ft_member) is False
    assert is_technician_membership(ft_member) is True

    site = Site.objects.create(organization=org_a, code="FT-S1", name="FT Site")
    start_dt, end_dt = metrics.parse_date_window()
    util = metrics.compute_technician_utilization(org_a, [site], start_dt, end_dt)
    assert util["technicians"] >= 1

    client = _login_client(user)
    r_my_work = client.get(reverse("dashboards:my_work"))
    assert r_my_work.status_code == 200
    assert r_my_work.context["is_technician"] is True

    r_wo_list = client.get(reverse("workorders:list"))
    assert r_wo_list.status_code == 200
    assert r_wo_list.context["is_technician"] is True


@pytest.mark.django_db
def test_inspection_list_scopes_open_findings_kpi_for_technician(org_a, make_member, owner_a):
    site = Site.objects.create(organization=org_a, code="INSP-S1", name="Inspection Site")
    cat = AssetCategory.objects.create(organization=org_a, name="Compressors")
    asset = Asset.objects.create(
        organization=org_a,
        site=site,
        category=cat,
        asset_tag="COMP-01",
        name="Compressor 1",
    )
    tech1 = make_member(org_a, "insp.tech1@alpha.test", "technician")
    tech2 = make_member(org_a, "insp.tech2@alpha.test", "technician")

    tpl = ChecklistTemplate.objects.create(
        organization=org_a,
        key=uuid.uuid4(),
        name="Compressor Safety Check",
        status="ACTIVE",
        created_by=owner_a,
    )
    item = ChecklistItem.objects.create(
        organization=org_a,
        template=tpl,
        position=1,
        prompt="Check gauge pressure",
        item_type=ChecklistItem.ItemType.BOOLEAN,
    )

    wo1 = WorkOrder.objects.create(
        organization=org_a,
        site=site,
        asset=asset,
        title="Tech1 WO",
        order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
        status=WorkOrder.Status.IN_PROGRESS,
        assigned_to=tech1,
        created_by=owner_a,
    )
    wo2 = WorkOrder.objects.create(
        organization=org_a,
        site=site,
        asset=asset,
        title="Tech2 WO",
        order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
        status=WorkOrder.Status.IN_PROGRESS,
        assigned_to=tech2,
        created_by=owner_a,
    )

    insp1 = Inspection.objects.create(
        organization=org_a,
        template=tpl,
        site=site,
        asset=asset,
        work_order=wo1,
        started_by=tech1,
    )
    insp2 = Inspection.objects.create(
        organization=org_a,
        template=tpl,
        site=site,
        asset=asset,
        work_order=wo2,
        started_by=tech2,
    )

    Finding.objects.create(
        organization=org_a,
        inspection=insp1,
        item=item,
        asset=asset,
        site=site,
        work_order=wo1,
        description="Minor leak on tech1 WO",
        severity="MEDIUM",
        status="OPEN",
        created_by=tech1.user,
    )
    Finding.objects.create(
        organization=org_a,
        inspection=insp2,
        item=item,
        asset=asset,
        site=site,
        work_order=wo2,
        description="Hidden leak on tech2 WO",
        severity="HIGH",
        status="OPEN",
        created_by=tech2.user,
    )

    client1 = _login_client(tech1.user)
    r = client1.get(reverse("checklists:inspections"))
    assert r.status_code == 200
    assert r.context["kpis"]["open_findings"] == 1


@pytest.mark.django_db
def test_work_completion_trend_in_my_work_and_api(org_a, make_member, owner_a):
    from rest_framework.test import APIClient

    site = Site.objects.create(organization=org_a, code="TR-S1", name="Trend Site 1")
    tech1 = make_member(org_a, "trend.tech1@alpha.test", "technician")
    tech2 = make_member(org_a, "trend.tech2@alpha.test", "technician")
    now = timezone.now()
    today = now.astimezone(datetime.UTC).date()
    yesterday = today - datetime.timedelta(days=1)

    WorkOrder.objects.create(
        organization=org_a,
        site=site,
        title="Completed Today",
        order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
        status=WorkOrder.Status.COMPLETED,
        assigned_to=tech1,
        created_by=owner_a,
        completed_at=now,
    )
    WorkOrder.objects.create(
        organization=org_a,
        site=site,
        title="Closed After Yesterday Completion",
        order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
        status=WorkOrder.Status.CLOSED,
        assigned_to=tech1,
        created_by=owner_a,
        completed_at=now - datetime.timedelta(days=1),
    )
    # Other technician's completed order should be excluded from tech1's personal trend
    WorkOrder.objects.create(
        organization=org_a,
        site=site,
        title="Tech2 Completed",
        order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
        status=WorkOrder.Status.COMPLETED,
        assigned_to=tech2,
        created_by=owner_a,
        completed_at=now,
    )

    start_dt, end_dt = metrics.parse_date_window(
        (today - datetime.timedelta(days=6)).isoformat(),
        today.isoformat(),
    )
    my_data = metrics.get_my_work_dashboard(tech1, start_dt, end_dt)
    assert my_data["kpis"]["completed_in_window"] == 2
    trend = my_data["details"]["completion_trend"]
    by_date = {row["date"]: row["count"] for row in trend}
    assert by_date[today.isoformat()] == 1
    assert by_date[yesterday.isoformat()] == 1

    # HTML My Work Cockpit renders Work Completion Trend section
    ui_client = _login_client(tech1.user)
    r_html = ui_client.get(
        reverse("dashboards:my_work")
        + f"?from={(today - datetime.timedelta(days=6)).isoformat()}&to={today.isoformat()}"
    )
    assert r_html.status_code == 200
    assert b"Work Completion Trend" in r_html.content

    # JSON API exposes completion_trend
    api_client = APIClient()
    api_client.force_authenticate(user=tech1.user)
    api_client.credentials(HTTP_X_ORGANIZATION=str(org_a.pk))
    r_api = api_client.get(
        f"/api/v1/dashboards/my-work/?from={(today - datetime.timedelta(days=6)).isoformat()}&to={today.isoformat()}"
    )
    assert r_api.status_code == 200
    assert "completion_trend" in r_api.data["data"]["details"]


@pytest.mark.django_db
def test_operations_hub_exposes_work_completion_trend(org_a, owner_a, make_member):
    site = Site.objects.create(organization=org_a, code="OPS-TR1", name="Ops Trend Site")
    tech = make_member(org_a, "opstrend.tech@alpha.test", "technician")
    now = timezone.now()
    today = now.astimezone(datetime.UTC).date()

    WorkOrder.objects.create(
        organization=org_a,
        site=site,
        title="Ops Completed Order",
        order_number=f"WO-{uuid.uuid4().hex[:8].upper()}",
        status=WorkOrder.Status.CLOSED,
        assigned_to=tech,
        created_by=owner_a,
        completed_at=now,
    )

    start_dt, end_dt = metrics.parse_date_window(
        (today - datetime.timedelta(days=6)).isoformat(),
        today.isoformat(),
    )
    ops_data = metrics.get_operations_dashboard(org_a, [site], start_dt, end_dt)
    assert "completion_trend" in ops_data["details"]
    assert any(item["count"] >= 1 for item in ops_data["details"]["completion_trend"])

    client = _login_client(owner_a)
    r_hub = client.get(
        reverse("dashboards:hub")
        + f"?section=operations&from={(today - datetime.timedelta(days=6)).isoformat()}&to={today.isoformat()}"
    )
    assert r_hub.status_code == 200
    assert b"Work Completion Trend" in r_hub.content


@pytest.mark.django_db
def test_shell_context_preserves_session_idle_timeout_ms(org_a, make_member, settings):
    settings.SESSION_IDLE_TIMEOUT_SECONDS = 300
    tech = make_member(org_a, "idle.tech@alpha.test", "technician")
    client = _login_client(tech.user)
    r = client.get("/app/")
    assert r.status_code == 200
    assert r.context["session_idle_timeout_ms"] == 300000
    assert b'data-idle-timeout-ms="300000"' in r.content
