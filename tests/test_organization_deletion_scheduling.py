from datetime import timedelta
import pytest
from django.utils import timezone
from apps.accounts.models import User
from apps.tenancy.models import Organization, Membership
from apps.tenancy import services as tenancy_services
from apps.rbac.models import Role, MembershipRole


@pytest.fixture
def platform_admin():
    user = User.objects.create_user(
        email="platform.admin.test@nexus.test",
        password="TestPassword@123",
        full_name="Platform Admin",
        is_platform_admin=True,
    )
    return user


@pytest.fixture
def org_with_owner(db):
    org = Organization.objects.create(
        name="Scheduled Deletion Test Org",
        slug="scheduled-deletion-test-org",
        status=Organization.Status.ACTIVE,
    )
    owner_user = User.objects.create_user(
        email="owner.test@deletion.test",
        password="OwnerPassword@123",
        full_name="Org Owner",
    )
    owner_role, _ = Role.objects.get_or_create(
        organization=org,
        system_key="owner",
        defaults={"name": "Organization Owner", "is_owner": True},
    )
    owner_m = Membership.objects.create(
        organization=org,
        user=owner_user,
        status=Membership.Status.ACTIVE,
    )
    MembershipRole.objects.create(membership=owner_m, role=owner_role)
    return org, owner_user, owner_m


@pytest.mark.django_db
def test_schedule_and_cancel_organization_deletion(platform_admin, org_with_owner):
    org, owner_user, _ = org_with_owner

    # 1. Schedule deletion for 14 days
    tenancy_services.schedule_organization_deletion(
        org,
        days=14,
        reason="Customer contract expiration",
        actor=platform_admin,
    )
    org.refresh_from_db()

    assert org.is_scheduled_for_deletion is True
    assert org.deletion_grace_days == 14
    assert org.deletion_reason == "Customer contract expiration"
    assert org.deletion_requested_by == platform_admin
    assert org.days_until_deletion == 14
    assert org.deletion_scheduled_at > timezone.now()

    # 2. Cancel scheduled deletion
    tenancy_services.cancel_organization_deletion(org, actor=platform_admin)
    org.refresh_from_db()

    assert org.is_scheduled_for_deletion is False
    assert org.deletion_scheduled_at is None
    assert org.deletion_reason == ""
    assert org.deletion_grace_days == 0
    assert org.days_until_deletion == 0


@pytest.mark.django_db
def test_platform_admin_views_schedule_and_cancel(client, platform_admin, org_with_owner):
    org, _, _ = org_with_owner
    client.force_login(platform_admin)

    # Verify modal contains days and reason inputs, but NO "Delete Instantly" option
    get_res = client.get("/platform/organizations/")
    assert get_res.status_code == 200
    get_html = get_res.content.decode()
    assert "Delete Instantly" not in get_html
    assert "Delete After (Days)" in get_html
    assert "Reason for Deletion" in get_html

    # Schedule deletion via POST with days=10 and reason
    response = client.post(
        f"/platform/organizations/{org.pk}/delete/",
        {"days": "10", "reason": "Non-payment notice period"},
        follow=True,
    )
    assert response.status_code == 200
    org.refresh_from_db()
    assert org.is_scheduled_for_deletion is True
    assert org.days_until_deletion == 10
    assert org.deletion_reason == "Non-payment notice period"

    html = response.content.decode()
    assert "Deletion in 10 days" in html
    assert "Reason: Non-payment notice period" in html
    assert "Cancel Deletion" in html
    assert "Delete Now" in html

    # Cancel deletion via POST
    response = client.post(f"/platform/organizations/{org.pk}/cancel-deletion/", follow=True)
    assert response.status_code == 200
    org.refresh_from_db()
    assert org.is_scheduled_for_deletion is False
    assert "Scheduled deletion for organization" in response.content.decode()

    # Re-schedule deletion
    client.post(
        f"/platform/organizations/{org.pk}/delete/",
        {"days": "5", "reason": "Immediate decommission test"},
        follow=True,
    )

    # Test Delete Now button via POST to delete-now/
    response = client.post(
        f"/platform/organizations/{org.pk}/delete-now/",
        follow=True,
    )
    assert response.status_code == 200
    assert "permanently deleted" in response.content.decode()
    # Org is permanently deleted from database
    assert not Organization.objects.filter(pk=org.pk).exists()


@pytest.mark.django_db
def test_organization_owner_sees_deletion_notice(client, platform_admin, org_with_owner):
    org, owner_user, _ = org_with_owner

    # Schedule deletion for 7 days
    tenancy_services.schedule_organization_deletion(
        org,
        days=7,
        reason="Decommissioning testing tenant",
        actor=platform_admin,
    )

    # Log in as the Organization Owner
    client.force_login(owner_user)
    session = client.session
    session["active_org_id"] = str(org.pk)
    session.save()

    # View home dashboard
    response = client.get("/app/", SERVER_NAME="localhost")
    assert response.status_code == 200
    html = response.content.decode()

    # Assert countdown and details are prominently displayed
    assert "Organization Deletion Warning" in html
    assert "7 days" in html
    assert "Decommissioning testing tenant" in html
    assert "Organization Owner Notice" in html

    # View organization profile
    response = client.get("/app/organization/", SERVER_NAME="localhost")
    assert response.status_code == 200
    html = response.content.decode()
    assert "Scheduled Deletion Notice" in html
    assert "7 days" in html
    assert "Decommissioning testing tenant" in html


@pytest.mark.django_db
def test_process_due_scheduled_deletions(platform_admin):
    # Create an org that is past its scheduled deletion timestamp
    past_due_org = Organization.objects.create(
        name="Past Due Deletion Org",
        slug="past-due-deletion-org",
        status=Organization.Status.ACTIVE,
        deletion_scheduled_at=timezone.now() - timedelta(minutes=5),
        deletion_reason="Time expired",
        deletion_requested_by=platform_admin,
    )

    count = tenancy_services.process_due_scheduled_deletions()
    assert count >= 1
    # It should now be permanently deleted
    assert not Organization.objects.filter(pk=past_due_org.pk).exists()
