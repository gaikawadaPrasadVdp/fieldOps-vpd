"""Unit tests for asset workflow actions (e.g. Start maintenance) and form validations."""
import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from apps.assets.forms import (
    AssetForm,
    CategoryForm,
    ComponentReplaceForm,
    MeterForm,
    ReadingForm,
    RelationshipFields,
)
from apps.assets.views import AssetStatusView, DocumentRemoveView
from apps.core.exceptions import ValidationFailed


def test_meter_form_name_and_unit_reject_numbers():
    f1 = MeterForm(data={"name": "Run hours 2", "unit": "hours"})
    assert not f1.is_valid()
    assert "name" in f1.errors
    assert "cannot contain numbers" in f1.errors["name"][0]

    f2 = MeterForm(data={"name": "Run hours", "unit": "km1"})
    assert not f2.is_valid()
    assert "unit" in f2.errors
    assert "cannot contain numbers" in f2.errors["unit"][0]

    f3 = MeterForm(data={"name": "Run hours", "unit": "hours"})
    assert f3.is_valid(), f"Errors: {f3.errors}"


def test_reading_form_notes_reject_numbers():
    f1 = ReadingForm(data={"value": "12.5", "notes": "Reading 123"})
    assert not f1.is_valid()
    assert "notes" in f1.errors
    assert "cannot contain numbers" in f1.errors["notes"][0]

    f2 = ReadingForm(data={"value": "12.5", "notes": "Routine inspection reading"})
    assert f2.is_valid(), f"Errors: {f2.errors}"


def test_relationship_fields_notes_reject_numbers():
    f1 = RelationshipFields(data={"relationship_type": "COMPONENT", "quantity": 1, "notes": "Bearing 44"})
    assert not f1.is_valid()
    assert "notes" in f1.errors
    assert "cannot contain numbers" in f1.errors["notes"][0]

    f2 = RelationshipFields(data={"relationship_type": "COMPONENT", "quantity": 1, "notes": "Primary drive bearing"})
    assert f2.is_valid(), f"Errors: {f2.errors}"


def test_component_replace_form_reason_rejects_numbers():
    mock_qs = MagicMock()
    mock_qs.all.return_value = []
    f1 = ComponentReplaceForm(data={"reason": "Worn bearing replaced 2026"}, candidates=mock_qs)
    assert "reason" in f1.errors
    assert "cannot contain numbers" in f1.errors["reason"][0]

    f2 = ComponentReplaceForm(data={"reason": "Worn bearing replaced during scheduled maintenance"}, candidates=mock_qs)
    assert "reason" not in f2.errors


def test_category_form_name_rejects_numbers():
    f1 = CategoryForm(data={"name": "Heavy Machinery 1"})
    assert not f1.is_valid()
    assert "name" in f1.errors
    assert "cannot contain numbers" in f1.errors["name"][0]

    f2 = CategoryForm(data={"name": "Heavy Machinery"})
    assert f2.is_valid(), f"Errors: {f2.errors}"


def test_asset_status_view_start_maintenance_rejects_numbers():
    asset_id = str(uuid.uuid4())
    factory = RequestFactory()
    request = factory.post(f"/app/assets/{asset_id}/transition/start_maintenance/", {"reason": "546556"})
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()
    request.organization = MagicMock()

    view = AssetStatusView()

    with patch("apps.assets.views._asset") as mock_asset, \
         patch("apps.assets.views.messages") as mock_messages, \
         patch("apps.assets.services.change_status") as mock_change_status:
        
        mock_asset.return_value = MagicMock(pk=asset_id)
        resp = view.post(request, pk=asset_id, action="start_maintenance")
        
        assert resp.status_code == 302
        mock_messages.error.assert_called_once_with(
            request, "Reason must contain only alphabetical characters and cannot contain numbers."
        )
        mock_change_status.assert_not_called()


def test_asset_status_view_start_maintenance_accepts_valid_reason():
    asset_id = str(uuid.uuid4())
    factory = RequestFactory()
    request = factory.post(f"/app/assets/{asset_id}/transition/start_maintenance/", {"reason": "Scheduled motor overhaul"})
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()
    request.organization = MagicMock()

    view = AssetStatusView()

    with patch("apps.assets.views._asset") as mock_asset, \
         patch("apps.assets.views.messages") as mock_messages, \
         patch("apps.assets.services.change_status") as mock_change_status:
        
        mock_asset.return_value = MagicMock(pk=asset_id)
        resp = view.post(request, pk=asset_id, action="start_maintenance")
        
        assert resp.status_code == 302
        mock_messages.success.assert_called_once_with(request, "Status updated.")
        mock_change_status.assert_called_once()
        assert mock_change_status.call_args[1]["reason"] == "Scheduled motor overhaul"


def test_document_remove_view_rejects_numbers_in_reason():
    doc_id = str(uuid.uuid4())
    asset_id = str(uuid.uuid4())
    factory = RequestFactory()
    request = factory.post(f"/app/assets/docs/{doc_id}/remove/", {"reason": "Outdated 2024"})
    request.user = MagicMock(is_authenticated=True)
    request.tenant_error = None
    request.membership = MagicMock()
    request.organization = MagicMock()

    view = DocumentRemoveView()

    with patch("apps.assets.views.selectors.get_document") as mock_get_doc, \
         patch("apps.assets.views.need"), \
         patch("apps.assets.views.messages") as mock_messages, \
         patch("apps.assets.services.remove_document") as mock_remove_doc:
        
        mock_doc = MagicMock()
        mock_doc.asset = MagicMock(pk=asset_id)
        mock_get_doc.return_value = mock_doc

        resp = view.post(request, pk=doc_id)
        assert resp.status_code == 302
        mock_messages.error.assert_called_once_with(
            request, "Reason must contain only alphabetical characters and cannot contain numbers."
        )
        mock_remove_doc.assert_not_called()


def _make_asset_form(data=None, creating=True):
    mock_sites = MagicMock()
    mock_site_qs = MagicMock()
    mock_site_qs.all.return_value = []
    mock_sites.filter.return_value.order_by.return_value = mock_site_qs

    mock_qs = MagicMock()
    mock_qs.all.return_value = []
    mock_qs.filter.return_value.select_related.return_value.order_by.return_value = mock_qs
    mock_qs.filter.return_value = mock_qs

    with patch("apps.assets.forms.Zone.objects.for_organization", return_value=mock_qs), \
         patch("apps.assets.forms.AssetCategory.objects.for_organization", return_value=mock_qs), \
         patch("apps.assets.forms.Membership.objects.for_organization", return_value=mock_qs):
        return AssetForm(data=data or {}, sites=mock_sites, org=MagicMock(), creating=creating)


def test_asset_form_required_fields_and_validations():
    form = _make_asset_form(data={}, creating=True)
    assert not form.is_valid()
    assert 'asset_tag' in form.errors
    assert 'name' in form.errors
    assert 'category' in form.errors
    assert 'site' in form.errors
    assert form.fields['asset_tag'].widget.attrs.get('required') == 'required'
    assert form.fields['name'].widget.attrs.get('required') == 'required'
    assert form.fields['category'].widget.attrs.get('required') == 'required'
    assert form.fields['site'].widget.attrs.get('required') == 'required'
    assert form.fields['asset_tag'].required is True
    assert form.fields['name'].required is True
    assert form.fields['category'].required is True
    assert form.fields['site'].required is True


def test_asset_form_name_validation():
    form = _make_asset_form(data={'name': 'A'}, creating=True)
    assert not form.is_valid()
    assert 'name' in form.errors
    assert 'at least 2 characters' in form.errors['name'][0]

    form_num = _make_asset_form(data={'name': 'Chiller 12'}, creating=True)
    assert not form_num.is_valid()
    assert 'name' in form_num.errors
    assert 'cannot contain numbers' in form_num.errors['name'][0]


def test_asset_form_description_rejects_numbers():
    form = _make_asset_form(data={'description': 'Model 45 breakdown'}, creating=True)
    assert 'description' in form.errors
    assert 'cannot contain numbers' in form.errors['description'][0]


def test_asset_form_reason_rejects_numbers():
    form = _make_asset_form(data={'reason': 'Relocated to building 5'}, creating=False)
    assert 'reason' in form.errors
    assert 'cannot contain numbers' in form.errors['reason'][0]
