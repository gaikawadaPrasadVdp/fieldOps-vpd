import pytest
from datetime import timedelta
from django.utils import timezone
from django.test import Client
from apps.accounts.models import User
from apps.rbac import services as rbac
from apps.rbac.models import Permission, Role, RolePermission
from apps.sites.models import Site
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership
from apps.workorders.models import TechnicianProfile as WOTechnicianProfile, WorkOrder
from apps.workorders import services as wo_services
from apps.workorders.forms import AssignForm
from apps.workorders.assignment_rules import available_technicians
from apps.workspace.models import TechnicianProfile as WSTechnicianProfile


@pytest.fixture
def wo_planned(org_a, site_a1, make_member, make_asset):
    dispatcher = make_member(org_a, "dispatcher_main@alpha.test", "service_dispatcher")
    asset = make_asset(org_a, site_a1, "AST-WO-001")
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=3)
    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        title="Check HVAC circuit",
        asset=asset,
        membership=dispatcher,
        actor=dispatcher.user,
        source_type=WorkOrder.SourceType.MANUAL,
    )
    wo = wo_services.plan_work_order(
        wo,
        membership=dispatcher,
        actor=dispatcher.user,
        planned_start=start,
        planned_end=end,
        due_at=end + timedelta(days=2),
        estimated_hours=3,
        work_type=WorkOrder.WorkType.CORRECTIVE,
        priority=WorkOrder.Priority.HIGH,
    )
    return wo, dispatcher, start, end


@pytest.mark.django_db
def test_newly_added_technician_invited_status_appears_in_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    new_tech_invited = tenancy.invite_member(
        org_a,
        email="newtech_invited@alpha.test",
        full_name="New Test Technician Invited",
        role_ids=[tech_role.pk],
        actor=owner_a,
    )
    assert new_tech_invited.status == Membership.Status.INVITED

    available = available_technicians(wo)
    assert new_tech_invited in available

    form = AssignForm(membership=dispatcher, site=wo.site, work_order=wo)
    assert new_tech_invited in form.fields["assigned_to"].queryset

    assigned = wo_services.assign_work_order(
        wo,
        membership=dispatcher,
        actor=dispatcher.user,
        assignee_id=new_tech_invited.pk,
        scheduled_start=start,
        scheduled_end=end,
    )
    assert assigned.status == WorkOrder.Status.ASSIGNED
    assert assigned.assigned_to == new_tech_invited


@pytest.mark.django_db
def test_newly_added_technician_active_status_appears_in_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    new_tech_active = tenancy.invite_member(
        org_a,
        email="newtech_active@alpha.test",
        full_name="New Test Technician Active",
        role_ids=[tech_role.pk],
        actor=owner_a,
        password="FieldOps@2026!",
    )
    assert new_tech_active.status == Membership.Status.ACTIVE

    available = available_technicians(wo)
    assert new_tech_active in available

    form = AssignForm(membership=dispatcher, site=wo.site, work_order=wo)
    assert new_tech_active in form.fields["assigned_to"].queryset


@pytest.mark.django_db
def test_newly_added_technician_custom_role_appears_in_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned

    custom_role = Role.objects.create(
        organization=org_a,
        name="Lead Field Technician",
        system_key="",
    )
    perm = Permission.objects.get(code="work_order.start")
    RolePermission.objects.create(role=custom_role, permission=perm)

    new_tech_custom = tenancy.invite_member(
        org_a,
        email="newtech_custom@alpha.test",
        full_name="New Test Technician Custom Role",
        role_ids=[custom_role.pk],
        actor=owner_a,
        password="ValidPassword123!",
    )

    available = available_technicians(wo)
    assert new_tech_custom in available

    form = AssignForm(membership=dispatcher, site=wo.site, work_order=wo)
    assert new_tech_custom in form.fields["assigned_to"].queryset


@pytest.mark.django_db
def test_newly_added_technician_named_technician_without_system_key(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned

    named_role = Role.objects.create(
        organization=org_a,
        name="Contract Technician",
        system_key="",
    )
    perm = Permission.objects.get(code="work_order.start")
    RolePermission.objects.create(role=named_role, permission=perm)

    new_tech_named = tenancy.invite_member(
        org_a,
        email="newtech_named@alpha.test",
        full_name="Contract Tech Person",
        role_ids=[named_role.pk],
        actor=owner_a,
    )

    available = available_technicians(wo)
    assert new_tech_named in available


@pytest.mark.django_db
def test_undispatchable_technician_excluded_from_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    tech = tenancy.invite_member(
        org_a,
        email="undispatchable@alpha.test",
        full_name="Undispatchable Tech",
        role_ids=[tech_role.pk],
        actor=owner_a,
        password="FieldOps@2026!",
    )
    WOTechnicianProfile.objects.create(
        organization=org_a,
        membership=tech,
        is_dispatchable=False,
    )

    available = available_technicians(wo)
    assert tech not in available


@pytest.mark.django_db
def test_on_leave_technician_excluded_from_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    tech = tenancy.invite_member(
        org_a,
        email="onleave@alpha.test",
        full_name="On Leave Tech",
        role_ids=[tech_role.pk],
        actor=owner_a,
        password="FieldOps@2026!",
    )
    WSTechnicianProfile.objects.create(
        organization=org_a,
        membership=tech,
        availability_status=WSTechnicianProfile.AvailabilityStatus.ON_LEAVE,
    )

    available = available_technicians(wo)
    assert tech not in available


@pytest.mark.django_db
def test_suspended_technician_excluded_from_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    tech = tenancy.invite_member(
        org_a,
        email="suspended@alpha.test",
        full_name="Suspended Tech",
        role_ids=[tech_role.pk],
        actor=owner_a,
        password="FieldOps@2026!",
    )
    tech.status = Membership.Status.SUSPENDED
    tech.save(update_fields=["status"])

    available = available_technicians(wo)
    assert tech not in available


@pytest.mark.django_db
def test_inactive_user_excluded_from_dropdown(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    tech = tenancy.invite_member(
        org_a,
        email="inactiveuser@alpha.test",
        full_name="Inactive User Tech",
        role_ids=[tech_role.pk],
        actor=owner_a,
        password="FieldOps@2026!",
    )
    tech.user.is_active = False
    tech.user.save(update_fields=["is_active"])

    available = available_technicians(wo)
    assert tech not in available


@pytest.mark.django_db
def test_workorder_action_assign_page_renders_newly_added_technician(org_a, wo_planned, owner_a):
    wo, dispatcher, start, end = wo_planned
    tech_role = rbac.system_role_by_key(org_a, "technician")
    new_tech = tenancy.invite_member(
        org_a,
        email="page_render_tech@alpha.test",
        full_name="Page Render Technician",
        role_ids=[tech_role.pk],
        actor=owner_a,
    )

    client = Client()
    client.force_login(dispatcher.user)
    session = client.session
    session["active_org_id"] = str(org_a.pk)
    session.save()

    from django.urls import reverse
    url = reverse("workorders:action", kwargs={"pk": wo.pk, "operation": "assign"})
    response = client.get(url)
    assert response.status_code == 200

    content = response.content.decode("utf-8")
    assert "No eligible technicians" not in content
    assert "Page Render Technician" in content
    assert "page_render_tech@alpha.test" in content
