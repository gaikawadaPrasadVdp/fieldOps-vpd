from __future__ import annotations

from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.assets import selectors as asset_selectors
from apps.assets.workflow import TERMINAL_STATES
from apps.core.exceptions import DomainError, NotFound, PermissionDenied
from apps.rbac import services as rbac
from apps.sites.views import need, or404
from apps.ui.mixins import TenantPermissionMixin

from . import selectors, services


class LabelBase(TenantPermissionMixin, View):
    pass


class LabelPanelView(LabelBase):
    """HTMX partial: renders the Labels tab panel inside Asset Detail."""

    required_permission = "asset.view"

    def get(self, request, pk):
        asset = or404(asset_selectors.get_asset, request.membership, request.organization, pk)
        need(request, "asset.view", asset.site_id)
        m = request.membership
        kinds = [("QR", "QR Code"), ("BARCODE", "Barcode")]
        active = selectors.active_for_asset(request.organization, asset)
        can_generate = rbac.has_permission(m, "qr.generate", asset.site_id) or rbac.has_permission(
            m, "asset.update", asset.site_id
        )
        ctx = {
            "asset": asset,
            "kinds": kinds,
            "active": active,
            "can_generate": can_generate,
            "terminal": asset.status in TERMINAL_STATES,
            "history": selectors.history_for_asset(request.organization, asset),
            "scans": selectors.scans_for_asset(request.organization, asset),
        }
        return render(request, "identification/_panel.html", ctx)


class LabelImageView(LabelBase):
    """Returns the SVG or PNG binary/image data for a label."""

    required_permission = "asset.view"

    def get(self, request, pk, kind, fmt):
        asset = or404(asset_selectors.get_asset, request.membership, request.organization, pk)
        need(request, "asset.view", asset.site_id)
        kind = kind.upper()
        fmt = fmt.lower()
        active = selectors.active_for_asset(request.organization, asset)
        ident = active.get(kind)
        if not ident:
            raise Http404(f"No active {kind} label for this asset.")

        if kind == "QR" and fmt == "png":
            content = services.render_qr_png(ident.token, request)
            resp = HttpResponse(content, content_type="image/png")
        elif kind == "QR" and fmt == "svg":
            content = services.render_qr_svg(ident.token, request)
            resp = HttpResponse(content, content_type="image/svg+xml")
        elif kind == "BARCODE" and fmt == "svg":
            content = services.render_barcode_svg(ident.token)
            resp = HttpResponse(content, content_type="image/svg+xml")
        else:
            raise Http404("Unsupported format.")

        if request.GET.get("download"):
            resp["Content-Disposition"] = f'attachment; filename="{asset.asset_tag}_{kind.lower()}.{fmt}"'
        return resp


class PanelActionView(LabelBase):
    """State-changing actions from the Labels tab (generate, replace, revoke)."""

    required_permission = "asset.update"
    http_method_names = ["post"]

    def post(self, request, pk, action):
        asset = or404(asset_selectors.get_asset, request.membership, request.organization, pk)
        need(request, "asset.update", asset.site_id)
        try:
            if action == "generate":
                kind = request.POST.get("kind", "QR").upper()
                services.generate_identifier(asset, kind=kind, actor=request.user, request=request)
                messages.success(request, f"{kind} label generated.")
            elif action == "replace":
                ident_pk = request.POST.get("identifier")
                ident = or404(selectors.get_identifier, request.organization, ident_pk)
                services.replace_identifier(
                    ident, reason=request.POST.get("reason", ""), actor=request.user, request=request
                )
                messages.success(request, f"{ident.kind} label replaced.")
            elif action == "revoke":
                ident_pk = request.POST.get("identifier")
                ident = or404(selectors.get_identifier, request.organization, ident_pk)
                services.revoke_identifier(
                    ident, reason=request.POST.get("reason", ""), actor=request.user, request=request
                )
                messages.success(request, f"{ident.kind} label revoked.")
            else:
                messages.error(request, f"Unknown action: {action}")
        except DomainError as exc:
            messages.error(request, exc.message)
        return redirect(f"/app/assets/{asset.pk}/?tab=labels")


class LabelPrintView(LabelBase):
    """Printable sheet for the asset's QR and barcode labels."""

    required_permission = "asset.view"

    def get(self, request, pk):
        asset = or404(asset_selectors.get_asset, request.membership, request.organization, pk)
        need(request, "asset.view", asset.site_id)
        active = selectors.active_for_asset(request.organization, asset)
        qr_ident = active.get("QR")
        bc_ident = active.get("BARCODE")
        qr_svg = services.render_qr_svg(qr_ident.token, request) if qr_ident else ""
        bc_svg = services.render_barcode_svg(bc_ident.token) if bc_ident else ""
        return render(
            request,
            "identification/label.html",
            {
                "asset": asset,
                "qr": qr_ident,
                "barcode": bc_ident,
                "qr_svg": qr_svg,
                "barcode_svg": bc_svg,
            },
        )


def _handle_scan_incident_creation(request, asset, form):
    data = form.cleaned_data
    from apps.incidents import services as incident_services
    sr = incident_services.create_request(
        request.organization,
        asset=asset,
        reporter=request.membership,
        title=data["title"],
        description=data.get("description", ""),
        severity=data["severity"],
        service_impact=data["service_impact"],
        failure_category=data.get("failure_category", ""),
        override_duplicate=data.get("override_duplicate", False),
        override_reason=data.get("override_reason", ""),
        actor=request.user,
        request=request,
    )
    attachment = request.FILES.get("attachment")
    if attachment:
        incident_services.add_evidence(
            sr,
            attachment,
            description=f"Evidence uploaded via QR scan report ({asset.asset_tag})",
            actor=request.user,
            request=request,
        )
    messages.success(request, f"Incident {sr.number} reported successfully for {asset.name}.")
    if hasattr(request.membership, "portal_account") and request.membership.portal_account.is_enabled:
        return redirect("portal:request_detail", pk=str(sr.pk))
    return redirect("incidents:detail", pk=sr.pk)


class ScanView(LabelBase):
    """Camera and manual scan interface with direct Scan-to-Report mode."""

    required_permission = "asset.view"

    def get(self, request):
        action = request.GET.get("action", "")
        return render(request, "identification/scan.html", {
            "is_report_mode": action == "report",
        })

    def post(self, request):
        token = request.POST.get("token", "").strip()
        work_order_id = request.POST.get("work_order") or request.GET.get("work_order")
        action = request.POST.get("action") or request.GET.get("action")
        if not token:
            messages.error(request, "Please enter a code or link.")
            return render(request, "identification/scan.html", {
                "is_report_mode": action == "report",
            })
        from django.urls import reverse
        if action == "report":
            url = reverse("identification:resolve_report", kwargs={"token": token})
        else:
            url = reverse("identification:resolve", kwargs={"token": token})
            if work_order_id:
                url += f"?work_order={work_order_id}"
        return redirect(url)


class ResolveView(LabelBase):
    """Resolves an opaque token to an asset within the user's organization and permissions."""

    required_permission = "asset.view"

    def get(self, request, token):
        try:
            ident, asset, is_active = services.resolve_token(
                request.membership, token, actor=request.user, request=request
            )
        except (NotFound, PermissionDenied, DomainError):
            return render(request, "identification/not_found.html", {"throttled": False}, status=404)

        action = request.GET.get("action")
        if action == "report" or request.GET.get("report") == "1":
            from django.urls import reverse
            return redirect(reverse("identification:resolve_report", kwargs={"token": token}))

        work_order_id = request.GET.get("work_order")
        if work_order_id:
            from apps.workorders.models import WorkOrder
            wo = WorkOrder.objects.filter(
                organization=request.organization, pk=work_order_id
            ).select_related("asset").first()
            if wo:
                if wo.asset_id and wo.asset_id == asset.pk:
                    messages.success(request, f"Asset Verified: Machine {asset.name} ({asset.asset_tag}) matches this work order.")
                elif wo.asset_id:
                    messages.error(request, f"Mismatch Warning! Scanned asset {asset.asset_tag} ({asset.name}) does NOT match assigned work order asset ({wo.asset.asset_tag}).")
                else:
                    messages.info(request, f"Scanned asset {asset.name} ({asset.asset_tag}) for work order {wo.order_number}.")
                return redirect("workspace:job_detail", pk=wo.pk)

        if is_active and request.GET.get("preview") != "1":
            from apps.workorders.models import WorkOrder
            my_wo = WorkOrder.objects.filter(
                organization=request.organization,
                asset=asset,
                assigned_to=request.membership,
                status__in=[WorkOrder.Status.IN_PROGRESS, WorkOrder.Status.DISPATCHED, WorkOrder.Status.PLANNED],
            ).order_by("-started_at", "-created_at").first()
            if my_wo:
                messages.info(request, f"Found assigned work order {my_wo.order_number} for {asset.name}.")
                return redirect("workspace:job_detail", pk=my_wo.pk)
            return redirect("assets:detail", pk=asset.pk)

        from apps.incidents import selectors as incident_selectors
        can_report = (
            is_active
            and asset.status not in TERMINAL_STATES
            and (
                rbac.has_permission(request.membership, "incident.create", asset.site_id)
                or incident_selectors.is_owned_asset_reporter(request.membership)
            )
        )
        from .forms import ScanIncidentReportForm
        return render(
            request,
            "identification/resolved.html",
            {
                "asset": asset,
                "identifier": ident,
                "revoked": not is_active,
                "res": {"asset_inactive": asset.status in TERMINAL_STATES},
                "can_report": can_report,
                "form": ScanIncidentReportForm() if can_report else None,
            },
        )

    def post(self, request, token):
        try:
            ident, asset, is_active = services.resolve_token(
                request.membership, token, actor=request.user, request=request
            )
        except (NotFound, PermissionDenied, DomainError):
            return render(request, "identification/not_found.html", {"throttled": False}, status=404)

        if not is_active:
            messages.error(request, "This asset label was revoked or replaced.")
            return redirect("identification:resolve", token=token)

        if asset.status in TERMINAL_STATES:
            messages.error(request, f"Cannot report an incident for a {asset.status.lower()} asset.")
            return redirect("identification:resolve", token=token)

        from apps.incidents import selectors as incident_selectors
        can_report = (
            rbac.has_permission(request.membership, "incident.create", asset.site_id)
            or incident_selectors.is_owned_asset_reporter(request.membership)
        )
        if not can_report:
            messages.error(request, "You do not have permission to report incidents for this asset.")
            return render(
                request,
                "identification/resolved.html",
                {"asset": asset, "identifier": ident, "can_report": False},
                status=403,
            )

        from .forms import ScanIncidentReportForm
        form = ScanIncidentReportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                "identification/resolved.html",
                {
                    "asset": asset,
                    "identifier": ident,
                    "revoked": False,
                    "res": {"asset_inactive": False},
                    "can_report": True,
                    "form": form,
                },
                status=400,
            )

        try:
            return _handle_scan_incident_creation(request, asset, form)
        except DomainError as exc:
            form.add_error(None, exc.message)
            return render(
                request,
                "identification/resolved.html",
                {
                    "asset": asset,
                    "identifier": ident,
                    "revoked": False,
                    "res": {"asset_inactive": False},
                    "can_report": True,
                    "form": form,
                },
                status=400,
            )


class ResolveReportView(LabelBase):
    """Direct QR scan-to-incident reporting page."""

    required_permission = "asset.view"

    def _resolve(self, request, token):
        try:
            return services.resolve_token(
                request.membership, token, actor=request.user, request=request
            )
        except (NotFound, PermissionDenied, DomainError):
            return None, None, False

    def get(self, request, token):
        ident, asset, is_active = self._resolve(request, token)
        if ident is None or asset is None:
            return render(request, "identification/not_found.html", {"throttled": False}, status=404)

        if not is_active:
            messages.error(request, "This asset label was revoked or replaced. Reporting an incident requires an active label.")
            return render(
                request,
                "identification/resolved.html",
                {
                    "asset": asset,
                    "identifier": ident,
                    "revoked": True,
                    "res": {"asset_inactive": asset.status in TERMINAL_STATES},
                    "can_report": False,
                },
                status=400,
            )

        if asset.status in TERMINAL_STATES:
            messages.error(request, f"Cannot report an incident for a {asset.status.lower()} asset.")
            return render(
                request,
                "identification/resolved.html",
                {
                    "asset": asset,
                    "identifier": ident,
                    "revoked": False,
                    "res": {"asset_inactive": True},
                    "can_report": False,
                },
                status=400,
            )

        from apps.incidents import selectors as incident_selectors
        can_report = (
            rbac.has_permission(request.membership, "incident.create", asset.site_id)
            or incident_selectors.is_owned_asset_reporter(request.membership)
        )
        if not can_report:
            messages.error(request, "You do not have permission to report incidents for this asset.")
            return render(
                request,
                "identification/resolved.html",
                {
                    "asset": asset,
                    "identifier": ident,
                    "revoked": False,
                    "res": {"asset_inactive": False},
                    "can_report": False,
                },
                status=403,
            )

        from .forms import ScanIncidentReportForm
        return render(
            request,
            "identification/scan_report.html",
            {
                "asset": asset,
                "identifier": ident,
                "form": ScanIncidentReportForm(),
                "can_report": True,
            },
        )

    def post(self, request, token):
        ident, asset, is_active = self._resolve(request, token)
        if ident is None or asset is None:
            return render(request, "identification/not_found.html", {"throttled": False}, status=404)

        if not is_active:
            messages.error(request, "This asset label was revoked or replaced.")
            return redirect("identification:resolve", token=token)

        if asset.status in TERMINAL_STATES:
            messages.error(request, f"Cannot report an incident for a {asset.status.lower()} asset.")
            return redirect("identification:resolve", token=token)

        from apps.incidents import selectors as incident_selectors
        can_report = (
            rbac.has_permission(request.membership, "incident.create", asset.site_id)
            or incident_selectors.is_owned_asset_reporter(request.membership)
        )
        if not can_report:
            messages.error(request, "You do not have permission to report incidents for this asset.")
            return render(
                request,
                "identification/resolved.html",
                {"asset": asset, "identifier": ident, "can_report": False},
                status=403,
            )

        from .forms import ScanIncidentReportForm
        form = ScanIncidentReportForm(request.POST, request.FILES)
        if not form.is_valid():
            return render(
                request,
                "identification/scan_report.html",
                {"asset": asset, "identifier": ident, "form": form, "can_report": True},
                status=400,
            )

        try:
            return _handle_scan_incident_creation(request, asset, form)
        except DomainError as exc:
            form.add_error(None, exc.message)
            return render(
                request,
                "identification/scan_report.html",
                {"asset": asset, "identifier": ident, "form": form, "can_report": True},
                status=400,
            )
