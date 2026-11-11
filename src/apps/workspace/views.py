from __future__ import annotations

from apps.rbac import services as rbac

from decimal import Decimal
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views import View

from apps.core.exceptions import DomainError
from apps.ui.mixins import TenantPermissionMixin
from apps.ui.pagination import paginate_dashboard_queryset
from apps.workorders.models import WorkOrder

from . import selectors, services


def _get_job(request, pk):
    from apps.workorders import selectors as wo_selectors
    from apps.core.exceptions import NotFound
    try:
        return wo_selectors.get_work_order(request.membership, request.organization, pk)
    except NotFound:
        raise Http404("Work order not found.")


class JobExecutionDrawerView(TenantPermissionMixin, View):
    """Renders the technician execution drawer fragment or full page."""

    required_permission = "work_order.view_assigned"

    def get(self, request, pk):
        wo = _get_job(request, pk)
        try:
            summary = services.get_drawer_summary(wo, membership=request.membership)
        except DomainError as exc:
            messages.error(request, exc.message)
            return HttpResponse(f'<div class="alert alert-danger">{exc.message}</div>', status=403)

        return render(request, "workspace/_drawer.html", summary)


class JobStartView(TenantPermissionMixin, View):
    required_permission = "work_order.start"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        try:
            services.start_job(wo, membership=request.membership, actor=request.user, request=request)
            messages.success(request, f"Work order {wo.order_number} started.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)
        return redirect("workspace:job_detail", pk=wo.pk)


class JobPauseView(TenantPermissionMixin, View):
    required_permission = "work_order.hold"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        reason = request.POST.get("reason", "").strip()
        try:
            services.pause_job(wo, reason=reason, membership=request.membership, actor=request.user, request=request)
            messages.success(request, f"Work order {wo.order_number} paused.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)
        return redirect("workspace:job_detail", pk=wo.pk)


class JobResumeView(TenantPermissionMixin, View):
    required_permission = "work_order.start"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        try:
            services.resume_job(wo, membership=request.membership, actor=request.user, request=request)
            messages.success(request, f"Work order {wo.order_number} resumed.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)
        return redirect("workspace:job_detail", pk=wo.pk)


class JobTravelLogView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        hours = request.POST.get("duration_hours", "")
        distance_km = request.POST.get("distance_km") or None
        route_details = request.POST.get("route_details", "")
        notes = request.POST.get("notes", "")
        work_date = request.POST.get("work_date") or None

        if work_date:
            try:
                work_date = timezone.datetime.strptime(work_date, "%Y-%m-%d").date()
            except ValueError:
                work_date = None

        try:
            services.log_travel(
                wo,
                membership=request.membership,
                actor=request.user,
                duration_hours=hours,
                work_date=work_date,
                distance_km=distance_km,
                route_details=route_details,
                notes=notes,
                record_labor_entry=True,
                request=request,
            )
            messages.success(request, "Travel logged successfully.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)
        return redirect("workspace:job_detail", pk=wo.pk)


class MyJobsView(TenantPermissionMixin, View):
    """Cockpit list view for assigned jobs."""

    required_permission = "work_order.view_assigned"

    def get(self, request):
        status_filter = request.GET.get("status", "active")
        search = request.GET.get("q", "").strip()

        jobs_qs = selectors.my_jobs(request.membership, status_filter=status_filter, search=search)
        page_obj, preserved_params = paginate_dashboard_queryset(request, jobs_qs, page_param="page", per_page=12)

        if request.headers.get("HX-Request"):
            # Partial HTMX swap only updates the jobs list table/grid; skip full counts & capacity summary
            active_count = upcoming_count = completed_count = all_count = 0
            capacity = None
        else:
            from django.db.models import Count, Q
            counts = (
                WorkOrder.objects.for_organization(request.organization)
                .filter(assigned_to=request.membership)
                .aggregate(
                    active=Count(
                        "id",
                        filter=Q(
                            status__in=[
                                WorkOrder.Status.IN_PROGRESS,
                                WorkOrder.Status.ON_HOLD,
                                WorkOrder.Status.DISPATCHED,
                            ]
                        ),
                    ),
                    upcoming=Count(
                        "id",
                        filter=Q(
                            status__in=[
                                WorkOrder.Status.ASSIGNED,
                                WorkOrder.Status.PLANNED,
                            ]
                        ),
                    ),
                    completed=Count(
                        "id",
                        filter=Q(
                            status__in=[
                                WorkOrder.Status.COMPLETED,
                                WorkOrder.Status.SUPERVISOR_REVIEW,
                                WorkOrder.Status.CLOSED,
                            ]
                        ),
                    ),
                    total=Count("id"),
                )
            )
            active_count = counts["active"]
            upcoming_count = counts["upcoming"]
            completed_count = counts["completed"]
            all_count = counts["total"]
            capacity = selectors.daily_capacity_summary(request.membership)

        ctx = {
            "jobs": page_obj.object_list,
            "page_obj": page_obj,
            "preserved_params": preserved_params,
            "status_filter": status_filter,
            "search": search,
            "active_count": active_count,
            "upcoming_count": upcoming_count,
            "completed_count": completed_count,
            "all_count": all_count,
            "capacity": capacity,
        }

        if request.headers.get("HX-Request"):
            return render(request, "workspace/_jobs_list_partial.html", ctx)
        return render(request, "workspace/my_jobs.html", ctx)


class JobDetailView(TenantPermissionMixin, View):
    """Focused technician execution detail screen."""

    required_permission = "work_order.view_assigned"

    def get(self, request, pk):
        try:
            context = selectors.get_job_detail(request.membership, pk)
        except DomainError as exc:
            messages.error(request, exc.message)
            return redirect("workspace:my_jobs")

        return render(request, "workspace/job_detail.html", context)


class JobCompleteView(TenantPermissionMixin, View):
    required_permission = "work_order.complete"

    def get(self, request, pk):
        wo = _get_job(request, pk)
        try:
            context = selectors.get_job_completion_context(request.membership, pk)
        except DomainError as exc:
            messages.error(request, exc.message)
            return redirect("workspace:job_detail", pk=pk)

        return render(request, "workspace/job_complete.html", context)

    def post(self, request, pk):
        wo = _get_job(request, pk)
        resolution_notes = request.POST.get("resolution_notes", "").strip()
        signer_name = request.POST.get("signer_name", "").strip()
        signer_title = request.POST.get("signer_title", "").strip()
        signature_data = request.POST.get("signature_data", "").strip()
        customer_notes = request.POST.get("customer_notes", "").strip()
        technician_notes = request.POST.get("technician_notes", "").strip()
        final_photo = request.FILES.get("final_photo") or request.FILES.get("evidence_file")

        try:
            if signer_name or signature_data or request.FILES.get("signature_file"):
                services.complete_job_with_signoff(
                    wo,
                    resolution_notes=resolution_notes,
                    signer_name=signer_name,
                    signer_title=signer_title,
                    signature_data_base64=signature_data or None,
                    signature_file=request.FILES.get("signature_file"),
                    final_photo_file=final_photo,
                    customer_notes=customer_notes,
                    technician_notes=technician_notes,
                    membership=request.membership,
                    actor=request.user,
                    request=request,
                )
                messages.success(request, f"Work order {wo.order_number} marked as completed and customer sign-off recorded.")
            else:
                services.complete_job(
                    wo,
                    resolution_notes=resolution_notes,
                    membership=request.membership,
                    actor=request.user,
                    request=request,
                )
                messages.success(request, f"Work order {wo.order_number} marked as completed.")
        except DomainError as exc:
            messages.error(request, exc.message)
            if not request.headers.get("HX-Request") and request.POST.get("is_completion_screen"):
                context = selectors.get_job_completion_context(request.membership, pk)
                context["initial_resolution_notes"] = resolution_notes
                context["initial_signer_name"] = signer_name
                context["initial_signer_title"] = signer_title
                context["initial_customer_notes"] = customer_notes
                return render(request, "workspace/job_complete.html", context, status=422)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)
        return redirect("workspace:job_detail", pk=wo.pk)


class JobWorkNoteView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        note_body = request.POST.get("body", "").strip()
        try:
            services.record_work_note(
                wo,
                note=note_body,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, "Work note recorded.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            notes = selectors.work_notes_for(wo)
            return render(request, "workspace/_notes_partial.html", {"notes": notes, "work_order": wo})
        return redirect("workspace:job_detail", pk=wo.pk)


class JobLaborView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        hours = request.POST.get("hours", "")
        description = request.POST.get("description", "")
        work_date = request.POST.get("work_date") or None
        if work_date:
            try:
                work_date = timezone.datetime.strptime(work_date, "%Y-%m-%d").date()
            except ValueError:
                work_date = None

        try:
            services.record_job_labor(
                wo,
                hours=hours,
                description=description,
                work_date=work_date,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, "Labor recorded successfully.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)
        return redirect("workspace:job_detail", pk=wo.pk)


class JobMaterialView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        item_name = request.POST.get("item_name", "").strip()
        quantity = request.POST.get("quantity", "").strip()
        unit = request.POST.get("unit", "ea").strip()
        notes = request.POST.get("notes", "").strip()

        try:
            services.record_job_material(
                wo,
                item_name=item_name,
                quantity=quantity,
                unit=unit,
                notes=notes,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Material '{item_name}' ({quantity} {unit}) recorded.")
        except DomainError as exc:
            messages.error(request, exc.message)

        return redirect("workspace:job_detail", pk=wo.pk)


class JobEvidenceUploadView(TenantPermissionMixin, View):
    required_permission = "work_order.attach"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        uploaded = request.FILES.get("evidence_file") or request.FILES.get("file")
        description = request.POST.get("description", "").strip()

        try:
            services.upload_job_evidence(
                wo,
                file=uploaded,
                description=description,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, "Completion evidence uploaded successfully.")
        except DomainError as exc:
            messages.error(request, exc.message)

        return redirect("workspace:job_detail", pk=wo.pk)


class JobPartConsumeView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk, line_pk=None):
        wo = _get_job(request, pk)
        if line_pk:
            from apps.inventory.models import WorkOrderPart
            if not WorkOrderPart.objects.filter(work_order=wo, pk=line_pk).exists():
                raise Http404("Part requirement line not found on this work order.")
        part_line_id = str(line_pk) if line_pk else request.POST.get("part_line_id", "").strip()
        quantity = request.POST.get("quantity", "").strip()

        try:
            line = services.consume_job_part(
                wo,
                part_line_id=part_line_id,
                quantity=quantity,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Consumed {quantity} {line.part.unit} of {line.part.name} ({line.part.part_number}).")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)

        return redirect("workspace:job_detail", pk=wo.pk)


class JobPartReturnView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk, line_pk=None):
        wo = _get_job(request, pk)
        if line_pk:
            from apps.inventory.models import WorkOrderPart
            if not WorkOrderPart.objects.filter(work_order=wo, pk=line_pk).exists():
                raise Http404("Part requirement line not found on this work order.")
        part_line_id = str(line_pk) if line_pk else request.POST.get("part_line_id", "").strip()
        quantity = request.POST.get("quantity", "").strip()
        reason = request.POST.get("reason", "").strip()

        try:
            line = services.return_job_part(
                wo,
                part_line_id=part_line_id,
                quantity=quantity,
                reason=reason,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Returned {quantity} {line.part.unit} of {line.part.name} ({line.part.part_number}) to warehouse.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)

        return redirect("workspace:job_detail", pk=wo.pk)


class JobMeterReadingView(TenantPermissionMixin, View):
    required_permission = "work_order.record"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        meter_id = request.POST.get("meter_id", "").strip()
        value = request.POST.get("value", "").strip()
        notes = request.POST.get("notes", "").strip()

        try:
            reading = services.record_job_meter_reading(
                wo,
                meter_id=meter_id,
                value=value,
                notes=notes,
                membership=request.membership,
                actor=request.user,
                request=request,
            )
            messages.success(request, f"Meter reading recorded: {reading.value} {reading.meter.unit} for {reading.meter.name}.")
        except DomainError as exc:
            messages.error(request, exc.message)

        if request.headers.get("HX-Request"):
            wo.refresh_from_db()
            summary = services.get_drawer_summary(wo, membership=request.membership)
            return render(request, "workspace/_drawer.html", summary)

        return redirect("workspace:job_detail", pk=wo.pk)


class JobReportDefectView(TenantPermissionMixin, View):
    """Technician reports an auxiliary defect or incident discovered on-site."""

    required_permission = "work_order.view_assigned"

    def post(self, request, pk):
        wo = _get_job(request, pk)
        title = request.POST.get("title", "").strip()
        asset_id = request.POST.get("asset_id", "").strip()
        description = request.POST.get("description", "").strip()
        kind = request.POST.get("kind", "INCIDENT").strip()
        severity = request.POST.get("severity", "MEDIUM").strip()
        service_impact = request.POST.get("service_impact", "NONE").strip()
        failure_category = request.POST.get("failure_category", "").strip()
        override_dup = request.POST.get("override_duplicate") in ("true", "1", "on")
        override_reason = request.POST.get("override_reason", "").strip()

        target_asset = None
        if asset_id:
            from apps.assets.models import Asset
            target_asset = Asset.objects.for_organization(request.organization).filter(pk=asset_id).first()

        try:
            sr = services.report_auxiliary_defect(
                wo,
                title=title,
                membership=request.membership,
                actor=request.user,
                asset=target_asset,
                description=description,
                kind=kind,
                severity=severity,
                service_impact=service_impact,
                failure_category=failure_category,
                override_duplicate=override_dup,
                override_reason=override_reason,
                request=request,
            )
            messages.success(request, f"Auxiliary defect {sr.number} reported successfully.")
        except DomainError as exc:
            messages.error(request, exc.message)

        return redirect("workspace:job_detail", pk=wo.pk)




# ==============================================================================
# Technician Profiles & Shifts Views (PRD Section 4.2, D-054)
# ==============================================================================

from apps.tenancy.models import Membership
from .forms import ShiftForm, TechnicianProfileForm
from .models import Shift, TechnicianProfile


class ShiftListView(TenantPermissionMixin, View):
    required_permission = "user.view"

    def get(self, request):
        shifts = selectors.shifts_for_org(request.organization)
        can_manage = (
            rbac.is_owner(request.membership)
            or rbac.has_permission_anywhere(request.membership, "user.update")
            or rbac.has_permission_anywhere(request.membership, "organization.update")
            or rbac.has_permission_anywhere(request.membership, "work_order.assign")
        )
        return render(
            request,
            "workspace/shifts_list.html",
            {"shifts": shifts, "can_manage": can_manage},
        )


class ShiftCreateView(TenantPermissionMixin, View):
    required_permission = "user.update"

    def get(self, request):
        form = ShiftForm(org=request.organization)
        return render(request, "workspace/shift_form.html", {"form": form, "title": "Create New Shift"})

    def post(self, request):
        form = ShiftForm(request.POST, org=request.organization)
        if form.is_valid():
            shift = form.save(commit=False)
            shift.organization = request.organization
            shift.save()
            messages.success(request, f"Shift '{shift.name}' created.")
            return redirect("workspace:shift_list")
        return render(request, "workspace/shift_form.html", {"form": form, "title": "Create New Shift"})


class ShiftEditView(TenantPermissionMixin, View):
    required_permission = "user.update"

    def get(self, request, pk):
        shift = selectors.get_shift(request.organization, pk)
        if not shift:
            raise Http404("Shift not found.")
        form = ShiftForm(instance=shift, org=request.organization)
        return render(request, "workspace/shift_form.html", {"form": form, "shift": shift, "title": f"Edit Shift: {shift.name}"})

    def post(self, request, pk):
        shift = selectors.get_shift(request.organization, pk)
        if not shift:
            raise Http404("Shift not found.")
        form = ShiftForm(request.POST, instance=shift, org=request.organization)
        if form.is_valid():
            form.save()
            messages.success(request, f"Shift '{shift.name}' updated.")
            return redirect("workspace:shift_list")
        return render(request, "workspace/shift_form.html", {"form": form, "shift": shift, "title": f"Edit Shift: {shift.name}"})


class TechnicianListView(TenantPermissionMixin, View):
    required_permission = "user.view"

    def get(self, request):
        site_filter = request.GET.get("site")
        status_filter = request.GET.get("status")

        # Find all members with technician role in this org
        members = Membership.objects.filter(
            organization=request.organization,
            status=Membership.Status.ACTIVE,
            membership_roles__role__system_key__in=["technician", "field_technician"],
        ).select_related("user", "technician_profile__shift", "technician_profile__primary_site").distinct()

        # Build display data
        from apps.workorders.assignment_rules import ACTIVE_ASSIGNMENT_STATES
        tech_list = []
        for m in members:
            profile = getattr(m, "technician_profile", None)
            if not profile:
                profile, _ = services.get_or_create_technician_profile(m)
            
            if status_filter and profile.availability_status != status_filter:
                continue
            if site_filter and profile.primary_site_id and str(profile.primary_site_id) != site_filter:
                continue

            active_jobs = WorkOrder.objects.filter(
                organization=request.organization,
                assigned_to=m,
                status__in=ACTIVE_ASSIGNMENT_STATES,
            ).count()

            tech_list.append({
                "membership": m,
                "profile": profile,
                "active_jobs": active_jobs,
            })

        sites = request.organization.sites.order_by("name") if hasattr(request.organization, "sites") else []
        can_manage = (
            rbac.is_owner(request.membership)
            or rbac.has_permission_anywhere(request.membership, "user.update")
            or rbac.has_permission_anywhere(request.membership, "work_order.assign")
        )
        return render(
            request,
            "workspace/technicians_list.html",
            {
                "technicians": tech_list,
                "statuses": TechnicianProfile.AvailabilityStatus.choices,
                "sites": sites,
                "can_manage": can_manage,
                "selected_status": status_filter,
                "selected_site": site_filter,
            },
        )


class TechnicianDetailView(TenantPermissionMixin, View):
    required_permission = "user.view"

    def get(self, request, pk):
        membership = Membership.objects.filter(
            organization=request.organization,
            pk=pk,
        ).select_related("user").first()
        if not membership:
            raise Http404("Technician not found.")

        profile, _ = services.get_or_create_technician_profile(membership)
        form = TechnicianProfileForm(instance=profile, org=request.organization)

        from apps.workorders.assignment_rules import ACTIVE_ASSIGNMENT_STATES
        active_jobs = WorkOrder.objects.filter(
            organization=request.organization,
            assigned_to=membership,
            status__in=ACTIVE_ASSIGNMENT_STATES,
        ).order_by("-planned_start")

        can_edit = (
            rbac.is_owner(request.membership)
            or rbac.has_permission_anywhere(request.membership, "user.update")
            or rbac.has_permission_anywhere(request.membership, "work_order.assign")
        )
        return render(
            request,
            "workspace/technician_detail.html",
            {
                "member": membership,
                "profile": profile,
                "form": form,
                "active_jobs": active_jobs,
                "can_edit": can_edit,
            },
        )

    def post(self, request, pk):
        membership = Membership.objects.filter(
            organization=request.organization,
            pk=pk,
        ).select_related("user").first()
        if not membership:
            raise Http404("Technician not found.")

        can_edit = (
            rbac.is_owner(request.membership)
            or rbac.has_permission_anywhere(request.membership, "user.update")
            or rbac.has_permission_anywhere(request.membership, "work_order.assign")
        )
        if not can_edit:
            raise Http404("Forbidden")

        profile, _ = services.get_or_create_technician_profile(membership)
        form = TechnicianProfileForm(request.POST, instance=profile, org=request.organization)
        if form.is_valid():
            form.save()
            messages.success(request, f"Profile for {membership.user.full_name or membership.user.email} updated.")
            return redirect("workspace:technician_detail", pk=pk)

        from apps.workorders.assignment_rules import ACTIVE_ASSIGNMENT_STATES
        active_jobs = WorkOrder.objects.filter(
            organization=request.organization,
            assigned_to=membership,
            status__in=ACTIVE_ASSIGNMENT_STATES,
        )
        return render(
            request,
            "workspace/technician_detail.html",
            {
                "member": membership,
                "profile": profile,
                "form": form,
                "active_jobs": active_jobs,
                "can_edit": can_edit,
            },
        )


class MyProfileView(TenantPermissionMixin, View):
    required_permission = "work_order.view_assigned"

    def get(self, request):
        profile, _ = services.get_or_create_technician_profile(request.membership)
        from apps.workorders.assignment_rules import ACTIVE_ASSIGNMENT_STATES
        active_jobs = WorkOrder.objects.filter(
            organization=request.organization,
            assigned_to=request.membership,
            status__in=ACTIVE_ASSIGNMENT_STATES,
        )
        return render(
            request,
            "workspace/my_profile.html",
            {
                "profile": profile,
                "active_jobs": active_jobs,
                "statuses": TechnicianProfile.AvailabilityStatus.choices,
            },
        )

    def post(self, request):
        profile, _ = services.get_or_create_technician_profile(request.membership)
        new_status = request.POST.get("availability_status")
        if new_status in [TechnicianProfile.AvailabilityStatus.AVAILABLE, TechnicianProfile.AvailabilityStatus.OFF_DUTY, TechnicianProfile.AvailabilityStatus.ON_LEAVE]:
            services.set_technician_availability(request.membership, new_status, actor=request.user, request=request)
            messages.success(request, f"Your availability has been set to {new_status}.")
        return redirect("workspace:my_profile")
