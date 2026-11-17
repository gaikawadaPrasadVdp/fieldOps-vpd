"""Forms for Analytics Hub and Snapshot filters and creation."""
from django import forms
from apps.dashboards.models import ReportSnapshot


class AnalyticsHubFilterForm(forms.Form):
    """Sanitizes and validates GET query parameters for the Analytics Hub."""
    SECTION_CHOICES = [
        ("operations", "Operations"),
        ("assets", "Assets"),
        ("maintenance", "Maintenance"),
        ("service", "Service"),
        ("inventory", "Inventory"),
    ]

    section = forms.ChoiceField(choices=SECTION_CHOICES, required=False)
    site = forms.UUIDField(required=False)
    days = forms.IntegerField(min_value=1, max_value=365, required=False, initial=30)
    from_date = forms.DateField(required=False)
    to_date = forms.DateField(required=False)

    def clean_days(self):
        val = self.cleaned_data.get("days")
        if val is None:
            return 30
        return max(1, min(val, 365))


class SnapshotFilterForm(forms.Form):
    """Filters for snapshot history list."""
    section = forms.CharField(max_length=50, required=False)
    type = forms.CharField(max_length=50, required=False)


class SnapshotCreateForm(forms.Form):
    """Validates parameters for generating a new report snapshot."""
    section = forms.ChoiceField(choices=ReportSnapshot.Section.choices)
    snapshot_type = forms.ChoiceField(choices=ReportSnapshot.SnapshotType.choices)
    period_start = forms.DateField(required=False)
    period_end = forms.DateField(required=False)
    notes = forms.CharField(max_length=500, required=False)
