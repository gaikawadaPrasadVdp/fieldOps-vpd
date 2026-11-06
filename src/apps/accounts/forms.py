from django import forms
from django.contrib.auth.forms import AuthenticationForm

from apps.ui.forms import BootstrapFormMixin, validate_phone_number
from .models import User


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "username"}))
    error_messages = {
        "invalid_login": "Invalid email or password.",
        "inactive": "This account is inactive.",
    }

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


class ProfileForm(BootstrapFormMixin, forms.ModelForm):
    full_name = forms.CharField(
        max_length=150,
        min_length=2,
        required=True,
        label="Full name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Dinuka Wijesinghe",
            "required": "required",
            "minlength": "2",
            "pattern": r"^[A-Za-z\s'-]+$",
            "title": "Full name must contain only alphabetical characters.",
        }),
    )
    phone = forms.CharField(
        max_length=32,
        required=False,
        label="Phone",
        help_text="Optional. International or national format (minimum 7 digits).",
        widget=forms.TextInput(attrs={"placeholder": "e.g. +94 11 289 9000", "type": "tel"}),
    )

    class Meta:
        model = User
        fields = ["full_name", "phone"]

    def clean_full_name(self):
        from apps.ui.forms import validate_alphabetical_name
        return validate_alphabetical_name(self.cleaned_data.get("full_name"), field_label="Full name")

    def clean_phone(self):
        return validate_phone_number(self.cleaned_data.get("phone"))
