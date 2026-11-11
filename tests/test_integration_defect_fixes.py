"""Test suite verifying resolutions for integration test defects DEF-001, DEF-002, DEF-003."""
import uuid
from datetime import date
from unittest.mock import MagicMock, patch
import pytest
from rest_framework.test import APIRequestFactory

from apps.workspace.serializers import ShiftWriteSerializer
from apps.contracts import services as contract_services
from apps.checklists.api_views import InspectionViewSet
from apps.core.exceptions import PermissionDenied
from apps.tenancy.models import Organization
from apps.assets.models import Asset
from apps.workorders.models import WorkOrder


def test_def_001_shift_identical_start_end_time_validation():
    """DEF-001: Identical start_time and end_time raises serializer ValidationError."""
    data = {
        "code": "NIGHT",
        "name": "Night Shift",
        "start_time": "09:00:00",
        "end_time": "09:00:00",
        "days_of_week": [0, 1, 2],
    }
    ser = ShiftWriteSerializer(data=data)
    assert not ser.is_valid()
    assert "start_time" in ser.errors
    assert "Shift start and end time cannot be identical." in str(ser.errors["start_time"])


def test_def_002_coverage_check_with_null_work_type():
    """DEF-002: WorkOrder with null/empty work_type defaults work_type to 'OTHER' and does not crash."""
    org = Organization(id=uuid.uuid4(), name="Test Org", slug="test-org")
    asset = Asset(id=uuid.uuid4(), organization=org, asset_tag="TAG-01", name="Test Asset")
    wo = WorkOrder(id=uuid.uuid4(), organization=org, asset=asset, work_type=None)

    mock_result = MagicMock()
    mock_result.best = None
    mock_result.eligible = False
    mock_result.reason = "No coverage found"

    # Use __wrapped__ to call record_check without triggering DB transaction.atomic
    func = getattr(contract_services.record_check, "__wrapped__", contract_services.record_check)

    with patch("apps.contracts.services.reference_date_for", return_value=date(2026, 11, 10)), \
         patch("apps.contracts.services.evaluate", return_value=mock_result) as mock_eval, \
         patch("apps.contracts.services.CoverageCheck.save"), \
         patch("apps.audit.services.record"):

        check = func(wo, actor=None)
        assert check.work_type == "OTHER"
        mock_eval.assert_called_once_with(org, asset, date(2026, 11, 10), "OTHER")


def test_def_003_inspections_requirements_portal_client_denied():
    """DEF-003: Portal clients calling requirements endpoint receive 403 PermissionDenied, not 500 NameError."""
    rf = APIRequestFactory()
    req = rf.get("/api/v1/inspections/requirements/")
    
    membership = MagicMock()
    membership.is_active = True
    req.membership = membership
    req.organization = MagicMock()
    req.user = MagicMock()

    view = InspectionViewSet()
    view.request = req

    with patch("apps.portal.services.is_portal_client", return_value=True):
        with pytest.raises(PermissionDenied) as exc_info:
            view.requirements(req)

    assert "Portal clients cannot access inspection requirements" in str(exc_info.value)


def test_avatar_initials_filter():
    """Verify avatar_initials template filter extracts standard 2-letter uppercase initials."""
    from apps.ui.templatetags.ui_tags import avatar_initials

    assert avatar_initials("John Doe") == "JD"
    assert avatar_initials("Jane Marie Doe") == "JD"
    assert avatar_initials("Alice") == "AL"
    assert avatar_initials("admin@example.com") == "AD"
    assert avatar_initials("jane.smith@fieldops.local") == "JS"
    assert avatar_initials("") == ""
    assert avatar_initials(None) == ""


def test_sidebar_fixed_layout_css():
    """Verify .fx-sidebar has position: fixed and .fx-main has margin-left offset for desktop."""
    with open("src/static/css/app.css", "r", encoding="utf-8") as f:
        css = f.read()

    assert ".fx-sidebar {" in css
    assert "position: fixed;" in css
    assert "margin-left: var(--fx-sidebar-w)" in css


def test_asset_manager_role_template_includes_inspection_and_checklist_views():
    """Verify Asset Manager template includes checklist.view and inspection.view."""
    from apps.rbac.role_templates import TEMPLATES

    asset_mgr = next((t for t in TEMPLATES if t.key == "asset_manager"), None)
    assert asset_mgr is not None
    assert "checklist.view" in asset_mgr.patterns
    assert "inspection.view" in asset_mgr.patterns



def test_asset_create_view_child_cannot_be_parent_handles_gracefully():
    """Verify AssetCreateView catches ValidationFailed when parent is already a child, redirecting instead of 500."""
    from apps.assets.views import AssetCreateView
    from apps.core.exceptions import ValidationFailed
    from django.test import RequestFactory
    from unittest.mock import MagicMock, patch

    rf = RequestFactory()
    req = rf.get("/app/assets/new/?parent=0fb0e8a1-47fc-4eb2-9b66-71f9b434010a")
    req.user = MagicMock()
    req.membership = MagicMock()
    req.organization = MagicMock()
    req._messages = MagicMock()

    view = AssetCreateView()
    view.request = req

    with patch.object(view, "_parent", side_effect=ValidationFailed("Cannot create a child under component.", code="child_cannot_be_parent")), \
         patch("apps.assets.views.messages.error") as mock_msg:
        response = view.get(req)

        assert response.status_code == 302
        assert "/app/assets/0fb0e8a1-47fc-4eb2-9b66-71f9b434010a/?tab=hierarchy" in response.url
        mock_msg.assert_called_once_with(req, "Cannot create a child under component.")


def test_reportsnapshot_cleanup_migration_exists():
    """Verify migration 0003 exists and cleans up legacy kind column for dashboards_reportsnapshot."""
    import importlib
    mig3 = importlib.import_module("apps.dashboards.migrations.0004_cleanup_legacy_reportsnapshot_columns")

    assert hasattr(mig3, "cleanup_legacy_columns")
    assert mig3.Migration.dependencies == [("dashboards", "0003_fix_snapshot_schema")]



def test_e2e_def_007_app_js_safe_form_action():
    """Verify app.js does not invoke .indexOf on form.action directly to prevent TypeError with input[name='action']."""
    with open("src/static/js/app.js", "r", encoding="utf-8") as f:
        js = f.read()

    assert 'form.action.indexOf("/accounts/logout/")' not in js
    assert 'typeof form.action === "string"' in js


def test_e2e_def_011_remember_me_session_expiry():
    """Verify form_valid in LoginView sets session expiry to 0 when remember me is not checked."""
    from apps.accounts.views import LoginView
    from django.test import RequestFactory
    from unittest.mock import MagicMock, patch

    rf = RequestFactory()
    req = rf.post("/accounts/login/", data={"username": "user@fieldops.local", "password": "secretpassword"})
    req.session = MagicMock()
    req.user = MagicMock()

    view = LoginView()
    view.request = req

    form = MagicMock()
    form.get_user.return_value = req.user

    with patch("apps.accounts.services.activate_pending_memberships"), patch("django.contrib.auth.views.LoginView.form_valid", return_value=MagicMock()):
        view.form_valid(form)
        req.session.set_expiry.assert_called_with(0)


def test_e2e_def_012_client_portal_account_blocked_from_staff_views():
    """Verify TenantPermissionMixin rejects client memberships trying to access staff pages."""
    from apps.ui.mixins import TenantPermissionMixin
    from django.core.exceptions import PermissionDenied
    from django.test import RequestFactory
    from unittest.mock import MagicMock

    rf = RequestFactory()
    req = rf.get("/app/audit/")
    req.user = MagicMock(is_authenticated=True)
    req.membership = MagicMock()
    req.tenant_error = None

    view = TenantPermissionMixin()
    view.required_permission = "audit.view"

    with patch("apps.ui.utils.is_client_membership", return_value=True):
        with pytest.raises(PermissionDenied) as exc_info:
            view.dispatch(req)
        assert "Client portal accounts cannot access internal staff operations" in str(exc_info.value)
