from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.api import StandardPagination
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
            "created_at", "updated_at"
        ]
        read_only_fields = fields


class WebhookEndpointSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = [
            "id", "name", "target_url", "secret_token",
            "event_pattern", "is_active", "created_at", "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def create(self, validated_data):
        request = self.context.get("request")
        org = getattr(request, "organization", None)
        return WebhookEndpoint.objects.create(organization=org, **validated_data)


class IntegrationEventViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = IntegrationEventSerializer
    pagination_class = StandardPagination
    permission_map = {
        "list": "audit.view",
        "retrieve": "audit.view",
        "retry": "audit.view",
    }

    def get_queryset(self):
        qs = IntegrationEvent.objects.for_organization(self.request.organization)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param.upper())
        event_type = self.request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)
        return qs

    @action(detail=True, methods=["post"], url_path="retry")
    def retry(self, request, pk=None):
        event = self.get_object()
        event.status = IntegrationEvent.Status.PENDING
        event.retry_count = 0
        event.save(update_fields=["status", "retry_count", "updated_at"])
        processed = process_single_event(str(event.pk))
        return Response(IntegrationEventSerializer(processed or event).data)


class WebhookEndpointViewSet(TenantAPIMixin, viewsets.ModelViewSet):
    serializer_class = WebhookEndpointSerializer
    pagination_class = StandardPagination
    permission_map = {
        "list": "audit.view",
        "retrieve": "audit.view",
        "create": "audit.view",
        "update": "audit.view",
        "partial_update": "audit.view",
        "destroy": "audit.view",
    }

    def get_queryset(self):
        qs = WebhookEndpoint.objects.for_organization(self.request.organization)
        is_active = self.request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() in ["true", "1"])
        return qs
