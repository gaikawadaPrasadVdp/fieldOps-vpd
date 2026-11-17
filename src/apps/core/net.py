"""Client network identity helpers shared by django-axes (login throttling) and the audit log.

Why this exists (incident 2026-10-03): behind Nginx every request has REMOTE_ADDR = the proxy, so per-IP
throttling treated all users as one client. ``client_ip`` honours X-Forwarded-For ONLY for the number of trusted
proxy hops configured in ``TRUSTED_PROXY_COUNT`` (0 = ignore the header entirely, so it cannot be spoofed).
"""
import ipaddress

from django.conf import settings


def _valid(value: str) -> str | None:
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def client_ip(request) -> str | None:
    remote = _valid(request.META.get("REMOTE_ADDR", "")) if request.META.get("REMOTE_ADDR") else None
    hops = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
    if hops > 0:
        # Each trusted proxy appends the address it received the request from; the client is `hops` entries
        # from the right. Anything the client itself put at the left of the header is ignored.
        chain = [p for p in request.META.get("HTTP_X_FORWARDED_FOR", "").split(",") if p.strip()]
        if len(chain) >= hops:
            candidate = _valid(chain[-hops])
            if candidate:
                return candidate
    return remote


def axes_username(request, credentials=None) -> str | None:
    """Username used by django-axes for lockout bookkeeping: the credential Django passes to authenticate()
    (key ``username``, even though our USERNAME_FIELD is ``email``), normalised so that case/whitespace
    variants cannot dodge the failure counter."""
    value = None
    if credentials and isinstance(credentials, dict):
        value = credentials.get("username") or credentials.get("email")
    if value is None and request:
        data = getattr(request, "data", None) or getattr(request, "POST", None)
        if data and hasattr(data, "get"):
            value = data.get("username") or data.get("email")
        if value is None:
            # For JSON API requests (like /api/v1/auth/token/) where DRF hasn't yet parsed request.data
            try:
                body = getattr(request, "_body", None)
                if body is None and hasattr(request, "body"):
                    body = request.body
                if body:
                    import json
                    payload = json.loads(body.decode("utf-8", errors="replace"))
                    if isinstance(payload, dict):
                        value = payload.get("username") or payload.get("email")
            except Exception:
                pass
    return value.strip().lower()[:254] if isinstance(value, str) and value.strip() else None


_SUPPRESSED_EMAIL_SUFFIXES = (
    "@example.com",
    ".example",
    ".example.com",
    ".test",
    ".invalid",
    ".local",
)


def is_suppressed_test_email(email: str) -> bool:
    """Return True when ``email`` belongs to a reserved/test domain and should not trigger real SMTP."""
    from django.conf import settings

    email_backend = getattr(settings, "EMAIL_BACKEND", "").lower()
    if "locmem" in email_backend:
        return False
    cleaned = (email or "").strip().lower()
    return bool(cleaned) and any(cleaned.endswith(suffix) for suffix in _SUPPRESSED_EMAIL_SUFFIXES)
