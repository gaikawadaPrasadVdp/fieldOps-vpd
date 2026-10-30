from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.audit.models import AuditLog
from apps.core.exceptions import Conflict, ValidationFailed

from .forms import PlatformOrganizationCreateForm
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
    qs = Organization.objects.order_by("name")
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip().upper()
    if q:
        qs = qs.filter(name__icontains=q)
    if status_filter in dict(Organization.Status.choices):
        qs = qs.filter(status=status_filter)

    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "tenancy/platform_organizations.html",
        {
            "page": page,
            "q": q,
            "status_filter": status_filter,
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
    try:
        hard, msg = services.delete_organization(org, actor=request.user, request=request)
        if hard:
            messages.success(request, msg)
        else:
            messages.warning(request, msg)
    except Exception as exc:
        messages.error(request, f"Failed to delete organization: {exc}")

    return redirect("platform_admin:organizations")


@platform_admin_required
def audit(request):
    page = Paginator(
        AuditLog.objects.select_related("organization").order_by("-occurred_at"), 50
    ).get_page(request.GET.get("page"))
    return render(request, "tenancy/platform_audit.html", {"page": page})
