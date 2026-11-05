import pytest
from apps.workorders.forms import (
    LaborForm,
    WorkUpdateForm,
    CompleteForm,
    ClosureCommentForm,
    ReasonForm,
    ReassignForm,
    ReviewForm,
    MaterialForm,
    EvidenceForm,
)
from apps.workorders.serializers import (
    LaborInputSerializer,
    WorkOrderCompleteSerializer,
    ClosureCommentSerializer,
    WorkOrderReasonSerializer,
    WorkNoteSerializer,
)
from apps.ui.forms import validate_alphabetical_description
from django.core.exceptions import ValidationError
from django.utils import timezone


def test_validate_alphabetical_description_helper():
    # Digits must be rejected
    with pytest.raises(ValidationError) as exc:
        validate_alphabetical_description("655555555557", "Work performed")
    assert "Work performed must contain only alphabetical characters and cannot contain numbers." in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        validate_alphabetical_description("5454545454ffffd", "Resolution notes")
    assert "Resolution notes must contain only alphabetical characters and cannot contain numbers." in str(exc.value)

    # Pure symbols/punctuation with no letters must be rejected
    with pytest.raises(ValidationError) as exc:
        validate_alphabetical_description("--- ...", "Comment")
    assert "Comment must contain alphabetical text." in str(exc.value)

    # Valid text with spaces and punctuation must pass
    valid_texts = [
        "Work completed properly and verified.",
        "Inspection complete; equipment is safe and operating correctly.",
        "Re-aligned motor's coupling (checked & tested).",
        "Diagnostic findings: zero leakage detected, pressure normal!",
    ]
    for text in valid_texts:
        assert validate_alphabetical_description(text) == text


def test_labor_form_alphabetical_validation():
    # Numeric description rejected
    form_bad = LaborForm(data={
        "started_at": "2026-11-05T10:00",
        "ended_at": "2026-11-05T12:00",
        "description": "655555555557",
    })
    assert not form_bad.is_valid()
    assert "description" in form_bad.errors
    assert "Work performed must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["description"])

    # Alphanumeric with numbers rejected
    form_alpha_num = LaborForm(data={
        "started_at": "2026-11-05T10:00",
        "ended_at": "2026-11-05T12:00",
        "description": "Replaced pump 2 motor",
    })
    assert not form_alpha_num.is_valid()
    assert "description" in form_alpha_num.errors

    # Valid alphabetical description accepted
    form_good = LaborForm(data={
        "started_at": "2026-11-05T10:00",
        "ended_at": "2026-11-05T12:00",
        "description": "Inspected pump casing and lubricated drive bearing thoroughly",
    })
    assert form_good.is_valid(), form_good.errors


def test_work_update_form_alphabetical_validation():
    # Numeric input rejected
    form_bad = WorkUpdateForm(data={"update": "566666666666667"})
    assert not form_bad.is_valid()
    assert "update" in form_bad.errors
    assert "Work update must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["update"])

    # Alphabetical accepted
    form_good = WorkUpdateForm(data={"update": "Diagnostic completed, awaiting safety clearance."})
    assert form_good.is_valid(), form_good.errors


def test_complete_form_alphabetical_validation():
    # Mixed numbers rejected
    form_bad = CompleteForm(data={"resolution_notes": "5454545454545454545454fffffffffffd"})
    assert not form_bad.is_valid()
    assert "resolution_notes" in form_bad.errors
    assert "Resolution notes must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["resolution_notes"])

    # Alphabetical accepted
    form_good = CompleteForm(data={"resolution_notes": "Inspection complete; equipment is safe and operating correctly."})
    assert form_good.is_valid(), form_good.errors


def test_closure_comment_form_alphabetical_validation():
    # Mixed numbers rejected
    form_bad = ClosureCommentForm(data={"comment": "455555555555dffffffffff"})
    assert not form_bad.is_valid()
    assert "comment" in form_bad.errors
    assert "Comment must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["comment"])

    # Alphabetical accepted
    form_good = ClosureCommentForm(data={"comment": "Supervisor approved repair and closed order."})
    assert form_good.is_valid(), form_good.errors


def test_reason_form_alphabetical_validation():
    # Numbers rejected
    form_bad = ReasonForm(data={"reason": "12345678"})
    assert not form_bad.is_valid()
    assert "reason" in form_bad.errors
    assert "Reason must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["reason"])

    # Alphabetical accepted
    form_good = ReasonForm(data={"reason": "Waiting for site access and isolation."})
    assert form_good.is_valid(), form_good.errors


def test_review_form_alphabetical_validation():
    # Notes with digits rejected
    form_bad = ReviewForm(data={"notes": "Inspection step 3 failed"})
    assert not form_bad.is_valid()
    assert "notes" in form_bad.errors
    assert "Review notes must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["notes"])

    # Alphabetical accepted
    form_good = ReviewForm(data={"notes": "Reviewed and approved by operations supervisor."})
    assert form_good.is_valid(), form_good.errors


def test_material_form_notes_alphabetical_validation():
    form_bad = MaterialForm(data={
        "item_name": "Bearing Seal",
        "quantity": 1,
        "notes": "Installed in unit 2",
    })
    assert not form_bad.is_valid()
    assert "notes" in form_bad.errors
    assert "Usage notes must contain only alphabetical characters and cannot contain numbers." in str(form_bad.errors["notes"])

    form_good = MaterialForm(data={
        "item_name": "Bearing Seal",
        "quantity": 1,
        "notes": "Installed replacement bearing seal according to maintenance guidelines.",
    })
    assert form_good.is_valid(), form_good.errors


def test_serializers_alphabetical_validation():
    # Complete serializer
    ser_bad_complete = WorkOrderCompleteSerializer(data={"resolution_notes": "Repaired 10 units properly."})
    assert not ser_bad_complete.is_valid()
    assert "resolution_notes" in ser_bad_complete.errors

    ser_good_complete = WorkOrderCompleteSerializer(data={"resolution_notes": "Repaired and aligned components properly."})
    assert ser_good_complete.is_valid(), ser_good_complete.errors

    # Closure serializer
    ser_bad_close = ClosureCommentSerializer(data={"comment": "Close order 123"})
    assert not ser_bad_close.is_valid()
    assert "comment" in ser_bad_close.errors

    ser_good_close = ClosureCommentSerializer(data={"comment": "Close order approved and verified."})
    assert ser_good_close.is_valid(), ser_good_close.errors

    # Labor serializer
    today = timezone.localdate().isoformat()
    ser_bad_labor = LaborInputSerializer(data={"work_date": today, "hours": "2.00", "description": "Overhaul 2 pumps"})
    assert not ser_bad_labor.is_valid()
    assert "description" in ser_bad_labor.errors

    ser_good_labor = LaborInputSerializer(data={"work_date": today, "hours": "2.00", "description": "Overhaul pump impeller and replace gasket"})
    assert ser_good_labor.is_valid(), ser_good_labor.errors


def test_incident_request_form_title_alphabetical_validation():
    from apps.incidents.forms import RequestForm

    # 1. Numeric title rejected (user reported 4555555555)
    form_numeric = RequestForm(data={
        "title": "4555555555",
        "kind": "INCIDENT",
        "severity": "MEDIUM",
        "service_impact": "DEGRADED",
    })
    assert not form_numeric.is_valid()
    assert "title" in form_numeric.errors
    assert "Title must contain only alphabetical characters and cannot contain numbers." in str(form_numeric.errors["title"])

    # 2. Title with mixed alphanumeric digits rejected
    form_mixed = RequestForm(data={
        "title": "Pump 2 failure",
        "kind": "INCIDENT",
        "severity": "MEDIUM",
        "service_impact": "DEGRADED",
    })
    assert not form_mixed.is_valid()
    assert "title" in form_mixed.errors
    assert "Title must contain only alphabetical characters and cannot contain numbers." in str(form_mixed.errors["title"])

    # 3. Clean alphabetical title accepted
    form_clean = RequestForm(data={
        "title": "Water pump pressure drop",
        "kind": "INCIDENT",
        "severity": "MEDIUM",
        "service_impact": "DEGRADED",
    })
    # Title passes validation
    form_clean.is_valid()
    assert "title" not in form_clean.errors


def test_portal_service_request_form_title_alphabetical_validation():
    from apps.portal.forms import PortalServiceRequestForm

    form_numeric = PortalServiceRequestForm(data={
        "title": "4555555555",
        "severity": "MEDIUM",
        "service_impact": "NONE",
    })
    assert not form_numeric.is_valid()
    assert "title" in form_numeric.errors
    assert "Title must contain only alphabetical characters and cannot contain numbers." in str(form_numeric.errors["title"])

    form_clean = PortalServiceRequestForm(data={
        "title": "Cooling unit compressor failure",
        "severity": "MEDIUM",
        "service_impact": "NONE",
    })
    form_clean.is_valid()
    assert "title" not in form_clean.errors


def test_incident_serializer_title_alphabetical_validation():
    from apps.incidents.api_views import ServiceRequestWriteSerializer
    import uuid

    ser_bad = ServiceRequestWriteSerializer(data={
        "asset": str(uuid.uuid4()),
        "title": "4555555555",
        "kind": "INCIDENT",
    })
    assert not ser_bad.is_valid()
    assert "title" in ser_bad.errors

    ser_good = ServiceRequestWriteSerializer(data={
        "asset": str(uuid.uuid4()),
        "title": "Cooling unit compressor failure",
        "kind": "INCIDENT",
    })
    ser_good.is_valid()
    assert "title" not in ser_good.errors
