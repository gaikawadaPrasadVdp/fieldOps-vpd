from decimal import Decimal
from django import forms

from apps.assets.models import Asset, AssetMeter
from apps.ui.forms import BootstrapFormMixin

from .models import MaintenanceSchedule
from .services import PRIORITIES


class _AssetChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.asset_tag} · {obj.name} ({obj.site.code})"


class _MeterChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.name} ({obj.unit})"


class PlanForm(BootstrapFormMixin, forms.Form):
    asset = _AssetChoice(queryset=Asset.objects.none(), label="Asset")
    name = forms.CharField(max_length=150, min_length=2, label="Plan name",
                           widget=forms.TextInput(attrs={"placeholder": "e.g. Monthly Bearing Lubrication"}))
    description = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Scope and procedures for this maintenance plan..."}))
    priority = forms.ChoiceField(choices=[(p, p.title()) for p in PRIORITIES], initial="MEDIUM")
    estimated_hours = forms.DecimalField(required=False, min_value=0, max_digits=6, decimal_places=2,
                                         widget=forms.NumberInput(attrs={"placeholder": "e.g. 2.5"}))
    checklist_key = forms.ChoiceField(required=False, label="Required checklist")

    def __init__(self, *args, assets=None, checklist_keys=(), editing=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["checklist_key"].choices = [("", "None")] + list(checklist_keys)
        if editing:
            del self.fields["asset"]
        else:
            self.fields["asset"].queryset = assets.exclude(status__in=["RETIRED", "DISPOSED"]).order_by("asset_tag")

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Plan name must be at least 2 characters.")
        return name

    def clean_estimated_hours(self):
        hours = self.cleaned_data.get("estimated_hours")
        if hours is not None and hours < 0:
            raise forms.ValidationError("Estimated hours cannot be negative.")
        return hours


class ScheduleForm(BootstrapFormMixin, forms.Form):
    trigger_type = forms.ChoiceField(choices=MaintenanceSchedule.Trigger.choices, label="Based on", initial="TIME")
    frequency = forms.ChoiceField(required=False, choices=[("", "-")] + MaintenanceSchedule.Frequency.choices,
                                  label="Repeats every ... (time-based)")
    interval_count = forms.IntegerField(required=False, min_value=1, max_value=1000, label="Interval (time-based)")
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                 label="First due date (time-based, site date)")
    meter = _MeterChoice(queryset=AssetMeter.objects.none(), required=False, label="Meter (meter-based)")
    interval_value = forms.DecimalField(required=False, min_value=0, max_digits=16, decimal_places=3,
                                        label="Every ... meter units (meter-based)")
    start_value = forms.DecimalField(required=False, min_value=0, max_digits=16, decimal_places=3, initial=0,
                                     label="Counting starts at (meter-based)")
    lead_days = forms.IntegerField(min_value=0, max_value=60, initial=0, label="Generate the work order ... days early")
    window_start_time = forms.TimeField(initial="08:00", widget=forms.TimeInput(attrs={"type": "time"}),
                                        label="Maintenance window starts at (site time)")
    window_hours = forms.IntegerField(min_value=1, max_value=24, initial=8, label="Window length (hours)")
    reminder_days = forms.IntegerField(min_value=0, max_value=60, initial=0, label="Remind planners ... days before")

    def __init__(self, *args, meters=None, editing=False, trigger_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["meter"].queryset = meters if meters is not None else AssetMeter.objects.none()
        self.editing = editing
        self.trigger_type = trigger_type or (self.data.get("trigger_type") if hasattr(self, "data") else None) or (self.initial.get("trigger_type") if hasattr(self, "initial") else None) or "TIME"
        if editing:
            if "trigger_type" in self.fields:
                del self.fields["trigger_type"]

    def clean(self):
        cleaned = super().clean()
        trigger = cleaned.get("trigger_type") or getattr(self, "trigger_type", None) or "TIME"
        cleaned["trigger_type"] = trigger

        if trigger == MaintenanceSchedule.Trigger.TIME:
            freq = cleaned.get("frequency")
            if not freq or freq not in MaintenanceSchedule.Frequency.values:
                self.add_error("frequency", "Choose a frequency.")

            count = cleaned.get("interval_count")
            if count is None:
                self.add_error("interval_count", "The interval must be a whole number.")
            elif count < 1 or count > 1000:
                self.add_error("interval_count", "The interval must be between 1 and 1000.")

            sdate = cleaned.get("start_date")
            if not sdate:
                self.add_error("start_date", "A start date is required.")

            cleaned["meter"] = None
            cleaned["interval_value"] = None
            cleaned["start_value"] = Decimal("0")
        elif trigger == MaintenanceSchedule.Trigger.METER:
            meter = cleaned.get("meter")
            if not meter:
                self.add_error("meter", "Meter not found in this organization.")

            ival = cleaned.get("interval_value")
            if ival is None:
                self.add_error("interval_value", "Interval must be a valid number.")
            elif ival <= 0:
                self.add_error("interval_value", "Interval must be greater than zero.")

            sval = cleaned.get("start_value")
            if sval is not None and sval < 0:
                self.add_error("start_value", "Start value cannot be negative.")

            cleaned["frequency"] = ""
            cleaned["interval_count"] = None
            cleaned["start_date"] = None
        else:
            self.add_error("trigger_type", "Choose time-based or meter-based.")

        lead = cleaned.get("lead_days")
        if lead is not None and (lead < 0 or lead > 60):
            self.add_error("lead_days", "Lead days must be between 0 and 60.")

        whours = cleaned.get("window_hours")
        if whours is not None and (whours < 1 or whours > 24):
            self.add_error("window_hours", "Window hours must be between 1 and 24.")

        remind = cleaned.get("reminder_days")
        if remind is not None and (remind < 0 or remind > 60):
            self.add_error("reminder_days", "Reminder days must be between 0 and 60.")

        return cleaned
