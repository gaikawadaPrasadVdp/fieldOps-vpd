import uuid
from urllib.parse import urlparse

from django.db import IntegrityError
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api import StandardPagination
from apps.core.apiutils import ID_PARAM
from apps.core.exceptions import Conflict, NotFound
from apps.core.models import IntegrationEvent, WebhookEndpoint
from apps.core.outbox import process_single_event
from apps.tenancy.api import TenantAPIMixin


class IntegrationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationEvent
        fields = [
            "id", "event_type", "aggregate_type", "aggregate_id",
            "payload", "status", "retry_count", "max_retries",
            "error_message", "published_at", "metadata",
            "created_at", "updated_at",
        ]
        read_only_fields = fields


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = [
            "id", "name", "target_url", "secret_token",
            "event_pattern", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {
            "secret_token": {"write_only": True, "required": False},
        }

    def validate_target_url(self, value):
        parsed = urlparse(value or "")
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise serializers.ValidationError("Target URL must use http:// or https:// with a valid host.")
        return value

    def create(self, validated_data):
        request = self.context.get("request")
        org = getattr(request, "organization", None)
        try:
            return WebhookEndpoint.objects.create(organization=org, **validated_data)
        except IntegrityError as exc:
            raise Conflict("A webhook endpoint with this target URL already exists.", code="duplicate_webhook") from exc

    def update(self, instance, validated_data):
        try:
            return super().update(instance, validated_data)
        except IntegrityError as exc:
            raise Conflict("A webhook endpoint with this target URL already exists.", code="duplicate_webhook") from exc


def _uuid_or_404(pk, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(pk))
    except (ValueError, TypeError) as exc:
        raise NotFound(f"{what} not found.") from exc


@extend_schema(parameters=[ID_PARAM])
class IntegrationEventViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationEventSerializer
    pagination_class = StandardPagination
    permission_map = {
        "list": "audit.view",
        "retrieve": "audit.view",
        "retry": "organization.update",
    }

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not getattr(self.request, "organization", None):
            return IntegrationEvent.objects.none()
        qs = IntegrationEvent.objects.for_organization(self.request.organization)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs

    def get_object(self):
        uid = _uuid_or_404(self.kwargs.get(self.lookup_field), "Integration event")
        obj = self.get_queryset().filter(pk=uid).first()
        if obj is None:
            raise NotFound("Integration event not found.")
        return obj

    @extend_schema(request=None, responses={200: IntegrationEventSerializer})
    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        event = self.get_object()
        event.status = IntegrationEvent.Status.PENDING
        event.retry_count = 0
        event.save(update_fields=["status", "retry_count", "updated_at"])
        processed = process_single_event(str(event.pk))
        return Response(IntegrationEventSerializer(processed or event).data)


@extend_schema(parameters=[ID_PARAM])
class WebhookEndpointViewSet(
    TenantAPIMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = WebhookEndpointSerializer
    pagination_class = StandardPagination
    permission_map = {
        "list": "audit.view",
        "retrieve": "audit.view",
        "create": "organization.update",
        "partial_update": "organization.update",
        "destroy": "organization.update",
    }

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False) or not getattr(self.request, "organization", None):
            return WebhookEndpoint.objects.none()
        qs = WebhookEndpoint.objects.for_organization(self.request.organization)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ["true", "1"])
        return qs

    def get_object(self):
        uid = _uuid_or_404(self.kwargs.get(self.lookup_field), "Webhook endpoint")
        obj = self.get_queryset().filter(pk=uid).first()
        if obj is None:
            raise NotFound("Webhook endpoint not found.")
        return obj
