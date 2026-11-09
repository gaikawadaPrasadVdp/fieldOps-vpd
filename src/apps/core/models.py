import uuid

from django.db import models

from .tenant import TenantManager, get_current_org


class BaseModel(models.Model):
    """UUID primary keys: opaque identifiers, no enumerable sequential IDs in URLs/APIs."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantOwnedModel(BaseModel):
    """Every tenant-owned record links directly to an Organization (docs/DECISIONS.md D-004)."""

    organization = models.ForeignKey(
        "tenancy.Organization", on_delete=models.PROTECT, related_name="+", editable=False
    )

    objects = TenantManager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        ctx = get_current_org()
        if self._state.adding and not self.organization_id and ctx is not None:
            self.organization = ctx
        if not self.organization_id:
            raise ValueError(f"{type(self).__name__} requires an organization.")
        if ctx is not None and self.organization_id != ctx.pk:
            raise ValueError("Cross-tenant write blocked: object organization differs from active tenant.")
        super().save(*args, **kwargs)


class DocumentSequence(TenantOwnedModel):
    """Per-organization, per-document-type counter (service request / work order numbers). Allocation is a
    single UPDATE ... SET last_value = last_value + 1, so concurrent allocations serialise on the row lock and
    never repeat a number (see ``core.sequences.next_number``)."""

    key = models.CharField(max_length=40)
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["organization", "key"], name="uniq_sequence_per_org_key")]

    def __str__(self):
        return f"{self.key}: {self.last_value}"


class IntegrationEvent(TenantOwnedModel):
    """Transactional Outbox event for external enterprise integrations (PRD §5.1).
    Events are committed atomically in the same database transaction as business operations.
    A reliable asynchronous processor (Celery) picks up pending events, delivers them to registered
    sinks or external endpoints, tracks retry counts and failures, and guarantees no event loss.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        PUBLISHED = "PUBLISHED", "Published"
        FAILED = "FAILED", "Failed"

    event_type = models.CharField(max_length=100, db_index=True)
    aggregate_type = models.CharField(max_length=80, db_index=True)
    aggregate_id = models.CharField(max_length=64, db_index=True)
    payload = models.JSONField(default=dict)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    retry_count = models.PositiveIntegerField(default=0)
    max_retries = models.PositiveIntegerField(default=5)
    error_message = models.TextField(blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_integ_evt_stat_created"),
            models.Index(fields=["aggregate_type", "aggregate_id"], name="idx_integ_evt_agg"),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.aggregate_type}:{self.aggregate_id}) - {self.status}"


class WebhookEndpoint(TenantOwnedModel):
    name = models.CharField(max_length=120)
    target_url = models.URLField(max_length=500)
    secret_token = models.CharField(
        blank=True,
        help_text="Secret key used to compute HMAC SHA-256 signature",
        max_length=128,
    )
    event_pattern = models.CharField(
        default="*",
        help_text="Wildcard or exact event pattern, e.g. work_order.* or asset.alert",
        max_length=100,
    )
    is_active = models.BooleanField(db_index=True, default=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(
                fields=["organization", "is_active"],
                name="core_webhoo_organiz_6dd066_idx",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.target_url})"

