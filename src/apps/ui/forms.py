"""Form helpers shared by module screens."""
import re
from django import forms
from django.core.exceptions import ValidationError

_PHONE_RE = re.compile(r"^[0-9+\s\-()]{7,32}$")


def validate_phone_number(value: str | None) -> str:
    """Validates phone number format and digit count.

    Accepts international and national formats: +94 11 289 9000, (555) 012-3456, etc.
    Requires at least 7 digits and at most 15 digits (ITU-T E.164 standard).
    """
    if not value:
        return ""
    val = value.strip()
    if not val:
        return ""
    digits = [c for c in val if c.isdigit()]
    if len(digits) < 7:
        raise ValidationError("Phone number must contain at least 7 digits (e.g. +94 11 289 9000).")
    if len(digits) > 15:
        raise ValidationError("Phone number cannot exceed 15 digits (ITU-T E.164 standard).")
    if not _PHONE_RE.fullmatch(val):
        raise ValidationError("Enter a valid phone number (e.g. +94 11 289 9000).")
    return val


def validate_alphabetical_description(value: str | None, field_label: str = "Description") -> str:
    """Validates that a descriptive text field contains alphabetical text only and cannot contain numbers."""
    if not value:
        return ""
    val = value.strip()
    if not val:
        return ""
    if any(character.isdigit() for character in val):
        raise ValidationError(f"{field_label} must contain only alphabetical characters and cannot contain numbers.")
    if not any(character.isalpha() for character in val):
        raise ValidationError(f"{field_label} must contain alphabetical text.")
    allowed_punctuation = set(".,;:!?'\"’“”()[]/\\-–—_&%\r\n\t")
    if any(not (character.isalpha() or character.isspace() or character in allowed_punctuation) for character in val):
        raise ValidationError(f"{field_label} can contain letters, spaces, and standard punctuation only.")
    return val


_NAME_ALPHABETICAL_RE = re.compile(r"^[A-Za-z\s'-]+$")


def validate_alphabetical_name(value: str | None, field_label: str = "Name", min_len: int = 2, required: bool = True) -> str:
    """Validates that a name field contains only alphabetical characters and spaces."""
    if not value or not str(value).strip():
        if required:
            raise ValidationError(f"{field_label} is required.")
        return ""
    val = str(value).strip()
    if len(val) < min_len:
        raise ValidationError(f"{field_label} must be at least {min_len} characters.")
    if any(character.isdigit() for character in val):
        raise ValidationError(f"{field_label} must contain only alphabetical characters and cannot contain numbers.")
    if not _NAME_ALPHABETICAL_RE.match(val):
        raise ValidationError(f"{field_label} must contain only alphabetical characters.")
    return val


_HTML_TAG_RE = re.compile(r"<[^>]*>|[<>]|javascript:|onerror=|onload=", re.IGNORECASE)
_REPEATED_CHARS_RE = re.compile(r"(.)\1{4,}|\S{35,}")
_BUSINESS_NAME_RE = re.compile(r"^[A-Za-z0-9\s.,'&\-/()#]+$")


def validate_business_name(value: str | None, field_label: str = "Name", min_len: int = 2, max_len: int = 150) -> str:
    """Validates business/provider name against XSS, HTML tags, repetitive spam, and non-standard symbols."""
    if not value or not str(value).strip():
        raise ValidationError(f"{field_label} is required.")
    val = str(value).strip()
    if len(val) < min_len:
        raise ValidationError(f"{field_label} must be at least {min_len} characters.")
    if len(val) > max_len:
        raise ValidationError(f"{field_label} cannot exceed {max_len} characters.")
    if _HTML_TAG_RE.search(val):
        raise ValidationError(f"{field_label} cannot contain HTML tags or script injection patterns.")
    if _REPEATED_CHARS_RE.search(val):
        raise ValidationError(f"{field_label} contains invalid repetitive character patterns.")
    if not any(c.isalnum() for c in val):
        raise ValidationError(f"{field_label} must contain letters or numbers.")
    if not _BUSINESS_NAME_RE.match(val):
        raise ValidationError(f"{field_label} contains invalid characters. Only letters, numbers, spaces, and . , ' & - / ( ) # are allowed.")
    return val


def validate_safe_text(value: str | None, field_label: str = "Notes", max_len: int = 500, required: bool = False) -> str:
    """Validates general notes/text fields against HTML/script injection and repetitive spam."""
    if not value or not str(value).strip():
        if required:
            raise ValidationError(f"{field_label} is required.")
        return ""
    val = str(value).strip()
    if len(val) > max_len:
        raise ValidationError(f"{field_label} cannot exceed {max_len} characters.")
    if _HTML_TAG_RE.search(val):
        raise ValidationError(f"{field_label} cannot contain HTML tags or script injection patterns.")
    if _REPEATED_CHARS_RE.search(val):
        raise ValidationError(f"{field_label} contains invalid repetitive character patterns.")
    return val


_EMAIL_STRICT_RE = re.compile(
    r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z][a-zA-Z0-9-]*(\.[a-zA-Z][a-zA-Z0-9-]*)*\.[a-zA-Z]{2,}$"
)


def validate_strict_email(value: str | None) -> str:
    """Validates email format strictly: domain must start with a letter and have a valid extension (e.g. .com)."""
    if not value:
        raise ValidationError("Email address is required.")
    val = value.strip().lower()
    if not val:
        raise ValidationError("Email address is required.")
    if len(val) > 254:
        raise ValidationError("Email address cannot exceed 254 characters.")
    if not _EMAIL_STRICT_RE.match(val):
        raise ValidationError(
            "Enter a valid email address with a valid domain (e.g. user@gmail.com). "
            "Domain names must start with a letter and have a valid extension (e.g. .com)."
        )
    return val


class BootstrapFormMixin:
    """Gives widgets Bootstrap 5 classes so server-rendered forms look consistent."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                cls = "form-check-input"
            elif isinstance(w, forms.Select | forms.SelectMultiple):
                cls = "form-select"
            elif isinstance(w, forms.CheckboxSelectMultiple | forms.RadioSelect | forms.FileInput):
                cls = "form-control" if isinstance(w, forms.FileInput) else ""
            else:
                cls = "form-control"
            if cls:
                w.attrs["class"] = f"{w.attrs.get('class', '')} {cls}".strip()

    def add_error(self, field, error):
        super().add_error(field, error)
        if field and field in self.fields:
            self._mark_field_invalid(field)

    def full_clean(self):
        super().full_clean()
        for field_name in self.errors:
            if field_name in self.fields:
                self._mark_field_invalid(field_name)

    def _mark_field_invalid(self, field_name):
        w = self.fields[field_name].widget
        existing = w.attrs.get("class", "")
        classes = existing.split()
        if "is-invalid" not in classes:
            classes.append("is-invalid")
            w.attrs["class"] = " ".join(classes)


class ReasonForm(BootstrapFormMixin, forms.Form):
    reason = forms.CharField(max_length=300, widget=forms.TextInput(attrs={"placeholder": "Reason (required)"}))


class ClientOnboardingForm(BootstrapFormMixin, forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name", required=True)
    email = forms.EmailField(label="Work email", required=True)
    phone = forms.CharField(max_length=30, label="Phone number", required=False)
    company_name = forms.CharField(max_length=200, label="Company / Organization", required=True)
    facility_address = forms.CharField(max_length=300, label="Facility address", required=False)
    service_scope = forms.CharField(
        max_length=500, label="Asset / Service scope",
        widget=forms.Textarea(attrs={"rows": 3, "placeholder": "Describe assets or maintenance services requested..."}),
        required=False,
    )
    terms_accepted = forms.BooleanField(
        label="I accept the enterprise platform terms and data protection policy",
        required=True,
    )

    def clean_full_name(self):
        return validate_alphabetical_name(self.cleaned_data.get("full_name"), field_label="Full name")

    def clean_phone(self):
        return validate_phone_number(self.cleaned_data.get("phone"))
