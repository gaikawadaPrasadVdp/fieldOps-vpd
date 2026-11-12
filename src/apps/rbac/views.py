import uuid
from itertools import groupby

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.views import View

from apps.core.exceptions import DomainError
from apps.sites.models import Site
from apps.tenancy import selectors, services as tenancy_services
from apps.tenancy.forms import RoleForm
from apps.ui.mixins import TenantPermissionMixin

from . import catalog, services
from .models import MembershipRole, Role, RolePermission


def _build_perm_matrix():
    groups = []
    for module, defs in groupby(catalog.all_defs(), key=lambda d: d.module):
        groups.append({
            "module": module.upper(),
            "perms": [{"code": d.code, "description": d.description} for d in defs],
        })
    return groups


class RoleListView(TenantPermissionMixin, View):
    required_permission = "role.view"

    def get(self, request):
        org = request.organization
        is_owner = services.is_owner(request.membership)

        members_qs = (
            selectors.organization_members(org)
            .select_related("user")
            .prefetch_related(
                "membership_roles__role",
                "membership_roles__site",
            )
        )

        q = (request.GET.get("q") or "").strip()
        role_filter = (request.GET.get("role") or "").strip()

        if q:
            members_qs = members_qs.filter(
                Q(user__full_name__icontains=q)
                | Q(user__email__icontains=q)
                | Q(job_title__icontains=q)
            )

        if role_filter:
            members_qs = members_qs.filter(membership_roles__role_id=role_filter).distinct()

        page = Paginator(members_qs.order_by("user__full_name"), 25).get_page(
            request.GET.get("page")
        )

        from apps.rbac.role_templates import PRIMARY_ROLE_KEYS

        # Available roles in this organization (Owner first, system + custom roles)
        all_roles = list(
            Role.objects.for_organization(org)
            .filter(Q(system_key__in=PRIMARY_ROLE_KEYS) | Q(system_key=""))
            .prefetch_related("role_permissions__permission")
            .order_by("-is_owner", "name")
        )
        custom_roles = [r for r in all_roles if not r.is_system]

        sites = list(Site.objects.filter(organization=org).order_by("name"))

        # Precompute owner counts to protect sole owner from removal
        owner_count = services.owner_memberships(org).count()

        for m in page:
            m.is_owner_member = services.is_owner(m)
            assigned_roles = [mr.role for mr in m.membership_roles.all()]
            m.active_role_ids = {mr.role_id for mr in m.membership_roles.all()}
            m.active_role_ids_str = {str(rid) for rid in m.active_role_ids}
            m.primary_site_id = next(
                (mr.site_id for mr in m.membership_roles.all() if mr.site_id),
                None,
            )
            # If member is an owner and there's only 1 owner, owner role cannot be removed
            m.can_remove_owner = not (m.is_owner_member and owner_count <= 1)

            if m.is_owner_member or any(r.is_owner for r in assigned_roles):
                m.granted_permissions = set(catalog.all_codes())
            else:
                granted = set(
                    RolePermission.objects.filter(role__in=assigned_roles).values_list(
                        "permission__code", flat=True
                    )
                )
                if m.is_active:
                    granted.update(services.membership_permissions(m))
                    for perms in services.site_permissions(m).values():
                        granted.update(perms)
                m.granted_permissions = catalog.expand(granted)

        # Build permission matrix grouped by module
        matrix = _build_perm_matrix()

        # Prepare role presets for modal dropdown
        role_presets = []
        for r in all_roles:
            if r.is_owner:
                codes = sorted(catalog.all_codes())
            else:
                codes = sorted(r.role_permissions.values_list("permission__code", flat=True))
            role_presets.append({
                "pk": str(r.pk),
                "name": r.name,
                "is_owner": r.is_owner,
                "codes_csv": ",".join(codes),
            })

        return render(
            request,
            "rbac/roles.html",
            {
                "page": page,
                "q": q,
                "role_filter": role_filter,
                "roles": all_roles,
                "custom_roles": custom_roles,
                "role_presets": role_presets,
                "matrix": matrix,
                "sites": sites,
                "is_owner": is_owner,
                "can_manage": is_owner,
            },
        )

    def post(self, request):
        org = request.organization
        is_owner = services.is_owner(request.membership)

        if not is_owner:
            messages.error(
                request,
                "Only an Organization Owner has permission to edit member roles and permissions.",
            )
            return redirect("rbac:roles")

        action = request.POST.get("action")
        member_id = request.POST.get("membership_id")

        if action in ("update_member_permissions", "update_member_roles"):
            try:
                target_membership = tenancy_services.get_membership(org, member_id)
            except Exception:
                messages.error(request, "Member not found in this organization.")
                return redirect("rbac:roles")

            codes = request.POST.getlist("permissions")
            if not codes:
                messages.error(request, "A member must have at least one permission assigned.")
                return redirect("rbac:roles")

            site_id = (request.POST.get("site_id") or "").strip()
            site_obj = None
            if site_id:
                try:
                    site_obj = Site.objects.get(pk=site_id, organization=org)
                except Site.DoesNotExist:
                    site_obj = None

            all_codes_set = catalog.all_codes()
            submitted_set = set(codes) & all_codes_set

            if not submitted_set:
                messages.error(request, "No valid permissions were selected.")
                return redirect("rbac:roles")

            # Protection: verify if attempting to remove owner status from sole owner
            if services.is_owner(target_membership) and submitted_set != all_codes_set:
                owners_count = services.owner_memberships(org).count()
                if owners_count <= 1:
                    messages.error(
                        request,
                        "Cannot remove Owner role: this organization must keep at least one active Owner.",
                    )
                    return redirect("rbac:roles")

            try:
                # 1. If all permissions are granted, assign Organization Owner role
                if submitted_set == all_codes_set:
                    owner_role = Role.objects.filter(organization=org, is_owner=True).first()
                    if owner_role:
                        services.set_membership_assignments(
                            target_membership,
                            [(owner_role, None)],
                            actor=request.user,
                            request=request,
                        )
                        messages.success(
                            request,
                            f"Full Owner permissions assigned to {target_membership.user.display_name}.",
                        )
                        return redirect("rbac:roles")

                # 2. Check if submitted permissions match an existing standard role exactly
                matched_role = None
                for r in Role.objects.for_organization(org).prefetch_related("role_permissions__permission"):
                    if not r.is_owner and r.is_system:
                        r_perms = set(r.role_permissions.values_list("permission__code", flat=True))
                        if r_perms == submitted_set:
                            matched_role = r
                            break

                if matched_role:
                    role_to_assign = matched_role
                else:
                    # 3. Dedicated custom role for this user's custom permissions
                    custom_role_name = f"Custom - {target_membership.user.display_name}"
                    custom_role = Role.objects.filter(organization=org, name=custom_role_name).first()
                    if not custom_role:
                        custom_role = Role.objects.create(
                            organization=org,
                            name=custom_role_name,
                            description=f"Custom permissions for {target_membership.user.display_name}",
                        )
                    services._apply_permissions(custom_role, list(submitted_set))
                    role_to_assign = custom_role

                # Assign role with optional site scope
                services.set_membership_assignments(
                    target_membership,
                    [(role_to_assign, site_obj)],
                    actor=request.user,
                    request=request,
                )

                scope_label = f" @ {site_obj.name}" if site_obj else " (Organization-wide)"
                messages.success(
                    request,
                    f"Permissions updated for {target_membership.user.display_name}: {role_to_assign.name} ({len(submitted_set)} permissions granted{scope_label}).",
                )
            except (DomainError, PermissionDenied) as exc:
                messages.error(request, str(exc))

        return redirect("rbac:roles")


def _get_role(request, pk) -> Role:
    try:
        return Role.objects.for_organization(request.organization).get(pk=uuid.UUID(str(pk)))
    except (Role.DoesNotExist, ValueError) as exc:
        raise Http404 from exc


def _matrix(selected: set[str]):
    rows = []
    for module, defs in groupby(catalog.all_defs(), key=lambda d: d.module):
        rows.append({"module": module, "perms": [{"code": d.code, "description": d.description,
                                                   "checked": d.code in selected} for d in defs]})
    return rows


class RoleCreateView(TenantPermissionMixin, View):
    required_permission = "role.manage"

    def get(self, request):
        return render(request, "rbac/role_form.html", {"form": RoleForm(), "matrix": _matrix(set()), "role": None})

    def post(self, request):
        form = RoleForm(request.POST)
        codes = request.POST.getlist("permissions")
        if form.is_valid():
            try:
                role = services.create_role(request.organization, name=form.cleaned_data["name"],
                                            description=form.cleaned_data["description"], permission_codes=codes,
                                            actor=request.user, request=request)
            except DomainError as exc:
                form.add_error(None, exc.message)
            else:
                messages.success(request, f"Role '{role.name}' created.")
                return redirect("rbac:role_detail", pk=role.pk)
        return render(request, "rbac/role_form.html", {"form": form, "matrix": _matrix(set(codes)), "role": None})


class RoleDetailView(TenantPermissionMixin, View):
    required_permission = "role.view"

    def get(self, request, pk):
        role = _get_role(request, pk)
        selected = set(role.role_permissions.values_list("permission__code", flat=True))
        form = RoleForm(initial={"name": role.name, "description": role.description})
        return render(request, "rbac/role_form.html", {
            "form": form, "matrix": _matrix(selected), "role": role,
            "can_manage": services.has_permission(request.membership, "role.manage"),
            "member_count": role.membership_roles.count(),
        })

    def post(self, request, pk):
        if not services.has_permission(request.membership, "role.manage"):
            raise PermissionDenied
        role = _get_role(request, pk)
        try:
            if request.POST.get("action") == "delete":
                services.delete_role(role, actor=request.user, request=request)
                messages.success(request, "Role deleted.")
                return redirect("rbac:roles")
            form = RoleForm(request.POST)
            if form.is_valid():
                services.update_role(role, name=form.cleaned_data["name"],
                                     description=form.cleaned_data["description"],
                                     permission_codes=request.POST.getlist("permissions"),
                                     actor=request.user, request=request)
                messages.success(request, "Role saved.")
        except DomainError as exc:
            messages.error(request, exc.message)
        return redirect("rbac:role_detail", pk=role.pk)
