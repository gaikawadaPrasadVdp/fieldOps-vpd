"""Regression tests for D4: Notify staff on client request submit and reopen.

Defect D4:
In apps/portal/services.py:
- submit_portal_service_request (line 239)
- reopen_portal_service_request (line 518)
Query MembershipRole with membership__is_active=True, but Membership has no is_active column
(it uses status=Membership.Status.ACTIVE). This causes FieldError which is swallowed by except Exception: pass,
resulting in internal staff never receiving notifications when requests are submitted or reopened by clients.
"""
import pytest
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.notifications.models import Notification
from apps.portal import services as portal_services
from apps.portal.models import PortalAccount, PortalAssetGrant
from apps.rbac import services as rbac
from apps.tenancy.models import Membership
from apps.workorders.models import WorkOrder

pytestmark = pytest.mark.django_db


@pytest.fixture
def portal_client(org_a, make_member):
    """Create a client member with active PortalAccount and client_requester role."""
    client_mem = make_member(org_a, "client.reopen.d4@test.com", "client_requester")
    acc, _ = PortalAccount.objects.unscoped().get_or_create(
        organization=org_a,
        membership=client_mem,
        defaults={"company_name": "Apex Client Corp", "is_enabled": True},
    )
    return client_mem, acc


def test_reopen_portal_service_request_notifies_staff(org_a, site_a1, make_asset, make_member, portal_client):
    """When a client reopens a resolved request, staff holding incident.triage/approve must receive a notification."""
    asset = make_asset(org_a, site_a1, "CHILLER-D4")
    client_mem, portal_acc = portal_client

    # Grant asset access to client
    PortalAssetGrant.objects.create(organization=org_a, portal_account=portal_acc, asset=asset)

    # Create staff members who should receive notifications
    triage_staff = make_member(org_a, "ops.triage.d4@test.com", "operations_manager")
    dispatcher_staff = make_member(org_a, "dispatcher.d4@test.com", "service_dispatcher")

    # 1. Client creates request
    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=client_mem,
        title="Chiller temperature spike",
        description="Temperature exceeding 80C threshold",
        severity="HIGH",
        service_impact=ServiceRequest.Impact.PARTIAL,
        actor=client_mem.user,
    )

    # 2. Staff triage and approve
    sr = incident_services.transition(sr, action="triage", actor=triage_staff.user)
    sr = incident_services.transition(sr, action="approve", actor=triage_staff.user)

    # 3. Work order created and resolved
    planner = make_member(org_a, "planner.d4@test.com", "maintenance_planner")
    wo = incident_services.create_work_order_for_request(
        sr,
        actor=planner.user,
        membership=planner,
    )
    sr.refresh_from_db()
    assert sr.status == "WORK_ORDER_CREATED"

    incident_services.on_work_order_started(sr, actor=triage_staff.user)
    sr.refresh_from_db()
    assert sr.status == "IN_SERVICE"
    incident_services.on_work_order_completed(sr, actor=triage_staff.user)
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"

    # Clear any prior notifications
    Notification.objects.filter(organization=org_a).delete()

    # 4. Client reopens the service request
    reopened_sr = portal_services.reopen_portal_service_request(
        client_mem,
        sr.pk,
        reason="Chiller spiked to 85C again after shift handover",
        actor=client_mem.user,
    )
    assert reopened_sr.status == "APPROVED"

    # 5. Verify staff notification was actually created and delivered
    notifications = Notification.objects.filter(
        organization=org_a,
        title__icontains="Reopened",
    )
    recipient_users = set(notifications.values_list("recipient_id", flat=True))

    assert notifications.exists(), "No staff notifications were sent upon client reopening request."
    assert triage_staff.user.pk in recipient_users, "Operations manager holding incident.approve was not notified."
    assert dispatcher_staff.user.pk in recipient_users, "Service dispatcher holding incident.triage was not notified."
    notif = notifications.first()
    assert sr.number in notif.title
    assert "Chiller spiked to 85C" in notif.body


def test_submit_portal_service_request_notifies_staff(org_a, site_a1, make_asset, make_member, portal_client):
    """When a client submits a new request, staff holding incident.triage must receive a notification."""
    asset = make_asset(org_a, site_a1, "BOILER-D4")
    client_mem, portal_acc = portal_client

    PortalAssetGrant.objects.create(organization=org_a, portal_account=portal_acc, asset=asset)

    triage_staff = make_member(org_a, "triage.sub.d4@test.com", "service_dispatcher")
    Notification.objects.filter(organization=org_a).delete()

    sr = portal_services.create_portal_service_request(
        client_mem,
        asset=asset,
        title="Boiler pressure warning",
        description="Pressure needle vibrating past safety zone",
        severity="HIGH",
        actor=client_mem.user,
    )
    assert sr.pk is not None

    notifications = Notification.objects.filter(
        organization=org_a,
        title__icontains="New Service Request",
    )
    recipient_users = set(notifications.values_list("recipient_id", flat=True))

    assert notifications.exists(), "No staff notifications were sent upon client submitting request."
    assert triage_staff.user.pk in recipient_users, "Service dispatcher holding incident.triage was not notified."



def test_submit_request_does_not_notify_inactive_or_unauthorized_staff(org_a, site_a1, site_a2, make_asset, make_member, portal_client):
    """Negative tests for submission:
    - Suspended membership is not notified
    - Inactive user is not notified
    - Technician lacking incident.triage is not notified
    - Staff member whose triage role is scoped to a different site is not notified
    """
    asset = make_asset(org_a, site_a1, "HVAC-D4-NEG")
    client_mem, portal_acc = portal_client
    PortalAssetGrant.objects.create(organization=org_a, portal_account=portal_acc, asset=asset)

    active_triage = make_member(org_a, "active.triage.neg@test.com", "service_dispatcher")
    suspended_staff = make_member(org_a, "suspended.staff@test.com", "service_dispatcher", active=False)

    inactive_user_staff = make_member(org_a, "inactive.user.staff@test.com", "service_dispatcher")
    inactive_user_staff.user.is_active = False
    inactive_user_staff.user.save()

    tech_staff = make_member(org_a, "technician.staff@test.com", "technician")

    diff_site_staff = make_member(org_a, "diff.site.staff@test.com", "client_requester")
    rbac.set_membership_assignments(
        diff_site_staff,
        [(rbac.system_role_by_key(org_a, "service_dispatcher"), site_a2)],
        actor=None,
        system=True,
    )

    Notification.objects.filter(organization=org_a).delete()

    sr = portal_services.create_portal_service_request(
        client_mem,
        asset=asset,
        title="HVAC cooling leak",
        description="Coolant leak detected near coil",
        severity="MEDIUM",
        actor=client_mem.user,
    )

    notifications = Notification.objects.filter(
        organization=org_a,
        title__icontains="New Service Request",
    )
    recipients = set(notifications.values_list("recipient_id", flat=True))

    assert active_triage.user.pk in recipients
    assert suspended_staff.user.pk not in recipients
    assert inactive_user_staff.user.pk not in recipients
    assert tech_staff.user.pk not in recipients
    assert diff_site_staff.user.pk not in recipients


def test_reopen_request_does_not_notify_inactive_or_unauthorized_staff(org_a, site_a1, site_a2, make_asset, make_member, portal_client):
    """Negative tests for reopening:
    - Suspended membership is not notified
    - Inactive user is not notified
    - Technician lacking triage/approve is not notified
    - Staff member scoped exclusively to a different site is not notified
    """
    asset = make_asset(org_a, site_a1, "GENSET-D4-NEG")
    client_mem, portal_acc = portal_client
    PortalAssetGrant.objects.create(organization=org_a, portal_account=portal_acc, asset=asset)

    triage_staff = make_member(org_a, "triage.reopen.neg@test.com", "operations_manager")
    suspended_staff = make_member(org_a, "suspended.reopen@test.com", "operations_manager", active=False)

    inactive_user_staff = make_member(org_a, "inactive.user.reopen@test.com", "operations_manager")
    inactive_user_staff.user.is_active = False
    inactive_user_staff.user.save()

    tech_staff = make_member(org_a, "tech.reopen@test.com", "technician")

    diff_site_staff = make_member(org_a, "diffsite.reopen@test.com", "client_requester")
    rbac.set_membership_assignments(
        diff_site_staff,
        [(rbac.system_role_by_key(org_a, "operations_manager"), site_a2)],
        actor=None,
        system=True,
    )

    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=client_mem,
        title="Genset vibration",
        description="High vibration on mount 2",
        severity="MEDIUM",
        service_impact=ServiceRequest.Impact.NONE,
        actor=client_mem.user,
    )
    sr = incident_services.transition(sr, action="triage", actor=triage_staff.user)
    sr = incident_services.transition(sr, action="approve", actor=triage_staff.user)
    planner = make_member(org_a, "planner.reopen.neg@test.com", "maintenance_planner")
    incident_services.create_work_order_for_request(sr, actor=planner.user, membership=planner)
    sr.refresh_from_db()
    incident_services.on_work_order_started(sr, actor=triage_staff.user)
    sr.refresh_from_db()
    incident_services.on_work_order_completed(sr, actor=triage_staff.user)
    sr.refresh_from_db()
    assert sr.status == "RESOLVED"

    Notification.objects.filter(organization=org_a).delete()

    reopened_sr = portal_services.reopen_portal_service_request(
        client_mem,
        sr.pk,
        reason="Vibration returned immediately",
        actor=client_mem.user,
    )
    assert reopened_sr.status == "APPROVED"

    notifications = Notification.objects.filter(
        organization=org_a,
        title__icontains="Reopened",
    )
    recipients = set(notifications.values_list("recipient_id", flat=True))

    assert triage_staff.user.pk in recipients
    assert suspended_staff.user.pk not in recipients
    assert inactive_user_staff.user.pk not in recipients
    assert tech_staff.user.pk not in recipients
    assert diff_site_staff.user.pk not in recipients
