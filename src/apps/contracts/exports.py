"""
M10 Warranty / AMC / Contract Export Handlers.
Provides CSV downloads for agreement lists, individual agreement summaries with covered assets, and expiry forecasts.
"""
from __future__ import annotations

import csv
import datetime
from django.http import HttpResponse

from . import selectors


def export_agreements_csv(qs, org) -> HttpResponse:
    """Download filtered coverage agreements as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="warranties_contracts_{org.slug}_{timestamp}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Reference",
        "Title",
        "Type",
        "Provider",
        "Site Code",
        "Start Date",
        "End Date",
        "State",
        "Active",
        "SLA Terms",
        "SLA Profile",
        "Renewal Alert (Days)",
        "Covered Assets Count",
        "Excluded Work Types",
        "Terms",
        "Created At",
    ])
    today = datetime.date.today()
    for a in qs.select_related("provider", "site", "sla_profile").prefetch_related("covered_assets__asset", "exclusions"):
        assets_count = a.covered_assets.count()
        exclusions = ", ".join(e.get_work_type_display() if hasattr(e, "get_work_type_display") else e.work_type for e in a.exclusions.all())
        writer.writerow([
            a.reference,
            a.title,
            a.get_kind_display(),
            a.provider.name if a.provider else "",
            a.site.code if a.site else "",
            a.start_date.isoformat() if a.start_date else "",
            a.end_date.isoformat() if a.end_date else "",
            a.state(today),
            "Yes" if a.is_active else "No",
            a.sla_terms or "",
            a.sla_profile.name if a.sla_profile else "",
            a.renewal_alert_days,
            assets_count,
            exclusions,
            a.terms or "",
            a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "",
        ])
    return response


def export_single_agreement_csv(ag) -> HttpResponse:
    """Download a single coverage agreement with its metadata, terms, and covered assets as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_ref = ag.reference.replace('/', '_').replace('\\', '_')
    response["Content-Disposition"] = f'attachment; filename="warranty_{safe_ref}_{timestamp}.csv"'
    writer = csv.writer(response)
    today = datetime.date.today()
    
    # Header Section
    writer.writerow(["AGREEMENT DETAILS"])
    writer.writerow(["Reference", ag.reference])
    writer.writerow(["Title", ag.title])
    writer.writerow(["Type", ag.get_kind_display()])
    writer.writerow(["State", ag.state(today)])
    writer.writerow(["Active", "Yes" if ag.is_active else "No"])
    writer.writerow(["Provider Name", ag.provider.name if ag.provider else ""])
    writer.writerow(["Provider Email", ag.provider.email if ag.provider else ""])
    writer.writerow(["Provider Phone", ag.provider.phone if ag.provider else ""])
    writer.writerow(["Site Code", ag.site.code if ag.site else ""])
    writer.writerow(["Site Name", ag.site.name if ag.site else ""])
    writer.writerow(["Start Date", ag.start_date.isoformat() if ag.start_date else ""])
    writer.writerow(["End Date", ag.end_date.isoformat() if ag.end_date else ""])
    writer.writerow(["SLA Terms", ag.sla_terms or ""])
    writer.writerow(["SLA Profile", ag.sla_profile.name if ag.sla_profile else ""])
    exclusions = ", ".join(e.get_work_type_display() if hasattr(e, "get_work_type_display") else e.work_type for e in ag.exclusions.all()) or "None"
    writer.writerow(["Exclusions", exclusions])
    writer.writerow(["Terms", ag.terms or ""])
    if ag.exclusion_notes:
        writer.writerow(["Exclusion Notes", ag.exclusion_notes])
    writer.writerow([])
    
    # Covered Assets Section
    writer.writerow(["COVERED ASSETS"])
    writer.writerow(["Asset Tag", "Asset Name", "Category", "Serial Number", "Status"])
    for link in selectors.covered_assets_for(ag).select_related("asset__category"):
        ast = link.asset
        writer.writerow([
            ast.asset_tag,
            ast.name,
            ast.category.name if ast.category else "",
            ast.serial_number or "",
            ast.get_status_display() if hasattr(ast, "get_status_display") else ast.status,
        ])
    return response


def export_expiry_csv(rows, org, days) -> HttpResponse:
    """Download expiring coverage agreements forecast as CSV."""
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    response["Content-Disposition"] = f'attachment; filename="expiring_warranties_{org.slug}_{days}d_{timestamp}.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Reference",
        "Title",
        "Type",
        "Provider",
        "Site Code",
        "End Date",
        "Days Left",
        "Renewed",
        "Covered Assets Count",
    ])
    today = datetime.date.today()
    for a in rows:
        writer.writerow([
            a.reference,
            a.title,
            a.get_kind_display(),
            a.provider.name if a.provider else "",
            a.site.code if a.site else "",
            a.end_date.isoformat() if a.end_date else "",
            (a.end_date - today).days,
            "Yes" if getattr(a, "renewed", False) else "No",
            a.covered_assets.count(),
        ])
    return response
