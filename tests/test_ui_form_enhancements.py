import pytest
from django.core.paginator import Paginator
from django.template import Context, Template
from apps.tenancy.forms import OrganizationForm, PlatformOrganizationCreateForm, TimezoneChoiceField, CountryChoiceField
from apps.ui.templatetags.ui_tags import elided_page_range, qs_without_page
from django.test import RequestFactory


@pytest.mark.django_db
def test_organization_form_dropdown_fields():
    form = OrganizationForm()
    assert isinstance(form.fields["timezone"], TimezoneChoiceField)
    assert isinstance(form.fields["country"], CountryChoiceField)

    # Valid standard choices
    valid_data = {
        "name": "Global Dynamics",
        "timezone": "Asia/Kolkata",
        "country": "IN",
    }
    bound_form = OrganizationForm(data=valid_data)
    assert bound_form.is_valid(), bound_form.errors
    assert bound_form.cleaned_data["timezone"] == "Asia/Kolkata"
    assert bound_form.cleaned_data["country"] == "IN"

    # Invalid timezone
    bad_tz = OrganizationForm(data={"name": "Global Dynamics", "timezone": "NonExistent/Zone"})
    assert not bad_tz.is_valid()
    assert "timezone" in bad_tz.errors

    # Invalid country
    bad_c = OrganizationForm(data={"name": "Global Dynamics", "timezone": "UTC", "country": "XYZ"})
    assert not bad_c.is_valid()
    assert "country" in bad_c.errors


@pytest.mark.django_db
def test_platform_organization_create_form_dropdown_fields():
    form = PlatformOrganizationCreateForm()
    assert isinstance(form.fields["timezone"], TimezoneChoiceField)
    assert isinstance(form.fields["country"], CountryChoiceField)
    assert form.fields["owner_password"] is not None

    data = {
        "name": "Acme Industries",
        "slug": "acme-industries",
        "owner_name": "Wile E. Coyote",
        "owner_email": "coyote@acme.example.com",
        "owner_password": "FieldOps@2026!",
        "timezone": "America/Chicago",
        "country": "US",
    }
    bound = PlatformOrganizationCreateForm(data=data)
    assert bound.is_valid(), bound.errors
    assert bound.cleaned_data["timezone"] == "America/Chicago"
    assert bound.cleaned_data["country"] == "US"


def test_elided_page_range_tag():
    items = list(range(100))
    paginator = Paginator(items, 10)
    page = paginator.page(5)

    pages = list(elided_page_range(page, on_each_side=1, on_ends=1))
    assert 1 in pages
    assert 5 in pages
    assert 10 in pages
    assert paginator.ELLIPSIS in pages


def test_pagination_component_rendering():
    factory = RequestFactory()
    request = factory.get("/app/assets/?search=pump&status=ACTIVE&page=2")
    items = list(range(50))
    paginator = Paginator(items, 10)
    page = paginator.page(2)

    template = Template('{% load ui_tags %}{% include "components/_pagination.html" %}')
    rendered = template.render(Context({"request": request, "page": page}))

    assert "Previous" in rendered
    assert "Next" in rendered
    assert "search=pump" in rendered
    assert "status=ACTIVE" in rendered
    assert "active" in rendered


def test_form_field_password_toggle_rendering():
    from django import forms
    class SamplePasswordForm(forms.Form):
        secret = forms.CharField(widget=forms.PasswordInput(attrs={"id": "id_secret"}), label="Master Secret")

    form = SamplePasswordForm()
    template = Template('{% for field in form %}{% include "components/_form_field.html" %}{% endfor %}')
    rendered = template.render(Context({"form": form}))

    assert "fx-password-toggle" in rendered
    assert "data-target=\"id_secret\"" in rendered
