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
        login_url = reverse(settings.LOGIN_URL) if hasattr(settings, "LOGIN_URL") and ":" in settings.LOGIN_URL else getattr(settings, "LOGIN_URL", "/accounts/login/")
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



def protected_media_serve(request, path, document_root=None, show_indexes=False):
    """Secure media file server enforcing authentication and tenant isolation (SEC-05)."""
    from django.views.static import serve as django_static_serve
    from pathlib import Path

    document_root = document_root or settings.MEDIA_ROOT
    _authenticate_request(request)

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
        if auth_header or "application/json" in request.headers.get("Accept", ""):
            return JsonResponse({"error": {"code": "unauthorized", "message": "Authentication required to access media."}}, status=401)
        login_url = reverse(settings.LOGIN_URL) if hasattr(settings, "LOGIN_URL") and ":" in settings.LOGIN_URL else getattr(settings, "LOGIN_URL", "/accounts/login/")
        return HttpResponseRedirect(f"{login_url}?next={request.path}")

    # Normalize path and prevent path traversal
    normalized = Path(path).as_posix().lstrip("/")
    parts = normalized.split("/")

    # If media is stored under organizations/<org_id>/...
    if len(parts) >= 2 and parts[0] == "organizations":
        target_org_id = parts[1]
        try:
            target_org_uuid = uuid.UUID(target_org_id)
        except ValueError:
            raise Http404("Invalid organization identifier in media path.")

        # Resolve user's active membership
        if request.membership is None:
            from apps.tenancy import selectors as tenant_selectors
            header = request.headers.get(getattr(settings, "ORGANIZATION_HEADER", "X-Organization")) or request.META.get("HTTP_X_ORGANIZATION")
            request.membership = tenant_selectors.resolve_membership(request.user, org_key=header or str(target_org_uuid))

        if not request.user.is_superuser and not getattr(request.user, "is_platform_admin", False):
            if request.membership is None or request.membership.organization_id != target_org_uuid:
                raise PermissionDenied("You do not have permission to access media for this organization.")

    return django_static_serve(request, path, document_root=document_root, show_indexes=show_indexes)
