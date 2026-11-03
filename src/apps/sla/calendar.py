"""Operating calendar and business hours engine for M11 SLA & Escalation.

Calculates SLA target due times, warnings, pause durations, and escalations using
site operating calendars (working days, business hours, and holiday schedules).
Falls back to 24/7 elapsed clock minutes when business hours are not enabled.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apps.sites.models import OperatingCalendar, Site

log = logging.getLogger(__name__)


def get_calendar_timezone(calendar: OperatingCalendar | None, site: Site | None = None) -> ZoneInfo:
    """Resolve timezone for calendar calculation, falling back to Site timezone or UTC."""
    tz_str = "UTC"
    if calendar and getattr(calendar, "site", None) and getattr(calendar.site, "timezone", None):
        tz_str = calendar.site.timezone
    elif site and getattr(site, "timezone", None):
        tz_str = site.timezone
    try:
        return ZoneInfo(tz_str)
    except Exception:
        return ZoneInfo("UTC")


def resolve_calendar(profile, site: Site | None = None) -> OperatingCalendar | None:
    """Resolve the applicable OperatingCalendar for a profile and site.

    1. Profile's explicit calendar (if configured).
    2. Site's default calendar.
    3. Site's first available calendar.
    4. Organization default calendar (if site not specified).
    """
    if profile and getattr(profile, "calendar_id", None):
        return profile.calendar

    target_site = site or (profile.site if profile else None)
    if target_site:
        cal = target_site.calendars.filter(is_default=True).first() or target_site.calendars.first()
        if cal:
            return cal

    if profile and getattr(profile, "organization_id", None):
        return OperatingCalendar.objects.for_organization(profile.organization).filter(is_default=True).first()

    return None


def get_holiday_dates(calendar: OperatingCalendar) -> set[date]:
    """Return set of holiday dates for a calendar."""
    if not calendar:
        return set()
    return set(calendar.holidays.values_list("date", flat=True))


def is_within_business_hours(dt: datetime, calendar: OperatingCalendar) -> bool:
    """Check if a timezone-aware datetime falls within calendar operating hours."""
    if not calendar:
        return True
    if calendar.is_24x7 and not calendar.holidays.exists():
        working_days = set(calendar.working_days or [1, 2, 3, 4, 5, 6, 7])
        if working_days == {1, 2, 3, 4, 5, 6, 7}:
            return True

    site_tz = get_calendar_timezone(calendar)
    local_dt = dt.astimezone(site_tz)
    local_date = local_dt.date()

    working_days = set(calendar.working_days or [1, 2, 3, 4, 5])
    if local_date.isoweekday() not in working_days:
        return False

    if local_date in get_holiday_dates(calendar):
        return False

    if calendar.is_24x7:
        return True

    start_time = calendar.start_time or time(9, 0)
    end_time = calendar.end_time or time(17, 0)
    curr_time = local_dt.time()

    if start_time < end_time:
        return start_time <= curr_time < end_time
    # Overnight shift (e.g. 22:00 to 06:00)
    return curr_time >= start_time or curr_time < end_time


def add_business_minutes(start_dt: datetime, minutes: int, calendar: OperatingCalendar) -> datetime:
    """Advance `start_dt` forward by `minutes` business minutes according to `calendar`.

    Skips non-working days, holidays, and off-work hours.
    If `start_dt` is outside working hours, computation starts at the next open business time.
    Returns timezone-aware UTC datetime.
    """
    if minutes <= 0:
        return start_dt

    if not calendar:
        return start_dt + timedelta(minutes=minutes)

    working_days = set(calendar.working_days or [1, 2, 3, 4, 5])
    if calendar.is_24x7 and working_days == {1, 2, 3, 4, 5, 6, 7} and not calendar.holidays.exists():
        return start_dt + timedelta(minutes=minutes)

    site_tz = get_calendar_timezone(calendar)
    local_dt = start_dt.astimezone(site_tz)
    holiday_dates = get_holiday_dates(calendar)

    start_time = calendar.start_time or time(9, 0)
    end_time = calendar.end_time or time(17, 0)
    is_24x7 = calendar.is_24x7

    remaining = minutes
    curr = local_dt
    days_checked = 0
    max_days = 3650  # Cap at 10 years to prevent infinite loop

    if not is_24x7 and start_time >= end_time and curr.time() < end_time:
        prev_date = curr.date() - timedelta(days=1)
        if (prev_date.isoweekday() in working_days) and (prev_date not in holiday_dates):
            # We are currently in the overnight shift that started yesterday
            curr_shift_close = datetime.combine(curr.date(), end_time, tzinfo=site_tz)
            avail_sec = (curr_shift_close - curr).total_seconds()
            avail_min = max(0, int(avail_sec // 60))
            if remaining <= avail_min:
                return (curr + timedelta(minutes=remaining)).astimezone(ZoneInfo("UTC"))
            remaining -= avail_min
            curr = datetime.combine(curr.date(), start_time, tzinfo=site_tz)

    while remaining > 0 and days_checked < max_days:
        curr_date = curr.date()
        is_work_day = (curr_date.isoweekday() in working_days) and (curr_date not in holiday_dates)

        if is_24x7:
            if is_work_day:
                day_end = datetime.combine(curr_date + timedelta(days=1), time(0, 0), tzinfo=site_tz)
                avail_sec = (day_end - curr).total_seconds()
                avail_min = max(0, int(avail_sec // 60))
                if remaining <= avail_min:
                    curr = curr + timedelta(minutes=remaining)
                    remaining = 0
                    break
                remaining -= avail_min
                curr = day_end
            else:
                curr = datetime.combine(curr_date + timedelta(days=1), time(0, 0), tzinfo=site_tz)
            days_checked += 1
            continue

        if start_time < end_time:
            day_open = datetime.combine(curr_date, start_time, tzinfo=site_tz)
            day_close = datetime.combine(curr_date, end_time, tzinfo=site_tz)

            if is_work_day:
                if curr < day_open:
                    curr = day_open
                if curr < day_close:
                    avail_sec = (day_close - curr).total_seconds()
                    avail_min = max(0, int(avail_sec // 60))
                    if remaining <= avail_min:
                        curr = curr + timedelta(minutes=remaining)
                        remaining = 0
                        break
                    remaining -= avail_min

            next_date = curr_date + timedelta(days=1)
            curr = datetime.combine(next_date, start_time, tzinfo=site_tz)
            days_checked += 1
        else:
            # Overnight shift (e.g. 22:00 to 06:00 next day)
            # Part 1: from start_time to midnight of curr_date
            # Part 2: from midnight to end_time of next_date
            day_open = datetime.combine(curr_date, start_time, tzinfo=site_tz)
            day_close = datetime.combine(curr_date + timedelta(days=1), end_time, tzinfo=site_tz)

            if is_work_day:
                if curr < day_open and curr.time() >= end_time:
                    curr = day_open
                if curr < day_close:
                    avail_sec = (day_close - curr).total_seconds()
                    avail_min = max(0, int(avail_sec // 60))
                    if remaining <= avail_min:
                        curr = curr + timedelta(minutes=remaining)
                        remaining = 0
                        break
                    remaining -= avail_min

            next_date = curr_date + timedelta(days=1)
            curr = datetime.combine(next_date, start_time, tzinfo=site_tz)
            days_checked += 1

    return curr.astimezone(ZoneInfo("UTC"))


def business_minutes_between(start_dt: datetime, end_dt: datetime, calendar: OperatingCalendar) -> int:
    """Calculate the total business minutes elapsed between start_dt and end_dt."""
    if end_dt <= start_dt or not calendar:
        return 0

    working_days = set(calendar.working_days or [1, 2, 3, 4, 5])
    if calendar.is_24x7 and working_days == {1, 2, 3, 4, 5, 6, 7} and not calendar.holidays.exists():
        return int((end_dt - start_dt).total_seconds() // 60)

    site_tz = get_calendar_timezone(calendar)
    local_start = start_dt.astimezone(site_tz)
    local_end = end_dt.astimezone(site_tz)
    holiday_dates = get_holiday_dates(calendar)

    start_time = calendar.start_time or time(9, 0)
    end_time = calendar.end_time or time(17, 0)
    is_24x7 = calendar.is_24x7

    total_minutes = 0
    curr_date = local_start.date()
    if start_time >= end_time and not is_24x7:
        curr_date = curr_date - timedelta(days=1)
    end_date = local_end.date()

    while curr_date <= end_date:
        is_work_day = (curr_date.isoweekday() in working_days) and (curr_date not in holiday_dates)
        if is_work_day:
            if is_24x7:
                window_start = max(local_start, datetime.combine(curr_date, time(0, 0), tzinfo=site_tz))
                window_end = min(local_end, datetime.combine(curr_date + timedelta(days=1), time(0, 0), tzinfo=site_tz))
                if window_end > window_start:
                    total_minutes += int((window_end - window_start).total_seconds() // 60)
            elif start_time < end_time:
                day_open = datetime.combine(curr_date, start_time, tzinfo=site_tz)
                day_close = datetime.combine(curr_date, end_time, tzinfo=site_tz)
                window_start = max(local_start, day_open)
                window_end = min(local_end, day_close)
                if window_end > window_start:
                    total_minutes += int((window_end - window_start).total_seconds() // 60)
            else:
                day_open = datetime.combine(curr_date, start_time, tzinfo=site_tz)
                day_close = datetime.combine(curr_date + timedelta(days=1), end_time, tzinfo=site_tz)
                window_start = max(local_start, day_open)
                window_end = min(local_end, day_close)
                if window_end > window_start:
                    total_minutes += int((window_end - window_start).total_seconds() // 60)
        curr_date += timedelta(days=1)

    return total_minutes
