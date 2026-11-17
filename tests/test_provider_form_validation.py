from apps.contracts.forms import ProviderForm


def _valid_payload(**overrides):
    data = {
        "name": "Daikin India",
        "provider_type": "OEM",
        "contact_name": "Rajesh Kumar",
        "phone": "+91 98765 43210",
        "email": "support@daikin.example",
        "address": "Bengaluru, Karnataka",
        "status": "ACTIVE",
        "notes": "",
    }
    data.update(overrides)
    return data


def test_provider_form_accepts_prd_example_data():
    form = ProviderForm(data=_valid_payload())
    assert form.is_valid(), f"Unexpected errors: {form.errors}"
    assert form.cleaned_data["name"] == "Daikin India"
    assert form.cleaned_data["provider_type"] == "OEM"
    assert form.cleaned_data["contact_name"] == "Rajesh Kumar"
    assert form.cleaned_data["phone"] == "+91 98765 43210"
    assert form.cleaned_data["email"] == "support@daikin.example"
    assert form.cleaned_data["address"] == "Bengaluru, Karnataka"
    assert form.cleaned_data["status"] == "ACTIVE"


def test_provider_form_requires_all_prd_fields():
    form = ProviderForm(data={})
    assert not form.is_valid()
    for field in ("name", "provider_type", "contact_name", "phone", "email", "address", "status"):
        assert field in form.errors, f"Expected {field} to be required"


def test_provider_form_rejects_invalid_provider_type_and_status():
    form = ProviderForm(data=_valid_payload(provider_type="INVALID_TYPE", status="UNKNOWN"))
    assert not form.is_valid()
    assert "provider_type" in form.errors
    assert "status" in form.errors


def test_provider_form_rejects_invalid_contact_phone_email_address():
    form = ProviderForm(
        data=_valid_payload(
            contact_name="Rajesh123",
            phone="123",
            email="Contact name Email",
            address="<script>alert(1)</script>",
        )
    )
    assert not form.is_valid()
    assert "contact_name" in form.errors
    assert "phone" in form.errors
    assert "email" in form.errors
    assert "address" in form.errors


def test_provider_form_rejects_short_or_punctuation_only_address():
    form = ProviderForm(data=_valid_payload(address="---"))
    assert not form.is_valid()
    assert "address" in form.errors


def test_provider_form_requires_alphabetical_provider_name():
    for bad_name in ("Daikin 123", "Daikin@India", "Apex & Co."):
        form = ProviderForm(data=_valid_payload(name=bad_name))
        assert not form.is_valid(), f"Expected {bad_name!r} to be rejected"
        assert "name" in form.errors


def test_provider_form_rejects_numeric_or_symbol_email_domains():
    for bad_email in ("user@3", "user@#", "user@123.com", "user@gmail2.com"):
        form = ProviderForm(data=_valid_payload(email=bad_email))
        assert not form.is_valid(), f"Expected {bad_email!r} to be rejected"
        assert "email" in form.errors


def test_provider_form_requires_10_digit_phone():
    assert ProviderForm(data=_valid_payload(phone="9876543210")).is_valid()
    assert ProviderForm(data=_valid_payload(phone="+91 98765 43210")).is_valid()
    for bad_phone in ("987654321", "98765432101", "98765abcde"):
        form = ProviderForm(data=_valid_payload(phone=bad_phone))
        assert not form.is_valid(), f"Expected {bad_phone!r} to be rejected"
        assert "phone" in form.errors

