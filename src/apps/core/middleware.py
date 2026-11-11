import re
import time
import uuid
import zoneinfo
from urllib.parse import quote

from django.conf import settings
from django.contrib.auth import logout as auth_logout
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone

from . import logging as flogging

_VALID_ID = re.compile(r"^[A-Za-z0-9\-_.]{8,64}$")


class RequestIdMiddleware:
    """Assigns/propagates X-Request-ID and emits one structured access-log line per request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import logging

        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _VALID_ID.match(incoming) else uuid.uuid4().hex
        request.request_id = rid

        for k, v in request.GET.items():
            if "\x00" in k or "\x00" in v:
                from django.http import JsonResponse
                return JsonResponse(
                    {
                        "error": {
                            "code": "validation_failed",
                            "message": "Null characters (0x00) are not permitted in query parameters.",
                            "details": {},
                            "request_id": rid,
                        }
                    },
                    status=400,
                )

        path = request.path_info or request.path or ""
        content_type = request.META.get("CONTENT_TYPE", "")
        if path.startswith("/api/") or "application/json" in content_type:
            content_length = request.META.get("CONTENT_LENGTH")
            if content_length:
                try:
                    cl_int = int(content_length)
                    max_allowed = 10 * 1024 * 1024 if "multipart/form-data" in content_type else 5 * 1024 * 1024
                    if cl_int > max_allowed:
                        from django.http import JsonResponse
                        resp = JsonResponse(
                            {
                                "error": {
                                    "code": "request_entity_too_large",
                                    "message": f"Request body exceeds maximum allowed size ({max_allowed // (1024 * 1024)}MB).",
                                    "details": {},
                                    "request_id": rid,
                                },
                                "success": False,
                                "meta": {"request_id": rid},
                            },
                            status=413,
                        )
                        resp["Connection"] = "close"
                        return resp
                except (ValueError, TypeError):
                    pass

        token = flogging.request_id_var.set(rid)
        started = time.monotonic()
        try:
            response = self.get_response(request)
        except Exception as exc:
            if exc.__class__.__name__ in ("RequestDataTooBig", "SuspiciousOperation"):
                from django.http import JsonResponse
                resp = JsonResponse(
                    {
                        "error": {
                            "code": "request_entity_too_large",
                            "message": "Request body exceeds maximum allowed size.",
                            "details": {},
                            "request_id": rid,
                        },
                        "success": False,
                        "meta": {"request_id": rid},
                    },
                    status=413,
                )
                resp["Connection"] = "close"
                return resp
            raise
        finally:
            elapsed = int((time.monotonic() - started) * 1000)
            flogging.request_id_var.reset(token)
        response["X-Request-ID"] = rid
        logging.getLogger("fieldops.access").info(
            "%s %s -> %s (%d ms)", request.method, request.path, response.status_code, elapsed,
            extra={"request_id": rid},
        )
        return response


class TimezoneMiddleware:
    """Activates the user's local timezone for each request so that all datetimes
    render accurately in the client's local time (e.g. Asia/Kolkata +05:30).

    Resolution priority:
    1. Client-provided cookie: request.COOKIES.get("user_timezone")
    2. Session value: request.session.get("django_timezone")
    3. Active organization timezone: request.organization.timezone (if not "UTC" and valid)
    4. Configured settings.TIME_ZONE (defaults to Asia/Kolkata)
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        cookie_tz = request.COOKIES.get("user_timezone")
        session_tz = getattr(request, "session", {}).get("django_timezone") if hasattr(request, "session") else None
        org_tz = getattr(getattr(request, "organization", None), "timezone", None)
        default_tz = getattr(settings, "TIME_ZONE", "Asia/Kolkata")

        candidates = [cookie_tz, session_tz]
        if org_tz and org_tz.strip().upper() != "UTC":
            candidates.append(org_tz)
        candidates.append(default_tz)
        candidates.append("Asia/Kolkata")

        active_zone = None
        for candidate in candidates:
            if candidate and isinstance(candidate, str):
                cleaned = candidate.strip()
                try:
                    active_zone = zoneinfo.ZoneInfo(cleaned)
                    break
                except Exception:
                    continue

        if active_zone:
            timezone.activate(active_zone)
            request.user_timezone = str(active_zone)
        else:
            timezone.deactivate()
            request.user_timezone = "UTC"

        try:
            return self.get_response(request)
        finally:
            timezone.deactivate()


class SecurityCacheControlMiddleware:
    """
    Prevents browsers and intermediate proxies from caching sensitive authenticated views.
    Ensures back-button navigation after logout immediately forces a fresh request
    to the server, which redirects unauthenticated requests to the login screen
    rather than showing stale dashboard or tenant data from bfcache/disk cache.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        path = request.path_info or request.path or ""

        static_url = getattr(settings, "STATIC_URL", "/static/")
        media_url = getattr(settings, "MEDIA_URL", "/media/")
        if (static_url and path.startswith(static_url)) or (media_url and path.startswith(media_url)):
            return response

        user = getattr(request, "user", None)
        is_authenticated = bool(user and getattr(user, "is_authenticated", False))

        if (
            is_authenticated
            or path.startswith("/app/")
            or path.startswith("/api/")
            or path.startswith("/portal/")
            or path.startswith("/accounts/")
        ):
            response["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0, private"
            response["Pragma"] = "no-cache"
            response["Expires"] = "0"

        return response


class SessionIdleTimeoutMiddleware:
    """Enforces server-side inactivity timeout for authenticated user sessions."""

    SESSION_ACTIVITY_KEY = "_last_activity_ts"
    _EXEMPT_PREFIXES = (
        "/health/",
        "/accounts/login/",
        "/accounts/logout/",
        "/api/v1/auth/logout/",
        "/favicon.ico",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def _is_exempt(self, path: str) -> bool:
        static_url = getattr(settings, "STATIC_URL", "") or ""
        media_url = getattr(settings, "MEDIA_URL", "") or ""
        if static_url and path.startswith(static_url):
            return True
        if media_url and path.startswith(media_url):
            return True
        return any(path.startswith(prefix) for prefix in self._EXEMPT_PREFIXES)

    def _wants_json(self, request) -> bool:
        if request.path.startswith("/api/"):
            return True
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return True
        accept = request.headers.get("Accept", "")
        return "application/json" in accept

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not self._is_exempt(request.path):
            idle_limit = max(1, int(getattr(settings, "SESSION_IDLE_TIMEOUT_SECONDS", 1800)))
            now_ts = int(time.time())
            last_raw = request.session.get(self.SESSION_ACTIVITY_KEY)
            last_ts = None

            if last_raw is not None:
                try:
                    last_ts = int(last_raw)
                except (TypeError, ValueError):
                    last_ts = None
                if last_ts is not None and (now_ts - last_ts) > idle_limit:
                    auth_logout(request)
                    if self._wants_json(request):
                        return JsonResponse(
                            {
                                "error": {
                                    "code": "session_expired",
                                    "message": "Your session expired due to inactivity. Please sign in again.",
                                }
                            },
                            status=401,
                        )
                    next_url = quote(request.get_full_path(), safe="")
                    return redirect(f"/accounts/login/?logged_out=1&next={next_url}")

            if last_ts is None or (now_ts - last_ts) >= 15:
                request.session[self.SESSION_ACTIVITY_KEY] = now_ts

        return self.get_response(request)
