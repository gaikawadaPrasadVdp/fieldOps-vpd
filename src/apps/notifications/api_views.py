from django.utils import timezone
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.core.exceptions import NotFound
from apps.tenancy.api import TenantAPIMixin

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "level", "title", "body", "link", "source", "read_at", "created_at"]


class NotificationViewSet(TenantAPIMixin, viewsets.ReadOnlyModelViewSet):
    """The caller's own notifications in the active organization."""

    serializer_class = NotificationSerializer
    permission_map = {"list": "__member__", "retrieve": "__member__", "read": "__member__", "read_all": "__member__"}
    filterset_fields: list = []

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.for_organization(self.request.organization).filter(recipient=self.request.user)

    @extend_schema(request=None, responses={200: NotificationSerializer})
    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        try:
            n = self.get_queryset().get(pk=pk)
        except (Notification.DoesNotExist, ValueError, Exception) as exc:
            raise NotFound("Notification not found.") from exc
        n.mark_read()
        return Response(NotificationSerializer(n).data)

    @extend_schema(
        request=None,
        responses={200: inline_serializer("NotificationReadAllResponse", fields={"marked": serializers.IntegerField()})},
    )
    @action(detail=False, methods=["post"], url_path="read-all")
    def read_all(self, request):
        n = self.get_queryset().filter(read_at__isnull=True).update(read_at=timezone.now())
        return Response({"marked": n}, status=status.HTTP_200_OK)

