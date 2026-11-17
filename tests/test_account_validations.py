import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from apps.accounts.forms import ProfileForm
from apps.audit.models import AuditLog
from apps.portal.forms import PortalAccountEditForm
from apps.portal.models import PortalAccount
from apps.rbac import services as rbac
from apps.tenancy.models import Membership
from apps.ui.forms import validate_phone_number

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_validate_phone_number_helper():
    # Valid formats
    assert validate_phone_number("+94 11 289 9000") == "+94 11 289 9000"
    assert validate_phone_number("+1 (555) 012-3456") == "+1 (555) 012-3456"
    assert validate_phone_number("0112899000") == "0112899000"
    assert validate_phone_number("") == ""
    assert validate_phone_number(None) == ""

    # Invalid: fewer than 7 digits (like '25565' from user screenshot)
    with pytest.raises(ValidationError) as exc:
        validate_phone_number("25565")
    assert "at least 7 digits" in str(exc.value)

    # Invalid: more than 15 digits
    with pytest.raises(ValidationError) as exc:
        validate_phone_number("1234567890123456")
    assert "cannot exceed 15 digits" in str(exc.value)

    # Invalid characters
    with pytest.raises(ValidationError) as exc:
        validate_phone_number("phone#1234567")
    assert "valid phone number" in str(exc.value)


def test_profile_form_validation():
    user = User.objects.create_user(email="test.profile@nexus.internal", password="Password123!", full_name="Original Name")

    # Reject short phone number (e.g. 25565)
    f_short_phone = ProfileForm(data={"full_name": "Valid Name", "phone": "25565"}, instance=user)
    assert not f_short_phone.is_valid()
    assert "phone" in f_short_phone.errors
    assert "at least 7 digits" in str(f_short_phone.errors["phone"])

    # Reject empty full name
    f_empty_name = ProfileForm(data={"full_name": "   ", "phone": "+94 11 289 9000"}, instance=user)
    assert not f_empty_name.is_valid()
    assert "full_name" in f_empty_name.errors

    # Reject single character full name
    f_single_char = ProfileForm(data={"full_name": "A", "phone": "+94 11 289 9000"}, instance=user)
    assert not f_single_char.is_valid()
    assert "full_name" in f_single_char.errors

    # Accept valid phone and full name
    f_valid = ProfileForm(data={"full_name": "Dinuka Wijesinghe", "phone": "+94 11 289 9000"}, instance=user)
    assert f_valid.is_valid()
    saved_user = f_valid.save()
    assert saved_user.full_name == "Dinuka Wijesinghe"
    assert saved_user.phone == "+94 11 289 9000"


def test_portal_account_edit_form_validation():
    # Valid data
    f_valid = PortalAccountEditForm(data={
        "company_name": "Acme Industrial Corporation",
        "full_name": "Sarah Connor",
        "phone": "+1 555 012 3456",
        "is_enabled": True,
        "notes": "Premium client tier.",
    })
    assert f_valid.is_valid()

    # Invalid: phone with 5 digits (25565)
    f_invalid_phone = PortalAccountEditForm(data={
        "company_name": "Acme Industrial Corporation",
        "full_name": "Sarah Connor",
        "phone": "25565",
        "is_enabled": True,
        "notes": "",
    })
    assert not f_invalid_phone.is_valid()
    assert "phone" in f_invalid_phone.errors
    assert "at least 7 digits" in str(f_invalid_phone.errors["phone"])

    # Invalid: company name too short
    f_short_company = PortalAccountEditForm(data={
        "company_name": "A",
        "full_name": "Sarah Connor",
        "phone": "+1 555 012 3456",
        "is_enabled": True,
    })
    assert not f_short_company.is_valid()
    assert "company_name" in f_short_company.errors


def test_portal_account_edit_views_and_permissions(client, org_a, make_member):
    # Setup users
    sm_user = make_member(org_a, "sm.tester@alpha.test", "service_manager").user
    tech_user = make_member(org_a, "tech.tester@alpha.test", "technician").user

    # Setup portal client account
    client_user = User.objects.create_user(
        email="client.edit@acme.test",
        password="Password123!",
        full_name="Old Client Name",
        phone="",
    )
    membership = Membership.objects.unscoped().create(
        organization=org_a,
        user=client_user,
        status=Membership.Status.ACTIVE,
        job_title="Client Requester",
    )
    role = rbac.system_role_by_key(org_a, "client_requester")
    rbac.set_membership_roles(membership, [role], actor=None, system=True)

    account = PortalAccount.objects.unscoped().create(
        organization=org_a,
        membership=membership,
        company_name="Old Acme Corp",
        is_enabled=True,
        notes="Old notes",
    )

    # 1. Technician forbidden from accessing edit view
    client.force_login(tech_user)
    r_tech = client.get(f"/app/portal/accounts/{account.pk}/edit/")
    assert r_tech.status_code == 403

    # 2. Service manager has permission and can access GET
    client.force_login(sm_user)
    r_sm_get = client.get(f"/app/portal/accounts/{account.pk}/edit/")
    assert r_sm_get.status_code == 200
    assert "Old Acme Corp" in r_sm_get.content.decode("utf-8")
    assert "Old Client Name" in r_sm_get.content.decode("utf-8")

    # 3. Accounts list displays Edit link
    r_list = client.get("/app/portal/accounts/")
    assert r_list.status_code == 200
    assert f"/app/portal/accounts/{account.pk}/edit/" in r_list.content.decode("utf-8")

    # 4. Service manager posts invalid data -> 400 Bad Request
    r_bad_post = client.post(
        f"/app/portal/accounts/{account.pk}/edit/",
        {
            "company_name": "Updated Corp",
            "full_name": "Updated Name",
            "phone": "25565",  # Invalid!
            "is_enabled": "on",
            "notes": "Testing error state",
        },
    )
    assert r_bad_post.status_code == 400
    assert "at least 7 digits" in r_bad_post.content.decode("utf-8")

    # 5. Service manager posts valid data -> redirects and updates DB
    r_good_post = client.post(
        f"/app/portal/accounts/{account.pk}/edit/",
        {
            "company_name": "Acme Global Industries",
            "full_name": "Jane Matrix",
            "phone": "+94 11 289 9000",
            "is_enabled": "on",
            "notes": "Updated tier 1 client",
        },
    )
    assert r_good_post.status_code == 302
    assert r_good_post.url == "/app/portal/accounts/"

    # Verify database state
    account.refresh_from_db()
    assert account.company_name == "Acme Global Industries"
    assert account.is_enabled is True
    assert account.notes == "Updated tier 1 client"

    client_user.refresh_from_db()
    assert client_user.full_name == "Jane Matrix"
    assert client_user.phone == "+94 11 289 9000"

    # Verify audit log was recorded
    audit_entry = AuditLog.objects.filter(
        organization=org_a,
        action="portal.account_updated",
        target_id=str(account.pk),
    ).first()
    assert audit_entry is not None
