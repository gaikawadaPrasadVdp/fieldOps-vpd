from django.db import models

from apps.core.models import TenantOwnedModel


class ReportSnapshot(TenantOwnedModel):
    """Immutable periodic snapshot of frozen operational KPIs and analytics (PRD §4.6, D-054, D-057)."""

    class SnapshotType(models.TextChoices):
        DAILY = "DAILY", "Daily"
        WEEKLY = "WEEKLY", "Weekly"
        MONTHLY = "MONTHLY", "Monthly"

    class Section(models.TextChoices):
        OPERATIONS = "OPERATIONS", "Operations"
        ASSETS = "ASSETS", "Assets & Equipment"
        MAINTENANCE = "MAINTENANCE", "Preventive Maintenance"
        SERVICE = "SERVICE", "Service & SLA"
        INVENTORY = "INVENTORY", "Inventory & Materials"

    snapshot_type = models.CharField(
        max_length=20,
        choices=SnapshotType.choices,
        default=SnapshotType.DAILY,
    )
    section = models.CharField(
        max_length=50,
        choices=Section.choices,
        default=Section.OPERATIONS,
    )
    period_start = models.DateField()
    period_end = models.DateField()
    site = models.ForeignKey(
        "sites.Site",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="report_snapshots",
    )
    metrics = models.JSONField(
        default=dict,
        help_text="Frozen dictionary of computed KPI metrics and aggregates for this period.",
    )
    created_by = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_report_snapshots",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-period_end", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "snapshot_type", "section", "period_start", "period_end"],
                name="uniq_report_snapshot_period",
            )
        ]

    def __str__(self):
        return f"{self.snapshot_type} Snapshot: {self.section} ({self.period_start} to {self.period_end})"
