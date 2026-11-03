import pytest
from apps.sites.forms import SiteForm


def test_valid_site_creation_kerala():
    """Verify that a site with country India, state Kerala, city Kochi, and valid Kerala PIN code passes validation."""
    data = {
        "code": "PLANT-KL-01",
        "name": "Kochi Processing Facility",
        "description": "Marine and spice processing facility",
        "address": "Plot 14, Industrial Development Area, Kalamassery",
        "country": "IN",
        "state_region": "Kerala",
        "city": "Kochi",
        "postal_code": "682001",
        "timezone": "Asia/Kolkata",
        "contact_name": "Rajesh Kumar",
        "contact_email": "rajesh@kochi.example.com",
        "contact_phone": "+91 98765 43210",
    }
    form = SiteForm(data=data)
    assert form.is_valid(), f"Form errors: {form.errors}"
    cleaned = form.cleaned_data
    assert cleaned["code"] == "PLANT-KL-01"
    assert cleaned["state_region"] == "Kerala"
    assert cleaned["city"] == "Kochi"
    assert cleaned["postal_code"] == "682001"


def test_invalid_pincode_mismatch():
    """Verify that a Kerala site with a Karnataka PIN code (560001) fails with a descriptive validation error."""
    data = {
        "code": "PLANT-KL-02",
        "name": "Kochi Unit 2",
        "country": "IN",
        "state_region": "Kerala",
        "city": "Kochi",
        "postal_code": "560001",  # Karnataka prefix 56, invalid for Kerala (67, 68, 69)
        "timezone": "Asia/Kolkata",
    }
    form = SiteForm(data=data)
    assert not form.is_valid()
    assert "postal_code" in form.errors
    err_msg = " ".join(form.errors["postal_code"])
    assert "Kerala" in err_msg or "match" in err_msg or "PIN" in err_msg


def test_invalid_site_code():
    """Verify that invalid characters in site code fail validation."""
    data = {
        "code": "plant@01!",
        "name": "Invalid Code Plant",
        "country": "IN",
        "state_region": "Kerala",
        "city": "Kochi",
        "postal_code": "682001",
        "timezone": "Asia/Kolkata",
    }
    form = SiteForm(data=data)
    assert not form.is_valid()
    assert "code" in form.errors


def test_numeric_site_name_rejected():
    """Verify that site names consisting purely of digits are rejected."""
    data = {
        "code": "PLANT-03",
        "name": "12345678",
        "country": "IN",
        "state_region": "Kerala",
        "city": "Kochi",
        "postal_code": "682001",
        "timezone": "Asia/Kolkata",
    }
    form = SiteForm(data=data)
    assert not form.is_valid()
    assert "name" in form.errors


def test_dynamic_choices_population():
    """Verify that when state_region is Kerala, Kerala cities are available in city choices."""
    form = SiteForm(initial={"country": "IN", "state_region": "Kerala"})
    city_choices = [c[0] for c in form.fields["city"].widget.choices]
    assert "Kochi" in city_choices
    assert "Thiruvananthapuram" in city_choices

def test_empty_country_initial_choices():
    """Verify that with no country selected, states and cities choices are both empty (only default prompts)."""
    form = SiteForm()
    state_choices = [c[0] for c in form.fields["state_region"].widget.choices]
    city_choices = [c[0] for c in form.fields["city"].widget.choices]
    assert state_choices == [""]
    assert city_choices == [""]


def test_country_selected_no_state_choices():
    """Verify that when Country is India but no State is selected, city choices is only the default prompt."""
    form = SiteForm(initial={"country": "IN"})
    state_choices = [c[0] for c in form.fields["state_region"].widget.choices]
    city_choices = [c[0] for c in form.fields["city"].widget.choices]
    assert "Andhra Pradesh" in state_choices
    assert "Karnataka" in state_choices
    assert city_choices == [""]  # No fallback cities!


def test_andhra_pradesh_cities_only():
    """Verify that selecting Andhra Pradesh provides ONLY Andhra Pradesh cities, not cities of other states."""
    form = SiteForm(initial={"country": "IN", "state_region": "Andhra Pradesh"})
    city_choices = [c[0] for c in form.fields["city"].widget.choices]
    # Check that Andhra Pradesh cities are present
    assert "Visakhapatnam" in city_choices
    assert "Vijayawada" in city_choices
    assert "Guntur" in city_choices
    assert "Nellore" in city_choices
    assert "Tirupati" in city_choices
    # Check that other states' cities are NOT present
    assert "Bengaluru" not in city_choices
    assert "Mumbai" not in city_choices
    assert "New Delhi" not in city_choices
    assert "Chennai" not in city_choices


def test_andhra_pradesh_city_mismatch_rejected():
    """Verify that selecting Andhra Pradesh as State but Bengaluru (Karnataka) as City fails validation."""
    data = {
        "code": "SITE-AP-01",
        "name": "Vizag Hub",
        "country": "IN",
        "state_region": "Andhra Pradesh",
        "city": "Bengaluru",
        "postal_code": "530001",
        "timezone": "Asia/Kolkata",
    }
    form = SiteForm(data=data)
    assert not form.is_valid()
    assert "city" in form.errors
    err = " ".join(form.errors["city"])
    assert "Bengaluru" in err


def test_andhra_pradesh_valid_site_accepted():
    """Verify that Andhra Pradesh with Visakhapatnam and matching PIN 530001 passes validation."""
    data = {
        "code": "SITE-AP-02",
        "name": "Vizag Logistics Center",
        "country": "IN",
        "state_region": "Andhra Pradesh",
        "city": "Visakhapatnam",
        "postal_code": "530001",
        "timezone": "Asia/Kolkata",
    }
    form = SiteForm(data=data)
    assert form.is_valid(), f"Form errors: {form.errors}"
    assert form.cleaned_data["city"] == "Visakhapatnam"
    assert form.cleaned_data["state_region"] == "Andhra Pradesh"

