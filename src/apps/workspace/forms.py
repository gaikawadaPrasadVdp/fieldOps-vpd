from django import forms
from django.core.exceptions import ValidationError

from apps.sites.models import Site
from apps.ui.forms import BootstrapFormMixin

from .models import Shift, TechnicianProfile

DAY_CHOICES = [
    ("0", "Monday"),
    ("1", "Tuesday"),
    ("2", "Wednesday"),
    ("3", "Thursday"),
    ("4", "Friday"),
    ("5", "Saturday"),
    ("6", "Sunday"),
]


class ShiftForm(BootstrapFormMixin, forms.ModelForm):
    days = forms.MultipleChoiceField(
        choices=DAY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Working Days",
        help_text="Select all days when this shift is active.",
    )

    class Meta:
        model = Shift
        fields = [
            "code",
            "name",
            "start_time",
            "end_time",
            "site",
            "is_active",
            "notes",
        ]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org
        if org:
            self.fields["site"].queryset = Site.objects.filter(organization=org).order_by("name")
        if self.instance and self.instance.pk:
            self.fields["days"].initial = [str(d) for d in (self.instance.days_of_week or [])]
        else:
            self.fields["days"].initial = ["0", "1", "2", "3", "4"]

    def clean_days(self):
        selected = self.cleaned_data.get("days") or []
        return [int(d) for d in selected]

    def clean_code(self):
        code = (self.cleaned_data.get("code") or "").strip().upper()
        if not code:
            raise ValidationError("Shift code is required.")
        qs = Shift.objects.filter(organization=self.org, code=code)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"A shift with code '{code}' already exists.")
        return code

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.days_of_week = self.cleaned_data["days"]
        if self.org:
            instance.organization = self.org
        if commit:
            instance.save()
        return instance


class TechnicianProfileForm(BootstrapFormMixin, forms.ModelForm):
    skills_text = forms.CharField(
        label="Skills (comma-separated)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. Electrical, HVAC, Hydraulics, PLC"}),
        help_text="Enter relevant technical disciplines separated by commas.",
    )
    certifications_text = forms.CharField(
        label="Certifications (comma-separated)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "e.g. OSHA 30, EPA Universal, ISO 9001"}),
        help_text="Enter recognized safety or professional certifications.",
    )

    class Meta:
        model = TechnicianProfile
        fields = [
            "shift",
            "primary_site",
            "hourly_rate",
            "max_active_jobs",
            "availability_status",
            "emergency_contact",
            "emergency_phone",
            "notes",
        ]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, org=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org
        if org:
            self.fields["shift"].queryset = Shift.objects.filter(organization=org, is_active=True).order_by("name")
            self.fields["primary_site"].queryset = Site.objects.filter(organization=org).order_by("name")
        if self.instance and self.instance.pk:
            self.fields["skills_text"].initial = ", ".join(self.instance.skills or [])
            self.fields["certifications_text"].initial = ", ".join(self.instance.certifications or [])

    def clean_skills_text(self):
        text = self.cleaned_data.get("skills_text", "")
        return [s.strip() for s in text.split(",") if s.strip()]

    def clean_certifications_text(self):
        text = self.cleaned_data.get("certifications_text", "")
        return [c.strip() for c in text.split(",") if c.strip()]

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.skills = self.cleaned_data["skills_text"]
        instance.certifications = self.cleaned_data["certifications_text"]
        if self.org and not instance.organization_id:
            instance.organization = self.org
        if commit:
            instance.save()
        return instance
