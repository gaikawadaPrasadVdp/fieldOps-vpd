"""Tests for PRD §5.1 IntegrationEvent Outbox Architecture.
Verifies transactional persistence, Celery worker processing, retries, failure thresholds,
and outbox event generation on domain events.
"""
from unittest.mock import MagicMock
import pytest
from django.db import transaction

from apps.core.models import IntegrationEvent
from apps.core.outbox import (
    deliver_event,
    process_pending_events,
    process_single_event,
    publish_integration_event,
    register_handler,
)
from apps.core.tasks import process_integration_events
from tests.phase3_support import new_wo, step


@pytest.fixture
def org(p3):
    return p3["org"]


def test_publish_integration_event(org):
    """Event is persisted with PENDING status and correct payload within transaction."""
    with transaction.atomic():
        event = publish_integration_event(
            org,
            event_type="test.event",
            aggregate_type="test_agg",
            aggregate_id="12345",
            payload={"key": "value"},
            metadata={"source": "unit_test"},
        )
        assert event.status == IntegrationEvent.Status.PENDING
        assert event.retry_count == 0
        assert event.payload == {"key": "value"}
        assert event.aggregate_type == "test_agg"

    fetched = IntegrationEvent.objects.get(pk=event.pk)
    assert fetched.status == IntegrationEvent.Status.PENDING
    assert fetched.published_at is None


def test_process_pending_events_success(org):
    """Processing pending events delivers to registered handlers and marks PUBLISHED."""
    handler = MagicMock()
    register_handler("order.created", handler)

    event = publish_integration_event(
        org,
        event_type="order.created",
        aggregate_type="order",
        aggregate_id="ORD-001",
        payload={"amount": 100},
    )

    processed = process_pending_events(batch_size=10)
    assert processed >= 1

    event.refresh_from_db()
    assert event.status == IntegrationEvent.Status.PUBLISHED
    assert event.published_at is not None
    assert event.error_message == ""
    assert handler.called


def test_process_pending_events_retry_and_failure(org):
    """Failing handlers increment retry_count; event is marked FAILED when max_retries reached."""
    failing_handler = MagicMock(side_effect=RuntimeError("External API 503 Service Unavailable"))
    register_handler("failing.event", failing_handler)

    event = publish_integration_event(
        org,
        event_type="failing.event",
        aggregate_type="service",
        aggregate_id="SVC-999",
        payload={"attempt": 1},
    )
    event.max_retries = 2
    event.save(update_fields=["max_retries"])

    # First attempt: increments retry_count to 1, status remains PENDING
    process_pending_events(batch_size=10)
    event.refresh_from_db()
    assert event.retry_count == 1
    assert event.status == IntegrationEvent.Status.PENDING
    assert "503" in event.error_message

    # Second attempt: increments retry_count to 2 == max_retries -> status FAILED
    process_pending_events(batch_size=10)
    event.refresh_from_db()
    assert event.retry_count == 2
    assert event.status == IntegrationEvent.Status.FAILED
    assert "503" in event.error_message


def test_celery_task_integration_events(org):
    """Celery task execution successfully processes pending outbox events."""
    event = publish_integration_event(
        org,
        event_type="celery.task.test",
        aggregate_type="task",
        aggregate_id="T-100",
        payload={"task_run": True},
    )

    result = process_integration_events(batch_size=10)
    assert result >= 1

    event.refresh_from_db()
    assert event.status == IntegrationEvent.Status.PUBLISHED


def test_work_order_lifecycle_emits_integration_event(p3):
    """Business operations automatically create integration events in the outbox."""
    wo = new_wo(p3, work_type="CORRECTIVE")
    # Verify integration event for work_order.created
    evt = IntegrationEvent.objects.filter(
        aggregate_type="work_order",
        aggregate_id=str(wo.pk),
        event_type="work_order.created",
    ).first()
    assert evt is not None
    assert evt.payload["order_number"] == wo.order_number
    assert evt.status == IntegrationEvent.Status.PENDING
