from django.core.cache.backends.locmem import LocMemCache
from django.core.validators import MaxLengthValidator
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.core.net import client_ip
from apps.tenancy import selectors

_FALLBACK_THROTTLE_CACHE = LocMemCache("fieldops-throttle-fallback", {})


class ClientIPScopedRateThrottle(ScopedRateThrottle):
    """Per-IP scoped throttle tolerant of reverse proxies and transient cache outages."""

    def get_ident(self, request):
        return client_ip(request) or super().get_ident(request)

    def get_rate(self):
        if getattr(self, "scope", None):
            rates = api_settings.DEFAULT_THROTTLE_RATES or {}
            if self.scope in rates:
                return rates[self.scope]
        return super().get_rate()

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception:
            self.cache = _FALLBACK_THROTTLE_CACHE
            return super().allow_request(request, view)


class BoundedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Caps login identifier length before Django's auth/axes backends touch the database."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        username_field = self.fields.get(self.username_field)
        if username_field is not None:
            username_field.max_length = 254
            username_field.validators.append(MaxLengthValidator(254))


class LoginThrottleMixin:
    throttle_classes = [ClientIPScopedRateThrottle]
    throttle_scope = "login"


class TokenObtain(LoginThrottleMixin, TokenObtainPairView):
    authentication_classes: list = []
    permission_classes: list = []
    serializer_class = BoundedTokenObtainPairSerializer


class TokenRefresh(LoginThrottleMixin, TokenRefreshView):
    authentication_classes: list = []
    permission_classes: list = []


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True, help_text="Optional refresh token to blacklist")


class LogoutView(APIView):
    """Logs out the user, discarding or blacklisting credentials."""

    @extend_schema(
        summary="User logout",
        request=LogoutSerializer,
        responses={200: inline_serializer("LogoutResponse", fields={"message": serializers.CharField()})},
        description="Logs out the current session and blacklists the refresh token if provided.",
    )
    def post(self, request):
        refresh_token = request.data.get("refresh") if isinstance(request.data, dict) else None
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass
        return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)


class MeOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    slug = serializers.CharField()
    name = serializers.CharField()


class MeSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    full_name = serializers.CharField()
    is_platform_admin = serializers.BooleanField()
    organizations = MeOrganizationSerializer(many=True)


class MeView(APIView):
    """The authenticated identity and the organizations they can act in. Not tenant-scoped."""

    @extend_schema(summary="Current user and organization memberships", responses=MeSerializer)
    def get(self, request):
        u = request.user
        return Response({
            "id": str(u.pk), "email": u.email, "full_name": u.full_name,
            "is_platform_admin": u.is_platform_admin,
            "organizations": [
                {"id": str(m.organization_id), "slug": m.organization.slug, "name": m.organization.name}
                for m in selectors.active_memberships(u)
            ],
        })
