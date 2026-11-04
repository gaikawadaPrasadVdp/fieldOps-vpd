from datetime import timedelta
from django import forms
from django.utils import timezone

from apps.assets.models import Asset
from apps.ui.forms import BootstrapFormMixin

from .models import ServiceRequest

DT_FORMAT = "%Y-%m-%dT%H:%M"
FUTURE_SLACK = timedelta(minutes=5)
MAX_PAST_DAYS = timedelta(days=90)


def dt_field(label, required=False, **kw):
    return forms.DateTimeField(required=required, label=label, input_formats=[DT_FORMAT, "%Y-%m-%d %H:%M"],
                               widget=forms.DateTimeInput(attrs={"type": "datetime-local"}, format=DT_FORMAT), **kw)


class _AssetChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.asset_tag} · {obj.name} ({obj.site.code})"


class RequestForm(BootstrapFormMixin, forms.Form):
    asset = _AssetChoice(queryset=Asset.objects.none(), label="Asset")
    kind = forms.ChoiceField(choices=ServiceRequest.Kind.choices, label="Type")
    title = forms.CharField(max_length=200, help_text="What failed or what is needed?")
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    severity = forms.ChoiceField(choices=ServiceRequest.Severity.choices, initial="MEDIUM")
    service_impact = forms.ChoiceField(choices=ServiceRequest.Impact.choices, label="Service impact")
    impact_notes = forms.CharField(max_length=500, required=False, label="Impact notes")
    failure_category = forms.CharField(max_length=100, required=False, label="Failure category",
                                       help_text="e.g. Mechanical, Electrical, Hydraulic, etc.")
    assigned_team = forms.CharField(max_length=100, required=False, label="Assigned team",
                                    help_text="Optional maintenance team to route to")
    occurred_at = dt_field("When did it happen? (blank = now)")
    downtime_started_at = dt_field("Downtime started (if the asset is down)")
    override_duplicate = forms.BooleanField(required=False, widget=forms.HiddenInput())
    override_reason = forms.CharField(max_length=500, required=False, label="Override reason",
                                      widget=forms.Textarea(attrs={"rows": 2}),
                                      help_text="Mandatory reason if creating a duplicate incident")

    def __init__(self, *args, assets=None, editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        if assets is not None:
            self.fields["asset"].queryset = assets.exclude(status__in=["RETIRED", "DISPOSED"]).order_by("asset_tag")
        if editing:
            for f in ("override_duplicate", "override_reason"):
                if f in self.fields:
                    del self.fields[f]

    def clean(self):
        cleaned = super().clean()
        now = timezone.now()
        future_limit = now + FUTURE_SLACK
        past_limit = now - MAX_PAST_DAYS

        occurred_at = cleaned.get("occurred_at")
        downtime_started_at = cleaned.get("downtime_started_at")

        if occurred_at:
            if occurred_at > future_limit:
                self.add_error("occurred_at", "The time of the failure cannot be in the future.")
            elif occurred_at < past_limit:
                self.add_error("occurred_at", "The time of the failure cannot be more than 90 days in the past.")

        if downtime_started_at:
            if downtime_started_at > future_limit:
                self.add_error("downtime_started_at", "The downtime start cannot be in the future.")
            elif downtime_started_at < past_limit:
                self.add_error("downtime_started_at", "The downtime start cannot be more than 90 days in the past.")

        if occurred_at and downtime_started_at and downtime_started_at < occurred_at:
            self.add_error(
                "downtime_started_at",
                "The downtime start cannot be before the incident occurred.",
            )

        if cleaned.get("override_duplicate") and len((cleaned.get("override_reason") or "").strip()) < 3:
            self.add_error("override_reason", "Enter at least 3 characters explaining why this is a separate incident.")
        return cleaned


class CreateWorkOrderForm(BootstrapFormMixin, forms.Form):
    title = forms.CharField(max_length=200, required=False, label="Work order title (blank = from request)")
    priority = forms.ChoiceField(choices=[("", "(from severity)"), ("LOW", "Low"), ("MEDIUM", "Medium"),
                                          ("HIGH", "High"), ("URGENT", "Urgent")], required=False)


class DowntimeForm(BootstrapFormMixin, forms.Form):
    started_at = dt_field("Downtime started", required=True)
    ended_at = dt_field("Downtime ended (blank = still down)")


class EvidenceForm(BootstrapFormMixin, forms.Form):
    file = forms.FileField()
    description = forms.CharField(max_length=200, required=False)
