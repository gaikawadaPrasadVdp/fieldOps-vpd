"""Comprehensive test suite verifying FieldOps Nexus Application Performance Optimizations."""
import uuid
from unittest.mock import MagicMock, patch
import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import RequestFactory

from apps.ui.context_processors import shell
from apps.workspace.views import MyJobsView
from apps.workorders.models import WorkOrder


def test_session_engine_configured_for_cached_db():
    """Verify SESSION_ENGINE uses cached_db to eliminate redundant session DB queries."""
    assert settings.SESSION_ENGINE == "django.contrib.sessions.backends.cached_db"
    assert getattr(settings, "SESSION_CACHE_ALIAS", "default") == "default"


def test_workorder_composite_indexes_exist():
    """Verify WorkOrder model includes composite indexes for tenant, assignee, site and status."""
    index_names = {idx.name: idx.fields for idx in WorkOrder._meta.indexes if idx.name}
    assert "wo_org_asgn_stat_idx" in index_names
    assert index_names["wo_org_asgn_stat_idx"] == ["organization", "assigned_to", "status"]

    assert "wo_org_site_stat_idx" in index_names
    assert index_names["wo_org_site_stat_idx"] == ["organization", "site", "status"]


def test_my_jobs_view_htmx_bypasses_counts_and_capacity():
    """Verify HTMX partial requests skip count aggregation and capacity calculations for maximum speed."""
    rf = RequestFactory()
    req = rf.get("/app/workspace/", HTTP_HX_REQUEST="true")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)

    membership = MagicMock()
    membership.pk = uuid.uuid4()
    membership.is_active = True
    membership.portal_account = None
    membership.organization = MagicMock(pk=uuid.uuid4())
    req.membership = membership
    req.organization = membership.organization

    view = MyJobsView()

    with patch("apps.workspace.views.selectors.my_jobs") as mock_my_jobs, \
         patch("apps.workspace.views.selectors.daily_capacity_summary") as mock_capacity, \
         patch("apps.workspace.views.paginate_dashboard_queryset") as mock_paginate, \
         patch("apps.workspace.views.render") as mock_render, \
         patch("apps.rbac.services.has_permission", return_value=True):

        mock_page = MagicMock()
        mock_page.object_list = []
        mock_paginate.return_value = (mock_page, "")
        mock_render.return_value = MagicMock(status_code=200)

        view.get(req)

        # In HTMX requests, daily_capacity_summary must NOT be called
        mock_capacity.assert_not_called()

        # In HTMX requests, selectors.my_jobs should only be called once for the list query, not for 4 counts
        assert mock_my_jobs.call_count == 1

        # Rendered template must be the partial
        assert mock_render.call_args[0][1] == "workspace/_jobs_list_partial.html"
        ctx = mock_render.call_args[0][2]
        assert ctx["active_count"] == 0
        assert ctx["capacity"] is None


def test_my_jobs_view_full_render_uses_single_aggregation():
    """Verify non-HTMX full page render calculates all counts in a single aggregate query."""
    rf = RequestFactory()
    req = rf.get("/app/workspace/")
    req.user = MagicMock(is_authenticated=True, is_platform_admin=False)

    membership = MagicMock()
    membership.pk = uuid.uuid4()
    membership.is_active = True
    membership.portal_account = None
    membership.organization = MagicMock(pk=uuid.uuid4())
    req.membership = membership
    req.organization = membership.organization

    view = MyJobsView()

    aggregate_result = {
        "active": 5,
        "upcoming": 3,
        "completed": 12,
        "total": 20,
    }

    with patch("apps.workspace.views.selectors.my_jobs") as mock_my_jobs, \
         patch("apps.workspace.views.selectors.daily_capacity_summary") as mock_capacity, \
         patch("apps.workspace.views.paginate_dashboard_queryset") as mock_paginate, \
         patch.object(WorkOrder.objects, "for_organization") as mock_for_org, \
         patch("apps.workspace.views.render") as mock_render, \
         patch("apps.rbac.services.has_permission", return_value=True):

        mock_page = MagicMock()
        mock_page.object_list = []
        mock_paginate.return_value = (mock_page, "")
        mock_render.return_value = MagicMock(status_code=200)
        mock_capacity.return_value = {"total_logged_hours": 4.0}

        mock_filter = MagicMock()
        mock_filter.aggregate.return_value = aggregate_result
        mock_for_org.return_value.filter.return_value = mock_filter

        view.get(req)

        # Verify single aggregate was called on WorkOrder queryset
        mock_for_org.return_value.filter.assert_called_once_with(assigned_to=membership)
        mock_filter.aggregate.assert_called_once()

        # Rendered template must be the full page
        assert mock_render.call_args[0][1] == "workspace/my_jobs.html"
        ctx = mock_render.call_args[0][2]
        assert ctx["active_count"] == 5
        assert ctx["upcoming_count"] == 3
        assert ctx["completed_count"] == 12
        assert ctx["all_count"] == 20
        assert ctx["capacity"] == {"total_logged_hours": 4.0}


def test_sidebar_navigation_caching_and_active_isolation():
    """Verify shell navigation caches the structure per membership but cleanly resolves active states."""
    cache.clear()
    rf = RequestFactory()
    req_home = rf.get("/app/")
    req_home.user = MagicMock(is_authenticated=True, is_platform_admin=False)

    member_id = uuid.uuid4()
    membership = MagicMock()
    membership.pk = member_id
    membership.is_active = True
    membership.portal_account = None
    membership.is_owner = True
    req_home.membership = membership
    req_home.active_memberships = []
    req_home.organization = MagicMock(name="Acme Corp")
    req_home.tenant_error = None

    from apps.rbac import services as rbac
    from apps.rbac.models import MembershipRole
    from apps.ui.context_processors import _build_tenant_nav

    with patch.object(rbac, "is_owner", return_value=True), \
         patch.object(MembershipRole.objects, "filter") as mock_role_filter, \
         patch("apps.ui.context_processors.is_client_membership", return_value=False), \
         patch("apps.ui.context_processors._build_tenant_nav", side_effect=_build_tenant_nav) as mock_build_nav:

        mock_role_filter.return_value.values_list.return_value = ["admin"]

        # First request (cache miss: _build_tenant_nav runs)
        ctx1 = shell(req_home)
        assert mock_build_nav.call_count == 1
        assert ctx1["shell_nav_sections"]["Overview"][0].get("active") is True

        # Second request to a different URL (cache hit: _build_tenant_nav bypassed!)
        req_orders = rf.get("/app/work-orders/")
        req_orders.user = req_home.user
        req_orders.membership = membership
        req_orders.active_memberships = []
        req_orders.organization = req_home.organization
        req_orders.tenant_error = None

        ctx2 = shell(req_orders)
        # _build_tenant_nav was NOT called again (cached!)
        assert mock_build_nav.call_count == 1

        # Verify active state resolved correctly for /app/work-orders/ on the cloned cached copy
        overview_item = ctx2["shell_nav_sections"]["Overview"][0]
        workorders_item = ctx2["shell_nav_sections"]["Operations"][1]
        assert overview_item.get("active") is not True
        assert workorders_item.get("active") is True


def test_redis_url_sanitization():
    """Verify that REDIS_URL without scheme or invalid placeholder falls back safely."""
    from config.settings.base import _VALID_REDIS_SCHEMES
    schemes = _VALID_REDIS_SCHEMES

    def sanitize(raw):
        raw = raw.strip()
        if raw and any(raw.startswith(s) for s in schemes):
            return raw
        elif raw and ":" in raw and " " not in raw and not raw.startswith(("http://", "https://")):
            return f"redis://{raw}"
        return ""

    assert sanitize("redis://default:secret@host:6379") == "redis://default:secret@host:6379"
    assert sanitize("rediss://host:6379") == "rediss://host:6379"
    assert sanitize("host.internal:6379") == "redis://host.internal:6379"
    assert sanitize("none") == ""
    assert sanitize("") == ""
