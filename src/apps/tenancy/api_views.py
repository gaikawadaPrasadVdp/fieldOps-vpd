from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api import StandardPagination

from . import selectors, services
from .api import PlatformAPIMixin, TenantAPIMixin
from .models import Membership, Organization

ORG_FIELDS = ["name", "legal_name", "timezone", "country", "contact_email", "contact_phone", "address"]


class OrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    slug = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    name = serializers.CharField(max_length=150)
    legal_name = serializers.CharField(max_length=200, required=False, allow_blank=True)
    timezone = serializers.CharField(max_length=64, required=False)
    country = serializers.CharField(max_length=2, required=False, allow_blank=True)
    contact_email = serializers.EmailField(required=False, allow_blank=True)
    contact_phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)


class OrganizationViewSet(TenantAPIMixin, viewsets.ViewSet):
    """The caller's active organization."""

    permission_map = {"retrieve": "organization.view", "partial_update": "organization.update"}

    @extend_schema(responses=OrganizationSerializer)
    def retrieve(self, request):
        return Response(OrganizationSerializer(request.organization).data)

    @extend_schema(request=OrganizationSerializer, responses=OrganizationSerializer)
    def partial_update(self, request):
        ser = OrganizationSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        org = services.update_organization(
            request.organization, actor=request.user, request=request, **ser.validated_data
        )
        return Response(OrganizationSerializer(org).data)


class PlatformOrganizationCreateSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    slug = serializers.CharField(max_length=60, required=False, allow_blank=True)
    owner_name = serializers.CharField(max_length=150)
    owner_email = serializers.EmailField()
    owner_password = serializers.CharField(max_length=128, required=False, allow_blank=True, default="FieldOps@2026!")
    timezone = serializers.CharField(max_length=64, required=False, default="UTC")
    country = serializers.CharField(max_length=2, required=False, allow_blank=True)


class PlatformOrganizationStatusSerializer(serializers.Serializer):
    active = serializers.BooleanField(required=True, help_text="True to activate, False to suspend the organization")
    reason = serializers.CharField(required=False, allow_blank=True, default="", help_text="Reason for the status change")



def _resolve_role_ids(org, role_str, role_ids=None):
    if role_ids:
        return role_ids
    if not role_str:
        return []
    from apps.rbac.models import Role
    role_raw = role_str.strip().lower()
    role_map = {
        "super_admin": "admin",
        "super admin": "admin",
        "administrator": "admin",
        "field_technician": "technician",
        "field technician": "technician",
        "stores": "stores_manager",
        "asset manager": "asset_manager",
        "service manager": "service_manager",
        "maintenance planner": "maintenance_planner",
        "compliance": "auditor",
    }
    role_key = role_map.get(role_raw, role_raw)
    role = Role.objects.filter(organization=org, system_key=role_key).first()
    if not role:
        role = Role.objects.filter(organization=org, name__iexact=role_str).first()
    if not role:
        role = Role.objects.filter(organization=org, system_key="technician").first()
    return [role.pk] if role else []


class PlatformUserCreateSerializer(serializers.Serializer):
    organization = serializers.UUIDField(required=False)
    organization_id = serializers.UUIDField(required=False)
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    password = serializers.CharField(max_length=128, required=False, allow_blank=True)
    role = serializers.CharField(max_length=50, required=False, default="super_admin")
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True)

class PlatformOrganizationViewSet(PlatformAPIMixin, viewsets.ViewSet):
    """Platform Super Admin management of all organizations (multi-tenant root)."""

    @extend_schema(responses=OrganizationSerializer(many=True))
    def list(self, request):
        orgs = Organization.objects.all().order_by("name")
        return Response(OrganizationSerializer(orgs, many=True).data)

    @extend_schema(responses=OrganizationSerializer)
    def retrieve(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        org = get_object_or_404(Organization, pk=pk)
        return Response(OrganizationSerializer(org).data)

    @extend_schema(request=PlatformOrganizationCreateSerializer, responses=OrganizationSerializer)
    def create(self, request):
        ser = PlatformOrganizationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        org, _ = services.create_organization(
            name=data["name"],
            slug=data.get("slug") or None,
            owner_name=data["owner_name"],
            owner_email=data["owner_email"],
            owner_password=data.get("owner_password") or "FieldOps@2026!",
            timezone_name=data.get("timezone", "UTC"),
            country=data.get("country", ""),
            actor=request.user,
            request=request,
        )
        return Response(OrganizationSerializer(org).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={200: serializers.DictField()})
    def destroy(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        org = get_object_or_404(Organization, pk=pk)
        hard, msg = services.delete_organization(org, actor=request.user, request=request)
        return Response({"success": True, "hard_deleted": hard, "message": msg}, status=status.HTTP_200_OK)

    @extend_schema(request=PlatformOrganizationStatusSerializer, responses=OrganizationSerializer, summary="Update organization status")
    @action(detail=True, methods=["post"])
    def set_status(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        org = get_object_or_404(Organization, pk=pk)
        active = bool(request.data.get("active", True))
        reason = request.data.get("reason", "") or ("Deactivated via platform API" if not active else "")
        services.set_organization_status(org, active=active, actor=request.user, reason=reason, request=request)
        return Response(OrganizationSerializer(org).data)

    @extend_schema(request=PlatformUserCreateSerializer, responses={201: lambda: MemberSerializer})
    @action(detail=True, methods=["post"], url_path="users")
    def create_user(self, request, pk=None):
        from django.shortcuts import get_object_or_404
        from django.utils import timezone
        org = get_object_or_404(Organization, pk=pk)
        ser = PlatformUserCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        full_name = d.get("full_name") or f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
        role_ids = _resolve_role_ids(org, d.get("role", "super_admin"))
        m = services.invite_member(
            org,
            email=d["email"],
            full_name=full_name,
            role_ids=role_ids,
            actor=request.user,
            request=request,
                    )
        u = m.user
        updated = False
        if d.get("password"):
            u.set_password(d["password"])
            updated = True
        if d.get("phone"):
            u.phone = d["phone"]
            updated = True
        if d.get("role", "").lower() in ("admin", "super_admin", "owner"):
            u.is_staff = True
            updated = True
        if updated:
            u.save()
            if d.get("password"):
                m.status = Membership.Status.ACTIVE
                m.activated_at = timezone.now()
                m.save(update_fields=["status", "activated_at"])
        return Response(MemberSerializer(m).data, status=status.HTTP_201_CREATED)


class PlatformUserViewSet(PlatformAPIMixin, viewsets.ViewSet):
    """Platform administrator user provisioning across organizations."""

    @extend_schema(request=PlatformUserCreateSerializer, responses={201: lambda: MemberSerializer})
    def create(self, request):
        from django.shortcuts import get_object_or_404
        from django.utils import timezone
        org_id = request.data.get("organization") or request.data.get("organization_id")
        if not org_id:
            raise serializers.ValidationError({"organization": "organization or organization_id is required."})
        org = get_object_or_404(Organization, pk=org_id)
        ser = PlatformUserCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        full_name = d.get("full_name") or f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
        role_ids = _resolve_role_ids(org, d.get("role", "super_admin"))
        m = services.invite_member(
            org,
            email=d["email"],
            full_name=full_name,
            role_ids=role_ids,
            actor=request.user,
            request=request,
                    )
        u = m.user
        updated = False
        if d.get("password"):
            u.set_password(d["password"])
            updated = True
        if d.get("phone"):
            u.phone = d["phone"]
            updated = True
        if d.get("role", "").lower() in ("admin", "super_admin", "owner"):
            u.is_staff = True
            updated = True
        if updated:
            u.save()
            if d.get("password"):
                m.status = Membership.Status.ACTIVE
                m.activated_at = timezone.now()
                m.save(update_fields=["status", "activated_at"])
        return Response(MemberSerializer(m).data, status=status.HTTP_201_CREATED)


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(source="user.full_name", read_only=True)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ["id", "email", "full_name", "job_title", "status", "roles", "invited_at", "activated_at"]

    def get_roles(self, obj) -> list[dict]:
        return [{"id": str(mr.role_id), "name": mr.role.name, "assignment_id": str(mr.pk),
                 "site_id": str(mr.site_id) if mr.site_id else None,
                 "site_code": mr.site.code if mr.site_id else None}
                for mr in obj.membership_roles.all()]


class RoleAssignmentSerializer(serializers.Serializer):
    role_id = serializers.UUIDField()
    site_id = serializers.UUIDField(required=False, allow_null=True, default=None)


class _AssignmentInput(serializers.Serializer):
    """Either ``role_ids`` (+ optional ``site_ids`` limiting every listed role to those sites) or explicit
    ``role_assignments`` [{role_id, site_id|null}]. No site = organization-wide."""

    role_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=False)
    site_ids = serializers.ListField(child=serializers.UUIDField(), required=False, allow_empty=False)
    role_assignments = RoleAssignmentSerializer(many=True, required=False, allow_empty=False)

    def validate(self, attrs):
        if "role_assignments" in attrs and ("role_ids" in attrs or "site_ids" in attrs):
            raise serializers.ValidationError("Use either role_assignments or role_ids/site_ids, not both.")
        if "site_ids" in attrs and "role_ids" not in attrs:
            raise serializers.ValidationError("site_ids requires role_ids.")
        return attrs


class InviteSerializer(_AssignmentInput):
    email = serializers.EmailField()
    full_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    first_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=100, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    password = serializers.CharField(max_length=128, required=False, allow_blank=True)
    role = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if "role_ids" not in attrs and "role_assignments" not in attrs and not attrs.get("role"):
            raise serializers.ValidationError("role, role_ids or role_assignments is required.")
        return attrs


class MemberUpdateSerializer(_AssignmentInput):
    full_name = serializers.CharField(max_length=150, required=False)
    job_title = serializers.CharField(max_length=100, required=False, allow_blank=True)
    role = serializers.CharField(max_length=50, required=False, allow_blank=True)
    is_active = serializers.BooleanField(required=False)


@extend_schema(parameters=[OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)])
class MemberViewSet(TenantAPIMixin, viewsets.ViewSet):
    pagination_class = StandardPagination
    permission_map = {
        "list": "user.view", "retrieve": "user.view", "create": "user.invite",
        "partial_update": "user.update", "deactivate": "user.deactivate",
        "reactivate": "user.deactivate", "resend": "user.invite",
    }

    def _qs(self, request):
        return selectors.organization_members(request.organization)

    @extend_schema(responses=MemberSerializer)
    def list(self, request):
        qs = self._qs(request).order_by("user__full_name")
        status_f = request.query_params.get("status")
        if status_f in Membership.Status.values:
            qs = qs.filter(status=status_f)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(MemberSerializer(page, many=True).data)

    @extend_schema(responses=MemberSerializer)
    def retrieve(self, request, pk=None):
        return Response(MemberSerializer(services.get_membership(request.organization, pk)).data)

    @extend_schema(request=InviteSerializer, responses={201: MemberSerializer})
    def create(self, request):
        from django.utils import timezone
        ser = InviteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        full_name = d.get("full_name") or f"{d.get('first_name', '')} {d.get('last_name', '')}".strip()
        role_ids = d.get("role_ids")
        if not role_ids and not d.get("role_assignments") and d.get("role"):
            role_ids = _resolve_role_ids(request.organization, d["role"])

        m = services.invite_member(request.organization, email=d["email"], full_name=full_name or "",
                                   role_ids=role_ids, site_ids=d.get("site_ids"),
                                   assignments=d.get("role_assignments"), actor=request.user, request=request)
        u = m.user
        updated = False
        if d.get("password"):
            u.set_password(d["password"])
            updated = True
        if d.get("phone"):
            u.phone = d["phone"]
            updated = True
        if updated:
            u.save()
            if d.get("password"):
                m.status = Membership.Status.ACTIVE
                m.activated_at = timezone.now()
                m.save(update_fields=["status", "activated_at"])

        return Response(MemberSerializer(m).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=MemberUpdateSerializer, responses=MemberSerializer)
    def partial_update(self, request, pk=None):
        m = services.get_membership(request.organization, pk)
        ser = MemberUpdateSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data

        if "is_active" in d:
            services.set_member_active(m, active=bool(d["is_active"]), actor=request.user, request=request)

        role_ids = d.get("role_ids")
        if not role_ids and not d.get("role_assignments") and d.get("role"):
            role_ids = _resolve_role_ids(request.organization, d["role"])

        services.update_member(m, actor=request.user, request=request, full_name=d.get("full_name"),
                               job_title=d.get("job_title"), role_ids=role_ids,
                               site_ids=d.get("site_ids"), assignments=d.get("role_assignments"))
        return Response(MemberSerializer(services.get_membership(request.organization, pk)).data)

    @extend_schema(request=None, responses=MemberSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        m = services.get_membership(request.organization, pk)
        services.set_member_active(m, active=False, actor=request.user, request=request)
        return Response(MemberSerializer(services.get_membership(request.organization, pk)).data)

    @extend_schema(request=None, responses=MemberSerializer)
    @action(detail=True, methods=["post"])
    def reactivate(self, request, pk=None):
        m = services.get_membership(request.organization, pk)
        services.set_member_active(m, active=True, actor=request.user, request=request)
        return Response(MemberSerializer(services.get_membership(request.organization, pk)).data)

    @extend_schema(request=None, responses={202: None})
    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        m = services.get_membership(request.organization, pk)
        services.resend_invitation(m, actor=request.user, request=request)
        return Response(status=status.HTTP_202_ACCEPTED)
