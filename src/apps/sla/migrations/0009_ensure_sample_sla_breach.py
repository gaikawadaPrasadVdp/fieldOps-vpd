from django.db import migrations
from django.utils import timezone


def ensure_sample_sla_breaches(apps, schema_editor):
    Organization = apps.get_model("tenancy", "Organization")
    Site = apps.get_model("sites", "Site")
    SLAProfile = apps.get_model("sla", "SLAProfile")
    SLATracking = apps.get_model("sla", "SLATracking")
    SLABreach = apps.get_model("sla", "SLABreach")
    WorkOrder = apps.get_model("workorders", "WorkOrder")

    for org in Organization.objects.all():
        try:
            if not SLABreach.objects.filter(organization=org).exists():
                site = Site.objects.filter(organization=org).first()
                if not site:
                    site = Site.objects.create(organization=org, name="Primary Site", code="SITE-01")
                profile = SLAProfile.objects.filter(organization=org).first()
                if not profile:
                    profile = SLAProfile.objects.create(
                        organization=org,
                        name="Standard SLA",
                        applies_to="WORK_ORDER",
                    )
                wo = WorkOrder.objects.filter(organization=org).first()
                tracking = SLATracking.objects.filter(organization=org).first()
                if not tracking and wo:
                    now = timezone.now()
                    tracking = SLATracking.objects.create(
                        organization=org,
                        site=site,
                        profile=profile,
                        work_order=wo,
                        priority="HIGH",
                        response_minutes=60,
                        resolution_minutes=240,
                        warning_percent=80,
                        started_at=now,
                        response_due_at=now,
                        resolution_due_at=now,
                        status="BREACHED",
                    )
                if tracking:
                    now = timezone.now()
                    SLABreach.objects.create(
                        organization=org,
                        tracking=tracking,
                        profile=profile,
                        site=site,
                        target_kind="RESPONSE",
                        priority="HIGH",
                        severity="MAJOR",
                        breached_at=now,
                        detected_at=now,
                        status="OPEN",
                    )
        except Exception:
            continue


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("sla", "0008_slaprofile_calendar_slaprofile_use_business_hours_and_more"),
        ("sites", "0001_initial"),
        ("workorders", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_sample_sla_breaches, reverse_code=reverse_noop),
    ]
