import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.core import tenant
from apps.rbac import services as rbac

from . import access
from .models import Attachment


def _authenticate_request(request):
    """Authenticate request using either existing session, JWT Bearer header, or token query param."""
    if getattr(request, "user", None) and request.user.is_authenticated:
        return
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION") or ""
    token_str = ""
    if auth_header.startswith("Bearer "):
        token_str = auth_header[7:].strip()
    elif "token" in request.GET:
        token_str = request.GET["token"].strip()

    if token_str:
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication
            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token_str)
            user = jwt_auth.get_user(validated_token)
            if user and user.is_active:
                request.user = user
                from apps.tenancy import selectors as tenant_selectors
                header = request.headers.get(getattr(settings, "ORGANIZATION_HEADER", "X-Organization")) or request.META.get("HTTP_X_ORGANIZATION")
                membership = tenant_selectors.resolve_membership(user, org_key=header)
                if membership:
                    request.membership = membership
                    request.organization = membership.organization
                    tenant.set_current(membership.organization)
        except Exception:
            pass


@require_GET
def download(request, pk):
    """Tenant-scoped (default manager) + per-attachment read permission; always served as a download.
    Supports both browser sessions and API JWT Bearer token downloads (SMK-INT-005)."""
    _authenticate_request(request)

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
        if auth_header or request.headers.get("Accept", "").find("application/json") != -1:
            return JsonResponse({"error": {"code": "unauthorized", "message": "Authentication required."}}, status=401)
        login_url = getattr(settings, "LOGIN_URL", "/accounts/login/")
        return HttpResponseRedirect(f"{login_url}?next={request.path}")

    if request.membership is None:
        from apps.tenancy import selectors as tenant_selectors
        header = request.headers.get(getattr(settings, "ORGANIZATION_HEADER", "X-Organization")) or request.META.get("HTTP_X_ORGANIZATION")
        membership = tenant_selectors.resolve_membership(request.user, org_key=header)
        if membership:
            request.membership = membership
            request.organization = membership.organization
            tenant.set_current(membership.organization)

    if request.membership is None:
        raise PermissionDenied("Active membership required.")

    try:
        att = Attachment.objects.for_organization(request.organization).get(pk=uuid.UUID(str(pk)))
    except (Attachment.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    checker = access.checker_for(f"{att.content_type.app_label}.{att.content_type.model}")
    if checker is not None:
        target = att.target
        if target is None or not access.allowed(checker, request.membership, target, att):
            raise Http404  # out of scope looks the same as absent
    elif att.read_permission and not rbac.has_permission(request.membership, att.read_permission):
        raise PermissionDenied
    response = FileResponse(att.file.open("rb"), as_attachment=True, filename=att.original_name,
                            content_type="application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response
