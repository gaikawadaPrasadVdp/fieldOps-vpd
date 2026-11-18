from __future__ import annotations

from django import forms

from apps.assets.models import Asset
from apps.incidents.models import ServiceRequest
from apps.sites.models import Site
from apps.ui.forms import BootstrapFormMixin, validate_phone_number, validate_alphabetical_description, validate_incident_title, validate_title


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
        required=True,
        label="Request Title / Subject",
        help_text="Brief summary of the issue or requested maintenance (minimum 3 characters).",
        error_messages={
            "required": "Request Title / Subject is required.",
            "min_length": "Request Title / Subject must be at least 3 characters.",
        },
        widget=forms.TextInput(attrs={"placeholder": "e.g., Water pump pressure drop on Line 2"}),
    )
    site = forms.ModelChoiceField(
        queryset=Site.objects.none(),
        required=True,
        empty_label="Please select a site / location",
        label="Site / Location",
        help_text="Select facility site or location.",
        error_messages={
            "required": "Please select a site / location.",
        },
        widget=forms.Select(attrs={"id": "id_site", "class": "form-select"}),
    )
    asset = _PortalAssetChoiceField(
        queryset=Asset.objects.none(),
        required=True,
        label="Related Asset",
        help_text="Select the facility asset requiring service.",
        error_messages={
            "required": "Please select a related asset.",
        },
        widget=_PortalAssetSelect(attrs={"id": "id_asset", "class": "form-select"}),
    )
    description = forms.CharField(
        required=True,
        min_length=3,
        label="Problem Description",
        help_text="Detailed description of the fault symptoms, observed behavior, or specific service needed.",
        error_messages={
            "required": "Problem Description is required.",
            "min_length": "Problem Description must be at least 3 characters.",
        },
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Describe what happened, error codes, unusual sounds, leaks, etc."}),
    )
    severity = forms.ChoiceField(
        choices=[
            ("", "Select priority / urgency..."),
            (ServiceRequest.Severity.LOW, "Low — Minor issue, system operational"),
            (ServiceRequest.Severity.MEDIUM, "Medium — Standard maintenance request"),
            (ServiceRequest.Severity.HIGH, "High — Urgent breakdown impacting operations"),
        ],
        required=True,
        label="Priority / Urgency",
        help_text="Select requested urgency. Note: Staff will verify and triage severity.",
        error_messages={
            "required": "Please select a priority / urgency.",
        },
        widget=forms.Select(attrs={"id": "id_severity", "class": "form-select"}),
    )
    service_impact = forms.ChoiceField(
        choices=[
            ("", "Select service impact..."),
            *ServiceRequest.Impact.choices,
        ],
        required=True,
        label="Service Impact",
        help_text="Current impact on operational capability.",
        error_messages={
            "required": "Please select a service impact.",
        },
        widget=forms.Select(attrs={"id": "id_service_impact", "class": "form-select"}),
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
        org = organization or (membership.organization if membership else None)
        if membership:
            from . import selectors
            from .services import _portal_account_site_ids, sync_portal_grants_for_account

            account = selectors.get_portal_account(membership)
            if account and account.auto_grant_assets and account.is_enabled:
                sync_portal_grants_for_account(account)

            asset_qs = selectors.granted_assets_for(membership)
            granted_site_ids = set(asset_qs.values_list("site_id", flat=True).distinct())
            allowed_site_ids = _portal_account_site_ids(account) if account else None

            if org:
                active_sites_qs = Site.objects.for_organization(org).filter(status=Site.Status.ACTIVE)
            else:
                active_sites_qs = Site.objects.filter(status=Site.Status.ACTIVE)

            if allowed_site_ids is not None:
                active_sites_qs = active_sites_qs.filter(id__in=allowed_site_ids)

            if account and account.auto_grant_assets:
                sites = active_sites_qs.order_by("name", "code")
            else:
                sites_with_assets = (
                    set(
                        Asset.objects.for_organization(org)
                        .exclude(status__in=["RETIRED", "DISPOSED"])
                        .values_list("site_id", flat=True)
                        .distinct()
                    )
                    if org
                    else set()
                )
                empty_or_new_site_ids = set(active_sites_qs.exclude(id__in=sites_with_assets).values_list("id", flat=True))
                visible_site_ids = granted_site_ids | empty_or_new_site_ids
                if not visible_site_ids and not sites_with_assets:
                    sites = active_sites_qs.order_by("name", "code")
                else:
                    sites = active_sites_qs.filter(id__in=visible_site_ids).order_by("name", "code")
        elif organization:
            asset_qs = (
                Asset.objects.for_organization(organization)
                .exclude(status__in=["RETIRED", "DISPOSED"])
                .select_related("site")
                .order_by("asset_tag")
            )
            sites = Site.objects.for_organization(organization).filter(status=Site.Status.ACTIVE).order_by("name", "code")
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
        if not site and "site" not in self._errors:
            self.add_error("site", "Please select a site / location.")
        if site and asset and asset.site_id != site.pk:
            self.add_error("asset", "The selected asset does not belong to the chosen site / location.")
        return cleaned_data

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        if not title:
            raise forms.ValidationError("Request Title / Subject is required.")
        validate_incident_title(title, field_label="Request Title / Subject")
        return title

    def clean_description(self):
        description = (self.cleaned_data.get("description") or "").strip()
        if not description:
            raise forms.ValidationError("Problem Description is required.")
        validate_alphabetical_description(description, field_label="Problem Description")
        return description

    def clean_impact_notes(self):
        notes = (self.cleaned_data.get("impact_notes") or "").strip()
        if notes:
            validate_alphabetical_description(notes, field_label="Impact Notes")
        return notes


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
    auto_grant_assets = forms.BooleanField(
        required=False,
        label="Auto-Sync New Sites & Assets",
        help_text="When enabled, newly registered organization sites and assets are automatically available in this client's portal dropdowns.",
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


class PortalScanRequestForm(BootstrapFormMixin, forms.Form):
    """Client-safe service request submission form for a QR-resolved asset."""

    title = forms.CharField(
        max_length=200,
        min_length=3,
        label="Request Title / Subject",
        help_text="Brief summary of the issue or requested maintenance (minimum 3 characters).",
        widget=forms.TextInput(attrs={"placeholder": "e.g., Unusual vibration on cooling pump"}),
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
        widget=forms.TextInput(attrs={"placeholder": "e.g., Production slowed"}),
    )
    attachment = forms.FileField(
        required=False,
        label="Photo / File Attachment",
        help_text="Optional document, log, or photo of the issue (up to 10 MB).",
    )
    override_duplicate = forms.BooleanField(required=False, widget=forms.HiddenInput())
    override_reason = forms.CharField(required=False, widget=forms.HiddenInput())

    def clean_title(self):
        title = (self.cleaned_data.get("title") or "").strip()
        validate_incident_title(title, field_label="Request Title / Subject")
        return title

    def clean_description(self):
        description = (self.cleaned_data.get("description") or "").strip()
        if description:
            validate_alphabetical_description(description, field_label="Problem Description")
        return description

    def clean_impact_notes(self):
        notes = (self.cleaned_data.get("impact_notes") or "").strip()
        if notes:
            validate_alphabetical_description(notes, field_label="Impact Notes")
        return notes

