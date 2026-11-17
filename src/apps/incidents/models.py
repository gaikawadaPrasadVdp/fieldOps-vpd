from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TenantOwnedModel

from .workflow import NEW, STATES


class ServiceRequest(TenantOwnedModel):
    """M05 incident / breakdown / service request. ``status`` changes ONLY through ``incidents.services``."""

    class Kind(models.TextChoices):
        INCIDENT = "INCIDENT", "Incident / breakdown"
        SERVICE_REQUEST = "SERVICE_REQUEST", "Service request"

    class Severity(models.TextChoices):
        LOW = "LOW", "Low"
        MEDIUM = "MEDIUM", "Medium"
        HIGH = "HIGH", "High"
        CRITICAL = "CRITICAL", "Critical"

    class Impact(models.TextChoices):
        NONE = "NONE", "No service impact"
        DEGRADED = "DEGRADED", "Degraded service"
        PARTIAL = "PARTIAL_OUTAGE", "Partial outage"
        FULL = "FULL_OUTAGE", "Full outage"

    Status = models.TextChoices("Status", {s: (s, s.replace("_", " ").title()) for s in STATES})

    number = models.CharField(max_length=20, editable=False)
    kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.INCIDENT)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MEDIUM, db_index=True)
    service_impact = models.CharField(max_length=20, choices=Impact.choices, default=Impact.NONE)
    impact_notes = models.CharField(max_length=500, blank=True)
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="service_requests")
    site = models.ForeignKey("sites.Site", on_delete=models.PROTECT, related_name="service_requests")
    status = models.CharField(max_length=20, choices=Status.choices, default=NEW, db_index=True)
    reported_by = models.ForeignKey("tenancy.Membership", on_delete=models.PROTECT, related_name="reported_requests")
    occurred_at = models.DateTimeField(help_text="When the failure / need was noticed.")
    triaged_at = models.DateTimeField(null=True, blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_reason = models.CharField(max_length=500, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    failure_category = models.CharField(max_length=100, blank=True, default="", help_text="Failure category")
    assigned_team = models.CharField(max_length=100, blank=True, default="", help_text="Assigned maintenance team")
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name="linked_requests",
                                    help_text="Existing active incident this request was linked to as duplicate")
    override_reason = models.CharField(max_length=500, blank=True, default="",
                                       help_text="Mandatory reason provided when overriding duplicate incident detection")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["organization", "number"], name="uniq_request_number_per_org")]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "site"]),
            models.Index(fields=["organization", "asset"]),
            models.Index(fields=["organization", "severity"]),
            models.Index(fields=["organization", "asset", "status"], name="incidents_org_asset_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} · {self.title}"

    @property
    def linked_work_order(self):
        if hasattr(self, "_linked_work_order"):
            return self._linked_work_order
        from django.apps import apps
        if apps.is_installed("apps.workorders"):
            from apps.workorders.models import WorkOrder
            live = WorkOrder.objects.filter(
                models.Q(source_request=self) |
                models.Q(source_id=self.pk) |
                models.Q(organization=self.organization, source_reference=self.number,
                         source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT))
            ).exclude(status__in=(WorkOrder.Status.CANCELLED, WorkOrder.Status.CLOSED)).first()
            if live is not None:
                return live
            return WorkOrder.objects.filter(
                models.Q(source_request=self) |
                models.Q(source_id=self.pk) |
                models.Q(organization=self.organization, source_reference=self.number,
                         source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT))
            ).order_by("-created_at").first()
        return None

    @property
    def work_order(self):
        return self.linked_work_order

    @linked_work_order.setter
    def linked_work_order(self, value):
        self._linked_work_order = value

    @property
    def coverage(self):
        from django.apps import apps
        if apps.is_installed("apps.contracts") and getattr(self, "asset_id", None):
            from apps.contracts import services as contracts
            ref_date = self.occurred_at.date() if self.occurred_at else None
            return contracts.evaluate(self.organization, self.asset, on=ref_date, work_type="CORRECTIVE")
        return None

    @property
    def assigned_team_display(self) -> str:
        if self.assigned_team:
            return self.assigned_team
        wo = self.linked_work_order
        if wo and wo.assigned_to:
            return wo.assigned_to.user.display_name
        return "Unassigned"

    @property
    def in_service_at(self):
        wo = self.linked_work_order
        if wo and getattr(wo, "started_at", None):
            return wo.started_at
        h = self.history.filter(to_status="IN_SERVICE").order_by("created_at").first()
        return h.created_at if h else None


class Downtime(TenantOwnedModel):
    """M05-owned downtime of the asset caused by one request (start required, end open until service is restored)."""

    request = models.OneToOneField(ServiceRequest, on_delete=models.PROTECT, related_name="downtime")
    asset = models.ForeignKey("assets.Asset", on_delete=models.PROTECT, related_name="downtimes")
    started_at = models.DateTimeField()
    ended_at = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    ended_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                 related_name="+")
    end_source = models.CharField(max_length=20, blank=True, help_text="manual | work_order")

    class Meta:
        constraints = [models.CheckConstraint(
            condition=models.Q(ended_at__isnull=True) | models.Q(ended_at__gte=models.F("started_at")),
            name="downtime_end_after_start")]
        indexes = [models.Index(fields=["organization", "asset"])]

    @property
    def duration(self):
        return (self.ended_at - self.started_at) if self.ended_at else None


class ServiceRequestHistory(TenantOwnedModel):
    """Append-only status history of a request."""

    request = models.ForeignKey(ServiceRequest, on_delete=models.PROTECT, related_name="history")
    from_status = models.CharField(max_length=20, blank=True)
    to_status = models.CharField(max_length=20)
    action = models.CharField(max_length=30)
    reason = models.CharField(max_length=500, blank=True)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+")
    source = models.CharField(max_length=20, default="manual", help_text="manual | work_order")

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("ServiceRequestHistory is append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("ServiceRequestHistory is append-only.")


class ServiceRequestComment(TenantOwnedModel):
    """Client / Staff communication thread and internal notes for a ServiceRequest."""

    request = models.ForeignKey(
        ServiceRequest,
        on_delete=models.CASCADE,
        related_name="comments",
        help_text="The ServiceRequest this message belongs to.",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_request_comments",
        help_text="User who wrote the comment (null if user is deleted).",
    )
    author_membership = models.ForeignKey(
        "tenancy.Membership",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="service_request_comments",
        help_text="Membership of the author at the time of posting.",
    )
    author_name = models.CharField(
        max_length=150,
        blank=True,
        default="",
        help_text="Snapshot of author display name in case user is deleted or deactivated.",
    )
    body = models.TextField(help_text="Comment text content.")
    is_internal = models.BooleanField(
        default=False,
        db_index=True,
        help_text="If True, only visible to staff/internal users, hidden from clients.",
    )

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["organization", "request", "created_at"]),
            models.Index(fields=["organization", "request", "is_internal"]),
        ]

    def __str__(self):
        prefix = "[INTERNAL] " if self.is_internal else ""
        return f"{prefix}{self.author_display}: {self.body[:40]}"

    @property
    def author_display(self) -> str:
        if self.author:
            name = getattr(self.author, "display_name", None) or getattr(self.author, "get_full_name", lambda: None)()
            if name:
                return name
            return self.author.email
        if self.author_name:
            return self.author_name
        return "Unknown User"

    def clean(self):
        super().clean()
        if not self.body or not self.body.strip():
            raise ValidationError({"body": "Comment message cannot be empty."})

    def save(self, *args, **kwargs):
        if self.body:
            self.body = self.body.strip()
        if not self.author_name and self.author:
            name = getattr(self.author, "display_name", None) or getattr(self.author, "get_full_name", lambda: None)()
            self.author_name = name or self.author.email
        super().save(*args, **kwargs)
