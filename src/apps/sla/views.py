"""SLA & Escalation HTML views. Chain: login -> ACTIVE membership -> permission gate -> organization + site-scoped lookup (404) ->
permission for the tracked item's site (403) -> service (validation, row locks, audit). Every button posts to an
endpoint that calls a service; nothing is simulated in the browser."""
from __future__ import annotations

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


class SlaBase(TenantPermissionMixin, View):
    required_permission = "sla.view"


def _paged(request, qs, size=25, parameter="page"):
    return Paginator(qs, size).get_page(request.GET.get(parameter))


def _fail(request, exc):
    messages.error(request, exc.message if isinstance(exc, DomainError) else str(exc))


def _safe_next(request, default):
    nxt = request.POST.get("next") or ""
    return nxt if nxt.startswith("/app/") and not nxt.startswith("//") else default


def _profile_form_page(request, *, title, form, submit, cancel_url, crumbs, subtitle="", status=200,
                       target_formset=None, rule_formset=None, profile=None, targets=None, rules=None):
    return render(request, "sla/profile_form.html", {
        "title": title, "form": form, "submit": submit, "cancel_url": cancel_url,
        "crumbs": crumbs, "subtitle": subtitle, "target_formset": target_formset,
        "rule_formset": rule_formset, "profile": profile, "targets": targets, "rules": rules,
    }, status=status)


# --- trackings / breaches ----------------------------------------------------------------------------------------------


class TrackingListView(SlaBase):
    def get(self, request):
        m, org = request.membership, request.organization
        qs = selectors.filter_trackings(selectors.trackings_for(m, org), request.GET)
        can_manage = rbac.has_permission(m, "sla.manage")
        return render(request, "sla/trackings.html", {
            "page": _paged(request, qs), "filters": request.GET,
            "sites": site_selectors.sites_for(m, org, "sla.view").order_by("code"),
            "can_process": rbac.has_permission(m, "sla.process"),
            "can_manage": can_manage,
            "summary": selectors.metrics(m, org)})


class TrackingDetailView(SlaBase):
    def get(self, request, pk):
        m, org = request.membership, request.organization
        t = or404(selectors.get_tracking, m, org, pk)
        return render(request, "sla/tracking_detail.html", {
            "t": t, "events": selectors.events_for(org, t), "breaches": t.breaches.all(),
            "pauses": t.pause_events.select_related("paused_by", "approved_by").all(),
            "can_ack": rbac.has_permission(m, "sla.acknowledge", t.site_id)})


class BreachListView(SlaBase):
    def get(self, request):
        m, org = request.membership, request.organization
        base_breaches = selectors.breaches_for(m, org)
        total_breaches = base_breaches.count()
        open_breaches = base_breaches.filter(acknowledged_at__isnull=True).count()
        ack_breaches = total_breaches - open_breaches
        page = _paged(request, selectors.filter_breaches(base_breaches, request.GET))
        for breach in page:
            breach.can_ack = rbac.has_permission(m, "sla.acknowledge", breach.site_id)
        return render(request, "sla/breaches.html", {
            "page": page, "filters": request.GET,
            "sites": site_selectors.sites_for(m, org, "sla.view").order_by("code"),
            "can_manage": rbac.has_permission(m, "sla.manage"),
            "total_breaches": total_breaches,
            "open_breaches": open_breaches,
            "ack_breaches": ack_breaches,
        })


class BreachAcknowledgeView(SlaBase):
    required_permission = "sla.view"
    http_method_names = ["post"]

    def post(self, request, pk):
        breach = or404(selectors.get_breach, request.membership, request.organization, pk)
        need(request, "sla.acknowledge", breach.site_id)
        try:
            services.acknowledge_breach(breach, actor=request.user, request=request)
            messages.success(request, "Breach acknowledged.")
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
    required_permission = "sla.manage"

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


class ProfileCreateView(SlaBase):
    required_permission = "sla.manage"
    crumbs = [("SLA profiles", "/app/sla/profiles/"), ("New", None)]

    def _form(self, request, data=None):
        raw_applies = (data.get("applies_to") if data else None) or request.POST.get("applies_to") or "WORK_ORDER"
        return ProfileForm(data, applies_to=raw_applies, organization=request.organization, **_profile_choices(request))

    def _target_formset(self, request, applies_to, data=None, is_draft=False, initial=None):
        prefix = "targets"
        if data is not None and "targets-TOTAL_FORMS" not in data and "form-TOTAL_FORMS" in data:
            prefix = "form"
        if initial is None and data is None:
            default_p = "URGENT" if applies_to == "WORK_ORDER" else "CRITICAL"
            initial = [{"priority": default_p, "response_minutes": "15 minutes", "resolution_minutes": "4 hours", "warning_percent": "80"}]
        return PriorityTargetFormSetFactory(data, initial=initial, applies_to=applies_to, prefix=prefix,
                                           is_draft=is_draft)

    def _rule_formset(self, request, data=None, initial=None):
        prefix = "rules"
        roles = Role.objects.for_organization(request.organization).order_by("name")
        if initial is None and data is None:
            sup_role = Role.objects.for_organization(request.organization).filter(
                system_key__in=["supervisor", "maintenance_supervisor"]
            ).first() or Role.objects.for_organization(request.organization).filter(name__icontains="supervisor").first()
            mgr_role = Role.objects.for_organization(request.organization).filter(
                system_key__in=["operations_manager", "service_manager", "admin", "owner"]
            ).first() or Role.objects.for_organization(request.organization).filter(name__icontains="manager").first()
            initial = [
                {
                    "target_kind": "RESOLUTION",
                    "trigger": "WARNING",
                    "level": 1,
                    "notify_role": sup_role.pk if sup_role else (mgr_role.pk if mgr_role else None),
                    "notify_assignee": True,
                    "after_minutes": None
                }
            ]
        return EscalationRuleFormSetFactory(data, initial=initial, roles=roles, prefix=prefix)

    def _render(self, request, form, status=200, target_formset=None, rule_formset=None):
        return _profile_form_page(
            request, title="New SLA Profile", form=form, submit="Create profile",
            cancel_url="/app/sla/profiles/", crumbs=self.crumbs,
            subtitle="Configure scope, response/resolution targets, and automated escalation notifications.",
            status=status, target_formset=target_formset, rule_formset=rule_formset)

    def get(self, request):
        form = self._form(request)
        applies_to = form.initial.get("applies_to") or "WORK_ORDER"
        target_formset = self._target_formset(request, applies_to)
        rule_formset = self._rule_formset(request)
        return self._render(request, form, target_formset=target_formset, rule_formset=rule_formset)

    def post(self, request):
        post_data = request.POST.copy()
        raw_applies = post_data.get("applies_to", "REQUEST")
        applies_to = "WORK_ORDER" if str(raw_applies).strip().upper() in ("WORK_ORDER", "WORK ORDER") or "WORK" in str(raw_applies).upper() else "REQUEST"
        post_data["applies_to"] = applies_to

        action = post_data.get("action", "").strip().lower()
        if action == "draft":
            is_active = False
            post_data["is_active"] = ""
            is_draft = True
        else:
            is_active = post_data.get("is_active") in ("on", "true", "1", "True") or action in ("activate", "save")
            if is_active:
                post_data["is_active"] = "on"
            is_draft = False

        has_target_inputs = any(k in post_data for k in ("priority", "response_target", "response_minutes", "targets-0-priority", "targets-TOTAL_FORMS"))

        if has_target_inputs and "targets-TOTAL_FORMS" not in post_data and "form-TOTAL_FORMS" not in post_data:
            post_data["targets-TOTAL_FORMS"] = "1"
            post_data["targets-INITIAL_FORMS"] = "0"
            post_data["targets-MIN_NUM_FORMS"] = "0"
            post_data["targets-MAX_NUM_FORMS"] = "4"
            default_p = "CRITICAL" if applies_to == "REQUEST" else "URGENT"
            post_data["targets-0-priority"] = str(post_data.get("priority") or default_p).strip().upper()
            post_data["targets-0-response_minutes"] = post_data.get("response_target") or post_data.get("response_minutes", "")
            post_data["targets-0-resolution_minutes"] = post_data.get("resolution_target") or post_data.get("resolution_minutes", "")
            post_data["targets-0-warning_percent"] = post_data.get("warning_alert") or post_data.get("warning_percent", "80")

        if "rules-TOTAL_FORMS" not in post_data and "form-TOTAL_FORMS" not in post_data:
            post_data["rules-TOTAL_FORMS"] = "0"
            post_data["rules-INITIAL_FORMS"] = "0"
            post_data["rules-MIN_NUM_FORMS"] = "0"
            post_data["rules-MAX_NUM_FORMS"] = "6"

        form = self._form(request, post_data)
        valid = form.is_valid()
        target_formset = None
        rule_formset = None

        if has_target_inputs:
            target_formset = self._target_formset(request, applies_to, post_data, is_draft=is_draft)
            rule_formset = self._rule_formset(request, post_data)
            valid = target_formset.is_valid() and rule_formset.is_valid() and valid

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
                    if target_formset:
                        for target_form in target_formset:
                            target_data = target_form.cleaned_data
                            if not target_data or target_data.get("DELETE") or not target_data.get("priority"):
                                continue
                            target_data = {k: v for k, v in target_data.items() if k != "DELETE" and v not in (None, "")}
                            services.set_target(profile, actor=request.user, request=request,
                                                **target_data)
                    if rule_formset:
                        for rule_form in rule_formset:
                            rule_data = rule_form.cleaned_data
                            if not rule_data or rule_data.get("DELETE") or not rule_data.get("target_kind"):
                                continue
                            rule_data = {key: value for key, value in rule_data.items()
                                         if key != "DELETE" and value not in (None, "")}
                            rule_data["after_minutes"] = rule_data.get("after_minutes") or 0
                            services.create_rule(profile, actor=request.user, request=request, **rule_data)

                    # Auto-seed standard workflow escalation rules if none exist and profile has targets
                    if profile.targets.exists() and not profile.rules.exists():
                        sup_role = Role.objects.for_organization(request.organization).filter(
                            system_key__in=["supervisor", "maintenance_supervisor"]
                        ).first() or Role.objects.for_organization(request.organization).filter(name__icontains="supervisor").first()
                        mgr_role = Role.objects.for_organization(request.organization).filter(
                            system_key__in=["operations_manager", "service_manager", "admin", "owner"]
                        ).first() or Role.objects.for_organization(request.organization).filter(name__icontains="manager").first()
                        if sup_role or mgr_role:
                            try:
                                services.create_rule(
                                    profile, target_kind="RESOLUTION", trigger="WARNING",
                                    notify_role=sup_role or mgr_role, notify_assignee=True,
                                    level=1, actor=request.user, request=request
                                )
                                services.create_rule(
                                    profile, target_kind="RESOLUTION", trigger="BREACH",
                                    notify_role=mgr_role or sup_role, notify_assignee=True,
                                    level=2, actor=request.user, request=request
                                )
                                services.create_rule(
                                    profile, target_kind="RESOLUTION", trigger="ESCALATION",
                                    after_minutes=30, notify_role=mgr_role or sup_role,
                                    notify_assignee=False, level=3, actor=request.user, request=request
                                )
                            except Exception:
                                pass
                messages.success(request, f"SLA Profile '{profile.name}' was created.")
                return redirect("sla:profile", pk=profile.pk)
            except DomainError as exc:
                form.add_error(None, exc.message)
        return self._render(request, form, status=400, target_formset=target_formset, rule_formset=rule_formset)


class ProfileBase(SlaBase):
    required_permission = "sla.manage"

    def profile(self, request, pk):
        return or404(selectors.get_profile, request.organization, pk)


def _profile_choices(request):
    org = request.organization
    clients = Membership.objects.for_organization(org).filter(status=Membership.Status.ACTIVE,
        membership_roles__role__system_key="client_requester").select_related("user").distinct()
    return {"sites": Site.objects.for_organization(org).order_by("code"), "clients": clients,
            "contracts": CoverageAgreement.objects.for_organization(org).filter(is_active=True)
                .select_related("site").order_by("reference"),
            "assets": Asset.objects.for_organization(org).select_related("site").order_by("asset_tag"),
            "categories": AssetCategory.objects.for_organization(org).order_by("name"),
            "calendars": OperatingCalendar.objects.for_organization(org).order_by("name")}


class ProfileDetailView(ProfileBase):
    def get(self, request, pk):
        p = self.profile(request, pk)
        org = request.organization
        return render(request, "sla/profile_detail.html", {
            "p": p, "targets": p.targets.order_by("priority"), "rules": p.rules.select_related("notify_role"),
            "target_form": TargetForm(applies_to=p.applies_to),
            "rule_form": RuleForm(roles=Role.objects.for_organization(org).order_by("name")),
            "max_rules": services.MAX_RULES_PER_PROFILE})


class ProfileEditView(ProfileBase):
    def _page(self, request, p, form, status=200, target_formset=None, rule_formset=None):
        return _profile_form_page(
            request,
            title=f"Edit SLA profile: {p.name}",
            form=form,
            submit="Save changes",
            status=status,
            cancel_url=f"/app/sla/profiles/{p.pk}/",
            crumbs=[("SLA profiles", "/app/sla/profiles/"), (p.name, f"/app/sla/profiles/{p.pk}/"),
                    ("Edit", None)],
            subtitle="Update scope matching criteria, milestone targets, operating hours, and pause rules.",
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
            target_initial = [{"priority": default_p, "response_minutes": "15 minutes", "resolution_minutes": "4 hours", "warning_percent": "80"}]

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
                        submitted_priorities = set()
                        for t_form in target_formset:
                            t_data = t_form.cleaned_data
                            if not t_data:
                                continue
                            prio = t_data.get("priority")
                            if t_data.get("DELETE"):
                                if prio:
                                    existing = p.targets.filter(priority=prio).first()
                                    if existing:
                                        services.remove_target(existing, actor=request.user, request=request)
                                continue
                            if prio and t_data.get("response_minutes") and t_data.get("resolution_minutes"):
                                clean_t_data = {k: v for k, v in t_data.items() if k != "DELETE" and v not in (None, "")}
                                services.set_target(p, actor=request.user, request=request, **clean_t_data)
                                submitted_priorities.add(prio)

                        for existing_t in p.targets.all():
                            if existing_t.priority not in submitted_priorities and not any(f.cleaned_data and f.cleaned_data.get('priority') == existing_t.priority for f in target_formset):
                                services.remove_target(existing_t, actor=request.user, request=request)

                        p.rules.all().delete()
                        for r_form in rule_formset:
                            r_data = r_form.cleaned_data
                            if not r_data or r_data.get("DELETE") or not r_data.get("target_kind"):
                                continue
                            r_data = {k: v for k, v in r_data.items() if k != "DELETE" and v not in (None, "")}
                            r_data["after_minutes"] = r_data.get("after_minutes") or 0
                            services.create_rule(p, actor=request.user, request=request, **r_data)

                    elif has_single_target:
                        resp_val = post_data.get("response_target") or post_data.get("response_minutes")
                        resol_val = post_data.get("resolution_target") or post_data.get("resolution_minutes")
                        prio_val = post_data.get("priority")
                        warn_val = post_data.get("warning_alert") or post_data.get("warning_percent", "80")
                        if resp_val and resol_val and prio_val:
                            from apps.sla.services import parse_duration_minutes, parse_percentage
                            services.set_target(
                                p,
                                priority=str(prio_val).strip().upper(),
                                response_minutes=parse_duration_minutes(resp_val, what="Response Target"),
                                resolution_minutes=parse_duration_minutes(resol_val, what="Resolution Target"),
                                warning_percent=parse_percentage(warn_val, what="Warning Alert"),
                                actor=request.user,
                                request=request
                            )
                messages.success(request, f"SLA Profile '{p.name}' updated.")
                return redirect("sla:profile", pk=p.pk)
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
        return redirect("sla:profile", pk=p.pk)


class TargetSetView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = self.profile(request, pk)
        form = TargetForm(request.POST, applies_to=p.applies_to)
        if form.is_valid() and form.cleaned_data.get("priority"):
            try:
                services.set_target(p, actor=request.user, request=request, **form.cleaned_data)
                messages.success(request, "Target saved. Items already being tracked keep their due times.")
            except DomainError as exc:
                _fail(request, exc)
        else:
            messages.error(request, "Check the target values: " + "; ".join(
                e for errs in form.errors.values() for e in errs))
        return redirect("sla:profile", pk=p.pk)


class TargetRemoveView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk, target_pk):
        p = self.profile(request, pk)
        target = SLATarget.objects.for_organization(request.organization).filter(pk=target_pk, profile=p).first()
        if target is None:
            raise Http404
        services.remove_target(target, actor=request.user, request=request)
        messages.success(request, "Target removed.")
        return redirect("sla:profile", pk=p.pk)


class RuleCreateView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk):
        p = self.profile(request, pk)
        form = RuleForm(request.POST, roles=Role.objects.for_organization(request.organization))
        if form.is_valid():
            d = {k: v for k, v in form.cleaned_data.items() if v not in (None, "")}
            try:
                services.create_rule(p, actor=request.user, request=request, **d)
                messages.success(request, "Escalation rule added.")
            except DomainError as exc:
                _fail(request, exc)
        else:
            messages.error(request, "Check the rule values: " + "; ".join(
                e for errs in form.errors.values() for e in errs))
        return redirect("sla:profile", pk=p.pk)


class RuleDeleteView(ProfileBase):
    http_method_names = ["post"]

    def post(self, request, pk, rule_pk):
        p = self.profile(request, pk)
        rule = EscalationRule.objects.for_organization(request.organization).filter(pk=rule_pk, profile=p).first()
        if rule is None:
            raise Http404
        services.delete_rule(rule, actor=request.user, request=request)
        messages.success(request, "Rule removed.")
        return redirect("sla:profile", pk=p.pk)
