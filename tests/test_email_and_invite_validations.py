import pytest
from unittest.mock import MagicMock, patch
from django.core.exceptions import ValidationError

from apps.ui.forms import validate_strict_email
from apps.tenancy.forms import InviteForm, MemberEditForm


def test_validate_strict_email_valid_formats():
    valid_emails = [
        "user@gmail.com",
        "dtgtgtgtgtgr@gmail.com",
        "john.doe@company.org",
        "test@fieldops.io",
        "jane+work@sub.domain.co",
        "operations@apex.tech",
    ]
    for email in valid_emails:
        assert validate_strict_email(email) == email.lower()


def test_validate_strict_email_rejects_invalid_domains():
    invalid_emails = [
        "user@23gmail",         # Missing dot / TLD and domain starts with number
        "user@23gmail.com",     # Domain starts with number
        "dtgtgtgtgtgr@23gmail", # Missing TLD
        "user@gmail",           # No TLD
        "@gmail.com",           # Missing local part
        "user@.com",            # Missing domain name
        "user@gmail.c",         # TLD too short (single character)
        "user@123.com",         # Domain starts with digits
        "",                     # Empty
        None,                   # None
    ]
    for email in invalid_emails:
        with pytest.raises(ValidationError):
            validate_strict_email(email)


def test_invite_form_email_rejects_numbers_in_domain():
    mock_org = MagicMock()
    mock_role = MagicMock()
    mock_role.pk = "role-1"
    
    with patch("apps.tenancy.forms._role_field") as mock_rf, \
         patch("apps.tenancy.forms._site_field"):
        mock_rf.return_value = MagicMock(clean=MagicMock(return_value=[mock_role]))
        
        # Invalid email with numbers starting domain (e.g. @23gmail.com or @23gmail)
        f1 = InviteForm(
            data={"email": "dtgtgtgtgtgr@23gmail.com", "full_name": "Valid Name", "roles": ["role-1"]},
            org=mock_org
        )
        assert not f1.is_valid()
        assert "email" in f1.errors
        assert "valid domain" in str(f1.errors["email"][0])

        f2 = InviteForm(
            data={"email": "dtgtgtgtgtgr@23gmail", "full_name": "Valid Name", "roles": ["role-1"]},
            org=mock_org
        )
        assert not f2.is_valid()
        assert "email" in f2.errors


def test_invite_form_full_name_rejects_numbers_and_symbols():
    mock_org = MagicMock()
    mock_role = MagicMock()
    mock_role.pk = "role-1"

    with patch("apps.tenancy.forms._role_field") as mock_rf, \
         patch("apps.tenancy.forms._site_field"):
        mock_rf.return_value = MagicMock(clean=MagicMock(return_value=[mock_role]))

        # User typed 'ads35' in screenshot
        f1 = InviteForm(
            data={"email": "valid.user@gmail.com", "full_name": "ads35", "roles": ["role-1"]},
            org=mock_org
        )
        assert not f1.is_valid()
        assert "full_name" in f1.errors
        assert "cannot contain numbers" in str(f1.errors["full_name"][0])

        # Reject symbols
        f2 = InviteForm(
            data={"email": "valid.user@gmail.com", "full_name": "John@Doe", "roles": ["role-1"]},
            org=mock_org
        )
        assert not f2.is_valid()
        assert "full_name" in f2.errors
        assert "only alphabetical characters" in str(f2.errors["full_name"][0])

        # Accept valid alphabetical names with hyphens and apostrophes
        f3 = InviteForm(
            data={"email": "valid.user@gmail.com", "full_name": "Mary-Jane O'Connor", "password": "password123", "roles": ["role-1"]},
            org=mock_org
        )
        assert f3.is_valid(), f3.errors


def test_invite_form_password_length_validation():
    mock_org = MagicMock()
    mock_role = MagicMock()
    mock_role.pk = "role-1"

    with patch("apps.tenancy.forms._role_field") as mock_rf, \
         patch("apps.tenancy.forms._site_field"):
        mock_rf.return_value = MagicMock(clean=MagicMock(return_value=[mock_role]))

        # Short password
        f1 = InviteForm(
            data={"email": "valid.user@gmail.com", "full_name": "Valid User", "password": "123", "roles": ["role-1"]},
            org=mock_org
        )
        assert not f1.is_valid()
        assert "password" in f1.errors
        assert "at least 8 characters" in str(f1.errors["password"][0])


def test_invite_form_mandatory_fields_and_stars():
    mock_org = MagicMock()
    with patch("apps.tenancy.forms._role_field") as mock_rf, \
         patch("apps.tenancy.forms._site_field"):
        mock_field = MagicMock()
        mock_field.required = True
        mock_field.clean.side_effect = ValidationError("Please select at least one role.")
        mock_rf.return_value = mock_field
        
        form = InviteForm(data={}, org=mock_org)
        assert not form.is_valid()
        # Verify required marks
        assert form.fields["email"].required is True
        assert form.fields["full_name"].required is True
        assert form.fields["password"].required is True
        assert form.fields["roles"].required is True
        assert "email" in form.errors
        assert "full_name" in form.errors
        assert "password" in form.errors


def test_profile_form_full_name_rejects_numbers():
    from apps.accounts.forms import ProfileForm
    f1 = ProfileForm(data={"full_name": "ads35"})
    assert not f1.is_valid()
    assert "full_name" in f1.errors
    assert "cannot contain numbers" in str(f1.errors["full_name"][0])


def test_member_edit_form_full_name_rejects_numbers():
    f1 = MemberEditForm(data={"full_name": "Jane Doe 2"})
    assert not f1.is_valid()
    assert "full_name" in f1.errors
    assert "cannot contain numbers" in str(f1.errors["full_name"][0])

    f2 = MemberEditForm(data={"full_name": "Jane Doe"})
    assert f2.is_valid()

