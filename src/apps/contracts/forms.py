import re

from django import forms

from apps.assets.models import Asset
from apps.ui.forms import (
    BootstrapFormMixin,
    validate_alphabetical_name,
    validate_business_name,
    validate_phone_number,
    validate_safe_text,
    validate_strict_email,
)

from .models import CoverageAgreement, ServiceProvider
from .services import WORK_TYPES


class _AssetChoices(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.asset_tag} · {obj.name} ({obj.site.code})"


class _DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kw):
        super().__init__(format="%Y-%m-%d", **kw)


_ALPHA_DOMAIN_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z][a-zA-Z-]*(\.[a-zA-Z][a-zA-Z-]*)*\.[a-zA-Z]{2,}$"
)


class ProviderForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(
        max_length=150,
        min_length=2,
        label="Provider Name",
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Daikin India",
                "required": "required",
                "minlength": "2",
                "maxlength": "150",
                "pattern": r"[A-Za-z\s'-]{2,150}",
                "title": "Provider Name must contain only alphabetical characters (letters, spaces, hyphens, apostrophes).",
                "data-live-validate": "true",
            }
        ),
    )
    provider_type = forms.ChoiceField(
        choices=ServiceProvider.ProviderType.choices,
        initial=ServiceProvider.ProviderType.OEM,
        label="Provider Type",
        required=True,
    )
    contact_name = forms.CharField(
        max_length=120,
        min_length=2,
        label="Contact Person",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Rajesh Kumar",
                "required": "required",
                "minlength": "2",
                "maxlength": "120",
                "pattern": r"[A-Za-z\s'-]{2,120}",
                "title": "Contact Person must contain only alphabetical characters (no numbers or special symbols).",
                "data-live-validate": "true",
            }
        ),
    )
    phone = forms.CharField(
        max_length=40,
        min_length=10,
        label="Phone",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. +91 98765 43210",
                "type": "tel",
                "required": "required",
                "minlength": "10",
                "maxlength": "20",
                "pattern": r"[0-9+\s()-]{10,20}",
                "title": "Phone number must be 10 digits (e.g. 9876543210 or +91 98765 43210).",
                "data-live-validate": "true",
            }
        ),
    )
    email = forms.EmailField(
        max_length=254,
        label="Email",
        required=True,
        widget=forms.EmailInput(
            attrs={
                "placeholder": "e.g. support@daikin.example",
                "required": "required",
                "maxlength": "254",
                "title": "Enter a valid email address with a letters-only domain (e.g. support@gmail.com).",
                "data-live-validate": "true",
            }
        ),
    )
    address = forms.CharField(
        max_length=300,
        min_length=3,
        label="Address",
        required=True,
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. Bengaluru, Karnataka",
                "required": "required",
                "minlength": "3",
                "maxlength": "300",
                "pattern": r".*[A-Za-z0-9].*",
                "title": "Address must be at least 3 characters and contain letters or numbers.",
                "data-live-validate": "true",
            }
        ),
    )
    status = forms.ChoiceField(
        choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")],
        initial="ACTIVE",
        label="Status",
        required=True,
    )
    notes = forms.CharField(
        max_length=500,
        required=False,
        label="Notes",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Optional notes", "maxlength": "500"}),
    )

    def clean_name(self):
        val = validate_business_name(self.cleaned_data.get("name"), field_label="Provider Name")
        return validate_alphabetical_name(val, field_label="Provider Name", min_len=2, required=True)

    def clean_provider_type(self):
        val = self.cleaned_data.get("provider_type")
        if val not in ServiceProvider.ProviderType.values:
            raise forms.ValidationError("Select a valid provider type.")
        return val

    def clean_contact_name(self):
        return validate_alphabetical_name(
            self.cleaned_data.get("contact_name"), field_label="Contact Person", min_len=2, required=True
        )

    def clean_phone(self):
        val = (self.cleaned_data.get("phone") or "").strip()
        if not val:
            raise forms.ValidationError("Phone is required.")
        val = validate_phone_number(val)
        digits = "".join(c for c in val if c.isdigit())
        if val.startswith("+91"):
            national_digits = digits[2:]
        elif val.startswith("+"):
            raise forms.ValidationError("Phone number must be 10 digits (e.g. 9876543210 or +91 98765 43210).")
        else:
            national_digits = digits
        if len(national_digits) != 10:
            raise forms.ValidationError("Phone number must be exactly 10 digits (e.g. 9876543210 or +91 98765 43210).")
        return val

    def clean_email(self):
        val = validate_strict_email(self.cleaned_data.get("email"))
        if not _ALPHA_DOMAIN_EMAIL_RE.match(val):
            raise forms.ValidationError(
                "Enter a valid email address with a letters-only domain (e.g. name@gmail.com). "
                "Numbers or symbols in the domain (e.g. @3, @#) are not allowed."
            )
        return val

    def clean_address(self):
        val = validate_safe_text(self.cleaned_data.get("address"), field_label="Address", max_len=300, required=True)
        if len(val) < 3 or not any(c.isalnum() for c in val):
            raise forms.ValidationError("Address must be at least 3 characters and contain letters or numbers.")
        return val

    def clean_status(self):
        val = self.cleaned_data.get("status")
        if val not in ("ACTIVE", "INACTIVE"):
            raise forms.ValidationError("Select a valid status.")
        return val

    def clean_notes(self):
        val = self.cleaned_data.get("notes")
        return validate_safe_text(val, field_label="Notes", max_len=500, required=False)


class AgreementForm(BootstrapFormMixin, forms.Form):
    kind = forms.ChoiceField(choices=CoverageAgreement.Kind.choices, label="Type")
    reference = forms.CharField(max_length=80, label="Contract / warranty number")
    title = forms.CharField(max_length=200)
    provider = forms.ModelChoiceField(queryset=ServiceProvider.objects.none())
    site = forms.ModelChoiceField(queryset=None, label="Site")
    start_date = forms.DateField(widget=_DateInput())
    end_date = forms.DateField(widget=_DateInput())
    assets = _AssetChoices(queryset=Asset.objects.none(), label="Covered assets (all at the chosen site)",
                           widget=forms.SelectMultiple(attrs={"size": 8}))
    excluded_work_types = forms.MultipleChoiceField(
        required=False, choices=[(w, w.title()) for w in WORK_TYPES], widget=forms.CheckboxSelectMultiple,
        label="Work types NOT covered")
    terms = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Coverage terms")
    exclusion_notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}),
                                      label="Other exclusions (text)")
    sla_terms = forms.CharField(max_length=300, required=False, label="Provider response terms")
    sla_profile = forms.ModelChoiceField(
        queryset=None, required=False, empty_label="(none - use the site / organization SLA)",
        label="Internal SLA profile", help_text="Applied to requests / work orders on the covered assets.")
    renewal_alert_days = forms.IntegerField(min_value=0, max_value=365, initial=30, label="Renewal alert (days before end)")

    def clean_title(self):
        return validate_business_name(self.cleaned_data.get("title"), field_label="Agreement title", max_len=200)

    def clean_reference(self):
        return validate_safe_text(self.cleaned_data.get("reference"), field_label="Reference number", max_len=80, required=True)

    def clean_terms(self):
        return validate_safe_text(self.cleaned_data.get("terms"), field_label="Coverage terms", max_len=2000, required=False)

    def clean_exclusion_notes(self):
        return validate_safe_text(self.cleaned_data.get("exclusion_notes"), field_label="Exclusion notes", max_len=1000, required=False)

    def clean_sla_terms(self):
        return validate_safe_text(self.cleaned_data.get("sla_terms"), field_label="SLA terms", max_len=300, required=False)

    def __init__(self, *args, providers, sites, assets, sla_profiles, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sla_profile"].queryset = sla_profiles
        self.fields["provider"].queryset = providers
        self.fields["site"].queryset = sites
        self.fields["assets"].queryset = assets
        if editing:  # type, site and assets are fixed once created (assets have their own add / remove buttons)
            for f in ("kind", "site", "assets"):
                del self.fields[f]
        self.fields["excluded_work_types"].widget.attrs.pop("class", None)


class RenewForm(BootstrapFormMixin, forms.Form):
    reference = forms.CharField(max_length=80, label="New contract / warranty number")
    new_end_date = forms.DateField(widget=_DateInput(), label="New end date")

    def clean_reference(self):
        return validate_safe_text(self.cleaned_data.get("reference"), field_label="New reference number", max_len=80, required=True)


class ReasonForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(max_length=300)

    def clean_reason(self):
        return validate_safe_text(self.cleaned_data.get("reason"), field_label="Reason", max_len=300, required=True)


class AddAssetForm(BootstrapFormMixin, forms.Form):
    asset = forms.ModelChoiceField(queryset=Asset.objects.none())

    def __init__(self, *args, assets, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = assets
