from __future__ import annotations

from django import forms

from apps.assets.models import Asset
from apps.incidents.models import ServiceRequest
from apps.sites.models import Site
from apps.ui.forms import BootstrapFormMixin, validate_phone_number, validate_alphabetical_description


class _PortalAssetSelect(forms.Select):
    """Select widget that injects data-site-id attribute for cascading site filtering."""

    def __init__(self, *args, option_data=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.option_data = option_data or {}

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        data = self.option_data.get(str(value), {})
        option["attrs"].update(data)
        return option


class _PortalAssetChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        site_name = obj.site.name or obj.site.code
        return f"{obj.asset_tag} — {obj.name} ({site_name})"


class PortalServiceRequestForm(BootstrapFormMixin, forms.Form):
    title = forms.CharField(
        max_length=200,
        min_length=3,
        label="Request Title / Subject",
        help_text="Brief summary of the issue or requested maintenance (minimum 3 characters).",
        widget=forms.TextInput(attrs={"placeholder": "e.g., Water pump pressure drop on Line 2"}),
    )
    site = forms.ModelChoiceField(
        queryset=Site.objects.none(),
        required=False,
        empty_label="All Sites / Locations",
        label="Site / Location",
        help_text="Filter facility assets by site or location.",
        widget=forms.Select(attrs={"id": "id_site", "class": "form-select"}),
    )
    asset = _PortalAssetChoiceField(
        queryset=Asset.objects.none(),
        label="Related Asset",
        help_text="Select the facility asset requiring service.",
        widget=_PortalAssetSelect(attrs={"id": "id_asset", "class": "form-select"}),
    )
    description = forms.CharField(
        required=False,
        label="Problem Description",
        help_text="Detailed description of the fault symptoms, observed behavior, or specific service needed.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Describe what happened, error codes, unusual sounds, leaks, etc."}),
    )
    severity = forms.ChoiceField(
        choices=[
            (ServiceRequest.Severity.LOW, "Low — Minor issue, system operational"),
            (ServiceRequest.Severity.MEDIUM, "Medium — Standard maintenance request"),
            (ServiceRequest.Severity.HIGH, "High — Urgent breakdown impacting operations"),
        ],
        initial=ServiceRequest.Severity.MEDIUM,
        label="Priority / Urgency",
        help_text="Select requested urgency. Note: Staff will verify and triage severity.",
    )
    service_impact = forms.ChoiceField(
        choices=ServiceRequest.Impact.choices,
        initial=ServiceRequest.Impact.NONE,
        label="Service Impact",
        help_text="Current impact on operational capability.",
    )
    impact_notes = forms.CharField(
        max_length=500,
        required=False,
        label="Impact Notes",
        help_text="Any additional context regarding operational downtime or affected areas.",
        widget=forms.TextInput(attrs={"placeholder": "e.g., Production slowed by approximately 30%"}),
    )
    attachment = forms.FileField(
        required=False,
        label="Photo / File Attachment",
        help_text="Optional document, log, or photo of the issue (up to 10 MB).",
    )
    override_duplicate = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput(),
    )
    override_reason = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, organization=None, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        if membership:
            from . import selectors
            asset_qs = selectors.granted_assets_for(membership)
            site_ids = list(asset_qs.values_list("site_id", flat=True).distinct())
            sites = Site.objects.filter(id__in=site_ids).order_by("name", "code")
        elif organization:
            asset_qs = (
                Asset.objects.for_organization(organization)
                .exclude(status__in=["RETIRED", "DISPOSED"])
                .select_related("site")
                .order_by("asset_tag")
            )
            site_ids = list(asset_qs.values_list("site_id", flat=True).distinct())
            sites = Site.objects.filter(id__in=site_ids).order_by("name", "code")
        else:
            asset_qs = Asset.objects.none()
            sites = Site.objects.none()

        self.fields["asset"].queryset = asset_qs
        self.fields["site"].queryset = sites
        self.fields["site"].label_from_instance = lambda s: f"{s.code} · {s.name}" if s.code and s.name else (s.name or s.code)
        self.fields["asset"].widget.option_data = {
            str(a.pk): {"data-site-id": str(a.site_id)} for a in asset_qs
        }

    def clean(self):
        cleaned_data = super().clean()
        site = cleaned_data.get("site")
        asset = cleaned_data.get("asset")
        if site and asset and asset.site_id != site.pk:
            self.add_error("asset", "The selected asset does not belong to the chosen site / location.")
        return cleaned_data

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        validate_alphabetical_description(title, field_label="Title")
        return title

    def clean_description(self):
        description = (self.cleaned_data.get("description") or "").strip()
        if description:
            validate_alphabetical_description(description, field_label="Problem description")
        return description


class PortalAccountEditForm(BootstrapFormMixin, forms.Form):
    """Form to edit client portal account metadata and requester contact information."""

    company_name = forms.CharField(
        max_length=150,
        required=True,
        min_length=2,
        label="Company / Client Name",
        help_text="Organization name associated with this portal account.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Acme Corporation"}),
    )
    full_name = forms.CharField(
        max_length=150,
        required=True,
        min_length=2,
        label="Requester Full Name",
        help_text="Name of the external client contact.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Jane Doe"}),
    )
    phone = forms.CharField(
        max_length=32,
        required=False,
        label="Phone Number",
        help_text="Optional. Minimum 7 digits (e.g. +94 11 289 9000).",
        widget=forms.TextInput(attrs={"placeholder": "e.g. +94 11 289 9000", "type": "tel"}),
    )
    is_enabled = forms.BooleanField(
        required=False,
        label="Portal Access Enabled",
        help_text="When enabled, this user can sign in and report service requests.",
    )
    notes = forms.CharField(
        required=False,
        label="Account Notes",
        help_text="Internal notes for operations staff (not visible to the client).",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Optional internal notes..."}),
    )

    def clean_company_name(self):
        val = (self.cleaned_data.get("company_name") or "").strip()
        if not val or len(val) < 2:
            raise forms.ValidationError("Company name must be at least 2 characters.")
        return val

    def clean_full_name(self):
        val = (self.cleaned_data.get("full_name") or "").strip()
        if not val or len(val) < 2:
            raise forms.ValidationError("Requester full name must be at least 2 characters.")
        return val

    def clean_phone(self):
        return validate_phone_number(self.cleaned_data.get("phone"))
