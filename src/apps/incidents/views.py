from __future__ import annotations
import logging
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, models
"""M05 HTML views. Same chain as M01/M02: login -> membership -> permission gate -> organization + site-scope
restricted lookup (404) -> permission for the request's site (403) -> service (validation, transaction, audit)."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from apps.assets import selectors as asset_selectors
from apps.core.exceptions import DomainError
from apps.rbac import services as rbac
from apps.sites import selectors as site_selectors
from apps.sites.views import form_page, need, or404
from apps.ui.mixins import TenantPermissionMixin

from . import selectors, services
from .forms import DowntimeForm, EvidenceForm, RequestForm, ServiceRequestCommentForm
from .models import ServiceRequest
from .workflow import ACTION_PERMISSIONS, BUTTON_STYLES, REASON_REQUIRED, REQUEST_STATUS, SYSTEM_ACTIONS, WORKFLOW_STATES

TABS = [("overview", "Overview"), ("comments", "Communication"), ("evidence", "Evidence"), ("history", "History")]
CONFIRMS = {"reject": "Reject this request?", "close": "Close this request?", "confirm": "Confirm resolution of this request?", "reopen": "Reopen this request for rework?"}
logger = logging.getLogger(__name__)


def _req(request, pk, code=None) -> ServiceRequest:
    sr = or404(selectors.get_request, request.membership, request.organization, pk, "incident.view_assigned")
    if code:
        need(request, code, sr.site_id)
    return sr


class IncidentBase(TenantPermissionMixin, View):
    def dispatch(self, request, *args, **kwargs):
        from apps.ui.utils import is_client_membership
        if (
            hasattr(request, "membership")
            and is_client_membership(request.membership)
            and not selectors.is_owned_asset_reporter(request.membership)
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class RequestListView(IncidentBase):
    required_permission = "incident.view_assigned"

    def get(self, request):
        m, org = request.membership, request.organization
        qs = selectors.filter_requests(selectors.requests_for(m, org), request.GET)
        page = Paginator(qs, 20).get_page(request.GET.get("page"))

        linked_wo_map = {}
        from django.apps import apps
        if apps.is_installed("apps.workorders"):
            from apps.workorders.models import WorkOrder
            req_numbers = [r.number for r in page]
            req_ids = [r.pk for r in page]
            for wo in WorkOrder.objects.for_organization(org).filter(
                models.Q(source_request_id__in=req_ids) |
                models.Q(source_id__in=req_ids) |
                models.Q(source_reference__in=req_numbers,
                         source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT))
            ).order_by("created_at"):
                if wo.source_request_id:
                    linked_wo_map[str(wo.source_request_id)] = wo
                if wo.source_id:
                    linked_wo_map[str(wo.source_id)] = wo
                if wo.source_reference:
                    linked_wo_map[wo.source_reference] = wo

        for r in page:
            wo = linked_wo_map.get(str(r.pk)) or linked_wo_map.get(r.number)
            r.linked_work_order = wo
            r.can_triage = (r.status == "NEW" and rbac.has_permission(m, "incident.triage", r.site_id))
            r.can_approve = (r.status == "TRIAGED" and rbac.has_permission(m, "incident.approve", r.site_id))
            r.can_reject = (r.status == "TRIAGED" and rbac.has_permission(m, "incident.approve", r.site_id))
            r.can_convert = (
                r.status == "APPROVED" and
                rbac.has_permission(m, "work_order.create", r.site_id) and
                not wo
            )

        base_reqs = selectors.requests_for(m, org)
        stats = base_reqs.order_by().aggregate(
            total=models.Count("pk"),
            open=models.Count("pk", filter=~models.Q(status__in=("CLOSED", "REJECTED", "CANCELLED"))),
            critical=models.Count("pk", filter=models.Q(severity="CRITICAL") & ~models.Q(status__in=("CLOSED", "REJECTED", "CANCELLED"))),
            closed=models.Count("pk", filter=models.Q(status__in=("RESOLVED", "CLOSED"))),
        )
        total_incidents = stats["total"] or 0
        open_incidents = stats["open"] or 0
        critical_incidents = stats["critical"] or 0
        closed_incidents = stats["closed"] or 0

        return render(request, "incidents/list.html", {
            "page": page, "filters": request.GET, "statuses": [(s, s.replace("_", " ").title()) for s in WORKFLOW_STATES],
            "severities": ServiceRequest.Severity.choices, "kinds": ServiceRequest.Kind.choices,
            "sites": site_selectors.sites_for(m, org, "incident.view").order_by("code"),
            "can_create": (rbac.has_permission_anywhere(m, "incident.create") or
                           selectors.is_owned_asset_reporter(m)),
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "critical_incidents": critical_incidents,
            "closed_incidents": closed_incidents})


class RequestCheckDuplicateView(IncidentBase):
    required_permission = "incident.create"

    def dispatch(self, request, *args, **kwargs):
        if selectors.is_owned_asset_reporter(request.membership):
            self.required_permission = "incident.report_owned"
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        from django.http import JsonResponse
        asset_id = request.GET.get("asset")
        if not asset_id:
            return JsonResponse({"duplicate_found": False, "duplicates": []})
        if selectors.is_owned_asset_reporter(request.membership):
            from apps.assets.models import Asset

            valid_asset = Asset.objects.for_organization(request.organization).filter(
                pk=asset_id, owner=request.membership).exclude(status__in=("RETIRED", "DISPOSED")).exists()
            if not valid_asset:
                raise Http404
        else:
            asset = asset_selectors.get_asset(request.membership, request.organization, asset_id, "asset.view")
            need(request, "incident.create", asset.site_id)
        duplicates = services.find_duplicate_incidents(
            request.organization,
            asset_id=asset_id,
            kind=request.GET.get("kind", "INCIDENT"),
            failure_category=request.GET.get("failure_category", ""),
            service_impact=request.GET.get("service_impact", ""),
            severity=request.GET.get("severity", ""),
            description=request.GET.get("description", ""),
            title=request.GET.get("title", ""),
        )
        return JsonResponse({
            "duplicate_found": len(duplicates) > 0,
            "duplicates": duplicates,
        })


class RequestCreateView(IncidentBase):
    required_permission = "incident.create"
    crumbs = [("Incidents & requests", "/app/incidents/"), ("Report", None)]

    def dispatch(self, request, *args, **kwargs):
        if selectors.is_owned_asset_reporter(request.membership):
            self.required_permission = "incident.report_owned"
        return super().dispatch(request, *args, **kwargs)

    def _assets(self, request, wanted=None):
        # The asset must lie in the caller's site scope (asset.view + incident.create), so a report can never be
        # raised against an asset outside the reporter's sites.
        m, org = request.membership, request.organization
        if selectors.is_owned_asset_reporter(m):
            from apps.assets.models import Asset

            return Asset.objects.for_organization(org).filter(owner=m).exclude(
                status__in=("RETIRED", "DISPOSED")).select_related("site").order_by("asset_tag")
        scope = rbac.site_scope(m, "incident.create")
        qs = asset_selectors.assets_for(m, org, "asset.view")
        return scope.filter(qs.distinct(), "site_id")

    def get(self, request):
        form = RequestForm(assets=self._assets(request, request.GET.get("asset")),
                           initial={"asset": request.GET.get("asset")})
        return render(request, "incidents/create.html", {
            "title": "Report an incident / request",
            "form": form,
            "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
            "cancel_url": "/app/incidents/",
            "crumbs": self.crumbs,
            "subtitle": "Describe what failed and its impact. A supervisor will triage it.",
            "detected_duplicates": None,
        })

    def post(self, request):
        if request.POST.get("action") == "link_duplicate":
            form = RequestForm(request.POST, assets=self._assets(request, request.POST.get("asset")))
            if not form.is_valid():
                return render(request, "incidents/create.html", {
                    "title": "Report an incident / request", "form": form,
                    "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
                    "cancel_url": "/app/incidents/", "crumbs": self.crumbs,
                    "subtitle": "Correct the report details before linking it.",
                    "detected_duplicates": None,
                }, status=400)
            existing_id = request.POST.get("existing_incident_id")
            report_permission = ("incident.report_owned" if selectors.is_owned_asset_reporter(request.membership)
                                 else "incident.create")
            if selectors.is_owned_asset_reporter(request.membership):
                existing_sr = ServiceRequest.objects.for_organization(request.organization).filter(
                    pk=existing_id).select_related("asset", "site").first()
                if existing_sr is None:
                    raise Http404
            else:
                existing_sr = or404(selectors.get_request, request.membership, request.organization,
                                    existing_id, report_permission)
            need(request, report_permission, existing_sr.site_id)
            d = form.cleaned_data
            if (selectors.is_owned_asset_reporter(request.membership) and
                    existing_sr.asset.owner_id != request.membership.pk):
                raise Http404
            if d["asset"].pk != existing_sr.asset_id or d["kind"] != existing_sr.kind:
                form.add_error(None, "The linked incident must match the report's asset and type.")
                return render(request, "incidents/create.html", {
                    "title": "Report an incident / request", "form": form,
                    "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
                    "cancel_url": "/app/incidents/", "crumbs": self.crumbs,
                    "subtitle": "Review the report details before linking it.",
                    "detected_duplicates": None,
                }, status=400)
            if existing_sr.status not in services.ACTIVE_INCIDENT_STATUSES:
                form.add_error(None, "Select one of the matching active incidents shown above.")
                return render(request, "incidents/create.html", {
                    "title": "Report an incident / request", "form": form,
                    "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
                    "cancel_url": "/app/incidents/", "crumbs": self.crumbs,
                    "subtitle": "Review the matching incident before linking this report.",
                    "detected_duplicates": None,
                }, status=400)
            try:
                linked = services.link_duplicate_request(
                    existing_sr,
                    reporter=request.membership,
                    actor=request.user,
                    title=d["title"],
                    description=d["description"],
                    notes=d["impact_notes"],
                    severity=d["severity"],
                    service_impact=d["service_impact"],
                    failure_category=d["failure_category"],
                    assigned_team=d["assigned_team"],
                    request=request,
                )
            except DomainError as exc:
                form.add_error(None, exc.message)
                return render(request, "incidents/create.html", {
                    "title": "Report an incident / request", "form": form,
                    "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
                    "cancel_url": "/app/incidents/", "crumbs": self.crumbs,
                    "subtitle": "The selected incident could not be linked.",
                    "detected_duplicates": None,
                }, status=exc.status_code)
            messages.success(request, f"New report {linked.number} linked to existing incident {existing_sr.number}.")
            if selectors.is_owned_asset_reporter(request.membership):
                return redirect("incidents:detail", pk=linked.pk)
            return redirect(f"/app/incidents/{existing_sr.pk}/?duplicate_review=1")

        form = RequestForm(request.POST, assets=self._assets(request, request.POST.get("asset")))
        if form.is_valid():
            d = dict(form.cleaned_data)
            asset = d.pop("asset")
            override_duplicate = d.pop("override_duplicate", False)
            override_reason = d.pop("override_reason", "")
            try:
                sr = services.create_request(
                    request.organization, asset=asset, reporter=request.membership,
                    actor=request.user, request=request,
                    override_duplicate=override_duplicate,
                    override_reason=override_reason,
                    **{k: v for k, v in d.items() if v not in (None, "")}
                )
                messages.success(request, f"{sr.number} reported.")
                return redirect("incidents:detail", pk=sr.pk)
            except services.DuplicateIncidentError as exc:
                return render(request, "incidents/create.html", {
                    "title": "Report an incident / request",
                    "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
                    "form": form,
                    "cancel_url": "/app/incidents/",
                    "crumbs": self.crumbs,
                    "subtitle": "Possible duplicate incident detected. Review existing details below.",
                    "detected_duplicates": exc.duplicates,
                }, status=409)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return render(request, "incidents/create.html", {
            "title": "Report an incident / request",
            "owned_asset_reporter": selectors.is_owned_asset_reporter(request.membership),
            "form": form,
            "cancel_url": "/app/incidents/",
            "crumbs": self.crumbs,
            "subtitle": "Describe what failed and its impact. A supervisor will triage it.",
            "detected_duplicates": None,
        }, status=400)


class RequestEditView(IncidentBase):
    required_permission = "incident.update"

    def _assets(self, request, current_asset_id=None):
        m, org = request.membership, request.organization
        if selectors.is_owned_asset_reporter(m):
            from apps.assets.models import Asset

            return Asset.objects.for_organization(org).filter(owner=m).exclude(
                status__in=("RETIRED", "DISPOSED")).select_related("site").order_by("asset_tag")
        scope = rbac.site_scope(m, "incident.create")
        qs = asset_selectors.assets_for(m, org, "asset.view")
        filtered_qs = scope.filter(qs.distinct(), "site_id")
        if current_asset_id:
            from apps.assets.models import Asset
            from django.db.models import Q
            return Asset.objects.for_organization(org).filter(
                Q(pk__in=filtered_qs.values("pk")) | Q(pk=current_asset_id)
            ).select_related("site").exclude(status__in=("RETIRED", "DISPOSED")).order_by("asset_tag")
        return filtered_qs.order_by("asset_tag")

    def get(self, request, pk):
        sr = _req(request, pk, "incident.update")
        dt = selectors.downtime_for(request.organization, sr)
        initial = {
            "asset": sr.asset_id,
            "kind": sr.kind,
            "title": sr.title,
            "description": sr.description,
            "severity": sr.severity,
            "service_impact": sr.service_impact,
            "impact_notes": sr.impact_notes,
            "failure_category": sr.failure_category,
            "assigned_team": sr.assigned_team,
            "occurred_at": sr.occurred_at,
            "downtime_started_at": dt.started_at if dt else sr.occurred_at,
        }
        form = RequestForm(
            initial=initial,
            assets=self._assets(request, sr.asset_id),
            editing=True,
        )
        return render(request, "incidents/edit.html", {
            "title": f"Edit {sr.number}",
            "subtitle": f"{sr.title} · Currently {sr.get_status_display()}",
            "sr": sr,
            "form": form,
            "cancel_url": f"/app/incidents/{sr.pk}/",
            "crumbs": [("Incidents & requests", "/app/incidents/"), (sr.number, f"/app/incidents/{sr.pk}/"), ("Edit", None)],
        })

    def post(self, request, pk):
        sr = _req(request, pk, "incident.update")
        form = RequestForm(
            request.POST,
            assets=self._assets(request, sr.asset_id),
            editing=True,
        )
        if form.is_valid():
            cleaned = dict(form.cleaned_data)
            changes = {k: v for k, v in cleaned.items() if not (k == "occurred_at" and v is None)}
            try:
                services.update_request(sr, actor=request.user, request=request, **changes)
                messages.success(request, f"Saved changes to {sr.number}.")
                return redirect("incidents:detail", pk=sr.pk)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return render(request, "incidents/edit.html", {
            "title": f"Edit {sr.number}",
            "subtitle": f"{sr.title} · Currently {sr.get_status_display()}",
            "sr": sr,
            "form": form,
            "cancel_url": f"/app/incidents/{sr.pk}/",
            "crumbs": [("Incidents & requests", "/app/incidents/"), (sr.number, f"/app/incidents/{sr.pk}/"), ("Edit", None)],
        }, status=400)


class RequestDetailView(IncidentBase):
    required_permission = "incident.view_assigned"

    def dispatch(self, request, *args, **kwargs):
        if request.GET.get("duplicate_review") == "1":
            self.required_permission = "incident.create"
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, pk):
        m, org = request.membership, request.organization
        if request.GET.get("duplicate_review") == "1":
            sr = or404(selectors.get_request, m, org, pk, "incident.create")
            need(request, "incident.create", sr.site_id)
        else:
            sr = _req(request, pk)
        tab = request.GET.get("tab", "overview")
        if tab not in dict(TABS):
            tab = "overview"
        can = {k: rbac.has_permission(m, code, sr.site_id) for k, code in (
            ("update", "incident.update"), ("attach", "incident.attach"), ("downtime", "incident.downtime.manage"),
            ("view_site", "site.view"))}

        linked_work_order = None
        from django.apps import apps
        if apps.is_installed("apps.workorders"):
            from apps.workorders.models import WorkOrder

            linked_orders = WorkOrder.objects.filter(
                models.Q(source_request=sr) |
                models.Q(source_id=sr.pk) |
                models.Q(organization=org, source_reference=sr.number,
                         source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT))
            )
            live_linked_orders = linked_orders.exclude(status__in=(WorkOrder.Status.CANCELLED, WorkOrder.Status.CLOSED))
            if live_linked_orders.exists():
                can["create_work_order"] = False
                if (rbac.has_permission(m, "work_order.view", sr.site_id) or
                        rbac.has_permission(m, "work_order.view_assigned", sr.site_id)):
                    linked_work_order = live_linked_orders.first()
            else:
                can["create_work_order"] = (sr.status == "APPROVED" and
                                             rbac.has_permission(m, "work_order.create", sr.site_id))
                if (rbac.has_permission(m, "work_order.view", sr.site_id) or
                        rbac.has_permission(m, "work_order.view_assigned", sr.site_id)):
                    linked_work_order = linked_orders.first()

        can["triage"] = (sr.status == "NEW" and rbac.has_permission(m, "incident.triage", sr.site_id))
        can["approve"] = (sr.status == "TRIAGED" and rbac.has_permission(m, "incident.approve", sr.site_id))
        can["reject"] = (sr.status == "TRIAGED" and rbac.has_permission(m, "incident.approve", sr.site_id))
        if "create_work_order" not in can:
            can["create_work_order"] = (sr.status == "APPROVED" and
                                         rbac.has_permission(m, "work_order.create", sr.site_id) and
                                         not linked_work_order)
        transitions = [
            {"action": t.action, "label": t.label, "url": f"/app/incidents/{sr.pk}/transition/{t.action}/", "style": BUTTON_STYLES.get(
                t.action, "primary"), "reason": t.action in REASON_REQUIRED, "confirm": CONFIRMS.get(t.action)}
            for t in REQUEST_STATUS.available(sr.status)
            if t.action not in SYSTEM_ACTIONS and rbac.has_permission(m, ACTION_PERMISSIONS[t.action], sr.site_id)]

        # Diagnostic and guidance context
        user_roles = [mr.role.name for mr in m.membership_roles.select_related("role").all()]
        user_roles_str = ", ".join(user_roles) if user_roles else "No roles assigned"
        is_client = hasattr(m, "portal_account") and m.portal_account.is_enabled

        can["confirm"] = (sr.status == "RESOLVED" and rbac.has_permission(m, "incident.confirm", sr.site_id))
        can["reopen"] = (sr.status == "RESOLVED" and rbac.has_permission(m, "incident.confirm", sr.site_id))
        can["close"] = (sr.status == "CONFIRMED" and rbac.has_permission(m, "incident.close", sr.site_id))

        if sr.status == "NEW":
            next_action_title = "Triage Request"
            required_perm = "incident.triage"
            authorized_roles = "Maintenance Supervisor, Service Manager, Operations Manager, Organization Owner"
            is_authorized = can["triage"]
            stage_index = 1
        elif sr.status == "TRIAGED":
            next_action_title = "Approve or Reject Request"
            required_perm = "incident.approve"
            authorized_roles = "Maintenance Supervisor, Service Manager, Operations Manager, Organization Owner"
            is_authorized = can["approve"]
            stage_index = 2
        elif sr.status == "APPROVED":
            next_action_title = "Convert to Work Order"
            required_perm = "work_order.create"
            authorized_roles = "Maintenance Planner, Organization Owner"
            is_authorized = can["create_work_order"]
            stage_index = 3
        elif sr.status == "WORK_ORDER_CREATED":
            next_action_title = "Work Order Execution (Start Service)"
            required_perm = "work_order.start"
            authorized_roles = "Field Technician, Supervisor"
            is_authorized = True
            stage_index = 4
        elif sr.status == "IN_SERVICE":
            next_action_title = "Service in Progress (Complete Work Order)"
            required_perm = "work_order.complete"
            authorized_roles = "Field Technician, Supervisor"
            is_authorized = True
            stage_index = 5
        elif sr.status == "RESOLVED":
            next_action_title = "Confirm Resolution or Reopen"
            required_perm = "incident.confirm"
            authorized_roles = "Client Requester, Service Manager, Maintenance Supervisor, Organization Owner"
            is_authorized = can["confirm"]
            stage_index = 6
        elif sr.status == "CONFIRMED":
            next_action_title = "Close Service Request"
            required_perm = "incident.close"
            authorized_roles = "Maintenance Supervisor, Service Manager, Operations Manager, Organization Owner"
            is_authorized = can["close"]
            stage_index = 7
        elif sr.status == "CLOSED":
            next_action_title = "Request Closed"
            required_perm = None
            authorized_roles = "N/A"
            is_authorized = False
            stage_index = 8
        elif sr.status == "REJECTED":
            next_action_title = "Request Rejected"
            required_perm = None
            authorized_roles = "N/A"
            is_authorized = False
            stage_index = 3
        else:
            next_action_title = sr.get_status_display()
            required_perm = None
            authorized_roles = "Internal Staff"
            is_authorized = True
            stage_index = 5

        workflow_guide = {
            "next_action_title": next_action_title,
            "required_perm": required_perm,
            "authorized_roles": authorized_roles,
            "is_authorized": is_authorized,
            "user_roles_str": user_roles_str,
            "stage_index": stage_index,
            "is_client": is_client,
        }

        ctx = {"sr": sr, "tab": tab, "tabs": TABS, "can": can, "transitions": transitions,
               "downtime": selectors.downtime_for(org, sr), "editable": sr.status in ("NEW", "TRIAGED"),
               "linked_work_order": linked_work_order, "workflow_guide": workflow_guide}
        if apps.is_installed("apps.sla"):
            from apps.sla.selectors import tracking_for_request
            ctx["sla"] = tracking_for_request(m, org, sr)
        if tab == "evidence":
            ctx["evidence"] = selectors.evidence_for(org, sr)
            ctx["evidence_form"] = EvidenceForm()
        elif tab == "comments":
            ctx["comments"] = selectors.comments_for(m, org, sr)
            ctx["comment_form"] = ServiceRequestCommentForm(is_staff=not is_client)
        elif tab == "history":
            ctx["history"] = selectors.history_for(org, sr)
        elif tab == "overview":
            dt = ctx["downtime"]
            ctx["downtime_form"] = DowntimeForm(initial={"started_at": dt.started_at if dt else None,
                                                         "ended_at": dt.ended_at if dt else None})
        return render(request, "incidents/detail.html", ctx)


class _Post(IncidentBase):
    http_method_names = ["post"]
    required_permission = "incident.view"
    tab = "overview"

    def done(self, request, sr, ok: str | None = None):
        if ok:
            messages.success(request, ok)
        return redirect(f"/app/incidents/{sr.pk}/?tab={self.tab}")


class RequestTransitionView(_Post):
    def post(self, request, pk, action):
        sr = _req(request, pk)
        if hasattr(request.membership, "portal_account") and request.membership.portal_account.is_enabled:
            if action == "confirm":
                return redirect(f"/portal/requests/{sr.pk}/confirm/")
            if action == "reopen":
                return redirect(f"/portal/requests/{sr.pk}/reopen/")
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Clients cannot perform internal service request actions.")
        if action not in ACTION_PERMISSIONS:
            messages.error(request, "That step is performed by the work order, not by hand.")
            return self.done(request, sr)
        need(request, ACTION_PERMISSIONS[action], sr.site_id)
        try:
            services.transition(
                sr,
                action=action,
                reason=request.POST.get("reason") or request.POST.get("rejection_reason", ""),
                actor=request.user,
                request=request
            )
            return self.done(request, sr, f"Status updated: {sr.get_status_display()}.")
        except DomainError as exc:
            messages.error(request, exc.message)
            return self.done(request, sr)


class RequestWorkOrderView(_Post):
    """Create the M06 work order from an approved M05 request using the shared services."""

    def post(self, request, pk):
        sr = _req(request, pk)
        if hasattr(request.membership, "portal_account") and request.membership.portal_account.is_enabled:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Clients cannot convert service requests into work orders.")

        if sr.status != "APPROVED":
            messages.error(
                request,
                f"Cannot convert to work order: Request must be in APPROVED status (currently '{sr.get_status_display()}')."
            )
            return self.done(request, sr)

        need(request, "work_order.create", sr.site_id)

        from apps.workorders.models import WorkOrder
        existing_wo = WorkOrder.objects.filter(
            models.Q(source_request=sr) |
            models.Q(source_id=sr.pk) |
            models.Q(organization=request.organization, source_reference=sr.number,
                     source_type__in=(WorkOrder.SourceType.REQUEST, WorkOrder.SourceType.INCIDENT))
        ).exclude(status__in=(WorkOrder.Status.CANCELLED, WorkOrder.Status.CLOSED)).first()
        if existing_wo:
            messages.error(
                request,
                f"A work order ({existing_wo.order_number}) is already linked to this request. Duplicate conversion is prevented."
            )
            return self.done(request, sr)

        try:
            wo = services.create_work_order_for_request(
                sr, actor=request.user, membership=request.membership, request=request)
        except DomainError as exc:
            messages.error(request, exc.message)
            return self.done(request, sr)
        except ValidationError as exc:
            msg = exc.message_dict if hasattr(exc, "message_dict") else (exc.messages if hasattr(exc, "messages") else str(exc))
            messages.error(request, f"Validation failed: {msg}")
            return self.done(request, sr)
        except IntegrityError as exc:
            logger.exception("Database integrity error converting request %s to work order: %s", sr.number, exc)
            exc_str = str(exc)
            if "source_request" in exc_str.lower() or "source_id" in exc_str.lower():
                messages.error(request, "Could not create work order: a work order is already linked to this incident.")
            elif "uniq_wo_number_org" in exc_str.lower() or "order_number" in exc_str.lower():
                messages.error(request, "Could not create work order: sequence number conflict. Please try again.")
            else:
                messages.error(request, f"Could not create work order: {exc_str.splitlines()[0] if exc_str else 'database integrity constraint error'}")
            return self.done(request, sr)
        except Exception as exc:
            logger.exception("Unexpected error converting request %s to work order: %s", sr.number, exc)
            messages.error(request, f"An unexpected error occurred while converting to work order: {exc}")
            return self.done(request, sr)
        messages.success(request, f"Work order {wo.order_number} created from {sr.number}.")
        return redirect("workorders:detail", pk=wo.pk)


RequestCreateWorkOrderView = RequestWorkOrderView


class RequestDowntimeView(_Post):
    def post(self, request, pk):
        sr = _req(request, pk, "incident.downtime.manage")
        form = DowntimeForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a valid downtime start (and optional end).")
            return self.done(request, sr)
        try:
            services.set_downtime(sr, started_at=form.cleaned_data["started_at"],
                                  ended_at=form.cleaned_data["ended_at"], actor=request.user, request=request)
            return self.done(request, sr, "Downtime saved.")
        except DomainError as exc:
            messages.error(request, exc.message)
            return self.done(request, sr)


class RequestEvidenceView(_Post):
    tab = "evidence"

    def post(self, request, pk):
        sr = _req(request, pk, "incident.attach")
        form = EvidenceForm(request.POST, request.FILES)
        if not form.is_valid():
            messages.error(request, "Choose a file to upload.")
            return self.done(request, sr)
        try:
            services.add_evidence(sr, form.cleaned_data["file"], description=form.cleaned_data["description"],
                                  actor=request.user, request=request)
            return self.done(request, sr, "Evidence uploaded.")
        except DomainError as exc:
            messages.error(request, exc.message)
            return self.done(request, sr)



class RequestCommentCreateView(_Post):
    tab = "comments"
    required_permission = "incident.view_assigned"

    def post(self, request, pk):
        sr = _req(request, pk)
        m = request.membership
        body = (request.POST.get("body") or "").strip()
        is_internal = request.POST.get("is_internal") in ("true", "True", "1", "on")
        from apps.ui.utils import is_client_membership
        if is_client_membership(m):
            is_internal = False
        if not body:
            messages.error(request, "Comment message cannot be empty.")
            return self.done(request, sr)
        try:
            services.add_comment(
                sr,
                body=body,
                actor=request.user,
                membership=m,
                is_internal=is_internal,
                request=request,
            )
            return self.done(request, sr, "Internal note added." if is_internal else "Comment posted.")
        except DomainError as exc:
            messages.error(request, exc.message)
            return self.done(request, sr)


class RequestCommentDeleteView(_Post):
    tab = "comments"
    required_permission = "incident.view_assigned"

    def post(self, request, pk, comment_id):
        sr = _req(request, pk)
        try:
            services.delete_comment(
                request.organization,
                comment_id,
                actor=request.user,
                membership=request.membership,
                request=request,
            )
            return self.done(request, sr, "Comment deleted.")
        except DomainError as exc:
            messages.error(request, exc.message)
            return self.done(request, sr)
