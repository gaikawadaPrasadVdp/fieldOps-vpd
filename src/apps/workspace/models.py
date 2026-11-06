from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from apps.core.models import TenantOwnedModel


class TravelLog(TenantOwnedModel):
    """Travel record logged by a technician while in transit or on arrival at a job site."""

    work_order = models.ForeignKey(
        "workorders.WorkOrder",
        on_delete=models.PROTECT,
        related_name="workspace_travel_logs",
    )
    technician = models.ForeignKey(
        "tenancy.Membership",
        on_delete=models.PROTECT,
        related_name="workspace_travel_logs",
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    duration_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    distance_km = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True,
    )
    route_details = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    labor_entry = models.ForeignKey(
        "workorders.WorkOrderLabor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="workspace_travel_origin",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(duration_hours__gt=0) & Q(duration_hours__lte=24),
                name="workspace_travel_duration_1_24",
            )
        ]

    def clean(self):
        super().clean()
        if self.work_order_id and self.organization_id != self.work_order.organization_id:
            raise ValidationError("Work order must belong to the same organization.")
        if self.technician_id and self.organization_id != self.technician.organization_id:
            raise ValidationError("Technician must belong to the same organization.")
        if self.duration_hours is not None and (self.duration_hours <= 0 or self.duration_hours > 24):
            raise ValidationError({"duration_hours": "Travel duration must be between 0 and 24 hours."})


class WorkNote(TenantOwnedModel):
    """Append-only technician notes attached to a work order during execution (D-041)."""

    work_order = models.ForeignKey(
        "workorders.WorkOrder",
        on_delete=models.PROTECT,
        related_name="workspace_notes",
    )
    author = models.ForeignKey(
        "tenancy.Membership",
        on_delete=models.PROTECT,
        related_name="workspace_notes",
    )
    body = models.TextField()

    class Meta:
        ordering = ["created_at"]

    def clean(self):
        super().clean()
        if self.work_order_id and self.organization_id != self.work_order.organization_id:
            raise ValidationError("Work order must belong to the same organization.")
        if not (self.body or "").strip():
            raise ValidationError({"body": "Note body cannot be empty."})


class Shift(TenantOwnedModel):
    """Configured work shift for field technicians (PRD Section 4.2, D-054)."""

    name = models.CharField(max_length=100)
    code = models.CharField(max_length=32)
    start_time = models.TimeField()
    end_time = models.TimeField()
    # Days of week: 0=Monday, 1=Tuesday, ..., 6=Sunday (standard Python weekday)
    days_of_week = models.JSONField(default=list, blank=True)
    site = models.ForeignKey(
        "sites.Site",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="workspace_shifts",
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "code"],
                name="workspace_shift_org_code_uniq",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def duration_hours(self) -> Decimal:
        """Calculate nominal duration of the shift in hours."""
        from datetime import date, datetime, timedelta

        dt_start = datetime.combine(date.today(), self.start_time)
        dt_end = datetime.combine(date.today(), self.end_time)
        if dt_end <= dt_start:
            dt_end += timedelta(days=1)
        diff_secs = (dt_end - dt_start).total_seconds()
        return Decimal(str(round(diff_secs / 3600.0, 2)))

    def clean(self):
        super().clean()
        if self.site_id and self.organization_id != self.site.organization_id:
            raise ValidationError({"site": "Site must belong to the same organization."})
        if self.start_time and self.end_time and self.start_time == self.end_time:
            raise ValidationError("Shift start and end time cannot be identical.")


class TechnicianProfile(TenantOwnedModel):
    """Profile attributes, shift assignment, and skills for field technicians (PRD Section 4.2, D-054)."""

    class AvailabilityStatus(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Available"
        ON_JOB = "ON_JOB", "On Job"
        ON_LEAVE = "ON_LEAVE", "On Leave"
        OFF_DUTY = "OFF_DUTY", "Off Duty"

    membership = models.OneToOneField(
        "tenancy.Membership",
        on_delete=models.CASCADE,
        related_name="technician_profile",
    )
    shift = models.ForeignKey(
        Shift,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="technicians",
    )
    primary_site = models.ForeignKey(
        "sites.Site",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="primary_technicians",
    )
    skills = models.JSONField(default=list, blank=True)
    certifications = models.JSONField(default=list, blank=True)
    hourly_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    max_active_jobs = models.PositiveIntegerField(default=3)
    availability_status = models.CharField(
        max_length=20,
        choices=AvailabilityStatus.choices,
        default=AvailabilityStatus.AVAILABLE,
    )
    emergency_contact = models.CharField(max_length=100, blank=True)
    emergency_phone = models.CharField(max_length=32, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["membership__user__full_name", "membership__user__email"]

    def __str__(self):
        name = getattr(self.membership.user, "full_name", "") or getattr(self.membership.user, "email", "Member")
        return f"Technician: {name}"

    def clean(self):
        super().clean()
        if self.membership_id and self.organization_id != self.membership.organization_id:
            raise ValidationError({"membership": "Membership must belong to the same organization."})
        if self.shift_id and self.organization_id != self.shift.organization_id:
            raise ValidationError({"shift": "Shift must belong to the same organization."})
        if self.primary_site_id and self.organization_id != self.primary_site.organization_id:
            raise ValidationError({"primary_site": "Primary site must belong to the same organization."})
