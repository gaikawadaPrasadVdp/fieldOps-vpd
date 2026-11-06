from django import forms

from apps.rbac.models import Role
from apps.sites.geo_data import COUNTRIES, TIMEZONES
from apps.ui.forms import BootstrapFormMixin


import re
import zoneinfo


class TimezoneChoiceField(forms.ChoiceField):
    """Dropdown selection for Operating Timezone populated with standard IANA options."""
    def __init__(self, *args, **kwargs):
        choices = [("", "Select Operating Timezone...")] + list(TIMEZONES)
        kwargs.setdefault("choices", choices)
        kwargs.setdefault("label", "Operating Timezone")
        widget = kwargs.get("widget") or forms.Select(attrs={"class": "form-select", "id": "id_timezone"})
        kwargs["widget"] = widget
        super().__init__(*args, **kwargs)

    def validate(self, value):
        if value:
            try:
                zoneinfo.ZoneInfo(value)
            except Exception:
                raise forms.ValidationError(f"Unknown timezone '{value}'. Please select a valid IANA timezone.")
        elif self.required:
            raise forms.ValidationError("Operating timezone is required.")


class CountryChoiceField(forms.ChoiceField):
    """Dropdown selection for Country Code populated with standard ISO country options."""
    def __init__(self, *args, **kwargs):
        choices = [("", "Select Country Code...")] + list(COUNTRIES)
        kwargs.setdefault("choices", choices)
        kwargs.setdefault("label", "Country Code")
        widget = kwargs.get("widget") or forms.Select(attrs={"class": "form-select", "id": "id_country"})
        kwargs["widget"] = widget
        super().__init__(*args, **kwargs)

    def validate(self, value):
        if value:
            code = value.strip().upper()
            if len(code) != 2 or not code.isalpha():
                raise forms.ValidationError("Country must be a valid 2-letter ISO code.")
        elif self.required:
            raise forms.ValidationError("Country code is required.")

class OrganizationForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(
        max_length=150,
        label="Organization Name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Apex Industrial Solutions",
            "required": "required",
            "autocomplete": "organization",
        }),
        help_text="Primary public and operational display name."
    )
    legal_name = forms.CharField(
        max_length=200,
        required=False,
        label="Legal Entity Name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Apex Industrial Pvt Ltd",
        }),
        help_text="Official registered name for invoices, tax, and compliance exports."
    )
    timezone = TimezoneChoiceField(
        required=True,
        help_text="Standard IANA timezone for operational scheduling, audits, and SLA tracking."
    )
    country = CountryChoiceField(
        required=False,
        help_text="Standard ISO 3166-1 alpha-2 country code."
    )
    contact_email = forms.EmailField(
        required=False,
        label="Contact Email",
        widget=forms.EmailInput(attrs={
            "placeholder": "e.g. operations@apexindustrial.example.com",
            "autocomplete": "email",
        }),
        help_text="Main address for operational alerts and incident escalations."
    )
    contact_phone = forms.CharField(
        max_length=32,
        required=False,
        label="Contact Phone",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. +91 93470 51771 or +1 (555) 019-2834",
            "autocomplete": "tel",
        }),
        help_text="Primary operational contact number with country code."
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            "rows": 3,
            "placeholder": "Building, street address, city, state, postal code...",
        }),
        required=False,
        label="Physical / Registered Address",
        help_text="Headquarters or primary operations facility location."
    )

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Organization name must be at least 2 characters long.")
        return name

    def clean_timezone(self):
        tz = self.cleaned_data.get("timezone", "").strip()
        if not tz:
            raise forms.ValidationError("Timezone is required.")
        try:
            zoneinfo.ZoneInfo(tz)
        except Exception:
            raise forms.ValidationError(f"Unknown timezone '{tz}'. Please select a valid IANA timezone (e.g. UTC, Asia/Kolkata, America/New_York).")
        return tz

    def clean_country(self):
        c = self.cleaned_data.get("country", "").strip().upper()
        if c and (len(c) != 2 or not c.isalpha()):
            raise forms.ValidationError("Country must be a valid 2-letter ISO code (e.g. IN, US, GB).")
        return c

    def clean_contact_phone(self):
        phone = self.cleaned_data.get("contact_phone", "").strip()
        if phone:
            digits = re.sub(r"\D", "", phone)
            if len(digits) < 5:
                raise forms.ValidationError("Please enter a valid phone number with at least 5 digits.")
        return phone


def _role_field(org, membership=None):
    from apps.rbac import services as rbac
    from apps.rbac.role_templates import PRIMARY_ROLE_KEYS

    qs = Role.objects.for_organization(org).filter(system_key__in=PRIMARY_ROLE_KEYS).order_by("name")
    if membership is not None:
        if not rbac.has_role_assignment_permission(membership):
            return forms.ModelMultipleChoiceField(
                queryset=Role.objects.none(),
                widget=forms.CheckboxSelectMultiple, label="Roles",
            )
        if not rbac.is_owner(membership):
            qs = qs.exclude(is_owner=True)
            if not rbac.has_permission(membership, "role.manage"):
                actor_perms = set(rbac.membership_permissions(membership))
                for perms in rbac.site_permissions(membership).values():
                    actor_perms.update(perms)
                allowed_ids = [
                    r.pk for r in qs.prefetch_related("role_permissions__permission")
                    if set(r.role_permissions.values_list("permission__code", flat=True)).issubset(actor_perms)
                ]
                qs = qs.filter(pk__in=allowed_ids)
    return forms.ModelMultipleChoiceField(
        queryset=qs,
        widget=forms.CheckboxSelectMultiple, label="Roles",
    )


def _site_field(org, membership=None, *, required=False):
    from apps.rbac import services as rbac
    from apps.sites.models import Site

    qs = Site.objects.for_organization(org).order_by("code")
    if membership is not None:
        if not rbac.has_role_assignment_permission(membership):
            return forms.ModelMultipleChoiceField(
                queryset=Site.objects.none(), required=True,
                widget=forms.CheckboxSelectMultiple, label="Limit to sites",
            )
        scope = rbac.authorized_sites_for_actor(membership)
        if not scope.all_sites:
            qs = qs.filter(pk__in=scope.site_ids)
            required = True
    return forms.ModelMultipleChoiceField(
        queryset=qs, required=required,
        widget=forms.CheckboxSelectMultiple, label="Limit to sites",
        help_text="Leave empty for organization-wide access. Selected sites limit the chosen roles to those sites.",
    )


class InviteForm(BootstrapFormMixin, forms.Form):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(attrs={
            "placeholder": "e.g. user@gmail.com",
            "required": "required",
            "autocomplete": "email",
            "pattern": r"^[a-zA-Z0-9][a-zA-Z0-9._%+-]*@[a-zA-Z][a-zA-Z0-9-]*(\.[a-zA-Z][a-zA-Z0-9-]*)*\.[a-zA-Z]{2,}$",
            "title": "Enter a valid email address with a valid domain (e.g. user@gmail.com). Domain names must start with a letter and have a valid extension (e.g. .com).",
        }),
    )
    full_name = forms.CharField(
        max_length=150,
        min_length=2,
        required=True,
        label="Full name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Jane Doe",
            "required": "required",
            "minlength": "2",
            "pattern": r"^[A-Za-z\s'-]+$",
            "title": "Full name must contain only alphabetical characters.",
            "autocomplete": "name",
        }),
        help_text="Required for new accounts."
    )
    password = forms.CharField(
        max_length=128,
        min_length=8,
        required=True,
        initial="FieldOps@2026!",
        label="Password",
        widget=forms.PasswordInput(render_value=True, attrs={
            "placeholder": "FieldOps@2026!",
            "required": "required",
            "autocomplete": "new-password",
            "minlength": "8",
        }),
        help_text="Initial password for login (default: FieldOps@2026!). The user can change this in their dashboard."
    )

    def __init__(self, *args, org, membership=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.org = org
        self.membership = membership
        self.fields["roles"] = _role_field(org, membership=membership)
        self.fields["sites"] = _site_field(org, membership=membership)

    def clean_email(self):
        from apps.ui.forms import validate_strict_email
        email = validate_strict_email(self.cleaned_data.get("email"))
        if self.org and getattr(self.org, "pk", None):
            try:
                from apps.accounts.models import User
                from apps.tenancy.models import Membership
                user = User.objects.filter(email__iexact=email).first()
                if user and Membership.objects.unscoped().filter(user=user, organization=self.org).exists():
                    raise forms.ValidationError(
                        f"A member with email '{email}' already exists in this organization."
                    )
            except forms.ValidationError:
                raise
            except Exception:
                pass
        return email

    def clean_full_name(self):
        from apps.ui.forms import validate_alphabetical_name
        return validate_alphabetical_name(self.cleaned_data.get("full_name"), field_label="Full name")

    def clean_password(self):
        pwd = (self.cleaned_data.get("password") or "").strip()
        if not pwd:
            raise forms.ValidationError("Password is required.")
        if len(pwd) < 8:
            raise forms.ValidationError("Password must be at least 8 characters.")
        return pwd

    def clean_roles(self):
        roles = self.cleaned_data.get("roles")
        if not roles:
            raise forms.ValidationError("Please select at least one role.")
        return roles


class MemberEditForm(forms.Form):
    full_name = forms.CharField(
        max_length=150,
        min_length=2,
        required=True,
        widget=forms.TextInput(attrs={
            "pattern": r"^[A-Za-z\s'-]+$",
            "title": "Full name must contain only alphabetical characters."
        })
    )
    job_title = forms.CharField(max_length=100, required=False)

    def clean_full_name(self):
        from apps.ui.forms import validate_alphabetical_name
        return validate_alphabetical_name(self.cleaned_data.get("full_name"), field_label="Full name")


class RoleAssignmentForm(BootstrapFormMixin, forms.Form):
    role = forms.ModelChoiceField(queryset=Role.objects.none())
    site = forms.ModelChoiceField(queryset=None, required=False, empty_label="All sites (organization-wide)")

    def __init__(self, *args, org, membership=None, **kwargs):
        from apps.sites.models import Site

        super().__init__(*args, **kwargs)
        self.org = org
        self.membership = membership

        from apps.rbac.role_templates import PRIMARY_ROLE_KEYS
        roles_qs = Role.objects.for_organization(org).filter(system_key__in=PRIMARY_ROLE_KEYS).order_by("name")
        sites_qs = Site.objects.for_organization(org).order_by("code")

        if membership is not None:
            from apps.rbac import services as rbac

            if not rbac.has_role_assignment_permission(membership):
                self.fields["site"].queryset = Site.objects.none()
                self.fields["role"].queryset = Role.objects.none()
                return

            scope = rbac.authorized_sites_for_actor(membership)
            if scope.all_sites:
                self.fields["site"].queryset = sites_qs
                self.fields["site"].required = False
                self.fields["site"].empty_label = "All sites (organization-wide)"
            else:
                self.fields["site"].queryset = sites_qs.filter(pk__in=scope.site_ids)
                self.fields["site"].required = True
                self.fields["site"].empty_label = "Select a site"

            # Filter assignable roles according to delegation rules
            if not rbac.is_owner(membership):
                roles_qs = roles_qs.exclude(is_owner=True)
                if not rbac.has_permission(membership, "role.manage"):
                    actor_perms = set(rbac.membership_permissions(membership))
                    for perms in rbac.site_permissions(membership).values():
                        actor_perms.update(perms)
                    allowed_role_ids = []
                    for r in roles_qs.prefetch_related("role_permissions__permission"):
                        r_codes = set(r.role_permissions.values_list("permission__code", flat=True))
                        scopable_codes = {c for c in r_codes if c in rbac.catalog.site_scoped_codes()}
                        if r_codes.issubset(actor_perms) or (not scope.all_sites and scopable_codes.issubset(actor_perms)):
                            allowed_role_ids.append(r.pk)
                    roles_qs = roles_qs.filter(pk__in=allowed_role_ids)
        else:
            self.fields["site"].queryset = sites_qs

        self.fields["role"].queryset = roles_qs

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        site = cleaned_data.get("site")

        if self.membership is not None:
            from apps.rbac import services as rbac

            if not rbac.has_role_assignment_permission(self.membership):
                self.add_error(None, "You do not have permission to assign roles.")
                return cleaned_data

            scope = rbac.authorized_sites_for_actor(self.membership)
            if site is None:
                if not scope.all_sites:
                    self.add_error("site", "Organization-wide role assignment requires full site authority.")
            else:
                if not scope.allows(site):
                    self.add_error("site", "You are not authorized to assign roles for this site.")

            if role:
                if role.is_owner and not rbac.is_owner(self.membership):
                    self.add_error("role", "Only an Owner can grant the Owner role.")
                elif not rbac.is_owner(self.membership) and not rbac.has_permission(self.membership, "role.manage"):
                    actor_perms = set(rbac.membership_permissions(self.membership))
                    if site:
                        actor_perms |= set(rbac.site_permissions(self.membership).get(site.pk, frozenset()))
                        role_codes = {
                            c for c in role.role_permissions.values_list("permission__code", flat=True)
                            if c in rbac.catalog.site_scoped_codes()
                        }
                    else:
                        role_codes = set(role.role_permissions.values_list("permission__code", flat=True))
                    if role_codes - actor_perms:
                        self.add_error("role", "Cannot assign roles with permissions beyond your own authority.")

        return cleaned_data


class RoleForm(forms.Form):
    name = forms.CharField(max_length=80)
    description = forms.CharField(max_length=300, required=False)

class PlatformOrganizationCreateForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(
        max_length=150,
        label="Organization Name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Apex Industrial Solutions",
            "required": "required",
            "autocomplete": "organization",
        }),
        help_text="Primary public and operational display name."
    )
    slug = forms.CharField(
        max_length=60,
        required=True,
        label="URL Slug",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. apex-industrial",
        }),
        help_text="Unique URL identifier. Leave blank to generate automatically from name."
    )
    owner_name = forms.CharField(
        max_length=150,
        label="Initial Owner Full Name",
        widget=forms.TextInput(attrs={
            "placeholder": "e.g. Alex Morgan",
            "required": "required",
            "autocomplete": "name",
        }),
        help_text="Name of the initial Organization Owner / Super Admin."
    )
    owner_email = forms.EmailField(
        label="Initial Owner Email",
        widget=forms.EmailInput(attrs={
            "placeholder": "e.g. owner@apexindustrial.example.com",
            "required": "required",
            "autocomplete": "email",
        }),
        help_text="The owner email address used for logging in."
    )
    owner_password = forms.CharField(
        max_length=128,
        required=False,
        initial="FieldOps@2026!",
        label="Initial Owner Password",
        widget=forms.PasswordInput(render_value=True, attrs={
            "placeholder": "FieldOps@2026!",
            "autocomplete": "new-password",
        }),
        help_text="Initial password for owner login (default: FieldOps@2026!). The owner can change this in their dashboard."
    )
    timezone = TimezoneChoiceField(
        initial="UTC",
        required=True,
        help_text="Standard IANA timezone for tenant operations and SLA calculations."
    )
    country = CountryChoiceField(
        required=False,
        help_text="Standard ISO 3166-1 alpha-2 country code."
    )

    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()
        if len(name) < 2:
            raise forms.ValidationError("Organization name must be at least 2 characters long.")
        return name

    def clean_slug(self):
        slug = self.cleaned_data.get("slug", "").strip().lower()
        if not slug:
            return ""
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,58}[a-z0-9]", slug):
            raise forms.ValidationError("Slug must be 3-60 characters: lowercase letters, numbers, and hyphens.")
        return slug

    def clean_timezone(self):
        tz = self.cleaned_data.get("timezone", "").strip() or "UTC"
        try:
            zoneinfo.ZoneInfo(tz)
        except Exception:
            raise forms.ValidationError(f"Unknown timezone '{tz}'. Please enter a valid IANA timezone.")
        return tz

    def clean_country(self):
        return (self.cleaned_data.get("country", "") or "").strip().upper()[:2]

