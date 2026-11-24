"""API foundation: pagination + uniform error envelope.

Error envelope (every non-2xx JSON response):
    {"error": {"code": "...", "message": "...", "details": {...}, "request_id": "..."}}
"""
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions as drf
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from . import logging as flogging
from .exceptions import DomainError


class StandardPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_page_size(self, request):
        params = getattr(request, "query_params", getattr(request, "GET", {}))
        if self.page_size_query_param and self.page_size_query_param in params:
            raw_val = params[self.page_size_query_param]
            try:
                val = int(raw_val)
                if val <= 0:
                    from apps.core.exceptions import ValidationFailed
                    raise ValidationFailed("page_size must be a positive integer.", code="invalid_page_size")
                if self.max_page_size and val > self.max_page_size:
                    from apps.core.exceptions import ValidationFailed
                    raise ValidationFailed(
                        f"page_size cannot exceed maximum allowed limit of {self.max_page_size}.",
                        code="invalid_page_size",
                    )
                return val
            except (TypeError, ValueError):
                from apps.core.exceptions import ValidationFailed
                raise ValidationFailed("page_size must be a valid integer.", code="invalid_page_size")
        return self.page_size


def _envelope(code, message, details=None):
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
            "request_id": flogging.request_id_var.get(),
        }
    }


def exception_handler(exc, context):
    if isinstance(exc, DomainError):
        return Response(_envelope(exc.code, exc.message, exc.details), status=exc.status_code)
    if isinstance(exc, DjangoPermissionDenied):
        exc = drf.PermissionDenied()
    if isinstance(exc, Http404):
        exc = drf.NotFound()

    response = drf_exception_handler(exc, context)
    if response is None:
        return None  # unhandled -> Django 500 handling + logging

    def _clean_msg(detail):
        if isinstance(detail, dict):
            if "detail" in detail:
                return _clean_msg(detail["detail"])
            for v in detail.values():
                return _clean_msg(v)
        elif isinstance(detail, (list, tuple)) and detail:
            return _clean_msg(detail[0])
        return str(detail)

    if isinstance(exc, drf.ValidationError):
        code, message, details = "validation_failed", "Validation failed.", {"fields": response.data}
    elif isinstance(exc, drf.NotAuthenticated | drf.AuthenticationFailed):
        exc_code = None
        if isinstance(exc.detail, dict):
          exc_code = exc.detail.get("code")
        if not exc_code:
          exc_code = getattr(exc.detail, "code", None)
        if exc_code == "token_not_valid":
          code = "token_not_valid"
          msg_str = "Token is invalid or expired."
          if isinstance(exc.detail, dict) and "messages" in exc.detail:
            msgs = exc.detail["messages"]
            if isinstance(msgs, list) and msgs:
              m0 = msgs[0]
              if isinstance(m0, dict) and "message" in m0:
                msg_str = str(m0["message"])
          message, details = msg_str, {}
        else:
          code, message, details = (
              "not_authenticated",
              _clean_msg(exc.detail),
              {},
          )
    elif isinstance(exc, drf.PermissionDenied):
        code = getattr(exc.detail, "code", None) or getattr(exc, "default_code", "permission_denied")
        message, details = _clean_msg(exc.detail), {}
    elif isinstance(exc, drf.NotFound):
        code, message, details = "not_found", "Not found.", {}
    elif isinstance(exc, drf.Throttled):
        code, message, details = "throttled", "Too many requests.", {"retry_after": exc.wait}
    else:
        code = getattr(exc, "default_code", "error")
        message, details = _clean_msg(getattr(exc, "detail", exc)), {}
    response.data = _envelope(code, message, details)
    return response
