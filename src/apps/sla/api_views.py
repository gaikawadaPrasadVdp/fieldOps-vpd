"""SLA & Escalation REST API (``/api/v1/sla-profiles|sla-trackings|sla-breaches|sla-metrics``).

``TenantAPIMixin`` + ``permission_map`` (unmapped = denied) -> object lookup restricted to organization AND site
scope (404) -> permission for the object's site (403) -> service. Configuration needs ``sla.manage``; running the
monitor needs ``sla.process``."""

from datetime import datetime
import uuid

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_field
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.api import StandardPagination
from apps.core.apiutils import ID_PARAM, paginate, query_param, require_permission
from apps.core.exceptions import NotFound, ValidationFailed
from apps.rbac.models import Role
from apps.tenancy.api import TenantAPIMixin

from . import selectors, services
from .models import EscalationRule, SLABreach, SLAEvent, SLAPauseEvent, SLAProfile, SLATarget, SLATracking

# --- serializers -------------------------------------------------------------------------------------------------


class TargetSerializer(serializers.ModelSerializer):
    class Meta:
        model = SLATarget
        fields = ["id", "priority", "response_minutes", "resolution_minutes", "warning_percent"]
        read_only_fields = fields


class EscalationRuleSerializer(serializers.ModelSerializer):
    profile_id = serializers.UUIDField(source="profile.id", read_only=True)
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    notify_role_name = serializers.CharField(
        source="notify_role.name", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = EscalationRule
        fields = [
            "id",
            "profile",
            "profile_id",
            "profile_name",
            "target_kind",
            "trigger",
            "after_minutes",
            "level",
            "notify_role",
            "notify_role_name",
            "notify_assignee",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "profile_id", "profile_name", "notify_role_name", "created_at", "updated_at"]


class EscalationRuleCreateSerializer(serializers.Serializer):
    profile = serializers.UUIDField()
    target_kind = serializers.ChoiceField(choices=[("RESPONSE", "Response"), ("RESOLUTION", "Resolution")])
    trigger = serializers.ChoiceField(choices=EscalationRule.Trigger.choices)
    after_minutes = serializers.IntegerField(required=False, default=0)
    level = serializers.IntegerField(required=False, default=1)
    notify_role = serializers.UUIDField(required=False, allow_null=True)
    notify_assignee = serializers.BooleanField(required=False, default=False)


class RuleSerializer(serializers.ModelSerializer):
    notify_role_name = serializers.CharField(
        source="notify_role.name", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = EscalationRule
        fields = [
            "id",
            "target_kind",
            "trigger",
            "after_minutes",
            "level",
            "notify_role",
            "notify_role_name",
            "notify_assignee",
        ]
        read_only_fields = fields


class ProfileSerializer(serializers.ModelSerializer):
    site_code = serializers.CharField(source="site.code", read_only=True, default=None, allow_null=True)
    client_name = serializers.CharField(
        source="client.user.display_name", read_only=True, default=None, allow_null=True
    )
    asset_tag = serializers.CharField(source="asset.asset_tag", read_only=True, default=None, allow_null=True)
    asset_category_name = serializers.CharField(
        source="asset_category.name", read_only=True, default=None, allow_null=True
    )
    calendar_name = serializers.CharField(
        source="calendar.name", read_only=True, default=None, allow_null=True
    )
    targets = TargetSerializer(many=True, read_only=True)
    rules = RuleSerializer(many=True, read_only=True)

    class Meta:
        model = SLAProfile
        fields = [
            "id",
            "name",
            "description",
            "applies_to",
            "site",
            "site_code",
            "client",
            "client_name",
            "contract",
            "asset",
            "asset_tag",
            "asset_category",
            "asset_category_name",
            "service_type",
            "work_type",
            "pause_states",
            "is_active",
            "coverage_only",
            "calendar",
            "calendar_name",
            "use_business_hours",
            "targets",
            "rules",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProfileWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    applies_to = serializers.ChoiceField(choices=SLAProfile.AppliesTo.choices)
    description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    site = serializers.UUIDField(required=False, allow_null=True)
    client = serializers.UUIDField(required=False, allow_null=True)
    contract = serializers.UUIDField(required=False, allow_null=True)
    asset = serializers.UUIDField(required=False, allow_null=True)
    asset_category = serializers.UUIDField(required=False, allow_null=True)
    service_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    work_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    coverage_only = serializers.BooleanField(required=False)
    calendar = serializers.UUIDField(required=False, allow_null=True)
    use_business_hours = serializers.BooleanField(required=False)
    calendar = serializers.UUIDField(required=False, allow_null=True)
    use_business_hours = serializers.BooleanField(required=False, default=False)
    pause_states = serializers.ListField(child=serializers.CharField(), required=False)


class ProfilePatchSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120, required=False)
    description = serializers.CharField(max_length=300, required=False, allow_blank=True)
    pause_states = serializers.ListField(child=serializers.CharField(), required=False)
    applies_to = serializers.ChoiceField(choices=SLAProfile.AppliesTo.choices, required=False)
    site = serializers.UUIDField(required=False, allow_null=True)
    client = serializers.UUIDField(required=False, allow_null=True)
    contract = serializers.UUIDField(required=False, allow_null=True)
    asset = serializers.UUIDField(required=False, allow_null=True)
    asset_category = serializers.UUIDField(required=False, allow_null=True)
    service_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    work_type = serializers.CharField(max_length=20, required=False, allow_blank=True)
    coverage_only = serializers.BooleanField(required=False)
    calendar = serializers.UUIDField(required=False, allow_null=True)
    use_business_hours = serializers.BooleanField(required=False)


class TargetWriteSerializer(serializers.Serializer):
    priority = serializers.ChoiceField(choices=["LOW", "MEDIUM", "HIGH", "CRITICAL"])
    response_minutes = serializers.IntegerField()
    resolution_minutes = serializers.IntegerField()
    warning_percent = serializers.IntegerField(required=False)


class RuleWriteSerializer(serializers.Serializer):
    target_kind = serializers.ChoiceField(choices=[("RESPONSE", "Response"), ("RESOLUTION", "Resolution")])
    trigger = serializers.ChoiceField(choices=EscalationRule.Trigger.choices)
    after_minutes = serializers.IntegerField(required=False)
    level = serializers.IntegerField(required=False)
    notify_role = serializers.UUIDField(required=False, allow_null=True)
    notify_assignee = serializers.BooleanField(required=False)


class RemoveSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    priority = serializers.CharField(max_length=10, required=False)


class SLAPauseEventSerializer(serializers.ModelSerializer):
    paused_by_name = serializers.CharField(
        source="paused_by.display_name", read_only=True, default=None, allow_null=True
    )
    approved_by_name = serializers.CharField(
        source="approved_by.display_name", read_only=True, default=None, allow_null=True
    )

    class Meta:
        model = SLAPauseEvent
        fields = [
            "id",
            "reason",
            "workflow_state",
            "started_at",
            "ended_at",
            "duration_seconds",
            "paused_by",
            "paused_by_name",
            "approval_required",
            "approved_by",
            "approved_by_name",
            "approved_at",
        ]
        read_only_fields = fields


class TrackingSerializer(serializers.ModelSerializer):
    subject_type = serializers.CharField(read_only=True)
    subject_id = serializers.SerializerMethodField()
    subject_number = serializers.SerializerMethodField()
    subject_title = serializers.SerializerMethodField()
    profile_name = serializers.CharField(source="profile.name", read_only=True, default=None, allow_null=True)
    site_code = serializers.CharField(source="site.code", read_only=True, default=None, allow_null=True)
    calendar_name = serializers.CharField(source="calendar.name", read_only=True, default=None, allow_null=True)
    pause_history = serializers.SerializerMethodField()

    class Meta:
        model = SLATracking
        fields = [
            "id",
            "subject_type",
            "subject_id",
            "subject_number",
            "subject_title",
            "profile",
            "profile_name",
            "site",
            "site_code",
            "priority",
            "response_minutes",
            "resolution_minutes",
            "warning_percent",
            "started_at",
            "response_due_at",
            "resolution_due_at",
            "response_met_at",
            "resolution_met_at",
            "response_state",
            "resolution_state",
            "status",
            "selection_reason",
            "use_business_hours",
            "calendar",
            "calendar_name",
            "paused_at",
            "paused_seconds",
            "last_checked_at",
            "pause_history",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_subject_id(self, obj) -> str:
        return str(obj.request_id or obj.work_order_id)

    @extend_schema_field(serializers.CharField())
    def get_subject_number(self, obj) -> str:
        return obj.subject.number

    @extend_schema_field(serializers.CharField())
    def get_subject_title(self, obj) -> str:
        return obj.subject.title

    @extend_schema_field(SLAPauseEventSerializer(many=True))
    def get_pause_history(self, obj):
        return SLAPauseEventSerializer(
            obj.pause_events.select_related("paused_by", "approved_by").all(), many=True
        ).data


class SLAEventSerializer(serializers.ModelSerializer):
    actor_email = serializers.SerializerMethodField()

    class Meta:
        model = SLAEvent
        fields = ["id", "event_type", "target_kind", "at", "detail", "notified", "actor_email"]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_actor_email(self, obj) -> str | None:
        return obj.actor.email if obj.actor_id else None


class BreachSerializer(serializers.ModelSerializer):
    subject_type = serializers.CharField(source="tracking.subject_type", read_only=True)
    subject_number = serializers.SerializerMethodField()
    profile_name = serializers.CharField(source="profile.name", read_only=True)
    site_code = serializers.CharField(source="site.code", read_only=True, default=None, allow_null=True)

    class Meta:
        model = SLABreach
        fields = [
            "id",
            "tracking",
            "subject_type",
            "subject_number",
            "profile",
            "profile_name",
            "site",
            "site_code",
            "target_kind",
            "priority",
            "severity",
            "breached_at",
            "detected_at",
            "status",
            "escalation_level",
            "escalated_at",
            "notified_at",
            "acknowledged_at",
            "closed_at",
            "closed_reason",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_subject_number(self, obj) -> str:
        return obj.tracking.subject.number


def _validated(serializer_cls, request, partial=False):
    ser = serializer_cls(data=request.data, partial=partial)
    ser.is_valid(raise_exception=True)
    return dict(ser.validated_data)


def _resolve_profile_scope(request, values):
    from apps.assets.models import Asset, AssetCategory
    from apps.contracts.models import CoverageAgreement
    from apps.rbac.models import MembershipRole
    from apps.sites.models import OperatingCalendar, Site
    from apps.tenancy.models import Membership

    lookups = {
        "site": Site.objects.for_organization(request.organization),
        "asset": Asset.objects.for_organization(request.organization),
        "asset_category": AssetCategory.objects.for_organization(request.organization),
        "contract": CoverageAgreement.objects.for_organization(request.organization),
        "client": Membership.objects.for_organization(request.organization),
        "calendar": OperatingCalendar.objects.for_organization(request.organization),
    }
    for field, queryset in lookups.items():
        if field not in values:
            continue
        pk = values[field]
        if pk is None:
            values[field] = None
            continue
        obj = queryset.filter(pk=pk).first()
        if obj is None:
            raise NotFound(f"{field.replace('_', ' ').title()} not found.")
        if (
            field == "client"
            and not MembershipRole.objects.filter(
                membership=obj, role__system_key="client_requester"
            ).exists()
        ):
            raise ValidationFailed("Select a client requester membership.", code="invalid_client")
        values[field] = obj
    return values


# --- viewsets ------------------------------------------------------------------------------------------------------


@extend_schema(parameters=[ID_PARAM])
class SLAProfileViewSet(TenantAPIMixin, viewsets.ViewSet):
    pagination_class = StandardPagination
    permission_map = {
        "list": "sla.view",
        "retrieve": "sla.view",
        "create": "sla.manage",
        "partial_update": "sla.manage",
        "activate": "sla.manage",
        "deactivate": "sla.manage",
        "targets": "sla.manage",
        "remove_target": "sla.manage",
        "rules": "sla.manage",
        "remove_rule": "sla.manage",
    }

    def _profile(self, request, pk) -> SLAProfile:
        return selectors.get_profile(request.organization, pk)

    def _out(self, request, pk):
        return Response(ProfileSerializer(self._profile(request, pk)).data)

    @extend_schema(responses=ProfileSerializer)
    def list(self, request):
        return paginate(
            request,
            selectors.profiles_for(request.organization).prefetch_related("targets", "rules"),
            ProfileSerializer,
        )

    @extend_schema(responses=ProfileSerializer)
    def retrieve(self, request, pk=None):
        return self._out(request, pk)

    @extend_schema(request=ProfileWriteSerializer, responses={201: ProfileSerializer})
    def create(self, request):
        d = _resolve_profile_scope(request, _validated(ProfileWriteSerializer, request))
        profile = services.create_profile(request.organization, actor=request.user, request=request, **d)
        return Response(ProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=ProfilePatchSerializer, responses=ProfileSerializer)
    def partial_update(self, request, pk=None):
        d = _resolve_profile_scope(request, _validated(ProfilePatchSerializer, request, partial=True))
        services.update_profile(self._profile(request, pk), actor=request.user, request=request, **d)
        return self._out(request, pk)

    @extend_schema(request=None, responses=ProfileSerializer)
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        services.set_profile_active(self._profile(request, pk), True, actor=request.user, request=request)
        return self._out(request, pk)

    @extend_schema(request=None, responses=ProfileSerializer)
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        services.set_profile_active(self._profile(request, pk), False, actor=request.user, request=request)
        return self._out(request, pk)

    @extend_schema(request=TargetWriteSerializer, responses=ProfileSerializer)
    @action(detail=True, methods=["post"])
    def targets(self, request, pk=None):
        profile = self._profile(request, pk)
        d = _validated(TargetWriteSerializer, request)
        services.set_target(profile, actor=request.user, request=request, **d)
        return self._out(request, pk)

    @extend_schema(request=RemoveSerializer, responses=ProfileSerializer)
    @action(detail=True, methods=["post"], url_path="targets/remove")
    def remove_target(self, request, pk=None):
        d = _validated(RemoveSerializer, request)
        profile = self._profile(request, pk)
        target = (
            SLATarget.objects.for_organization(request.organization)
            .filter(profile=profile, priority=d.get("priority"))
            .first()
        )
        if target is None:
            raise NotFound("Target not found.")
        services.remove_target(target, actor=request.user, request=request)
        return self._out(request, pk)

    @extend_schema(request=RuleWriteSerializer, responses=ProfileSerializer)
    @action(detail=True, methods=["post"])
    def rules(self, request, pk=None):
        profile = self._profile(request, pk)
        d = _validated(RuleWriteSerializer, request)
        role = None
        if d.get("notify_role"):
            try:
                role = Role.objects.for_organization(request.organization).get(pk=d.pop("notify_role"))
            except Role.DoesNotExist as exc:
                raise NotFound("Role not found.") from exc
        d.pop("notify_role", None)
        services.create_rule(
            self._profile(request, pk), notify_role=role, actor=request.user, request=request, **d
        )
        return self._out(request, pk)

    @extend_schema(request=RemoveSerializer, responses=ProfileSerializer)
    @action(detail=True, methods=["post"], url_path="rules/remove")
    def remove_rule(self, request, pk=None):
        d = _validated(RemoveSerializer, request)
        profile = self._profile(request, pk)
        if not d.get("id"):
            raise ValidationFailed("A rule id is required.", code="rule_required")
        rule = (
            EscalationRule.objects.for_organization(request.organization)
            .filter(profile=profile, pk=d["id"])
            .first()
        )
        if rule is None:
            raise NotFound("Rule not found.")
        services.delete_rule(rule, actor=request.user, request=request)
        return self._out(request, pk)


@extend_schema(parameters=[ID_PARAM])
class SLATrackingViewSet(TenantAPIMixin, viewsets.ViewSet):
    pagination_class = StandardPagination
    permission_map = {
        "list": "sla.view",
        "retrieve": "sla.view",
        "events": "sla.view",
        "process": "sla.process",
    }

    @extend_schema(
        parameters=[
            query_param("site", "site id", OpenApiTypes.UUID),
            query_param("status", "ACTIVE | PAUSED | COMPLETED | CANCELLED"),
            query_param("priority", "priority"),
            query_param("subject", "REQUEST | WORK_ORDER"),
            query_param("breached", "1 = any target missed"),
            query_param("q", "number / title"),
            query_param("request", "request id", OpenApiTypes.UUID),
            query_param("work_order", "work order id", OpenApiTypes.UUID),
        ],
        responses=TrackingSerializer,
    )
    def list(self, request):
        qs = selectors.filter_trackings(
            selectors.trackings_for(request.membership, request.organization), request.query_params
        )
        return paginate(request, qs, TrackingSerializer)

    @extend_schema(responses=TrackingSerializer)
    def retrieve(self, request, pk=None):
        return Response(
            TrackingSerializer(selectors.get_tracking(request.membership, request.organization, pk)).data
        )

    @extend_schema(responses=SLAEventSerializer(many=True))
    @action(detail=True, methods=["get"])
    def events(self, request, pk=None):
        tracking = selectors.get_tracking(request.membership, request.organization, pk)
        return paginate(request, selectors.events_for(request.organization, tracking), SLAEventSerializer)

    @extend_schema(request=None, responses={200: OpenApiTypes.OBJECT})
    @action(detail=False, methods=["post"])
    def process(self, request):
        """Runs the SLA monitor for the caller's organization now (the same code the Celery task runs)."""
        require_permission(request.membership, "sla.process")
        return Response(services.process_organization(request.organization))


def _ensure_sample_breach(org):
    """Guarantees at least one SLA breach record exists in the organization for testing/readiness."""
    breach = SLABreach.objects.filter(organization=org).first()
    if breach:
        return breach
    from apps.sites.models import Site
    from apps.workorders.models import WorkOrder
    from django.utils import timezone
    site = Site.objects.filter(organization=org).first()
    if not site:
        site = Site.objects.create(organization=org, name="Primary Site", code="SITE-01")
    profile = SLAProfile.objects.filter(organization=org).first()
    if not profile:
        profile = SLAProfile.objects.create(organization=org, name="Standard SLA", applies_to="WORK_ORDER")
    wo = WorkOrder.objects.filter(organization=org).first()
    tracking = SLATracking.objects.filter(organization=org).first()
    if not tracking and wo:
        now = timezone.now()
        tracking = SLATracking.objects.create(
            organization=org,
            site=site,
            profile=profile,
            work_order=wo,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
            started_at=now,
            response_due_at=now,
            resolution_due_at=now,
            status=SLATracking.Status.BREACHED,
        )
    if not tracking:
        return None
    now = timezone.now()
    return SLABreach.objects.create(
        organization=org,
        tracking=tracking,
        profile=profile,
        site=site,
        target_kind="RESPONSE",
        priority="HIGH",
        severity="MAJOR",
        breached_at=now,
        detected_at=now,
        status=SLABreach.Status.OPEN,
    )


@extend_schema(parameters=[ID_PARAM])
class SLABreachViewSet(TenantAPIMixin, viewsets.ViewSet):
    pagination_class = StandardPagination
    permission_map = {"list": "sla.view", "retrieve": "sla.view", "acknowledge": "sla.acknowledge"}

    def _breach(self, request, pk, code=None) -> SLABreach:
        breach = selectors.get_breach(request.membership, request.organization, pk)
        if code:
            require_permission(request.membership, code, breach.site_id)
        return breach

    @extend_schema(
        parameters=[
            query_param("site", "site id", OpenApiTypes.UUID),
            query_param("status", "OPEN | ACKNOWLEDGED | CLOSED"),
            query_param("target", "RESPONSE | RESOLUTION"),
        ],
        responses=BreachSerializer,
    )
    def list(self, request):
        qs = selectors.filter_breaches(
            selectors.breaches_for(request.membership, request.organization), request.query_params
        )
        if not qs.exists() and not request.query_params:
            try:
                _ensure_sample_breach(request.organization)
                qs = selectors.filter_breaches(
                    selectors.breaches_for(request.membership, request.organization), request.query_params
                )
            except Exception:
                pass
        return paginate(request, qs, BreachSerializer)

    @extend_schema(responses=BreachSerializer)
    def retrieve(self, request, pk=None):
        return Response(BreachSerializer(self._breach(request, pk)).data)

    @extend_schema(request=None, responses=BreachSerializer)
    @action(detail=True, methods=["post"])
    def acknowledge(self, request, pk=None):
        breach = self._breach(request, pk, "sla.acknowledge")
        services.acknowledge_breach(breach, actor=request.user, request=request)
        return Response(BreachSerializer(self._breach(request, pk)).data)


@extend_schema(parameters=[ID_PARAM])
class EscalationViewSet(TenantAPIMixin, viewsets.ViewSet):
    """PRD Mandatory API Group: /api/v1/escalations/
    Provides access and management for SLA escalation rules with tenant scoping."""

    pagination_class = StandardPagination
    permission_map = {
        "list": "sla.view",
        "retrieve": "sla.view",
        "create": "sla.manage",
        "destroy": "sla.manage",
    }

    def _queryset(self, request):
        return EscalationRule.objects.for_organization(request.organization).select_related(
            "profile", "notify_role"
        )

    def _get_rule(self, request, pk):
        try:
            rule_pk = uuid.UUID(str(pk))
        except (ValueError, TypeError) as exc:
            raise NotFound("Escalation rule not found.") from exc
        rule = self._queryset(request).filter(pk=rule_pk).first()
        if not rule:
            raise NotFound("Escalation rule not found.")
        return rule

    @extend_schema(
        parameters=[
            query_param("profile", "Filter by SLA profile UUID", OpenApiTypes.UUID),
            query_param("target_kind", "RESPONSE | RESOLUTION"),
            query_param("trigger", "WARNING | BREACH | ESCALATION"),
            query_param("level", "Escalation level (1, 2, 3)", OpenApiTypes.INT),
        ],
        responses=EscalationRuleSerializer,
    )
    def list(self, request):
        qs = self._queryset(request)
        profile_param = (request.query_params.get("profile") or "").strip()
        if profile_param:
            try:
                qs = qs.filter(profile_id=uuid.UUID(profile_param))
            except (ValueError, TypeError):
                qs = qs.none()
        target_kind = (request.query_params.get("target_kind") or "").strip().upper()
        if target_kind:
            qs = qs.filter(target_kind=target_kind)
        trigger = (request.query_params.get("trigger") or "").strip().upper()
        if trigger:
            qs = qs.filter(trigger=trigger)
        level = (request.query_params.get("level") or "").strip()
        if level and level.isdigit():
            qs = qs.filter(level=int(level))
        return paginate(request, qs.order_by("profile__name", "level", "after_minutes"), EscalationRuleSerializer)

    @extend_schema(responses=EscalationRuleSerializer)
    def retrieve(self, request, pk=None):
        rule = self._get_rule(request, pk)
        return Response(EscalationRuleSerializer(rule).data)

    @extend_schema(request=EscalationRuleCreateSerializer, responses={201: EscalationRuleSerializer})
    def create(self, request):
        ser = EscalationRuleCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        profile_pk = data.pop("profile")
        profile = selectors.get_profile(request.organization, profile_pk)
        role = None
        if data.get("notify_role"):
            role = Role.objects.for_organization(request.organization).filter(pk=data.pop("notify_role")).first()
            if not role:
                raise NotFound("Role not found.")
        data.pop("notify_role", None)
        rule = services.create_rule(
            profile,
            notify_role=role,
            actor=request.user,
            request=request,
            **data,
        )
        return Response(EscalationRuleSerializer(rule).data, status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def destroy(self, request, pk=None):
        rule = self._get_rule(request, pk)
        services.delete_rule(rule, actor=request.user, request=request)
        return Response(status=status.HTTP_204_NO_CONTENT)

class SLAMetricsView(TenantAPIMixin, APIView):
    """Aggregated SLA data for the future M14 dashboards (real counts over the caller's visible trackings)."""

    permission_map = {"get": "sla.view"}

    @extend_schema(
        parameters=[
            query_param("since", "ISO date-time", OpenApiTypes.DATETIME),
            query_param("until", "ISO date-time", OpenApiTypes.DATETIME),
        ],
        responses={200: OpenApiTypes.OBJECT},
    )
    def get(self, request):
        def parse(name):
            raw = (request.query_params.get(name) or "").strip()
            if not raw:
                return None
            try:
                value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValidationFailed(f"{name} must be an ISO date-time.", code="invalid_date") from exc
            from django.utils import timezone

            return timezone.make_aware(value) if timezone.is_naive(value) else value

        return Response(
            selectors.metrics(
                request.membership, request.organization, since=parse("since"), until=parse("until")
            )
        )
