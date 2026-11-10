"""SLA & Escalation HTML views. Chain: login -> ACTIVE membership -> permission gate -> organization + site-scoped lookup (404) ->
permission for the tracked item's site (403) -> service (validation, row locks, audit). Every button posts to an
endpoint that calls a service; nothing is simulated in the browser."""
from __future__ import annotations

import datetime
import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.assets.models import Asset, AssetCategory
from apps.contracts.models import CoverageAgreement
from apps.core.exceptions import DomainError
from apps.rbac import services as rbac
from apps.rbac.models import Role
from apps.sites import selectors as site_selectors
from apps.sites.models import OperatingCalendar, Site
from apps.sites.views import need, or404
from apps.tenancy.models import Membership
from apps.ui.mixins import TenantPermissionMixin

from . import selectors, services
from .forms import (
    EscalationRuleFormSetFactory,
    PriorityTargetFormSetFactory,
    ProfileForm,
    RuleForm,
    TargetForm,
)
from .models import EscalationRule, SLATarget

logger = logging.getLogger(__name__)

# Constants to satisfy duplicate literal checks (SonarQube)
PERM_SLA_VIEW = "sla.view"
PERM_SLA_MANAGE = "sla.manage"
PERM_SLA_ACK = "sla.acknowledge"
URL_PROFILES_LIST = "/app/sla/profiles/"
ROUTE_PROFILE_DETAIL = "sla:profile"
DEFAULT_RESPONSE_MINUTES = "15 minutes"
DEFAULT_RESOLUTION_MINUTES = "4 hours"


class SlaBase(TenantPermissionMixin, View):
    required_permission = PERM_SLA_VIEW


def _paged(request, qs, size=25, parameter="page"):
    return Paginator(qs, size).get_page(request.GET.get(parameter))


def _fail(request, exc):
    messages.error(request, exc.message if isinstance(exc, DomainError) else str(exc))


def _safe_next(request, default):
    nxt = request.POST.get("next") or ""
    return nxt if nxt.startswith("/app/") and not nxt.startswith("//") else default


def _format_form_errors(form, default_msg="Please check required values.") -> str:
    errors = []
    for field, errs in form.errors.items():
        if field == "__all__":
            for e in errs:
                errors.append(str(e))
        else:
            field_obj = form.fields.get(field)
            label = field_obj.label if (field_obj and field_obj.label) else field.replace("_", " ").title()
            for e in errs:
                errors.append(f"{label}: {e}")
    return "; ".join(errors) if errors else default_msg


def _find_default_escalation_role_pk(org):
    roles = Role.objects.for_organization(org)
    sup = roles.filter(system_key__in=["supervisor", "maintenance_supervisor"]).first()
    if sup:
        return sup.pk
    sup_by_name = roles.filter(name__icontains="supervisor").first()
    if sup_by_name:
        return sup_by_name.pk
    mgr = roles.filter(system_key__in=["operations_manager", "service_manager", "admin", "owner"]).first()
    if mgr:
        return mgr.pk
    mgr_by_name = roles.filter(name__icontains="manager").first()
    return mgr_by_name.pk if mgr_by_name else None


def _profile_form_page(request, *, title, form, submit, cancel_url, crumbs, subtitle="", status=200,
                       target_formset=None, rule_formset=None, profile=None, targets=None, rules=None):
    return render(request, "sla/profile_form.html", {
        "title": title, "form": form, "submit": submit, "cancel_url": cancel_url,
        "crumbs": crumbs, "subtitle": subtitle, "target_formset": target_formset,
        "rule_formset": rule_formset, "profile": profile, "targets": targets, "rules": rules,
    }, status=status)


# --- trackings / breaches ----------------------------------------------------------------------------------------------


TRACKING_STATUS_OPTIONS = (
    ("ACTIVE", "Active"),
    ("AT_RISK", "At Risk"),
    ("PAUSED", "Paused"),
    ("BREACHED", "Breached"),
    ("UNDER_REVIEW", "Under Review"),
    ("COMPLETED", "Completed"),
    ("CLOSED", "Closed"),
    ("CANCELLED", "Cancelled"),
)
BREACH_STATUS_OPTIONS = (
    ("OPEN", "Open"),
    ("ACKNOWLEDGED", "Acknowledged"),
    ("CLOSED", "Closed"),
)


class TrackingListView(SlaBase):
    def get(self, request):
        m, org = request.membership, request.organization
        base_trackings = selectors.trackings_for(m, org)
        qs = selectors.filter_trackings(base_trackings, request.GET)
        can_manage = rbac.has_permission(m, PERM_SLA_MANAGE)
        summary = selectors.metrics_for_trackings(qs, m, org)
        present_statuses = set(base_trackings.values_list("status", flat=True).distinct())
        selected_status = (request.GET.get("status") or "").strip()
        status_choices = [
            (val, label) for val, label in TRACKING_STATUS_OPTIONS
            if val in present_statuses or val == selected_status
        ]
        return render(request, "sla/trackings.html", {
            "page": _paged(request, qs), "filters": request.GET,
            "sites": site_selectors.sites_for(m, org, PERM_SLA_VIEW).order_by("code"),
            "status_choices": status_choices,
            "can_process": rbac.has_permission(m, "sla.process"),
            "can_manage": can_manage,
            "summary": summary})


class TrackingDetailView(SlaBase):
    def get(self, request, pk):
        m, org = request.membership, request.organization
        t = or404(selectors.get_tracking, m, org, pk)
        return render(request, "sla/tracking_detail.html", {
            "t": t, "events": selectors.events_for(org, t), "breaches": t.breaches.all(),
            "pauses": t.pause_events.select_related("paused_by", "approved_by").all(),
            "can_ack": rbac.has_permission(m, PERM_SLA_ACK, t.site_id)})


class BreachListView(SlaBase):
    def get(self, request):
        m, org = request.membership, request.organization
        base_breaches = selectors.breaches_for(m, org)
        filtered_breaches = selectors.filter_breaches(base_breaches, request.GET)
        total_breaches = filtered_breaches.count()
        open_breaches = filtered_breaches.filter(status="OPEN").count()
        ack_breaches = filtered_breaches.filter(status="ACKNOWLEDGED").count()
        page = _paged(request, filtered_breaches)
        for breach in page:
            breach.can_ack = rbac.has_permission(m, PERM_SLA_ACK, breach.site_id)
        present_statuses = set(base_breaches.values_list("status", flat=True).distinct())
        selected_status = (request.GET.get("status") or "").strip()
        status_choices = [
            (val, label) for val, label in BREACH_STATUS_OPTIONS
            if val in present_statuses or val == selected_status
        ]
        return render(request, "sla/breaches.html", {
            "page": page, "filters": request.GET,
            "sites": site_selectors.sites_for(m, org, PERM_SLA_VIEW).order_by("code"),
            "status_choices": status_choices,
            "can_manage": rbac.has_permission(m, PERM_SLA_MANAGE),
            "total_breaches": total_breaches,
            "open_breaches": open_breaches,
            "ack_breaches": ack_breaches,
        })


class BreachAcknowledgeView(SlaBase):
    required_permission = PERM_SLA_VIEW
    http_method_names = ["post"]

    def post(self, request, pk):
        breach = or404(selectors.get_breach, request.membership, request.organization, pk)
        need(request, PERM_SLA_ACK, breach.site_id)
        try:
            services.acknowledge_breach(breach, actor=request.user, request=request)
            messages.success(request, f"Breach acknowledged: {breach.get_target_kind_display()} Target.")
        except DomainError as exc:
            _fail(request, exc)
        return redirect(_safe_next(request, "/app/sla/breaches/"))


class ProcessNowView(SlaBase):
    required_permission = "sla.process"
    http_method_names = ["post"]

    def post(self, request):
        res = services.process_organization(request.organization)
        is_ajax = (
            request.headers.get("X-Requested-With") == "XMLHttpRequest"
            or "application/json" in request.headers.get("Accept", "")
            or request.POST.get("format") == "json"
        )
        if is_ajax:
            m, org = request.membership, request.organization
            metrics = selectors.metrics(m, org)
            return JsonResponse({
                "ok": True,
                "result": res,
                "metrics": metrics,
                "message": (
                    f"Checked {res['checked']} running SLA timer(s): "
                    f"{res['warnings']} warning alert(s), "
                    f"{res['breaches']} SLA breach(es), "
                    f"{res['escalations']} escalation(s), "
                    f"{res.get('notifications', 0)} notification(s) handled."
                ),
            })

        messages.success(
            request,
            f"SLA Check completed: {res['checked']} running SLA timer(s) evaluated. "
            f"{res['warnings']} warning alert(s), {res['breaches']} SLA breach(es), "
            f"{res['escalations']} escalation(s), {res.get('notifications', 0)} notification(s) handled."
        )
        next_url = _safe_next(request, request.POST.get("next") or "/app/sla/trackings/")
        return redirect(next_url)


# --- profiles -----------------------------------------------------------------------------------------------------------


class ProfileListView(SlaBase):
    required_permission = PERM_SLA_MANAGE

    def get(self, request):
        base_profiles = selectors.profiles_for(request.organization)
        total_profiles = base_profiles.count()
        active_profiles = base_profiles.filter(is_active=True).count()
        inactive_profiles = total_profiles - active_profiles
        page = _paged(request, base_profiles.prefetch_related("targets"))
        return render(request, "sla/profiles.html", {
            "page": page,
            "can_manage": True,
            "total_profiles": total_profiles,
            "active_profiles": active_profiles,
            "inactive_profiles": inactive_profiles,
        })


def _inject_single_target_meta(post_data, applies_to):
    post_data["targets-TOTAL_FORMS"] = "1"
    post_data["targets-INITIAL_FORMS"] = "0"
    post_data["targets-MIN_NUM_FORMS"] = "0"
    post_data["targets-MAX_NUM_FORMS"] = "4"
    default_p = "CRITICAL" if applies_to == "REQUEST" else "URGENT"
    post_data["targets-0-priority"] = str(post_data.get("priority") or default_p).strip().upper()
    post_data["targets-0-response_minutes"] = post_data.get("response_target") or post_data.get("response_minutes", "")
    post_data["targets-0-resolution_minutes"] = post_data.get("resolution_target") or post_data.get("resolution_minutes", "")
    post_data["targets-0-warning_percent"] = post_data.get("warning_alert") or post_data.get("warning_percent", "80")


def _prepare_create_post_data(post_data):
    raw_applies = post_data.get("applies_to", "REQUEST")
    applies_to = "WORK_ORDER" if "WORK" in str(raw_applies).upper() else "REQUEST"
    post_data["applies_to"] = applies_to

    action = post_data.get("action", "").strip().lower()
    is_draft = action == "draft"
    if is_draft:
        is_active = False
        post_data["is_active"] = ""
    else:
        is_active = post_data.get("is_active") in ("on", "true", "1", "True") or action in ("activate", "save")
        if is_active:
            post_data["is_active"] = "on"

    has_target_inputs = any(k in post_data for k in ("priority", "response_target", "response_minutes", "targets-0-priority", "targets-TOTAL_FORMS"))
    if has_target_inputs and "targets-TOTAL_FORMS" not in post_data and "form-TOTAL_FORMS" not in post_data:
        _inject_single_target_meta(post_data, applies_to)

    if "rules-TOTAL_FORMS" not in post_data and "form-TOTAL_FORMS" not in post_data:
        post_data["rules-TOTAL_FORMS"] = "0"
        post_data["rules-INITIAL_FORMS"] = "0"
        post_data["rules-MIN_NUM_FORMS"] = "0"
        post_data["rules-MAX_NUM_FORMS"] = "6"

    return applies_to, is_active, is_draft, has_target_inputs


def _save_target_formset(profile, target_formset, request):
    for target_form in target_formset:
        target_data = target_form.cleaned_data
        if not target_data or target_data.get("DELETE") or not target_data.get("priority"):
            continue
        cleaned_target = {k: v for k, v in target_data.items() if k != "DELETE" and v not in (None, "")}
        services.set_target(profile, actor=request.user, request=request, **cleaned_target)


def _save_rule_formset(profile, rule_formset, request):
    for rule_form in rule_formset:
        rule_data = rule_form.cleaned_data
        if not rule_data or rule_data.get("DELETE") or not rule_data.get("target_kind"):
            continue
        cleaned_rule = {k: v for k, v in rule_data.items() if k != "DELETE" and v not in (None, "")}
        cleaned_rule["after_minutes"] = cleaned_rule.get("after_minutes") or 0
        services.create_rule(profile, actor=request.user, request=request, **cleaned_rule)


def _save_profile_formsets(profile, target_formset, rule_formset, has_target_inputs, has_rule_inputs, request):
    if target_formset and has_target_inputs:
        _save_target_formset(profile, target_formset, request)
    if rule_formset and has_rule_inputs:
        _save_rule_formset(profile, rule_formset, request)


def _seed_profile_default_rules(profile, request):
    if not profile.targets.exists() or profile.rules.exists():
        return
    role_pk = _find_default_escalation_role_pk(request.organization)
    role_obj = Role.objects.for_organization(request.organization).filter(pk=role_pk).first() if role_pk else None
    try:
        services.create_rule(profile, target_kind="RESOLUTION", trigger="WARNING",
                             notify_role=role_obj, notify_assignee=True, level=1, actor=request.user, request=request)
        services.create_rule(profile, target_kind="RESOLUTION", trigger="BREACH",
                             notify_role=role_obj, notify_assignee=True, level=2, actor=request.user, request=request)
        services.create_rule(profile, target_kind="RESOLUTION", trigger="ESCALATION",
                             after_minutes=30, notify_role=role_obj, notify_assignee=False, level=3, actor=request.user, request=request)
    except Exception as exc:
        logger.warning("Could not auto-seed standard escalation rules: %s", exc)


class ProfileCreateView(SlaBase):
    required_permission = PERM_SLA_MANAGE
    crumbs = [("SLA profiles", URL_PROFILES_LIST), ("New", None)]

    def _form(self, request, data=None):
        raw_applies = (data.get("applies_to") if data else None) or request.POST.get("applies_to") or "WORK_ORDER"
        return ProfileForm(data, applies_to=raw_applies, organization=request.organization, **_profile_choices(request))

    def _target_formset(self, request, applies_to, data=None, is_draft=False, initial=None):
        prefix = "targets"
        if data is not None and "targets-TOTAL_FORMS" not in data and "form-TOTAL_FORMS" in data:
            prefix = "form"
        if initial is None and (data is None or "targets-TOTAL_FORMS" not in data):
            default_p = "URGENT" if applies_to == "WORK_ORDER" else "CRITICAL"
            initial = [{"priority": default_p, "response_minutes": DEFAULT_RESPONSE_MINUTES, "resolution_minutes": DEFAULT_RESOLUTION_MINUTES, "warning_percent": "80"}]
        return PriorityTargetFormSetFactory(data, initial=initial, applies_to=applies_to, prefix=prefix,
                                           is_draft=is_draft)

    def _rule_formset(self, request, data=None, initial=None):
        prefix = "rules"
        roles = Role.objects.for_organization(request.organization).order_by("name")
        if initial is None and (data is None or "rules-TOTAL_FORMS" not in data):
            role_pk = _find_default_escalation_role_pk(request.organization)
            initial = [
                {
                    "target_kind": "RESOLUTION",
                    "trigger": "WARNING",
                    "level": 1,
                    "notify_role": role_pk,
                    "notify_assignee": True,
                    "after_minutes": None
                }
            ]
        return EscalationRuleFormSetFactory(data, initial=initial, roles=roles, prefix=prefix)

    def _render(self, request, form, status=200, target_formset=None, rule_formset=None):
        applies_to = getattr(form, "applies_to", None) or (form.initial.get("applies_to") if hasattr(form, "initial") else None) or "WORK_ORDER"
        if target_formset is None or len(target_formset.forms) == 0:
            target_formset = self._target_formset(request, applies_to)
        if rule_formset is None or len(rule_formset.forms) == 0:
            rule_formset = self._rule_formset(request)
        return _profile_form_page(
            request, title="New SLA Profile", form=form, submit="Create profile",
            cancel_url=URL_PROFILES_LIST, crumbs=self.crumbs,
            subtitle="Configure profile scope, operating hours, and pause rules.",
            status=status, target_formset=target_formset, rule_formset=rule_formset)

    def get(self, request):
        form = self._form(request)
        applies_to = form.initial.get("applies_to") or "WORK_ORDER"
        target_formset = self._target_formset(request, applies_to)
        rule_formset = self._rule_formset(request)
        return self._render(request, form, target_formset=target_formset, rule_formset=rule_formset)

    def post(self, request):
        post_data = request.POST.copy()
        applies_to, is_active, is_draft, has_target_inputs = _prepare_create_post_data(post_data)

        form = self._form(request, post_data)
        target_formset = self._target_formset(request, applies_to, post_data if has_target_inputs else None, is_draft=is_draft)
        has_rule_inputs = any(k.startswith("rules-") and not k.endswith("TOTAL_FORMS") and not k.endswith("INITIAL_FORMS") and not k.endswith("MIN_NUM_FORMS") and not k.endswith("MAX_NUM_FORMS") for k in post_data)
        rule_formset = self._rule_formset(request, post_data if has_rule_inputs else None)

        target_valid = target_formset.is_valid() if has_target_inputs else True
        rule_valid = rule_formset.is_valid() if has_rule_inputs else True
        valid = form.is_valid() and target_valid and rule_valid

        if valid:
            d = dict(form.cleaned_data)
            d["is_active"] = is_active
            try:
                with transaction.atomic():
                    profile = services.create_profile(
                        request.organization, actor=request.user, request=request,
                        name=d["name"], applies_to=d["applies_to"], description=d["description"],
                        site=d.get("site"), client=d.get("client"), contract=d.get("contract"),
                        asset=d.get("asset"), asset_category=d.get("asset_category"),
                        service_type=d.get("service_type", ""), work_type=d.get("work_type", ""),
                        pause_states=d["pause_states"], coverage_only=d.get("coverage_only", False),
                        is_active=d["is_active"], calendar=d.get("calendar"),
                        use_business_hours=d.get("use_business_hours", False))
                    _save_profile_formsets(profile, target_formset, rule_formset, has_target_inputs, has_rule_inputs, request)
                    _seed_profile_default_rules(profile, request)

                messages.success(request, f"SLA Profile '{profile.name}' was created.")
                return redirect(ROUTE_PROFILE_DETAIL, pk=profile.pk)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return self._render(request, form, status=400, target_formset=target_formset, rule_formset=rule_formset)


class ProfileBase(SlaBase):
    required_permission = PERM_SLA_MANAGE

    def profile(self, request, pk):
        return or404(selectors.get_profile, request.organization, pk)


def _ensure_default_operating_calendars(org):
    calendars_qs = OperatingCalendar.objects.for_organization(org).select_related("site").order_by("site__code", "name")
    if calendars_qs.exists():
        return calendars_qs
    sites = Site.objects.for_organization(org)
    for s in sites:
        try:
            OperatingCalendar.objects.create(
                organization=org,
                site=s,
                name=f"Standard Business Hours ({s.code})",
                working_days=[1, 2, 3, 4, 5],
                start_time=datetime.time(8, 0),
                end_time=datetime.time(17, 0),
                is_default=True,
                is_24x7=False,
                notes=f"Default 08:00-17:00 Mon-Fri operating calendar for {s.code}"
            )
        except Exception as e:
            logger.warning("Could not auto-seed OperatingCalendar for site %s: %s", s.code, e)
    return OperatingCalendar.objects.for_organization(org).select_related("site").order_by("site__code", "name")


def _profile_choices(request):
    org = request.organization
    clients = Membership.objects.for_organization(org).filter(status=Membership.Status.ACTIVE,
        membership_roles__role__system_key="client_requester").select_related("user").distinct()

    calendars_qs = _ensure_default_operating_calendars(org)

    return {
        "sites": Site.objects.for_organization(org).order_by("code"),
        "clients": clients,
        "contracts": CoverageAgreement.objects.for_organization(org).filter(is_active=True)
            .select_related("site").order_by("reference"),
        "assets": Asset.objects.for_organization(org).select_related("site").order_by("asset_tag"),
        "categories": AssetCategory.objects.for_organization(org).order_by("name"),
        "calendars": calendars_qs,
    }


class ProfileDetailView(ProfileBase):
    def get(self, request, pk):
        p = self.profile(request, pk)
        org = request.organization
        return render(request, "sla/profile_detail.html", {
            "p": p, "targets": p.targets.order_by("priority"), "rules": p.rules.select_related("notify_role"),
            "target_form": TargetForm(applies_to=p.applies_to),
            "rule_form": RuleForm(roles=Role.objects.for_organization(org).order_by("name"), applies_to=p.applies_to),
            "max_rules": services.MAX_RULES_PER_PROFILE})


def _remove_missing_targets(profile, submitted_priorities, target_formset, request):
    form_priorities = {
        f.cleaned_data.get("priority")
        for f in target_formset
        if f.cleaned_data and f.cleaned_data.get("priority")
    }
    for existing_t in profile.targets.all():
        if existing_t.priority not in submitted_priorities and existing_t.priority not in form_priorities:
            services.remove_target(existing_t, actor=request.user, request=request)


def _sync_edit_targets(profile, target_formset, request):
    submitted_priorities = set()
    for t_form in target_formset:
        t_data = t_form.cleaned_data
        if not t_data:
            continue
        prio = t_data.get("priority")
        if t_data.get("DELETE"):
            existing = profile.targets.filter(priority=prio).first() if prio else None
            if existing:
                services.remove_target(existing, actor=request.user, request=request)
            continue
        if prio and t_data.get("response_minutes") and t_data.get("resolution_minutes"):
            clean_t_data = {k: v for k, v in t_data.items() if k != "DELETE" and v not in (None, "")}
            services.set_target(profile, actor=request.user, request=request, **clean_t_data)
            submitted_priorities.add(prio)

    _remove_missing_targets(profile, submitted_priorities, target_formset, request)


def _sync_edit_formsets(profile, target_formset, rule_formset, request):
    _sync_edit_targets(profile, target_formset, request)
    profile.rules.all().delete()
    _save_rule_formset(profile, rule_formset, request)


def _sync_edit_single_target(profile, post_data, request):
    resp_val = post_data.get("response_target") or post_data.get("response_minutes")
    resol_val = post_data.get("resolution_target") or post_data.get("resolution_minutes")
    prio_val = post_data.get("priority")
    warn_val = post_data.get("warning_alert") or post_data.get("warning_percent", "80")
    if resp_val and resol_val and prio_val:
        services.set_target(
            profile,
            priority=str(prio_val).strip().upper(),
            response_minutes=services.parse_duration_minutes(resp_val, what="Response Target"),
            resolution_minutes=services.parse_duration_minutes(resol_val, what="Resolution Target"),
            warning_percent=services.parse_percentage(warn_val, what="Warning Alert"),
            actor=request.user,
            request=request
        )


class ProfileEditView(ProfileBase):
    def _page(self, request, p, form, status=200, target_formset=None, rule_formset=None):
        return _profile_form_page(
            request,
            title=f"Edit SLA profile: {p.name}",
            form=form,
            submit="Save changes",
            status=status,
            cancel_url=f"/app/sla/profiles/{p.pk}/",
            crumbs=[("SLA profiles", URL_PROFILES_LIST), (p.name, f"/app/sla/profiles/{p.pk}/"),
                    ("Edit", None)],
            subtitle="Update scope matching criteria, operating hours, and pause rules.",
            profile=p,
            targets=p.targets.order_by("priority"),
            rules=p.rules.select_related("notify_role"),
            target_formset=target_formset,
            rule_formset=rule_formset
        )

    def get(self, request, pk):
        p = self.profile(request, pk)
        initial = {
            "name": p.name,
            "description": p.description,
            "pause_states": p.pause_states,
            "applies_to": p.applies_to,
            "site": p.site_id,
            "client": p.client_id,
            "contract": p.contract_id,
            "asset": p.asset_id,
            "asset_category": p.asset_category_id,
            "service_type": p.service_type or p.work_type,
            "work_type": p.work_type,
            "coverage_only": p.coverage_only,
            "calendar": p.calendar_id,
            "use_business_hours": p.use_business_hours,
        }
        form = ProfileForm(
            editing=True,
            applies_to=p.applies_to,
            instance=p,
            organization=request.organization,
            initial=initial,
            **_profile_choices(request)
        )
        target_initial = [
            {
                "priority": t.priority,
                "response_minutes": f"{t.response_minutes} minutes",
                "resolution_minutes": f"{t.resolution_minutes} minutes",
                "warning_percent": f"{t.warning_percent}%",
            }
            for t in p.targets.order_by("priority")
        ]
        if not target_initial:
            default_p = "URGENT" if p.applies_to == "WORK_ORDER" else "CRITICAL"
            target_initial = [{"priority": default_p, "response_minutes": DEFAULT_RESPONSE_MINUTES, "resolution_minutes": DEFAULT_RESOLUTION_MINUTES, "warning_percent": "80"}]

        target_formset = PriorityTargetFormSetFactory(
            initial=target_initial, applies_to=p.applies_to, prefix="targets"
        )
        roles = Role.objects.for_organization(request.organization).order_by("name")
        rule_initial = [
            {
                "target_kind": r.target_kind,
                "trigger": r.trigger,
                "after_minutes": r.after_minutes if r.trigger == "ESCALATION" else None,
                "level": r.level,
                "notify_role": r.notify_role_id,
                "notify_assignee": r.notify_assignee,
            }
            for r in p.rules.order_by("level", "trigger")
        ]
        rule_formset = EscalationRuleFormSetFactory(
            initial=rule_initial, roles=roles, prefix="rules"
        )
        return self._page(request, p, form, target_formset=target_formset, rule_formset=rule_formset)

    def post(self, request, pk):
        p = self.profile(request, pk)
        post_data = request.POST.copy()
        applies_to = post_data.get("applies_to", p.applies_to)
        form = ProfileForm(post_data, editing=True, applies_to=applies_to,
                           instance=p, organization=request.organization,
                           **_profile_choices(request))
        roles = Role.objects.for_organization(request.organization).order_by("name")

        has_target_formset = "targets-TOTAL_FORMS" in post_data
        has_single_target = "priority" in post_data and ("response_target" in post_data or "response_minutes" in post_data)

        target_formset = None
        rule_formset = None
        valid = form.is_valid()

        if has_target_formset:
            target_formset = PriorityTargetFormSetFactory(post_data, applies_to=applies_to, prefix="targets")
            rule_formset = EscalationRuleFormSetFactory(post_data, roles=roles, prefix="rules")
            valid = valid and target_formset.is_valid() and rule_formset.is_valid()

        if valid:
            try:
                with transaction.atomic():
                    services.update_profile(p, actor=request.user, request=request, **form.cleaned_data)
                    if has_target_formset:
                        _sync_edit_formsets(p, target_formset, rule_formset, request)
                    elif has_single_target:
                        _sync_edit_single_target(p, post_data, request)

                messages.success(request, f"SLA Profile '{p.name}' updated.")
                return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return self._page(request, p, form, status=400, target_formset=target_formset, rule_formset=rule_formset)


class ProfileActiveView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = self.profile(request, pk)
        active = request.POST.get("active") == "1"
        try:
            services.set_profile_active(p, active, actor=request.user, request=request)
            messages.success(request, "SLA Profile activated." if active else
                             "SLA Profile deactivated: new Incident / Breakdown or Work Order records will not be tracked by it.")
        except DomainError as exc:
            _fail(request, exc)
        return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)


class TargetSetView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = self.profile(request, pk)
        form = TargetForm(request.POST, applies_to=p.applies_to)
        if form.is_valid() and form.cleaned_data.get("priority"):
            try:
                services.set_target(p, actor=request.user, request=request, **form.cleaned_data)
                messages.success(request, f"Target for {form.cleaned_data['priority'].title()} saved.")
            except DomainError as exc:
                _fail(request, exc)
            except Exception as exc:
                messages.error(request, f"Could not save target: {exc}")
        else:
            err_msg = _format_form_errors(form, "Choose a priority and valid duration targets.")
            messages.error(request, f"Check the target values: {err_msg}")
        return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)


class TargetRemoveView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk, target_pk):
        p = self.profile(request, pk)
        target = SLATarget.objects.for_organization(request.organization).filter(pk=target_pk, profile=p).first()
        if target is None:
            raise Http404
        services.remove_target(target, actor=request.user, request=request)
        messages.success(request, "Target removed.")
        return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)


class RuleCreateView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = self.profile(request, pk)
        form = RuleForm(request.POST, roles=Role.objects.for_organization(request.organization), applies_to=p.applies_to)
        if form.is_valid():
            d = dict(form.cleaned_data)
            d["after_minutes"] = d.get("after_minutes") or 0
            d["notify_assignee"] = bool(d.get("notify_assignee"))
            try:
                services.create_rule(p, actor=request.user, request=request, **d)
                messages.success(request, f"Escalation rule for {d['target_kind'].title()} ({d['trigger'].title()}) saved.")
            except DomainError as exc:
                _fail(request, exc)
            except Exception as exc:
                messages.error(request, f"Could not add rule: {exc}")
        else:
            err_msg = _format_form_errors(form, "Provide required rule values.")
            messages.error(request, f"Check the rule values: {err_msg}")
        return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)


class RuleUpdateView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk, rule_pk):
        p = self.profile(request, pk)
        rule = EscalationRule.objects.for_organization(request.organization).filter(pk=rule_pk, profile=p).first()
        if rule is None:
            raise Http404
        form = RuleForm(request.POST, roles=Role.objects.for_organization(request.organization), applies_to=p.applies_to)
        if form.is_valid():
            d = dict(form.cleaned_data)
            d["after_minutes"] = d.get("after_minutes") or 0
            d["notify_assignee"] = bool(d.get("notify_assignee"))
            try:
                services.update_rule(rule, actor=request.user, request=request, **d)
                messages.success(request, "Escalation rule updated.")
            except DomainError as exc:
                _fail(request, exc)
            except Exception as exc:
                messages.error(request, f"Could not update rule: {exc}")
        else:
            err_msg = _format_form_errors(form, "Provide required rule values.")
            messages.error(request, f"Check the rule values: {err_msg}")
        return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)


class RuleDeleteView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk, rule_pk):
        p = self.profile(request, pk)
        rule = EscalationRule.objects.for_organization(request.organization).filter(pk=rule_pk, profile=p).first()
        if rule is None:
            raise Http404
        services.delete_rule(rule, actor=request.user, request=request)
        messages.success(request, "Rule removed.")
        return redirect(ROUTE_PROFILE_DETAIL, pk=p.pk)
