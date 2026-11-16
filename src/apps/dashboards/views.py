from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any

from django.core.exceptions import PermissionDenied
from django.shortcuts import render
from django.views import View

from apps.assets.models import Asset
from apps.dashboards import metrics, services
from apps.ui.pagination import paginate_dashboard_queryset
from .forms import AnalyticsHubFilterForm, SnapshotFilterForm, SnapshotCreateForm
from apps.incidents.models import ServiceRequest
from apps.inventory.models import StockBalance
from apps.notifications.views import MemberOnlyMixin
from apps.rbac import services as rbac
from apps.sla.models import SLABreach
from apps.ui.mixins import TenantPermissionMixin
from apps.ui.utils import is_technician_membership
from apps.workorders.models import WorkOrder, WorkOrderLabor


def _build_completion_trend_bars(trend: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert non-zero work completion trend buckets into CSS bar items for dashboards."""
    active = [item for item in trend if item.get("count", 0) > 0]
    if not active:
        return []
    max_count = max(item["count"] for item in active) or 1
    return [
        {
            "label": item.get("label") or item["date"],
            "count": f"{item['count']} completed",
            "pct": round((item["count"] / max_count) * 100, 1),
        }
        for item in active
    ]


class DashboardHubView(TenantPermissionMixin, View):
    """Multi-tab operational dashboard hub with pure CSS visualization (D-052)."""

    required_permission = "report.view"
    template_name = "dashboards/hub.html"

    SECTIONS = [
        ("operations", "Operations"),
        ("assets", "Assets"),
        ("maintenance", "Maintenance"),
        ("service", "Service"),
        ("inventory", "Inventory"),
    ]

    @classmethod
    def can_access_section(cls, membership, sec: str) -> bool:
        if sec == "operations":
            return (
                rbac.has_permission_anywhere(membership, "work_order.dispatch")
                or rbac.has_permission_anywhere(membership, "work_order.assign")
                or rbac.has_permission_anywhere(membership, "work_order.review")
                or rbac.has_permission_anywhere(membership, "work_order.plan")
                or rbac.has_permission_anywhere(membership, "work_order.create")
                or rbac.has_permission_anywhere(membership, "sla.view")
                or rbac.has_permission_anywhere(membership, "audit.view")
                or rbac.is_owner(membership)
            )
        elif sec == "assets":
            return rbac.has_permission_anywhere(membership, "asset.view")
        elif sec == "maintenance":
            return rbac.has_permission_anywhere(membership, "maintenance.view")
        elif sec == "service":
            return (
                rbac.has_permission_anywhere(membership, "incident.view")
                or rbac.has_permission_anywhere(membership, "sla.view")
            )
        elif sec == "inventory":
            return (
                rbac.has_permission_anywhere(membership, "inventory.view")
                or rbac.has_permission_anywhere(membership, "inventory.part.view")
                or rbac.has_permission_anywhere(membership, "inventory.reconcile")
                or rbac.has_permission_anywhere(membership, "inventory.warehouse.manage")
                or rbac.has_permission_anywhere(membership, "inventory.adjust")
                or rbac.is_owner(membership)
            )
        return False

    def get(self, request):
        permitted_sections = [
            (sec, label)
            for sec, label in self.SECTIONS
            if self.can_access_section(request.membership, sec)
        ]
        if not permitted_sections:
            raise PermissionDenied("You do not have permission to view any dashboard sections.")

        valid_sections = dict(permitted_sections)

        # Determine preferred default section based on role/persona if not explicitly provided
        default_section = None
        if not request.GET.get("section"):
            from apps.rbac.models import MembershipRole
            user_roles = set(
                MembershipRole.objects.filter(membership=request.membership).values_list("role__system_key", flat=True)
            )
            if user_roles & {"stores_manager", "stores_inventory"} and "inventory" in valid_sections:
                default_section = "inventory"
            elif user_roles & {"asset_manager"} and "assets" in valid_sections:
                default_section = "assets"
            elif user_roles & {"maintenance_planner"} and "maintenance" in valid_sections:
                default_section = "maintenance"
            elif user_roles & {"service_manager"} and "service" in valid_sections:
                default_section = "service"

        requested_section = request.GET.get("section")
        if requested_section:
            section = requested_section.strip().lower().replace("-", "_")
            if not self.can_access_section(request.membership, section):
                raise PermissionDenied(f"Permission required to view {section} dashboard.")
        else:
            section = default_section or permitted_sections[0][0]

        # 2. Date Window Parsing
        from_str = request.GET.get("from")
        to_str = request.GET.get("to")
        start_dt, end_dt = metrics.parse_date_window(from_str, to_str)

        # 3. Permitted Sites Resolution
        requested_site = request.GET.get("site")
        all_user_sites = metrics.resolve_permitted_sites(
            membership=request.membership,
            organization=request.organization,
            section=section,
        )
        if not all_user_sites:
            raise PermissionDenied("No permitted sites available for this dashboard.")

        if requested_site:
            permitted_sites = metrics.resolve_permitted_sites(
                membership=request.membership,
                organization=request.organization,
                section=section,
                requested_site_id=requested_site,
            )
        else:
            permitted_sites = all_user_sites

        # 4. Metric Aggregation
        filter_form = AnalyticsHubFilterForm(request.GET)
        filter_form.is_valid()
        trace_data: dict[str, Any] = {}
        preserved_params = ""
        if section == "operations":
            data = metrics.get_operations_dashboard(request.organization, permitted_sites, start_dt, end_dt)
            qs = WorkOrder.objects.filter(
                organization=request.organization,
                site__in=permitted_sites,
            ).select_related("site", "asset", "assigned_to__user").order_by("-created_at")
            page_obj, preserved_params = paginate_dashboard_queryset(request, qs, page_param="page", per_page=10)
            trace_data["recent_orders"] = list(page_obj)
            trace_data["page_obj"] = page_obj
        elif section == "assets":
            data = metrics.get_assets_dashboard(request.organization, permitted_sites, start_dt, end_dt)
            qs = Asset.objects.filter(
                organization=request.organization,
                site__in=permitted_sites,
            ).select_related("site", "category").order_by("-created_at")
            page_obj, preserved_params = paginate_dashboard_queryset(request, qs, page_param="page", per_page=10)
            trace_data["recent_assets"] = list(page_obj)
            trace_data["page_obj"] = page_obj
        elif section == "maintenance":
            data = metrics.get_maintenance_dashboard(request.organization, permitted_sites, start_dt, end_dt)
            qs = WorkOrder.objects.filter(
                organization=request.organization,
                site__in=permitted_sites,
                work_type=WorkOrder.WorkType.PREVENTIVE,
            ).select_related("site", "asset").order_by("-due_at")
            page_obj, preserved_params = paginate_dashboard_queryset(request, qs, page_param="page", per_page=10)
            trace_data["preventive_orders"] = list(page_obj)
            trace_data["page_obj"] = page_obj
        elif section == "service":
            data = metrics.get_service_dashboard(request.organization, permitted_sites, start_dt, end_dt)
            qs = ServiceRequest.objects.filter(
                organization=request.organization,
                site__in=permitted_sites,
            ).select_related("site", "asset").order_by("-created_at")
            page_obj, preserved_params = paginate_dashboard_queryset(request, qs, page_param="page", per_page=10)
            trace_data["service_requests"] = list(page_obj)
            trace_data["page_obj"] = page_obj
            trace_data["sla_breaches"] = list(
                SLABreach.objects.filter(
                    organization=request.organization,
                    site__in=permitted_sites,
                    breached_at__gte=start_dt,
                    breached_at__lte=end_dt,
                ).select_related("site", "tracking__work_order").order_by("-breached_at")[:8]
            )
        elif section == "inventory":
            data = metrics.get_inventory_dashboard(request.organization, permitted_sites, start_dt, end_dt)
            all_balances = StockBalance.objects.filter(
                organization=request.organization,
                warehouse__site__in=permitted_sites,
            ).select_related("part", "warehouse", "warehouse__site")
            low_stock = []
            for b in all_balances:
                try:
                    if b.is_low:
                        low_stock.append(b)
                except Exception:
                    continue
            page_obj, preserved_params = paginate_dashboard_queryset(request, low_stock, page_param="page", per_page=10)
            trace_data["low_stock_lines"] = list(page_obj)
            trace_data["page_obj"] = page_obj

        # 5. Precompute Pure CSS Bar Percentages
        css_bars = self._compute_css_bars(section, data.get("details", {}))

        is_technician = is_technician_membership(request.membership)

        context = {
            "is_technician": is_technician,
            "section": section,
            "section_display": valid_sections[section],
            "sections": permitted_sections,
            "kpis": data.get("kpis", {}),
            "details": data.get("details", {}),
            "data": data,
            "css_bars": css_bars,
            "trace_data": trace_data,
            "date_from": start_dt.date().isoformat(),
            "date_to": end_dt.date().isoformat(),
            "selected_site": requested_site or "",
            "permitted_sites": all_user_sites,
            "kpi_definitions": metrics.KPI_DEFINITIONS,
            "preserved_params": preserved_params,
            "filter_form": filter_form,
        }
        return render(request, self.template_name, context)

    def _compute_css_bars(self, section: str, details: dict[str, Any]) -> dict[str, Any]:
        """Calculates normalized percentage widths (0-100%) for pure CSS bar visualization."""
        bars: dict[str, Any] = {}
        if section == "operations":
            status_dist = details.get("status_distribution", {})
            total_status = sum(status_dist.values()) or 1
            bars["status_distribution"] = [
                {"label": k, "count": v, "pct": round((v / total_status) * 100, 1)}
                for k, v in status_dist.items() if v > 0
            ]

            prio_dist = details.get("priority_distribution", {})
            total_prio = sum(prio_dist.values()) or 1
            bars["priority_distribution"] = [
                {"label": k, "count": v, "pct": round((v / total_prio) * 100, 1)}
                for k, v in prio_dist.items() if v > 0
            ]
            bars["completion_trend"] = _build_completion_trend_bars(details.get("completion_trend", []))

        elif section == "maintenance":
            work_mix = details.get("work_type_mix", {})
            total_mix = sum(work_mix.values()) or 1
            bars["work_type_mix"] = [
                {"label": k, "count": v, "pct": round((v / total_mix) * 100, 1)}
                for k, v in work_mix.items()
            ]

        elif section == "assets":
            top_failing = details.get("top_failing_assets", [])
            max_outages = max([item["outage_count"] for item in top_failing], default=1) or 1
            bars["top_failing"] = [
                {
                    "label": f"{item['asset__asset_tag']} - {item['asset__name']}",
                    "count": item["outage_count"],
                    "pct": round((item["outage_count"] / max_outages) * 100, 1),
                }
                for item in top_failing
            ]

        elif section == "inventory":
            parts_data = details.get("parts_data", {})
            top_parts = parts_data.get("top_parts", [])
            max_qty = max([float(item.get("total_qty") or 0) for item in top_parts], default=1.0) or 1.0
            bars["top_parts"] = [
                {
                    "label": f"{item.get('part__part_number')} - {item.get('part__name')}",
                    "count": f"{int(round(float(item.get('total_qty'))))} {item.get('part__unit') or 'units'}",
                    "pct": round((float(item.get("total_qty") or 0) / max_qty) * 100, 1),
                }
                for item in top_parts if item.get("total_qty")
            ]

        return bars


class MyWorkDashboardView(MemberOnlyMixin, View):
    """Personal technician operational workspace summary cockpit."""

    template_name = "dashboards/my_work.html"

    def get(self, request):
        if not (
            rbac.has_permission_anywhere(request.membership, "work_order.view")
            or rbac.has_permission_anywhere(request.membership, "work_order.view_assigned")
        ):
            raise PermissionDenied("Work order permissions are required to access My Work Cockpit.")

        from_str = request.GET.get("from")
        to_str = request.GET.get("to")
        start_dt, end_dt = metrics.parse_date_window(from_str, to_str)

        data = metrics.get_my_work_dashboard(request.membership, start_dt, end_dt)

        # Trace assigned jobs
        open_jobs_qs = WorkOrder.objects.filter(
            organization=request.organization,
            assigned_to=request.membership,
        ).exclude(
            status__in=[
                WorkOrder.Status.COMPLETED,
                WorkOrder.Status.SUPERVISOR_REVIEW,
                WorkOrder.Status.CLOSED,
                WorkOrder.Status.CANCELLED,
            ]
        ).select_related("site", "asset").order_by("-priority", "planned_start")
        open_jobs_page_obj, my_work_params = paginate_dashboard_queryset(request, open_jobs_qs, page_param="jobs_page", per_page=10)
        open_jobs = list(open_jobs_page_obj)

        recent_labor = list(
            WorkOrderLabor.objects.filter(
                organization=request.organization,
                technician=request.membership,
                work_date__gte=start_dt.date(),
                work_date__lte=end_dt.date(),
            ).select_related("work_order").order_by("-work_date")[:10]
        )

        capacity = max(1.0, data["details"]["available_capacity_hours"])
        logged = data["details"]["total_labor_hours"]
        util_pct = min(100.0, round((logged / capacity) * 100.0, 1))

        is_technician = is_technician_membership(request.membership)
        can_view_hub = rbac.has_permission_anywhere(request.membership, "report.view")

        context = {
            "is_technician": is_technician,
            "can_view_hub": can_view_hub,
            "data": data,
            "kpis": data.get("kpis", {}),
            "trend_bars": _build_completion_trend_bars(data.get("details", {}).get("completion_trend", [])),
            "open_jobs": open_jobs,
            "open_jobs_page_obj": open_jobs_page_obj,
            "recent_labor": recent_labor,
            "preserved_params": my_work_params,
            "util_pct": util_pct,
            "date_from": start_dt.date().isoformat(),
            "date_to": end_dt.date().isoformat(),
        }
        return render(request, self.template_name, context)


import json
from django.http import Http404, JsonResponse
from django.contrib import messages
from django.shortcuts import redirect
from .models import ReportSnapshot
from . import services


class SnapshotListView(TenantPermissionMixin, View):
    required_permission = "report.view"
    template_name = "dashboards/snapshots_list.html"

    def get(self, request):
        filter_form = SnapshotFilterForm(request.GET)
        filter_form.is_valid()
        sec_filter = filter_form.cleaned_data.get("section")
        type_filter = filter_form.cleaned_data.get("type")
        qs = services.get_snapshot_history(
            request.organization,
            snapshot_type=type_filter,
            section=sec_filter,
            limit=None,
        )
        page, preserved_params = paginate_dashboard_queryset(request, qs, page_param="page", per_page=20)
        return render(
            request,
            self.template_name,
            {
                "page": page,
                "snapshots": page,
                "sections": ReportSnapshot.Section.choices,
                "types": ReportSnapshot.SnapshotType.choices,
                "selected_section": sec_filter,
                "selected_type": type_filter,
                "filter_form": filter_form,
                "preserved_params": preserved_params,
            },
        )

    def post(self, request):
        sec = request.POST.get("section") or ReportSnapshot.Section.OPERATIONS
        stype = request.POST.get("snapshot_type") or ReportSnapshot.SnapshotType.DAILY
        start_str = request.POST.get("period_start")
        end_str = request.POST.get("period_end")
        notes = request.POST.get("notes", "")

        try:
            start_date = datetime.date.fromisoformat(start_str) if start_str else timezone.localdate() - datetime.timedelta(days=1)
            end_date = datetime.date.fromisoformat(end_str) if end_str else timezone.localdate() - datetime.timedelta(days=1)
            snap = services.create_report_snapshot(
                request.organization,
                snapshot_type=stype,
                section=sec,
                period_start=start_date,
                period_end=end_date,
                actor=request.user,
                notes=notes,
                request=request,
            )
            messages.success(request, f"Snapshot generated for {snap.get_section_display()} ({snap.period_start} to {snap.period_end}).")
        except Exception as exc:
            messages.error(request, f"Failed to generate snapshot: {exc}")

        return redirect("dashboards:snapshot_list")


class SnapshotDetailView(TenantPermissionMixin, View):
    required_permission = "report.view"
    template_name = "dashboards/snapshot_detail.html"

    def get(self, request, pk):
        snapshot = ReportSnapshot.objects.filter(organization=request.organization, pk=pk).select_related("site", "created_by").first()
        if not snapshot:
            raise Http404("Snapshot not found.")
        return render(request, self.template_name, {"snapshot": snapshot})


class SnapshotExportView(TenantPermissionMixin, View):
    required_permission = "report.view"

    def get(self, request, pk):
        snapshot = ReportSnapshot.objects.filter(organization=request.organization, pk=pk).first()
        if not snapshot:
            raise Http404("Snapshot not found.")
        response = JsonResponse(snapshot.metrics, json_dumps_params={"indent": 2})
        filename = f"snapshot_{snapshot.section}_{snapshot.period_start}_{snapshot.period_end}.json"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
