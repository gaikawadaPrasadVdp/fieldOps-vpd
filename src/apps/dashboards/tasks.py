"""Celery tasks for M14 KPI snapshot archiving. Idempotent, tenant-isolated, and retry-safe."""
import logging
from celery import shared_task
from django.db import OperationalError

log = logging.getLogger(__name__)


@shared_task(
    name="apps.dashboards.tasks.archive_periodic_report_snapshots",
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    max_retries=3,
)
def archive_periodic_report_snapshots(self) -> dict:
    """Fan out snapshot archiving across all active organizations for yesterday's KPIs."""
    from apps.core.tenant import tenant_context
    from apps.tenancy.models import Organization

    from . import services

    stats = {"organizations": 0, "snapshots_created": 0}
    for org in Organization.objects.filter(status=Organization.Status.ACTIVE):
        with tenant_context(org):
            snaps = services.archive_snapshots_for_organization(org)
            stats["organizations"] += 1
            stats["snapshots_created"] += len(snaps)

    log.info("Report snapshots archived successfully", extra={"snapshot_stats": stats})
    return stats


@shared_task(
    name="apps.dashboards.tasks.archive_report_snapshots_for_org",
    bind=True,
    autoretry_for=(OperationalError,),
    retry_backoff=True,
    max_retries=3,
)
def archive_report_snapshots_for_org(self, organization_id: str, date_str: str | None = None) -> dict:
    """Archive snapshots for a specific organization."""
    import datetime
    from apps.core.tenant import tenant_context
    from apps.tenancy.models import Organization

    from . import services

    org = Organization.objects.get(pk=organization_id, status=Organization.Status.ACTIVE)
    target_date = datetime.date.fromisoformat(date_str) if date_str else None
    with tenant_context(org):
        snaps = services.archive_snapshots_for_organization(org, target_date=target_date)

    return {"organization": str(org.pk), "snapshots_created": len(snaps)}
