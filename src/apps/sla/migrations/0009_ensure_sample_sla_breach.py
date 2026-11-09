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
        if not SLABreach.objects.filter(organization=org).exists():
            site = Site.objects.filter(organization=org).first()
            if not site:
                site = Site.objects.create(organization=org, name="Primary Site", code="SITE-01")
            profile = SLAProfile.objects.filter(organization=org).first()
            if not profile:
                profile = SLAProfile.objects.create(organization=org, name="Standard SLA", is_default=True)
            wo = WorkOrder.objects.filter(organization=org).first()
            tracking = SLATracking.objects.filter(organization=org).first()
            if not tracking:
                tracking = SLATracking.objects.create(
                    organization=org,
                    site=site,
                    profile=profile,
                    work_order=wo,
                    status="BREACHED",
                )
            SLABreach.objects.create(
                organization=org,
                tracking=tracking,
                profile=profile,
                site=site,
                target_kind="RESPONSE",
                priority="HIGH",
                severity="MAJOR",
                breached_at=timezone.now(),
                detected_at=timezone.now(),
                status="OPEN",
            )


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
