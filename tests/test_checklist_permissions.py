"""Unit tests for checklist view permissions and TenantPermissionMixin multi-permission support."""
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.views import View

from apps.checklists.views import TemplateDetailView, TemplateListView
from apps.ui.mixins import TenantPermissionMixin


class DummyMultiPermView(TenantPermissionMixin, View):
    required_permissions = ("checklist.view", "checklist.execute", "inspection.execute")

    def get(self, request):
        return "OK"


class DummySinglePermView(TenantPermissionMixin, View):
    required_permission = "checklist.view"

    def get(self, request):
        return "OK"


def test_tenant_permission_mixin_single_perm():
    factory = RequestFactory()
    request = factory.get("/test/")
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()

    view = DummySinglePermView.as_view()

    with patch("apps.rbac.services.has_permission_anywhere", return_value=True):
        resp = view(request)
        assert resp == "OK"

    with patch("apps.rbac.services.has_permission_anywhere", return_value=False):
        with pytest.raises(PermissionDenied):
            view(request)


def test_tenant_permission_mixin_multi_permissions():
    factory = RequestFactory()
    request = factory.get("/test/")
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()

    view = DummyMultiPermView.as_view()

    # User only has checklist.execute
    def mock_has_perm(membership, code):
        return code == "checklist.execute"

    with patch("apps.rbac.services.has_permission_anywhere", side_effect=mock_has_perm):
        resp = view(request)
        assert resp == "OK"

    # User has none of the permissions
    with patch("apps.rbac.services.has_permission_anywhere", return_value=False):
        with pytest.raises(PermissionDenied):
            view(request)


def test_template_list_view_allows_technician_with_execute_permission():
    factory = RequestFactory()
    request = factory.get("/app/checklists/")
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()
    request.organization = MagicMock()

    view = TemplateListView()

    # Simulate technician who only holds checklist.execute
    def mock_has_perm(membership, code):
        return code == "checklist.execute"

    with patch("apps.rbac.services.has_permission_anywhere", side_effect=mock_has_perm), \
         patch("apps.checklists.selectors.templates_for") as mock_templates, \
         patch("apps.checklists.selectors.filter_templates") as mock_filter, \
         patch("apps.checklists.views.render") as mock_render, \
         patch("apps.checklists.views.Inspection") as mock_insp, \
         patch("apps.checklists.views.Finding") as mock_finding:
        
        mock_templates.return_value.count.return_value = 5
        mock_templates.return_value.filter.return_value.count.return_value = 3
        mock_filter.return_value = []
        mock_render.return_value = "rendered_response"

        resp = view.dispatch(request)
        assert resp == "rendered_response"
        assert view.required_permission == "checklist.execute"


def test_template_detail_view_allows_technician_with_execute_permission():
    factory = RequestFactory()
    request = factory.get("/app/checklists/template-123/")
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()
    request.organization = MagicMock()

    view = TemplateDetailView()

    # Simulate technician who only holds inspection.execute
    def mock_has_perm(membership, code):
        return code == "inspection.execute"

    with patch("apps.rbac.services.has_permission_anywhere", side_effect=mock_has_perm), \
         patch("apps.checklists.views._template") as mock_template, \
         patch("apps.checklists.selectors.items_for", return_value=[]), \
         patch("apps.checklists.views.render") as mock_render:
        
        t = MagicMock()
        t.status = "ACTIVE"
        t.inspections.count.return_value = 2
        mock_template.return_value = t
        mock_render.return_value = "rendered_detail"

        resp = view.dispatch(request, pk="template-123")
        assert resp == "rendered_detail"
        assert view.required_permission == "inspection.execute"


def test_template_list_view_denies_user_without_checklist_or_inspection_permission():
    factory = RequestFactory()
    request = factory.get("/app/checklists/")
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()
    request.organization = MagicMock()

    view = TemplateListView()

    with patch("apps.rbac.services.has_permission_anywhere", return_value=False):
        with pytest.raises(PermissionDenied):
            view.dispatch(request)
