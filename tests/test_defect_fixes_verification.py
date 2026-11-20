import pytest
import uuid
from apps.core.exceptions import Conflict, ValidationFailed
from apps.incidents import services as incident_services
from apps.sites.forms import SiteForm
from apps.workorders import services as wo_services
from apps.workorders import workflow as wo_workflow
from apps.workorders.views import WorkOrderViewSet
from apps.sla.api_views import EscalationViewSet
from apps.rbac import services as rbac_services
from apps.rbac.models import Role
from django.db.models import ProtectedError
from unittest import mock


def test_def_002_role_delete_handles_protected_error():
    role = mock.MagicMock(spec=Role)
    role.is_system = False
    role.membership_roles.exists.return_value = False
    role.name = "Custom Role"
    role.organization = mock.MagicMock()
    role.pk = uuid.uuid4()
    role.delete.side_effect = ProtectedError("Cannot delete role", [role])

    func = getattr(rbac_services.delete_role, "__wrapped__", rbac_services.delete_role)
    with pytest.raises(Conflict) as exc_info:
        func(role, actor=mock.MagicMock())
    assert exc_info.value.code == "role_in_use"


def test_def_004_validate_checklist_permission_not_view_only():
    view = WorkOrderViewSet()
    view.action = "validate_checklist"
    view.request = mock.MagicMock()
    # Should require work_order.complete, NOT be downgraded to work_order.view
    perm = view.get_required_permission()
    assert perm == "work_order.complete"


def test_def_005_sla_filter_level_invalid():
    view = EscalationViewSet()
    req = mock.MagicMock()
    req.query_params = {"level": "invalid_number"}
    view._queryset = mock.MagicMock()
    with pytest.raises(ValidationFailed) as exc_info:
        view.list(req)
    assert exc_info.value.code == "invalid_level"


def test_def_006_workorder_transition_has_schema():
    assert hasattr(WorkOrderViewSet.transition, "_schema_extend") or hasattr(WorkOrderViewSet.transition, "kwargs")
    assert "post" in WorkOrderViewSet.transition.mapping


def test_def_007_state_machines_synchronized():
    from_machine = {}
    for t in wo_workflow.WORK_ORDER_STATUS.transitions:
        for s in t.sources:
            from_machine.setdefault(s, set()).add(t.target)
    combined = {str(k): {str(x) for x in v} for k, v in wo_services.TRANSITIONS.items()}
    for s_ in wo_services.CANCELLABLE_STATUSES:
        combined.setdefault(str(s_), set()).add(wo_workflow.CANCELLED)
    assert combined == {k: set(v) for k, v in from_machine.items()}


def test_def_009_validate_linked_priority_permits_planner_adjustment():
    wo = mock.MagicMock()
    wo.source_request_id = uuid.uuid4()
    wo.source_request.severity = "HIGH"
    # Should not raise ValidationFailed even if priority is LOW
    wo_services._validate_linked_priority(wo, "LOW")
    wo_services._validate_linked_priority(wo, "HIGH")


def test_def_010_invite_derives_name_when_blank():
    email = "john.doe@example.com"
    full_name = "   "
    # Verify name derivation logic directly
    derived = email.split("@")[0].replace(".", " ").replace("_", " ").strip().title()
    assert derived == "John Doe"

    from apps.tenancy import services as tenancy_services
    with mock.patch("apps.tenancy.services.User.objects.filter") as mock_user_filt, \
         mock.patch("apps.tenancy.services.User.objects.create_user") as mock_create_user, \
         mock.patch("apps.tenancy.services.Membership.objects") as mock_membership_mgr:
        mock_user_filt.return_value.first.return_value = None
        mock_membership_mgr.unscoped.return_value.filter.return_value.exists.return_value = False

        # Stop after user creation
        mock_create_user.side_effect = RuntimeError("User created successfully")

        with pytest.raises(RuntimeError, match="User created successfully"):
            tenancy_services._invite(
                mock.MagicMock(),
                email=email,
                full_name=full_name,
                roles=[],
                invited_by=mock.MagicMock(),
            )
        _, kwargs = mock_create_user.call_args
        assert kwargs["full_name"] == "John Doe"


def test_def_011_editable_excludes_asset_and_kind():
    assert "asset" not in incident_services._EDITABLE
    assert "kind" not in incident_services._EDITABLE
    assert "status" not in incident_services._EDITABLE
    assert "title" in incident_services._EDITABLE


def test_def_012_site_phone_validation_wording():
    form = SiteForm(data={
        "code": "SITE-01",
        "name": "Test Site",
        "contact_phone": "123456789abc",
    })
    form.is_valid()
    assert "contact_phone" in form.errors
    error_str = " ".join(form.errors["contact_phone"]).lower()
    assert "valid phone" in error_str
