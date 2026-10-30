from celery import shared_task
from . import services


@shared_task(name="apps.tenancy.tasks.process_scheduled_deletions")
def process_scheduled_deletions():
    """Processes any organizations whose scheduled deletion timestamp has arrived."""
    count = services.process_due_scheduled_deletions()
    return f"Processed {count} due organization deletions."
