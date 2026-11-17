from django.db import migrations


def reconcile_maintenance_legacy_columns(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    expected_not_null = {
        "maintenance_maintenanceplan": {
            "id", "created_at", "updated_at", "organization_id", "asset_id", "site_id",
            "name", "description", "priority", "checklist_key", "is_active",
        },
        "maintenance_maintenanceschedule": {
            "id", "created_at", "updated_at", "organization_id", "plan_id", "trigger_type",
            "frequency", "start_value", "lead_days", "window_start_time", "window_hours",
            "reminder_days", "is_active", "next_sequence", "sequence_offset", "last_error",
        },
        "maintenance_maintenancecycle": {
            "id", "created_at", "updated_at", "organization_id", "schedule_id",
            "sequence", "skipped", "trigger",
        },
    }

    with connection.cursor() as cursor:
        for table_name, keep_not_null in expected_not_null.items():
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = %s
                  AND is_nullable = 'NO'
                """,
                [table_name],
            )
            for (column_name,) in cursor.fetchall():
                if column_name not in keep_not_null:
                    cursor.execute(
                        f'ALTER TABLE "{table_name}" ALTER COLUMN "{column_name}" DROP NOT NULL'
                    )


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0006_ensure_schedule_window_columns"),
    ]

    operations = [
        migrations.RunPython(reconcile_maintenance_legacy_columns, reverse_code=migrations.RunPython.noop),
    ]

