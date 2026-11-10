"""Resilient rate throttling with graceful fallback during cache outages."""
from __future__ import annotations

import logging
from django.core.cache.backends.locmem import LocMemCache
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

logger = logging.getLogger("django.request")

_FALLBACK_THROTTLE_CACHE = LocMemCache("fieldops-throttle-fallback", {})


class SafeAnonRateThrottle(AnonRateThrottle):
    """Anonymous rate throttle tolerant of Redis/cache connection outages."""

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as exc:
            logger.warning("Primary cache throttle failed for anon user (%s); using in-memory fallback.", exc)
            self.cache = _FALLBACK_THROTTLE_CACHE
            try:
                return super().allow_request(request, view)
            except Exception:
                return True


class SafeUserRateThrottle(UserRateThrottle):
    """Authenticated user rate throttle tolerant of Redis/cache connection outages."""

    def allow_request(self, request, view):
        try:
            return super().allow_request(request, view)
        except Exception as exc:
            logger.warning("Primary cache throttle failed for authenticated user (%s); using in-memory fallback.", exc)
            self.cache = _FALLBACK_THROTTLE_CACHE
            try:
                return super().allow_request(request, view)
            except Exception:
                return True
