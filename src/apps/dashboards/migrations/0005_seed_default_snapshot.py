from datetime import date, timedelta
from django.db import migrations


def seed_default_snapshots(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DO $$
                DECLARE
                    col RECORD;
                BEGIN
                    FOR col IN 
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name = 'dashboards_reportsnapshot'
                          AND column_name NOT IN (
                              'id', 'created_at', 'updated_at', 'deleted_at', 'is_deleted',
                              'snapshot_type', 'section', 'period_start', 'period_end',
                              'site_id', 'metrics', 'created_by_id', 'notes', 'organization_id'
                          )
                    LOOP
                        EXECUTE 'ALTER TABLE dashboards_reportsnapshot ALTER COLUMN ' || quote_ident(col.column_name) || ' DROP NOT NULL';
                        EXECUTE 'ALTER TABLE dashboards_reportsnapshot DROP COLUMN IF EXISTS ' || quote_ident(col.column_name);
                    END LOOP;
                END $$;
                """
            )

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
                period_start=period_start,
                period_end=today,
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
