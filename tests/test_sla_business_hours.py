from __future__ import annotations

import datetime
from datetime import date, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from apps.core.exceptions import ValidationFailed
from apps.incidents import services as incident_services
from apps.sites.models import CalendarHoliday, OperatingCalendar
from apps.sla import services as sla_services
from apps.sla.calendar import add_business_minutes, business_minutes_between, is_within_business_hours
from apps.sla.models import EscalationRule, SLABreach, SLAProfile, SLATracking
from apps.workorders import services as wo_services

pytestmark = pytest.mark.django_db


@pytest.fixture
def business_calendar(org_a, site_a1):
    """Standard Monday-Friday 09:00 to 17:00 UTC calendar."""
    site_a1.timezone = "UTC"
    site_a1.save(update_fields=["timezone"])
    cal = OperatingCalendar.objects.create(
        organization=org_a,
        site=site_a1,
        name="Standard Office Hours",
        working_days=[1, 2, 3, 4, 5],
        start_time=time(9, 0),
        end_time=time(17, 0),
        is_24x7=False,
        is_default=True,
    )
    return cal


def test_calendar_within_and_add_business_minutes(business_calendar):
    """Test standard business hours additions and checks."""
    tz = ZoneInfo("UTC")
    # Monday 10:00 is within hours
    mon_10am = datetime.datetime(2026, 11, 2, 10, 0, tzinfo=tz)  # 2026-11-02 is Monday
    assert is_within_business_hours(mon_10am, business_calendar) is True

    # Saturday 10:00 is outside hours
    sat_10am = datetime.datetime(2026, 11, 7, 10, 0, tzinfo=tz)
    assert is_within_business_hours(sat_10am, business_calendar) is False

    # 120 minutes added to Monday 10:00 -> Monday 12:00
    res = add_business_minutes(mon_10am, 120, business_calendar)
    assert res == datetime.datetime(2026, 11, 2, 12, 0, tzinfo=tz)


def test_calendar_spans_overnight(business_calendar):
    """Adding minutes that exceed end_time should wrap into next business morning."""
    tz = ZoneInfo("UTC")
    # Monday 16:00 + 120 minutes: 60 mins until 17:00, remaining 60 mins from 09:00 Tuesday -> 10:00 Tuesday
    mon_4pm = datetime.datetime(2026, 11, 2, 16, 0, tzinfo=tz)
    res = add_business_minutes(mon_4pm, 120, business_calendar)
    assert res == datetime.datetime(2026, 11, 3, 10, 0, tzinfo=tz)


def test_calendar_skips_weekend_and_holiday(business_calendar, org_a):
    """Adding minutes on Friday wraps across weekend and skips configured holidays."""
    tz = ZoneInfo("UTC")
    # Friday 2026-11-06 16:00 (1 hour left in work week)
    fri_4pm = datetime.datetime(2026, 11, 6, 16, 0, tzinfo=tz)

    # Without holiday: +120 minutes -> Monday 2026-11-09 10:00
    res_no_holiday = add_business_minutes(fri_4pm, 120, business_calendar)
    assert res_no_holiday == datetime.datetime(2026, 11, 9, 10, 0, tzinfo=tz)

    # Add Monday 2026-11-09 as a holiday
    CalendarHoliday.objects.create(
        organization=org_a,
        calendar=business_calendar,
        name="Tech Holiday",
        date=date(2026, 11, 9),
    )

    # With holiday: skips Saturday, Sunday, AND Monday -> Tuesday 2026-11-10 10:00
    res_with_holiday = add_business_minutes(fri_4pm, 120, business_calendar)
    assert res_with_holiday == datetime.datetime(2026, 11, 10, 10, 0, tzinfo=tz)


def test_calendar_starts_outside_business_hours(business_calendar):
    """When an event starts outside working hours, clock begins at the next opening."""
    tz = ZoneInfo("UTC")
    # Sunday afternoon 14:00 + 60 minutes -> starts Monday 09:00 -> finishes Monday 10:00
    sun_2pm = datetime.datetime(2026, 11, 8, 14, 0, tzinfo=tz)
    res = add_business_minutes(sun_2pm, 60, business_calendar)
    assert res == datetime.datetime(2026, 11, 9, 10, 0, tzinfo=tz)


def test_calendar_business_minutes_between(business_calendar):
    """Calculate elapsed business minutes across working days, nights, and weekends."""
    tz = ZoneInfo("UTC")
    # Friday 16:00 to Monday 10:00: 60 mins on Friday + 60 mins on Monday = 120 business minutes
    fri_4pm = datetime.datetime(2026, 11, 6, 16, 0, tzinfo=tz)
    mon_10am = datetime.datetime(2026, 11, 9, 10, 0, tzinfo=tz)
    assert business_minutes_between(fri_4pm, mon_10am, business_calendar) == 120

    # During weekend: 0 business minutes
    sat_10am = datetime.datetime(2026, 11, 7, 10, 0, tzinfo=tz)
    sun_4pm = datetime.datetime(2026, 11, 8, 16, 0, tzinfo=tz)
    assert business_minutes_between(sat_10am, sun_4pm, business_calendar) == 0


def test_sla_profile_calendar_validation(org_a, org_b, site_a1, site_b1, owner_a):
    """Cross-tenant calendar or mismatched site calendar must be rejected."""
    # Calendar belonging to org_b
    cal_b = OperatingCalendar.objects.create(
        organization=org_b,
        site=site_b1,
        name="Org B Calendar",
        working_days=[1, 2, 3, 4, 5],
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    with pytest.raises(ValidationFailed) as exc:
        sla_services.create_profile(
            org_a,
            name="Invalid Calendar Profile",
            applies_to=SLAProfile.AppliesTo.REQUEST,
            actor=owner_a,
            calendar=cal_b,
            use_business_hours=True,
        )
    assert exc.value.code == "cross_tenant_calendar"

    # Mismatched site calendar in org_a
    from apps.sites.models import Site
    site_a2 = Site.objects.create(organization=org_a, name="Second Site", code="SS-02")
    cal_a2 = OperatingCalendar.objects.create(
        organization=org_a,
        site=site_a2,
        name="Site 2 Calendar",
        working_days=[1, 2, 3, 4, 5],
        start_time=time(9, 0),
        end_time=time(17, 0),
    )
    with pytest.raises(ValidationFailed) as exc:
        sla_services.create_profile(
            org_a,
            name="Mismatched Site Profile",
            applies_to=SLAProfile.AppliesTo.REQUEST,
            site=site_a1,
            actor=owner_a,
            calendar=cal_a2,
            use_business_hours=True,
        )
    assert exc.value.code == "scope_calendar_mismatch"


def test_service_request_with_business_hours_sla(org_a, site_a1, owner_a, make_asset, business_calendar):
    """Creating a ServiceRequest covered by a business hours SLA profile calculates targets within business hours."""
    tz = ZoneInfo("UTC")
    asset = make_asset(org_a, site_a1, "AST-SR-BIZ")
    owner_m = owner_a.memberships.get(organization=org_a)

    # 1. Create request first before profile exists -> no tracking created yet
    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=owner_m,
        actor=owner_a,
        title="Server Room Overheating",
        description="AC stopped working on Friday afternoon",
        severity="CRITICAL",
        kind="INCIDENT",
    )
    assert SLATracking.objects.filter(request=sr).count() == 0

    # 2. Create business hours profile & target
    profile = sla_services.create_profile(
        org_a,
        name="Biz Hours SR SLA",
        applies_to=SLAProfile.AppliesTo.REQUEST,
        site=site_a1,
        actor=owner_a,
        calendar=business_calendar,
        use_business_hours=True,
    )
    sla_services.set_target(
        profile,
        priority="CRITICAL",
        response_minutes=60,
        resolution_minutes=240,
        warning_percent=80,
        actor=owner_a,
    )

    # 3. Simulate Friday 16:30 created_at and start tracking
    fri_created = datetime.datetime(2026, 11, 6, 16, 30, tzinfo=tz)
    sr.created_at = fri_created
    sr.save(update_fields=["created_at"])
    tracking = sla_services.on_request_created(sr)

    assert tracking is not None
    assert tracking.use_business_hours is True
    assert tracking.calendar == business_calendar

    # Response target: 60 business minutes
    # 30 mins left on Friday (16:30 -> 17:00), remaining 30 mins on Monday (09:00 -> 09:30)
    assert tracking.response_due_at == datetime.datetime(2026, 11, 9, 9, 30, tzinfo=tz)

    # Resolution target: 240 business minutes (4 hours)
    # 30 mins on Friday, 210 mins (3.5 hrs) on Monday (09:00 -> 12:30)
    assert tracking.resolution_due_at == datetime.datetime(2026, 11, 9, 12, 30, tzinfo=tz)


def test_work_order_with_business_hours_sla(org_a, site_a1, owner_a, tech_a, make_asset, business_calendar):
    """Standalone Work Order under business hours policy respects operating calendar."""
    tz = ZoneInfo("UTC")
    asset = make_asset(org_a, site_a1, "AST-BIZ-1")

    # 1. Create work order first
    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        title="Pump Maintenance",
        description="Quarterly check",
        work_type="CORRECTIVE",
        priority="HIGH",
        actor=owner_a,
    )
    assert SLATracking.objects.filter(work_order=wo).count() == 0

    # 2. Create business hours profile & target
    profile = sla_services.create_profile(
        org_a,
        name="Biz Hours WO SLA",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        site=site_a1,
        actor=owner_a,
        calendar=business_calendar,
        use_business_hours=True,
    )
    sla_services.set_target(
        profile,
        priority="HIGH",
        response_minutes=120,
        resolution_minutes=480,
        warning_percent=75,
        actor=owner_a,
    )

    # 3. Simulate Monday 09:00 start and trigger SLA
    mon_start = datetime.datetime(2026, 11, 2, 9, 0, tzinfo=tz)
    wo.created_at = mon_start
    wo.save(update_fields=["created_at"])
    tracking = sla_services.on_work_order_created(wo)

    assert tracking is not None
    assert tracking.use_business_hours is True
    # Response due: 09:00 + 2 hrs = 11:00 Monday
    assert tracking.response_due_at == datetime.datetime(2026, 11, 2, 11, 0, tzinfo=tz)
    # Resolution due: 09:00 + 8 hrs = 17:00 Monday (full 8-hr business day)
    assert tracking.resolution_due_at == datetime.datetime(2026, 11, 2, 17, 0, tzinfo=tz)


def test_business_hours_pause_and_resume(org_a, site_a1, owner_a, tech_a, make_asset, business_calendar):
    """Pausing during business hours shifts due dates by business minutes; weekend pause does not shift."""
    tz = ZoneInfo("UTC")
    asset = make_asset(org_a, site_a1, "AST-BIZ-PAUSE")

    # 1. Create work order first
    wo = wo_services.create_work_order(
        org_a,
        site_id=site_a1.pk,
        asset=asset,
        title="Hold Test",
        work_type="CORRECTIVE",
        priority="HIGH",
        actor=owner_a,
    )
    assert SLATracking.objects.filter(work_order=wo).count() == 0

    # 2. Create profile with pause states
    profile = sla_services.create_profile(
        org_a,
        name="Pause Biz SLA",
        applies_to=SLAProfile.AppliesTo.WORK_ORDER,
        site=site_a1,
        actor=owner_a,
        calendar=business_calendar,
        use_business_hours=True,
        pause_states=["WORK_ORDER:ON_HOLD"],
    )
    sla_services.set_target(
        profile,
        priority="HIGH",
        response_minutes=120,
        resolution_minutes=480,
        actor=owner_a,
    )

    # Started Friday 10:00 -> response due Friday 12:00, resolution due Monday 10:00 (7 hrs Friday + 1 hr Monday)
    fri_10am = datetime.datetime(2026, 11, 6, 10, 0, tzinfo=tz)
    wo.created_at = fri_10am
    wo.save(update_fields=["created_at"])
    tracking = sla_services.on_work_order_created(wo)
    initial_reso_due = tracking.resolution_due_at

    # Put on hold Friday 11:00
    fri_11am = datetime.datetime(2026, 11, 6, 11, 0, tzinfo=tz)
    wo._workflow_transition_write = True
    wo.status = "ON_HOLD"
    wo.hold_reason = "Waiting for specialized spare parts"
    wo.save()
    sla_services._sync_pause(tracking, fri_11am, actor=owner_a)
    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.PAUSED

    # Resume Friday 12:00 (paused for 60 business minutes)
    fri_12pm = datetime.datetime(2026, 11, 6, 12, 0, tzinfo=tz)
    wo._workflow_transition_write = True
    wo.status = "IN_PROGRESS"
    wo.save()
    sla_services._sync_pause(tracking, fri_12pm, actor=owner_a)
    tracking.refresh_from_db()

    assert tracking.status == SLATracking.Status.ACTIVE
    # Resolution due date should be shifted forward by exactly 60 business minutes!
    assert tracking.resolution_due_at == initial_reso_due + timedelta(hours=1)


def test_business_hours_warning_breach_and_escalation(org_a, site_a1, owner_a, make_asset, business_calendar):
    """Monitor detects warning at threshold, breach when unmet, and escalations after business minutes."""
    tz = ZoneInfo("UTC")
    asset = make_asset(org_a, site_a1, "AST-ESC-BIZ")
    owner_m = owner_a.memberships.get(organization=org_a)

    # 1. Create request first
    sr = incident_services.create_request(
        org_a,
        asset=asset,
        reporter=owner_m,
        actor=owner_a,
        title="Critical Failure",
        description="Machine down",
        severity="CRITICAL",
        kind="INCIDENT",
    )
    assert SLATracking.objects.filter(request=sr).count() == 0

    # 2. Create profile & target
    profile = sla_services.create_profile(
        org_a,
        name="Escalation Biz SLA",
        applies_to=SLAProfile.AppliesTo.REQUEST,
        site=site_a1,
        actor=owner_a,
        calendar=business_calendar,
        use_business_hours=True,
    )
    sla_services.set_target(
        profile,
        priority="CRITICAL",
        response_minutes=60,
        resolution_minutes=120,
        warning_percent=50,  # Warning after 60 business minutes (50% remaining)
        actor=owner_a,
    )
    # Escalation 60 business minutes after breach
    sla_services.create_rule(
        profile,
        target_kind="RESOLUTION",
        trigger=EscalationRule.Trigger.ESCALATION,
        after_minutes=60,
        level=1,
        notify_assignee=True,
        actor=owner_a,
    )

    # Monday 09:00 start -> Resolution due Monday 11:00 (120 mins)
    mon_9am = datetime.datetime(2026, 11, 2, 9, 0, tzinfo=tz)
    sr.created_at = mon_9am
    sr.save(update_fields=["created_at"])
    tracking = sla_services.on_request_created(sr)

    # Meet the response target on-time at 09:15 so only resolution is monitored
    sla_services._meet(tracking, "RESPONSE", datetime.datetime(2026, 11, 2, 9, 15, tzinfo=tz), actor=owner_a)

    # 1. At 09:20 (20 mins elapsed, resolution due 11:00, remaining 100 mins > 60 min threshold) -> on track
    mon_920 = datetime.datetime(2026, 11, 2, 9, 20, tzinfo=tz)
    sla_services.process_tracking(tracking, mon_920)
    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.ACTIVE

    # 2. At 10:05 (65 mins elapsed, remaining 55 mins < 60 min threshold) -> warning triggers, status becomes AT_RISK
    mon_1005 = datetime.datetime(2026, 11, 2, 10, 5, tzinfo=tz)
    res_1005 = sla_services.process_tracking(tracking, mon_1005)
    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.AT_RISK
    assert res_1005["warnings"] >= 1

    # 3. At 11:05 (past 11:00 due date) -> breach triggers
    mon_1105 = datetime.datetime(2026, 11, 2, 11, 5, tzinfo=tz)
    sla_services.process_tracking(tracking, mon_1105)
    tracking.refresh_from_db()
    assert tracking.status == SLATracking.Status.BREACHED
    assert SLABreach.objects.filter(tracking=tracking, target_kind="RESOLUTION", status="OPEN").exists()

    # 4. At 11:30 (30 mins after breach, rule requires 60 business minutes) -> no escalation yet
    mon_1130 = datetime.datetime(2026, 11, 2, 11, 30, tzinfo=tz)
    res_1130 = sla_services.process_tracking(tracking, mon_1130)
    assert res_1130["escalations"] == 0

    # 5. At 12:05 (65 business minutes after breach at 11:00) -> escalation fires!
    mon_1205 = datetime.datetime(2026, 11, 2, 12, 5, tzinfo=tz)
    res_1205 = sla_services.process_tracking(tracking, mon_1205)
    assert res_1205["escalations"] == 1
    breach = SLABreach.objects.get(tracking=tracking, target_kind="RESOLUTION")
    assert breach.escalation_level == 1


def test_business_hours_profile_api(org_a, site_a1, owner_a, business_calendar, client):
    """Test REST API support for creating, retrieving, and updating business hours SLA profiles."""
    from rest_framework.test import APIClient
    api_client = APIClient()
    api_client.force_authenticate(user=owner_a)

    # 1. Create Profile with business hours via REST API
    payload = {
        "name": "API Business Hours SLA",
        "description": "Configured via REST API",
        "applies_to": "WORK_ORDER",
        "site": str(site_a1.pk),
        "calendar": str(business_calendar.pk),
        "use_business_hours": True,
        "pause_states": ["WORK_ORDER:ON_HOLD"],
    }
    create_res = api_client.post("/api/v1/sla-profiles/", data=payload, format="json")
    assert create_res.status_code == 201, create_res.data
    prof_id = create_res.data["id"]
    assert create_res.data["use_business_hours"] is True
    assert create_res.data["calendar_name"] == "Standard Office Hours"

    # 2. Retrieve Profile via REST API
    get_res = api_client.get(f"/api/v1/sla-profiles/{prof_id}/")
    assert get_res.status_code == 200
    assert get_res.data["use_business_hours"] is True
    assert str(get_res.data["calendar"]) == str(business_calendar.pk)

    # 3. Patch Profile via REST API (switch off business hours)
    patch_res = api_client.patch(
        f"/api/v1/sla-profiles/{prof_id}/",
        data={"use_business_hours": False},
        format="json",
    )
    assert patch_res.status_code == 200
    assert patch_res.data["use_business_hours"] is False
