import logging
from typing import Any, Callable

from django.db import transaction
from django.utils import timezone

from apps.core.models import IntegrationEvent

logger = logging.getLogger(__name__)

# Registry of handlers for integration events: event_type -> list of callables
_HANDLERS: dict[str, list[Callable[[IntegrationEvent], Any]]] = {}


def register_handler(event_type: str, handler: Callable[[IntegrationEvent], Any]) -> None:
    """Register an asynchronous consumer/sink for an integration event type."""
    if event_type not in _HANDLERS:
        _HANDLERS[event_type] = []
    if handler not in _HANDLERS[event_type]:
        _HANDLERS[event_type].append(handler)


def get_handlers(event_type: str) -> list[Callable[[IntegrationEvent], Any]]:
    handlers = list(_HANDLERS.get(event_type, []))
    # Support wildcard handlers
    if "*" in _HANDLERS:
        handlers.extend(_HANDLERS["*"])
    return handlers


def publish_integration_event(
    organization,
    event_type: str,
    aggregate_type: str,
    aggregate_id: Any,
    payload: dict,
    metadata: dict | None = None,
) -> IntegrationEvent:
    """Transactionally persist an event to the IntegrationEvent outbox table.
    Ensures events are saved atomically with business mutations in the current transaction.
    """
    event = IntegrationEvent(
        organization=organization,
        event_type=str(event_type),
        aggregate_type=str(aggregate_type),
        aggregate_id=str(aggregate_id),
        payload=payload or {},
        metadata=metadata or {},
        status=IntegrationEvent.Status.PENDING,
    )
    event.full_clean()
    event.save()
    return event


def deliver_event(event: IntegrationEvent) -> bool:
    """Deliver a single integration event to registered handlers.
    Returns True on success, raises exception on failure.
    """
    handlers = get_handlers(event.event_type)
    for handler in handlers:
        handler(event)
    return True


@transaction.atomic
def process_single_event(event_id: str) -> IntegrationEvent:
    """Process a single event with row locking, idempotency check, and retry tracking."""
    event = (
        IntegrationEvent.objects.select_for_update(skip_locked=True)
        .filter(pk=event_id)
        .first()
    )
    if not event:
        return None
    if event.status == IntegrationEvent.Status.PUBLISHED:
        return event

    event.status = IntegrationEvent.Status.PROCESSING
    event.save(update_fields=["status", "updated_at"])

    try:
        deliver_event(event)
        event.status = IntegrationEvent.Status.PUBLISHED
        event.published_at = timezone.now()
        event.error_message = ""
        event.save(update_fields=["status", "published_at", "error_message", "updated_at"])
    except Exception as exc:
        logger.exception("Failed delivering IntegrationEvent %s: %s", event.pk, exc)
        event.retry_count += 1
        event.error_message = str(exc)
        if event.retry_count >= event.max_retries:
            event.status = IntegrationEvent.Status.FAILED
        else:
            event.status = IntegrationEvent.Status.PENDING
        event.save(update_fields=["status", "retry_count", "error_message", "updated_at"])

    return event


def process_pending_events(batch_size: int = 50) -> int:
    """Fetch and process pending integration events across all tenants using SKIP LOCKED."""
    processed_count = 0
    candidate_ids = list(
        IntegrationEvent.objects.unscoped()
        .filter(
            status__in=[IntegrationEvent.Status.PENDING, IntegrationEvent.Status.FAILED],
        )
        .exclude(retry_count__gte=5)
        .order_by("created_at")
        .values_list("pk", flat=True)[:batch_size]
    )

    for event_id in candidate_ids:
        res = process_single_event(str(event_id))
        if res and res.status == IntegrationEvent.Status.PUBLISHED:
            processed_count += 1

    return processed_count
