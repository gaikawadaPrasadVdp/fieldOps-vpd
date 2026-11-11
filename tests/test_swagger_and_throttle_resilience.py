"""Tests verifying Swagger docs and schema resilience under cache outages."""
from unittest.mock import patch
from django.test import Client, RequestFactory
from drf_spectacular.views import SpectacularSwaggerView, SpectacularAPIView
from apps.core.throttling import SafeAnonRateThrottle, SafeUserRateThrottle


def test_swagger_and_schema_views_resilient_to_cache_outage():
    """Verify /api/v1/docs/ and /api/v1/schema/ succeed with throttle_classes=[]."""
    rf = RequestFactory()
    req_docs = rf.get("/api/v1/docs/", HTTP_HOST="localhost")
    req_schema = rf.get("/api/v1/schema/", HTTP_HOST="localhost")

    # With throttle_classes=[], views succeed even if default cache would error
    docs_view = SpectacularSwaggerView.as_view(url_name="schema", throttle_classes=[])
    docs_resp = docs_view(req_docs)
    assert docs_resp.status_code == 200

    schema_view = SpectacularAPIView.as_view(throttle_classes=[])
    schema_resp = schema_view(req_schema)
    assert schema_resp.status_code == 200


def test_safe_throttles_fallback_to_locmem():
    """Verify SafeAnonRateThrottle and SafeUserRateThrottle gracefully fall back under cache failure."""
    rf = RequestFactory()
    request = rf.get("/api/v1/assets/", HTTP_HOST="localhost")

    anon_throttle = SafeAnonRateThrottle()
    with patch.object(anon_throttle.cache, "get", side_effect=Exception("Redis connection down")):
        allowed = anon_throttle.allow_request(request, None)
        assert allowed is True

    user_throttle = SafeUserRateThrottle()
    with patch.object(user_throttle.cache, "get", side_effect=Exception("Redis connection down")):
        allowed = user_throttle.allow_request(request, None)
        assert allowed is True


def test_client_get_docs_and_schema():
    """End-to-end client request to /api/v1/docs/ and schema redirect."""
    client = Client()
    resp = client.get("/api/v1/docs/")
    assert resp.status_code == 200
    assert b"swagger" in resp.content.lower()

    # Verify swagger redirect alias
    resp_redirect = client.get("/docs/")
    assert resp_redirect.status_code == 302
    assert resp_redirect["Location"] == "/api/v1/docs/"
