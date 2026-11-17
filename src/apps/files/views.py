import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.core import tenant
from apps.core.exceptions import PermissionDenied as DomainPermissionDenied
from apps.rbac import services as rbac

from . import access
from .models import Attachment

logger = logging.getLogger(__name__)


def _wants_json(request) -> bool:
    auth_header = request.headers.get("Authorization") or request.META.get("HTTP_AUTHORIZATION")
    return bool(auth_header or "application/json" in request.headers.get("Accept", ""))


def _ensure_membership(request, org_hint: str | None = None):
    if getattr(request, "membership", None) is not None:
        return request.membership
    from apps.tenancy import selectors as tenant_selectors

    header = (
        request.headers.get(getattr(settings, "ORGANIZATION_HEADER", "X-Organization"))
        or request.META.get("HTTP_X_ORGANIZATION")
    )
    try:
        membership = tenant_selectors.resolve_membership(request.user, org_key=header or org_hint)
    except DomainPermissionDenied as exc:
        raise PermissionDenied(exc.message) from exc
    if membership is not None:
        request.membership = membership
        request.organization = membership.organization
        tenant.set_current(membership.organization)
    return membership


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
                _ensure_membership(request)
        except Exception:
            pass


@require_GET
def download(request, pk):
    """Tenant-scoped (default manager) + per-attachment read permission; always served as a download.
    Supports both browser sessions and API JWT Bearer token downloads (SMK-INT-005)."""
    _authenticate_request(request)

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        if _wants_json(request):
            return JsonResponse({"error": {"code": "unauthorized", "message": "Authentication required."}}, status=401)
        login_url = reverse(settings.LOGIN_URL) if hasattr(settings, "LOGIN_URL") and ":" in settings.LOGIN_URL else getattr(settings, "LOGIN_URL", "/accounts/login/")
        return HttpResponseRedirect(f"{login_url}?next={request.path}")

    _ensure_membership(request)
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
    try:
        file_handle = att.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("Stored file is not available.") from exc
    except Exception as exc:
        err_code = getattr(exc, "response", {}).get("Error", {}).get("Code", "") if hasattr(exc, "response") else ""
        if err_code in {"NoSuchKey", "404", "NotFound"}:
            raise Http404("Stored file is not available.") from exc
        logger.exception("Failed to open attachment %s: %s", att.pk, exc)
        raise Http404("Stored file could not be read.") from exc
    response = FileResponse(file_handle, as_attachment=True, filename=att.original_name,
                            content_type="application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response


def protected_media_serve(request, path, document_root=None, show_indexes=False):
    """Secure media file server enforcing authentication and tenant isolation (SEC-05)."""
    from django.views.static import serve as django_static_serve

    document_root = document_root or settings.MEDIA_ROOT
    normalized = Path(path).as_posix().lstrip("/")
    parts = [p for p in normalized.split("/") if p]
    if not parts or ".." in parts:
        raise Http404("Media file not found.")

    # Non-tenant paths cannot contain org media: return controlled 404 before auth redirect
    # so probes for missing files (e.g. /media/smk-missing-file.txt) receive 404 instead of 200 Login HTML.
    if parts[0] != "organizations":
        root_path = Path(document_root).resolve()
        candidate = (root_path / normalized).resolve()
        try:
            candidate.relative_to(root_path)
        except ValueError as exc:
            raise Http404("Media file not found.") from exc
        if not candidate.is_file():
            raise Http404("Media file not found.")

    _authenticate_request(request)

    if not getattr(request, "user", None) or not request.user.is_authenticated:
        if _wants_json(request):
            return JsonResponse({"error": {"code": "unauthorized", "message": "Authentication required to access media."}}, status=401)
        login_url = reverse(settings.LOGIN_URL) if hasattr(settings, "LOGIN_URL") and ":" in settings.LOGIN_URL else getattr(settings, "LOGIN_URL", "/accounts/login/")
        return HttpResponseRedirect(f"{login_url}?next={request.path}")

    # If media is stored under organizations/<org_id>/...
    if len(parts) >= 2 and parts[0] == "organizations":
        target_org_id = parts[1]
        try:
            target_org_uuid = uuid.UUID(target_org_id)
        except ValueError as exc:
            raise Http404("Invalid organization identifier in media path.") from exc

        _ensure_membership(request, org_hint=str(target_org_uuid))

        if not request.user.is_superuser and not getattr(request.user, "is_platform_admin", False):
            if request.membership is None or request.membership.organization_id != target_org_uuid:
                raise PermissionDenied("You do not have permission to access media for this organization.")

    return django_static_serve(request, path, document_root=document_root, show_indexes=show_indexes)
