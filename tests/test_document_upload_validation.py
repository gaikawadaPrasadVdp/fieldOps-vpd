import pytest
from unittest.mock import MagicMock, patch
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError

from apps.assets.forms import DocumentForm
from apps.assets.models import AssetDocument
from apps.assets import services
from apps.core.exceptions import ValidationFailed


def test_document_form_choices():
    form = DocumentForm()
    choices = form.fields["doc_type"].choices
    assert len(choices) == 3
    assert choices == [("PHOTO", "Photograph"), ("PDF", "PDF"), ("OTHER", "Other")]


def test_document_form_other_validation():
    # Valid file for OTHER (e.g. txt or csv or pdf or image)
    txt_file = SimpleUploadedFile("logs.txt", b"System logs data", content_type="text/plain")
    form = DocumentForm(
        data={"doc_type": "OTHER", "title": "System logs"},
        files={"file": txt_file}
    )
    assert form.is_valid(), form.errors

    # Reject unsupported format for OTHER (e.g. .exe)
    exe_file = SimpleUploadedFile("program.exe", b"MZ\x90\x00", content_type="application/octet-stream")
    form_err = DocumentForm(
        data={"doc_type": "OTHER", "title": "Invalid"},
        files={"file": exe_file}
    )
    assert not form_err.is_valid()
    assert "file" in form_err.errors
    assert "not supported" in str(form_err.errors["file"][0])


def test_document_form_photo_validation():
    # PNG image header
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    valid_png = SimpleUploadedFile("test.png", png_content, content_type="image/png")

    form = DocumentForm(
        data={"doc_type": "PHOTO", "title": "Machine photo"},
        files={"file": valid_png}
    )
    assert form.is_valid(), form.errors

    # Reject PDF when PHOTO is selected
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    pdf_as_photo = SimpleUploadedFile("manual.pdf", pdf_content, content_type="application/pdf")
    form_err = DocumentForm(
        data={"doc_type": "PHOTO", "title": "Invalid"},
        files={"file": pdf_as_photo}
    )
    assert not form_err.is_valid()
    assert "file" in form_err.errors
    assert "Selected document type is Photograph" in str(form_err.errors["file"][0])

    # Reject txt file when PHOTO is selected
    txt_file = SimpleUploadedFile("notes.txt", b"some notes", content_type="text/plain")
    form_err2 = DocumentForm(
        data={"doc_type": "PHOTO", "title": "Invalid"},
        files={"file": txt_file}
    )
    assert not form_err2.is_valid()
    assert "file" in form_err2.errors


def test_document_form_pdf_validation():
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
    valid_pdf = SimpleUploadedFile("specs.pdf", pdf_content, content_type="application/pdf")

    form = DocumentForm(
        data={"doc_type": "PDF", "title": "Spec Sheet"},
        files={"file": valid_pdf}
    )
    assert form.is_valid(), form.errors

    # Reject PNG when PDF is selected
    png_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
    png_as_pdf = SimpleUploadedFile("picture.png", png_content, content_type="image/png")
    form_err = DocumentForm(
        data={"doc_type": "PDF", "title": "Invalid"},
        files={"file": png_as_pdf}
    )
    assert not form_err.is_valid()
    assert "file" in form_err.errors
    assert "Selected document type is PDF" in str(form_err.errors["file"][0])


def test_document_form_empty_file_rejected():
    empty_file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
    form = DocumentForm(
        data={"doc_type": "PDF", "title": "Empty"},
        files={"file": empty_file}
    )
    assert not form.is_valid()
    assert "file" in form.errors


def test_services_add_document_enforces_photo_vs_pdf():
    mock_asset = MagicMock()
    mock_asset.organization = MagicMock()
    mock_actor = MagicMock()

    func = getattr(services.add_document, "__wrapped__", services.add_document)

    # Mismatched file for PHOTO (uploading .pdf)
    bad_photo = SimpleUploadedFile("doc.pdf", b"%PDF-1.4", content_type="application/pdf")
    with pytest.raises(ValidationFailed) as exc_info:
        func(mock_asset, bad_photo, doc_type="PHOTO", actor=mock_actor)
    assert "Selected document type is Photograph" in str(exc_info.value)

    # Mismatched file for PDF (uploading .jpg)
    bad_pdf = SimpleUploadedFile("doc.jpg", b"\xff\xd8\xff", content_type="image/jpeg")
    with pytest.raises(ValidationFailed) as exc_info2:
        func(mock_asset, bad_pdf, doc_type="PDF", actor=mock_actor)
    assert "Selected document type is PDF" in str(exc_info2.value)
