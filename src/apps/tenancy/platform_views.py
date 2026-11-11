from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, ValidationFailed

from .forms import PlatformOrganizationCreateForm, PlatformOrganizationFilterForm
from apps.ui.pagination import paginate_dashboard_queryset
from .models import Organization
from . import services


def platform_admin_required(view):
    @login_required
    def wrapped(request, *args, **kwargs):
        if not (getattr(request.user, "is_platform_admin", False) or request.user.is_superuser):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


@platform_admin_required
def organizations(request):
    try:
        services.process_due_scheduled_deletions()
    except Exception as exc:
        import logging
        logging.getLogger("django.request").warning("Background scheduled deletion check failed: %s", exc)
    filter_form = PlatformOrganizationFilterForm(request.GET)
    filter_form.is_valid()
    q = filter_form.cleaned_data.get("q", "").strip() if filter_form.is_valid() else ""
    status_filter = filter_form.cleaned_data.get("status", "") if filter_form.is_valid() else ""

    qs = Organization.objects.order_by("name")
    if q:
        qs = qs.filter(name__icontains=q)
    if status_filter in dict(Organization.Status.choices):
        qs = qs.filter(status=status_filter)

    page, preserved_params = paginate_dashboard_queryset(request, qs, page_param="page", per_page=25)
    return render(
        request,
        "tenancy/platform_organizations.html",
        {
            "page": page,
            "q": q,
            "status_filter": status_filter,
            "filter_form": filter_form,
            "preserved_params": preserved_params,
            "total_count": Organization.objects.count(),
            "active_count": Organization.objects.filter(status=Organization.Status.ACTIVE).count(),
            "suspended_count": Organization.objects.filter(status=Organization.Status.SUSPENDED).count(),
        },
    )


@platform_admin_required
def organization_create(request):
    if request.method == "POST":
        form = PlatformOrganizationCreateForm(request.POST)
        if form.is_valid():
            try:
                owner_pwd = form.cleaned_data.get("owner_password") or "FieldOps@2026!"
                org, owner_m = services.create_organization(
                    name=form.cleaned_data["name"],
                    slug=form.cleaned_data.get("slug") or None,
                    owner_name=form.cleaned_data["owner_name"],
                    owner_email=form.cleaned_data["owner_email"],
                    owner_password=owner_pwd,
                    timezone_name=form.cleaned_data["timezone"],
                    country=form.cleaned_data["country"],
                    actor=request.user,
                    request=request,
                )
                messages.success(
                    request,
                    f"Organization '{org.name}' created successfully. Owner invite created for '{owner_m.user.email}'.",
                )
                return redirect("platform_admin:organizations")
            except (Conflict, ValidationFailed) as exc:
                form.add_error(None, str(exc))
    else:
        form = PlatformOrganizationCreateForm()

    return render(request, "tenancy/platform_organization_create.html", {"form": form})


@platform_admin_required
def organization_toggle_status(request, org_id):
    if request.method != "POST":
        return redirect("platform_admin:organizations")

    org = get_object_or_404(Organization, pk=org_id)
    new_active = org.status != Organization.Status.ACTIVE
    reason = request.POST.get("reason", "").strip()
    if not new_active and not reason:
        reason = "Deactivated by platform administrator"

    try:
        services.set_organization_status(org, active=new_active, actor=request.user, reason=reason, request=request)
        action_verb = "activated" if new_active else "deactivated"
        messages.success(request, f"Organization '{org.name}' successfully {action_verb}.")
    except Exception as exc:
        messages.error(request, f"Failed to update organization status: {exc}")

    return redirect("platform_admin:organizations")


@platform_admin_required
def organization_delete(request, org_id):
    if request.method != "POST":
        return redirect("platform_admin:organizations")

    org = get_object_or_404(Organization, pk=org_id)
    reason = request.POST.get("reason", "").strip()
    days_val = request.POST.get("days", "").strip()

    try:
        grace_days = int(days_val) if days_val else 7
    except ValueError:
        grace_days = 7

    if grace_days < 1:
        grace_days = 1

    if not reason:
        reason = "Deleted by platform administrator"

    try:
        services.schedule_organization_deletion(org, days=grace_days, reason=reason, actor=request.user, request=request)
        messages.warning(
            request,
            f"Organization '{org.name}' scheduled for deletion in {grace_days} day(s). The organization owner will see a countdown notice.",
        )
    except Exception as exc:
        messages.error(request, f"Failed to schedule deletion for organization: {exc}")

    return redirect("platform_admin:organizations")


@platform_admin_required
def organization_delete_now(request, org_id):
    if request.method != "POST":
        return redirect("platform_admin:organizations")

    org = get_object_or_404(Organization, pk=org_id)
    reason = request.POST.get("reason", "").strip() or org.deletion_reason or "Deleted immediately by platform administrator"

    try:
        hard, msg = services.permanently_delete_organization(org, actor=request.user, reason=reason, request=request)
        messages.success(request, msg)
    except Exception as exc:
        messages.error(request, f"Failed to permanently delete organization: {exc}")

    return redirect("platform_admin:organizations")


@platform_admin_required
def organization_cancel_deletion(request, org_id):
    if request.method != "POST":
        return redirect("platform_admin:organizations")

    org = get_object_or_404(Organization, pk=org_id)
    try:
        services.cancel_organization_deletion(org, actor=request.user, request=request)
        messages.success(request, f"Scheduled deletion for organization '{org.name}' has been cancelled.")
    except Exception as exc:
        messages.error(request, f"Failed to cancel scheduled deletion: {exc}")

    return redirect("platform_admin:organizations")


@platform_admin_required
def audit(request):
    # Rule D-008: Platform admin has no tenant operational rights and cannot view tenant-internal changes
    # (incidents, work orders, assets, checklists, maintenance, inventory, etc.).
    # Platform audit is strictly restricted to platform governance, authentication, and security events.
    from django.db.models import Q

    platform_filter = (
        Q(action__startswith="auth.")
        | Q(action__startswith="organization.")
        | Q(action="portal.client_onboarding_requested")
    )
    qs = AuditLog.objects.filter(platform_filter).select_related("organization")

    category = request.GET.get("category", "").strip().lower()
    if category == "auth":
        qs = qs.filter(action__startswith="auth.")
    elif category == "org":
        qs = qs.filter(action__startswith="organization.")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(actor_email__icontains=q)
            | Q(target_repr__icontains=q)
            | Q(action__icontains=q)
            | Q(organization__name__icontains=q)
        )

    page = Paginator(qs.order_by("-occurred_at"), 50).get_page(request.GET.get("page"))
    return render(
        request,
        "tenancy/platform_audit.html",
        {
            "page": page,
            "q": q,
            "category": category,
        },
    )
