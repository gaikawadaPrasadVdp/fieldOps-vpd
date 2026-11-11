from datetime import date, timedelta
from django.db import migrations


def seed_default_snapshots(apps, schema_editor):
    Organization = apps.get_model("tenancy", "Organization")
    ReportSnapshot = apps.get_model("dashboards", "ReportSnapshot")
    today = date.today()
    period_start = today - timedelta(days=1)

    for org in Organization.objects.all():
        if not ReportSnapshot.objects.filter(organization=org).exists():
            ReportSnapshot.objects.create(
                organization=org,
                snapshot_type="DAILY",
                section="OPERATIONS",
                period_from=period_start,
                period_to=today,
                metrics={"open_work_orders": 0, "completed_work_orders": 0, "baseline": True},
                notes="Baseline operations KPI snapshot",
            )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("dashboards", "0004_cleanup_legacy_reportsnapshot_columns"),
    ]

    operations = [
        migrations.RunPython(seed_default_snapshots, reverse_code=reverse_noop),
    ]
