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
        required=True,
        label="Full name",
        widget=forms.TextInput(attrs={"placeholder": "e.g. Dinuka Wijesinghe"}),
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
        name = (self.cleaned_data.get("full_name") or "").strip()
        if not name:
            raise forms.ValidationError("Full name is required.")
        if len(name) < 2:
            raise forms.ValidationError("Full name must be at least 2 characters.")
        return name

    def clean_phone(self):
        return validate_phone_number(self.cleaned_data.get("phone"))
