import re
import time
import uuid
import zoneinfo

from django.conf import settings
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
                flogging.request_id_var.reset(token)
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
