from django.db import migrations


def cleanup_legacy_columns(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = 'dashboards_reportsnapshot'
                      AND column_name = 'kind'
                ) THEN
                    ALTER TABLE dashboards_reportsnapshot ALTER COLUMN kind DROP NOT NULL;
                    ALTER TABLE dashboards_reportsnapshot DROP COLUMN IF EXISTS kind;
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("dashboards", "0002_sync_schema"),
    ]

    operations = [
        migrations.RunPython(cleanup_legacy_columns, reverse_code=migrations.RunPython.noop),
    ]
