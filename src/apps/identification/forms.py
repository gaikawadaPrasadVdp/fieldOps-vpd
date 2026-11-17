from django import forms

from apps.incidents.models import ServiceRequest
from apps.ui.forms import BootstrapFormMixin


class ScanIncidentReportForm(BootstrapFormMixin, forms.Form):
    """User-friendly incident report form submitted directly after scanning an asset QR code."""

    title = forms.CharField(
        max_length=200,
        label="Incident Title",
        help_text="Brief summary of what failed or what is required.",
        widget=forms.TextInput(
            attrs={"placeholder": "e.g. Pump leaking hydraulic fluid", "autocomplete": "off"}
        ),
    )
    severity = forms.ChoiceField(
        choices=ServiceRequest.Severity.choices,
        initial=ServiceRequest.Severity.MEDIUM,
        label="Severity",
        help_text="Urgency and operational impact of the incident.",
    )
    service_impact = forms.ChoiceField(
        choices=ServiceRequest.Impact.choices,
        initial=ServiceRequest.Impact.NONE,
        label="Service Impact",
        help_text="Current level of service disruption.",
    )
    failure_category = forms.CharField(
        max_length=100,
        required=False,
        label="Failure Category",
        help_text="e.g. Mechanical, Electrical, Hydraulic, Structural, Software.",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Mechanical"}),
    )
    description = forms.CharField(
        required=False,
        label="Detailed Description",
        help_text="Symptoms, alarm codes, observed damage, or steps to reproduce.",
        widget=forms.Textarea(attrs={"rows": 4, "placeholder": "Describe what occurred..."}),
    )
    attachment = forms.FileField(
        required=False,
        label="Photo or Evidence",
        help_text="Optional photo of machine damage, gauge reading, or nameplate.",
    )
    override_duplicate = forms.BooleanField(required=False, widget=forms.HiddenInput())
    override_reason = forms.CharField(
        max_length=500,
        required=False,
        label="Override Reason",
        widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Required if overriding duplicate warning..."}),
        help_text="Mandatory explanation if filing a new incident when active duplicates exist.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("override_duplicate") and len((cleaned.get("override_reason") or "").strip()) < 3:
            self.add_error("override_reason", "Provide an override reason of at least 3 characters.")
        return cleaned
