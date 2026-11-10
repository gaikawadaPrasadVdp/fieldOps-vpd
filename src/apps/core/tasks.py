from celery import shared_task
from django.core.management import call_command


@shared_task(name="apps.core.tasks.clear_expired_sessions")
def clear_expired_sessions():
    call_command("clearsessions")


@shared_task(name="apps.core.tasks.process_integration_events")
def process_integration_events(batch_size: int = 50) -> int:
    """Asynchronous worker task that polls and publishes transactional outbox integration events."""
    from apps.core.outbox import process_pending_events

    return process_pending_events(batch_size=batch_size)
