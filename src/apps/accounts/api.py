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

from .jwt_revocation import revoke_token_jti, revoke_user_tokens

_FALLBACK_THROTTLE_CACHE = LocMemCache("fieldops-throttle-fallback", {})


class ClientIPScopedRateThrottle(ScopedRateThrottle):
    """Per-IP scoped throttle tolerant of reverse proxies and transient cache outages.

    Counters are kept in the shared ``login_throttle`` cache (Redis when configured,
    otherwise the ``core_login_throttle`` database table), so the documented 10/min
    limit holds across workers and instances. If that backend is missing or errors,
    the throttle degrades to per-process memory instead of failing authentication:
    a cache outage must never take login down with it (QA 2026-11-10, DEF-002).
    """

    def get_ident(self, request):
        return client_ip(request) or super().get_ident(request)

    def get_rate(self):
        if getattr(self, "scope", None) == "login":
            return "10/min"
        if getattr(self, "scope", None):
            rates = api_settings.DEFAULT_THROTTLE_RATES or {}
            if self.scope in rates:
                return rates[self.scope]
        return "10/min" if getattr(self, "scope", None) == "login" else super().get_rate()

    def get_cache_key(self, request, view):
        user = getattr(request, "user", None)
        if user and getattr(user, "is_authenticated", False):
            ident = user.pk
        else:
            ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}

    @staticmethod
    def _shared_cache():
        try:
            from django.core.cache import caches

            return caches["login_throttle"]
        except Exception:
            try:
                from django.core.cache import cache

                return cache
            except Exception:
                return None

    def allow_request(self, request, view):
        from django.conf import settings

        self.scope = getattr(view, self.scope_attr, None) or "login"
        self.rate = self.get_rate()
        self.num_requests, self.duration = self.parse_rate(self.rate)

        # Login throttle is always enforced (10/min) as per security requirement
        if self.scope != "login" and not getattr(settings, "RATE_LIMITING_ENABLED", False):
            return True
        for backend in (self._shared_cache(), _FALLBACK_THROTTLE_CACHE):
            if backend is None:
                continue
            self.cache = backend
            try:
                return super(ScopedRateThrottle, self).allow_request(request, view)
            except Exception:
                continue
        # No usable counter store: allow the request rather than block authentication.
        return True


class BoundedTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Caps login identifier length before Django's auth/axes backends touch the database."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        username_field = self.fields.get(self.username_field)
        if username_field is not None:
            username_field.max_length = 254
            username_field.validators.append(MaxLengthValidator(254))

    def to_internal_value(self, data):
        if isinstance(data, dict) and "body" in data and isinstance(data["body"], dict):
            data = data["body"]
        return super().to_internal_value(data)

    def validate(self, attrs):
        from axes.handlers.proxy import AxesProxyHandler
        from django.conf import settings
        from rest_framework.exceptions import Throttled

        request = self.context.get("request")
        http_request = getattr(request, "_request", request)
        username = (attrs.get(self.username_field) or "").strip().lower()
        credentials = {"username": username, "email": username}

        if getattr(settings, "AXES_ENABLED", True) and http_request:
            if not AxesProxyHandler.is_allowed(http_request, credentials):
                cooloff = getattr(settings, "AXES_COOLOFF_TIME", None)
                wait = int(cooloff.total_seconds()) if cooloff else 900
                raise Throttled(detail="Account temporarily locked due to repeated failed login attempts.", wait=wait)

        try:
            data = super().validate(attrs)
            if getattr(settings, "AXES_ENABLED", True) and http_request and getattr(self, "user", None):
                try:
                    from django.contrib.auth.signals import user_logged_in
                    user_logged_in.send(
                        sender=self.user.__class__,
                        request=http_request,
                        user=self.user,
                    )
                except Exception:
                    pass
            return data
        except Exception:
            # Allow attempt 5 to return 401 completing the 5 failed attempts,
            # while ensuring subsequent requests (attempts >= 5) lock out with 429.
            if getattr(settings, "AXES_ENABLED", True):
                if http_request:
                    http_request.axes_locked_out = False
                if request:
                    request.axes_locked_out = False
            raise


class LoginThrottleMixin:
    throttle_classes = [ClientIPScopedRateThrottle]
    throttle_scope = "login"


class TokenObtain(LoginThrottleMixin, TokenObtainPairView):
    authentication_classes: list = []
    permission_classes: list = []
    serializer_class = BoundedTokenObtainPairSerializer

    def initial(self, request, *args, **kwargs):
        if request.method == "POST":
            ct = request.content_type
            if ct and ct not in ("application/json", "application/x-www-form-urlencoded", "multipart/form-data"):
                from rest_framework.exceptions import UnsupportedMediaType
                raise UnsupportedMediaType(ct)
        super().initial(request, *args, **kwargs)

    def check_throttles(self, request):
        super().check_throttles(request)


class TokenRefresh(LoginThrottleMixin, TokenRefreshView):
    authentication_classes: list = []
    permission_classes: list = []


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(required=False, allow_blank=True, default="", help_text="Refresh token to blacklist")


class LogoutView(APIView):
    """Logs out the user, discarding or blacklisting credentials."""

    @extend_schema(
        summary="User logout",
        request=LogoutSerializer,
        responses={200: inline_serializer("LogoutResponse", fields={"message": serializers.CharField()})},
        description="Logs out the current session and blacklists the refresh token.",
    )
    def post(self, request):
        serializer = LogoutSerializer(data=request.data if isinstance(request.data, dict) else {})
        serializer.is_valid(raise_exception=True)
        refresh_token = serializer.validated_data.get("refresh", "").strip()

        user_id = None
        if refresh_token:
            try:
                from rest_framework_simplejwt.tokens import RefreshToken, TokenError
                token = RefreshToken(refresh_token)
                user_id = token.payload.get("user_id")
                token.blacklist()
            except TokenError as exc:
                if not getattr(request.user, "is_authenticated", False):
                    return Response(
                        {"error": {"code": "invalid_token", "message": str(exc), "details": {}}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
            except Exception:
                if not getattr(request.user, "is_authenticated", False):
                    return Response(
                        {"error": {"code": "invalid_token", "message": "Invalid token.", "details": {}}},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

        # Revoke access token JTI if present in request.auth
        if hasattr(request, "auth") and isinstance(request.auth, dict):
            jti = request.auth.get("jti")
            if jti:
                revoke_token_jti(jti)
            if not user_id:
                user_id = request.auth.get("user_id")

        if not user_id and getattr(request.user, "is_authenticated", False):
            user_id = str(request.user.pk)

        if user_id:
            revoke_user_tokens(str(user_id))

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
