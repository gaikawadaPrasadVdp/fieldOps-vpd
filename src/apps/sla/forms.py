from django import forms
from django.forms import BaseFormSet, formset_factory

from apps.assets.models import Asset, AssetCategory
from apps.contracts.models import CoverageAgreement
from apps.rbac.models import Role
from apps.sites.models import OperatingCalendar, Site
from apps.tenancy.models import Membership
from apps.ui.forms import BootstrapFormMixin

from .models import EscalationRule
from .services import REQUEST_PRIORITIES, WORK_ORDER_PRIORITIES, valid_pause_tokens


class _SiteChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.code} · {obj.name}"


class _ClientChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"{obj.user.display_name} · {obj.user.email}"


class _AssetChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        site_str = f" [{obj.site.code}]" if getattr(obj, "site", None) else ""
        return f"{obj.asset_tag} · {obj.name}{site_str}"


class _ContractChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        site_str = f" [{obj.site.code}]" if getattr(obj, "site", None) else ""
        return f"{obj.reference} · {obj.title}{site_str}"


class _CalendarChoice(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        site_str = f" [{obj.site.code}]" if getattr(obj, "site", None) else ""
        return f"{obj.name}{site_str}"


def _pause_choices(applies_to=None, current_values=None):
    primary = [
        ("WORK_ORDER:ON_HOLD", "Work Order · On Hold (Recommended: waiting for parts, client, access, approval, weather)"),
        ("REQUEST:ON_HOLD", "Incident / Service Request · On Hold"),
    ]
    seen = {k for k, _ in primary}
    if current_values:
        for val in current_values:
            if val and val not in seen:
                primary.append((val, val.replace("_", " ").title()))
                seen.add(val)
    return primary


class AppliesToChoiceField(forms.ChoiceField):
    def valid_value(self, value):
        if super().valid_value(value):
            return True
        s = str(value).strip().upper()
        return s in ("REQUEST", "WORK_ORDER", "INCIDENT / BREAKDOWN", "WORK ORDER", "SERVICE REQUEST", "SERVICE REQUESTS / INCIDENTS")


class ProfileForm(BootstrapFormMixin, forms.Form):
    name = forms.CharField(max_length=120, label="Name")
    description = forms.CharField(max_length=300, required=False, label="Description")
    applies_to = AppliesToChoiceField(
        choices=[
            ("WORK_ORDER", "Work Order"),
            ("REQUEST", "Incident / Breakdown"),
        ],
        initial="WORK_ORDER",
        label="Applies to"
    )
    site = _SiteChoice(queryset=Site.objects.none(), required=False, label="Site (blank = whole organization)")
    client = _ClientChoice(queryset=Membership.objects.none(), required=False, label="Client / requester (Optional)")
    contract = _ContractChoice(
        queryset=CoverageAgreement.objects.none(),
        required=False,
        label="Maintenance Agreement (Optional)",
        help_text="Optional. Only required if this SLA is specific to a vendor maintenance agreement or warranty."
    )
    asset = _AssetChoice(queryset=Asset.objects.none(), required=False, label="Asset (Optional)")
    asset_category = forms.ModelChoiceField(queryset=AssetCategory.objects.none(), required=False,
                                            label="Asset category (Optional)")
    coverage_only = forms.BooleanField(
        required=False,
        label="Coverage-only profile",
        help_text="Apply only to assets covered by a warranty / AMC / contract that names this profile."
    )
    service_type = forms.ChoiceField(choices=[], required=False, label="Service type")
    work_type = forms.CharField(max_length=20, required=False, widget=forms.HiddenInput())
    use_business_hours = forms.BooleanField(
        required=False,
        initial=False,
        label="Calculate SLA targets using business hours",
        help_text="When enabled, target deadlines pause outside operating calendar hours and on holidays."
    )
    calendar = _CalendarChoice(
        queryset=OperatingCalendar.objects.none(),
        required=False,
        label="Operating calendar (optional)",
        help_text="Operating calendar schedule. If left blank, the site calendar or organization default calendar is used."
    )
    is_active = forms.BooleanField(required=False, initial=True, label="Activate this profile when saved")
    pause_states = forms.MultipleChoiceField(
        required=False, choices=_pause_choices(), widget=forms.CheckboxSelectMultiple,
        initial=["WORK_ORDER:ON_HOLD"],
        label="Pause the timers while the item is in",
        help_text="Leave empty to never pause (timers keep running).")

    def __init__(self, *args, sites=None, clients=None, contracts=None, assets=None, categories=None,
                 calendars=None, applies_to="WORK_ORDER", editing=False, organization=None, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organization = organization
        self.instance = instance
        self.editing = editing
        if self.is_bound:
            raw_applies = self.data.get("applies_to") or applies_to
            applies_to = "WORK_ORDER" if str(raw_applies).strip().upper() in ("WORK_ORDER", "WORK ORDER") or "WORK" in str(raw_applies).upper() else "REQUEST"
        else:
            raw_applies = self.initial.get("applies_to") or applies_to
            applies_to = "WORK_ORDER" if str(raw_applies).strip().upper() in ("WORK_ORDER", "WORK ORDER") or "WORK" in str(raw_applies).upper() else "REQUEST"
        cur_pauses = self.data.getlist("pause_states") if self.is_bound else self.initial.get("pause_states")
        self.fields["pause_states"].choices = _pause_choices(applies_to, cur_pauses)
        self.fields["site"].queryset = sites if sites is not None else Site.objects.none()
        self.fields["client"].queryset = clients or Membership.objects.none()
        self.fields["client"].queryset = self.fields["client"].queryset.select_related("user")
        self.fields["contract"].queryset = contracts if contracts is not None else CoverageAgreement.objects.none()
        self.fields["asset"].queryset = assets or Asset.objects.none()
        self.fields["asset_category"].queryset = categories or AssetCategory.objects.none()
        self.fields["calendar"].queryset = calendars if calendars is not None else OperatingCalendar.objects.none()
        from apps.incidents.models import ServiceRequest
        from apps.workorders.models import WorkOrder
        if applies_to == "WORK_ORDER":
            self.fields["service_type"].label = "Work order type"
            self.fields["service_type"].choices = [("", "All Work Order Types")] + list(WorkOrder.WorkType.choices)
            self.fields["service_type"].help_text = (
                "Optional filter. Matches specific work order types (e.g. Corrective, Emergency) or leave blank for all.")
        else:
            self.fields["service_type"].label = "Incident type"
            self.fields["service_type"].choices = [("", "All Incident / Breakdown tickets")]
            self.fields["service_type"].help_text = ""
        if editing:
            self.fields.pop("is_active")

    def clean_name(self):
        name = (self.cleaned_data.get("name") or "").strip()
        if len(name) < 3:
            raise forms.ValidationError("Profile name must be at least 3 characters long.")
        if self.organization:
            from .models import SLAProfile
            qs = SLAProfile.objects.for_organization(self.organization).filter(name__iexact=name)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(f"An SLA Profile named '{name}' already exists in your organization. Choose a distinct name.")
        return name

    def clean_applies_to(self):
        val = self.cleaned_data.get("applies_to")
        if not val:
            return "REQUEST"
        s = str(val).strip()
        if s in ("REQUEST", "WORK_ORDER"):
            return s
        if "WORK" in s.upper():
            return "WORK_ORDER"
        return "REQUEST"

    def clean(self):
        cleaned = super().clean()
        applies_to = cleaned.get("applies_to") or "REQUEST"
        if applies_to == "REQUEST":
            cleaned["service_type"] = ""
            cleaned["work_type"] = ""
        else:
            if not cleaned.get("work_type") and cleaned.get("service_type"):
                cleaned["work_type"] = cleaned.get("service_type")
        site = cleaned.get("site")
        asset = cleaned.get("asset")
        category = cleaned.get("asset_category")
        contract = cleaned.get("contract")
        calendar = cleaned.get("calendar")

        if asset and not site and getattr(asset, "site", None):
            cleaned["site"] = asset.site
            site = asset.site
        if contract and not site and getattr(contract, "site", None):
            cleaned["site"] = contract.site
            site = contract.site

        if asset and site and asset.site_id != site.pk:
            site_name = site.name or site.code
            asset_site_name = asset.site.name if asset.site else "another site"
            self.add_error(
                "asset",
                f"The selected asset '{asset.asset_tag}' belongs to '{asset_site_name}', but site '{site_name}' is selected. Choose an asset located at '{site_name}', or leave blank to apply to all equipment at this site."
            )
        if asset and category and asset.category_id != category.pk:
            self.add_error("asset", f"The selected asset does not belong to the selected category '{category.name}'.")
        if calendar and site and calendar.site_id and calendar.site_id != site.pk:
            self.add_error("calendar", "The selected calendar must belong to the policy site.")
        return cleaned


class TargetForm(BootstrapFormMixin, forms.Form):
    priority = forms.CharField(required=False, label="Priority")
    response_minutes = forms.CharField(
        required=False, label="Response Target",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 15 minutes"}))
    resolution_minutes = forms.CharField(
        required=False, label="Resolution Target",
        widget=forms.TextInput(attrs={"placeholder": "e.g. 4 hours"}))
    warning_percent = forms.CharField(
        required=False, initial=80, label="Warning Alert",
        widget=forms.TextInput(attrs={"placeholder": "80"}))

    def __init__(self, *args, applies_to="REQUEST", **kwargs):
        super().__init__(*args, **kwargs)
        self.applies_to = "WORK_ORDER" if str(applies_to).strip().upper() in ("WORK_ORDER", "WORK ORDER") or "WORK" in str(applies_to).upper() else "REQUEST"
        if self.applies_to == "WORK_ORDER":
            choices = [("", "Choose priority (optional)"), ("URGENT", "Urgent"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")]
        else:
            choices = [("", "Choose priority (optional)"), ("CRITICAL", "Critical"), ("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")]
        self.fields["priority"] = forms.CharField(
            required=False, label="Priority",
            widget=forms.Select(choices=choices, attrs={"class": "form-select"})
        )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        pfx = f"{self.prefix}-" if self.prefix else ""

        priority_val = cleaned.get("priority")
        if not priority_val and self.is_bound:
            priority_val = self.data.get(f"{pfx}priority")

        resp_val = cleaned.get("response_minutes")
        if (resp_val is None or str(resp_val).strip() == "") and self.is_bound:
            resp_val = self.data.get(f"{pfx}response_target") or self.data.get(f"{pfx}response_minutes") or self.data.get(f"{pfx}response")

        resol_val = cleaned.get("resolution_minutes")
        if (resol_val is None or str(resol_val).strip() == "") and self.is_bound:
            resol_val = self.data.get(f"{pfx}resolution_target") or self.data.get(f"{pfx}resolution_minutes") or self.data.get(f"{pfx}resolution")

        warn_val = cleaned.get("warning_percent")
        if (warn_val is None or str(warn_val).strip() == "") and self.is_bound:
            warn_val = self.data.get(f"{pfx}warning_alert") or self.data.get(f"{pfx}warning_percent") or self.data.get(f"{pfx}warn_at")

        # Completely empty row check
        if not priority_val and (resp_val is None or str(resp_val).strip() == "") and (resol_val is None or str(resol_val).strip() == ""):
            return {}

        from .services import parse_duration_minutes, parse_percentage
        valid_prios = WORK_ORDER_PRIORITIES if self.applies_to == "WORK_ORDER" else REQUEST_PRIORITIES

        # Validate priority
        if not priority_val:
            self.add_error("priority", "Choose a priority.")
        else:
            clean_p = str(priority_val).strip().upper()
            if clean_p not in valid_prios:
                self.add_error("priority", f"Priority must be one of {', '.join(p.title() for p in valid_prios)}.")
            else:
                cleaned["priority"] = clean_p

        # Validate response target
        if resp_val is None or str(resp_val).strip() == "":
            self.add_error("response_minutes", "Response Target is required.")
        else:
            try:
                resp_mins = parse_duration_minutes(resp_val, what="Response Target")
                if resp_mins <= 0:
                    self.add_error("response_minutes", "Response Target must be greater than zero.")
                else:
                    cleaned["response_minutes"] = resp_mins
            except Exception as e:
                self.add_error("response_minutes", str(e))

        # Validate resolution target
        if resol_val is None or str(resol_val).strip() == "":
            self.add_error("resolution_minutes", "Resolution Target is required.")
        else:
            try:
                resol_mins = parse_duration_minutes(resol_val, what="Resolution Target")
                if resol_mins <= 0:
                    self.add_error("resolution_minutes", "Resolution Target must be greater than zero.")
                else:
                    cleaned["resolution_minutes"] = resol_mins
            except Exception as e:
                self.add_error("resolution_minutes", str(e))

        # Validate warning alert
        if warn_val is None or str(warn_val).strip() == "":
            cleaned["warning_percent"] = 80
        else:
            try:
                warn_pct = parse_percentage(warn_val, what="Warning Alert")
                if warn_pct < 1 or warn_pct > 99:
                    self.add_error("warning_percent", "Warning Alert must be between 1% and 99%.")
                else:
                    cleaned["warning_percent"] = warn_pct
            except Exception as e:
                self.add_error("warning_percent", str(e))

        # Check resolution >= response
        if cleaned.get("response_minutes") and cleaned.get("resolution_minutes"):
            if cleaned["resolution_minutes"] < cleaned["response_minutes"]:
                self.add_error("resolution_minutes", "The Resolution Target cannot be shorter than the Response Target.")

        return cleaned


class PriorityTargetFormSet(BaseFormSet):
    def __init__(self, *args, applies_to="REQUEST", is_draft=False, **kwargs):
        self.applies_to = "WORK_ORDER" if str(applies_to).strip().upper() in ("WORK_ORDER", "WORK ORDER") or "WORK" in str(applies_to).upper() else "REQUEST"
        self.is_draft = is_draft
        super().__init__(*args, form_kwargs={"applies_to": self.applies_to}, **kwargs)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active_priorities = []
        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue
            prio = form.cleaned_data.get("priority")
            if prio:
                active_priorities.append(prio)
        if not active_priorities:
            if not self.is_draft:
                raise forms.ValidationError("An active SLA Profile requires at least one complete Priority Target (both Response Target and Resolution Target). Define a target or save as Draft.")
            return
        if len(active_priorities) != len(set(active_priorities)):
            duplicates = [p for p in set(active_priorities) if active_priorities.count(p) > 1]
            dup_str = ", ".join(d.title() for d in duplicates)
            raise forms.ValidationError(f"Duplicate priority target detected: {dup_str}. Each priority level can only have one target in an SLA Profile.")


PriorityTargetFormSetFactory = formset_factory(
    TargetForm, formset=PriorityTargetFormSet, extra=0, min_num=0, validate_min=False,
    max_num=4, validate_max=True, can_delete=True,
)


class RuleForm(BootstrapFormMixin, forms.Form):
    target_kind = forms.ChoiceField(required=False,
                                    choices=[("", "Choose target"), ("RESPONSE", "Response Target"),
                                             ("RESOLUTION", "Resolution Target")], label="Target")
    trigger = forms.ChoiceField(required=False,
                                choices=[("", "Choose trigger"), *EscalationRule.Trigger.choices], label="When")
    after_minutes = forms.IntegerField(required=False, min_value=1, label="Escalate after (minutes, Escalation only)")
    level = forms.IntegerField(min_value=1, max_value=3, initial=1, label="Escalation level")
    notify_role = forms.ModelChoiceField(queryset=Role.objects.none(), required=False, label="Notify role")
    notify_assignee = forms.BooleanField(required=False, label="Notify the assignee")

    def __init__(self, *args, roles=None, **kwargs):
        super().__init__(*args, **kwargs)
        if roles is not None:
            self.fields["notify_role"].queryset = roles

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("DELETE"):
            return cleaned
        target, trigger = cleaned.get("target_kind"), cleaned.get("trigger")
        role, assignee = cleaned.get("notify_role"), cleaned.get("notify_assignee")
        after = cleaned.get("after_minutes")
        if not any((target, trigger, role, assignee, after)):
            return cleaned
        if not target:
            self.add_error("target_kind", "Choose which target this rule monitors.")
        if not trigger:
            self.add_error("trigger", "Choose when this rule should run.")
        if not role and not assignee:
            self.add_error("notify_role", "Choose a role or the assignee to notify.")
        if trigger == EscalationRule.Trigger.ESCALATION and not after:
            self.add_error("after_minutes", "Set how many minutes after the SLA Breach to escalate.")
        if trigger and trigger != EscalationRule.Trigger.ESCALATION and after:
            self.add_error("after_minutes", "Only Escalation rules use an after-breach delay.")
        return cleaned


class EscalationRuleFormSet(BaseFormSet):
    def __init__(self, *args, roles=None, **kwargs):
        super().__init__(*args, form_kwargs={"roles": roles}, **kwargs)


EscalationRuleFormSetFactory = formset_factory(
    RuleForm, formset=EscalationRuleFormSet, extra=0, can_delete=True, max_num=6, validate_max=True,
)
