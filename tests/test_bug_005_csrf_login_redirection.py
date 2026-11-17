"""Regression tests for Bug-005:
CSRF verification failed (403 Forbidden) error thrown on standard credential submission and redirection.
"""
import re
import pytest
from django.test import Client
from apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_bug_005_login_with_csrf_enforcement_and_logged_out_redirect():
    """Verify that visiting /accounts/login/?logged_out=1&next=... with enforce_csrf_checks=True

    and submitting credentials succeeds without 403 Forbidden CSRF failure.
    """
    user = User.objects.create_user(email="storesorInventory@nexus.test", password="SecurePassword@123")

    client = Client(enforce_csrf_checks=True)

    # 1. User arrives at login page after logout / redirect with query parameters
    url = "/accounts/login/?logged_out=1&next=/app/work-orders/"
    get_resp = client.get(url, HTTP_HOST="fieldops-qry5.onrender.com")
    assert get_resp.status_code == 200

    html = get_resp.content.decode()

    # 2. Extract CSRF token from rendered HTML form
    match = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', html)
    assert match is not None, "CSRF token input not found in login form"
    csrf_token = match.group(1)

    # 3. Verify csrftoken cookie is present
    assert "csrftoken" in client.cookies
    assert client.cookies["csrftoken"].value

    # 4. Submit login credentials with query parameters in form action and Referer from render domain
    post_resp = client.post(
        url,
        {
            "username": "storesorInventory@nexus.test",
            "password": "SecurePassword@123",
            "csrfmiddlewaretoken": csrf_token,
            "next": "/app/work-orders/",
        },
        HTTP_HOST="fieldops-qry5.onrender.com",
        HTTP_REFERER="https://fieldops-qry5.onrender.com/accounts/login/?logged_out=1&next=/app/work-orders/",
        HTTP_ORIGIN="https://fieldops-qry5.onrender.com",
    )

    # Must succeed (302 redirect), NOT throw 403 Forbidden CSRF verification failed
    assert post_resp.status_code == 302, f"Expected 302 redirect on login, got {post_resp.status_code}"
    assert post_resp.url == "/app/work-orders/"


def test_bug_005_login_with_staging_origin_onrender():
    """Verify CSRF verification succeeds for all .onrender.com origins (e.g. fieldops-vpd-nb4u.onrender.com)."""
    user = User.objects.create_user(email="staging.user@nexus.test", password="SecurePassword@123")

    client = Client(enforce_csrf_checks=True)

    url = "/accounts/login/"
    get_resp = client.get(url, HTTP_HOST="fieldops-vpd-nb4u.onrender.com")
    assert get_resp.status_code == 200

    html = get_resp.content.decode()
    match = re.search(r'name=["\']csrfmiddlewaretoken["\']\s+value=["\']([^"\']+)["\']', html)
    csrf_token = match.group(1)

    post_resp = client.post(
        url,
        {
            "username": "staging.user@nexus.test",
            "password": "SecurePassword@123",
            "csrfmiddlewaretoken": csrf_token,
            "next": "/app/",
        },
        HTTP_HOST="fieldops-vpd-nb4u.onrender.com",
        HTTP_REFERER="https://fieldops-vpd-nb4u.onrender.com/accounts/login/",
        HTTP_ORIGIN="https://fieldops-vpd-nb4u.onrender.com",
    )

    assert post_resp.status_code == 302, f"Expected 302 redirect on login, got {post_resp.status_code}"
