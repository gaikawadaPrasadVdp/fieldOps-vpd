from __future__ import annotations

import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from django.db import transaction
from django.utils import timezone

from apps.audit import services as audit
from apps.core.exceptions import ValidationFailed
from apps.sites.models import Site

from . import metrics
from .models import ReportSnapshot

if TYPE_CHECKING:
    from django.http import HttpRequest
    from apps.accounts.models import User
    from apps.tenancy.models import Organization


def _sanitize_for_json(data: Any) -> Any:
    """Recursively convert Decimals, dates, and non-primitives to JSON-serializable types."""
    if isinstance(data, dict):
        return {k: _sanitize_for_json(v) for k, v in data.items()}
    if isinstance(data, list | tuple):
        return [_sanitize_for_json(v) for v in data]
    if isinstance(data, Decimal):
        return float(data)
    if isinstance(data, datetime.datetime | datetime.date | datetime.time):
        return data.isoformat()
    return data


@transaction.atomic
def create_report_snapshot(
    organization: Organization,
    *,
    snapshot_type: str = ReportSnapshot.SnapshotType.DAILY,
    section: str = ReportSnapshot.Section.OPERATIONS,
    period_start: datetime.date,
    period_end: datetime.date,
    site: Site | None = None,
    actor: User | None = None,
    notes: str = "",
    request: HttpRequest | None = None,
) -> ReportSnapshot:
    """Compute and persist an immutable KPI snapshot for the given period and section."""
    if period_end < period_start:
        raise ValidationFailed("Period end date cannot be earlier than period start date.", code="invalid_period")

    # Start and end datetimes for calculation
    start_dt = timezone.make_aware(datetime.datetime.combine(period_start, datetime.time.min))
    end_dt = timezone.make_aware(datetime.datetime.combine(period_end, datetime.time.max))

    sites = [site] if site else list(Site.objects.filter(organization=organization))

    # Compute metrics based on section
    if section == ReportSnapshot.Section.OPERATIONS:
        computed = metrics.get_operations_dashboard(organization, sites, start_dt, end_dt)
    elif section == ReportSnapshot.Section.ASSETS:
        computed = metrics.get_assets_dashboard(organization, sites, start_dt, end_dt)
    elif section == ReportSnapshot.Section.MAINTENANCE:
        computed = metrics.get_maintenance_dashboard(organization, sites, start_dt, end_dt)
    elif section == ReportSnapshot.Section.SERVICE:
        computed = metrics.get_service_dashboard(organization, sites, start_dt, end_dt)
    elif section == ReportSnapshot.Section.INVENTORY:
        computed = metrics.get_inventory_dashboard(organization, sites, start_dt, end_dt)
    else:
        computed = metrics.get_operations_dashboard(organization, sites, start_dt, end_dt)

    sanitized = _sanitize_for_json(computed)

    snapshot, created = ReportSnapshot.objects.update_or_create(
        organization=organization,
        snapshot_type=snapshot_type,
        section=section,
        period_start=period_start,
        period_end=period_end,
        defaults={
            "site": site,
            "metrics": sanitized,
            "created_by": actor,
            "notes": notes,
        },
    )

    if actor:
        audit.record(
            action="dashboards.report_snapshot_created",
            organization=organization,
            actor=actor,
            target=snapshot,
            metadata={
                "snapshot_type": snapshot_type,
                "section": section,
                "period": f"{period_start} to {period_end}",
            },
            request=request,
        )

    return snapshot


def archive_snapshots_for_organization(
    organization: Organization,
    *,
    target_date: datetime.date | None = None,
    snapshot_type: str = ReportSnapshot.SnapshotType.DAILY,
) -> list[ReportSnapshot]:
    """Archive snapshots across all standard reporting sections for an organization."""
    if target_date is None:
        target_date = timezone.localdate() - datetime.timedelta(days=1)

    period_start = target_date
    period_end = target_date

    sections = [
        ReportSnapshot.Section.OPERATIONS,
        ReportSnapshot.Section.ASSETS,
        ReportSnapshot.Section.MAINTENANCE,
        ReportSnapshot.Section.SERVICE,
        ReportSnapshot.Section.INVENTORY,
    ]

    snapshots = []
    for section in sections:
        try:
            snap = create_report_snapshot(
                organization,
                snapshot_type=snapshot_type,
                section=section,
                period_start=period_start,
                period_end=period_end,
                notes=f"Automated periodic {snapshot_type} snapshot",
            )
            snapshots.append(snap)
        except Exception:
            # Continue archiving other sections even if one encounters no data
            continue

    return snapshots


def get_snapshot_history(
    organization: Organization,
    *,
    snapshot_type: str | None = None,
    section: str | None = None,
    limit: int = 30,
):
    """Retrieve historical report snapshots scoped to the organization."""
    qs = ReportSnapshot.objects.filter(organization=organization).select_related("site", "created_by")
    if snapshot_type:
        qs = qs.filter(snapshot_type=snapshot_type)
    if section:
        qs = qs.filter(section=section)
    return qs[:limit]
