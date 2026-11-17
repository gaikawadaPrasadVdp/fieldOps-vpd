from django.db import migrations


def clean_interval_column_and_constraints(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("""
                DO $$
                BEGIN
                    -- Check if legacy 'interval' column exists on maintenance_maintenanceschedule
                    IF EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'interval'
                    ) THEN
                        -- Make interval nullable to prevent NOT NULL insertion errors from models that don't know about it
                        ALTER TABLE maintenance_maintenanceschedule ALTER COLUMN "interval" DROP NOT NULL;
                        ALTER TABLE maintenance_maintenanceschedule ALTER COLUMN "interval" SET DEFAULT NULL;

                        -- Drop any legacy check constraint on interval column
                        ALTER TABLE maintenance_maintenanceschedule DROP CONSTRAINT IF EXISTS maintenance_maintenanceschedule_interval_check;
                        ALTER TABLE maintenance_maintenanceschedule DROP CONSTRAINT IF EXISTS maintenance_maintenanceschedule_interval_gte_1;

                        -- Sync values to interval_count where missing
                        UPDATE maintenance_maintenanceschedule
                        SET interval_count = "interval"
                        WHERE interval_count IS NULL AND "interval" IS NOT NULL;
                    END IF;

                    -- Ensure interval_count has sensible fallback for existing rows
                    UPDATE maintenance_maintenanceschedule
                    SET interval_count = 1
                    WHERE trigger_type = 'TIME' AND interval_count IS NULL;

                END $$;
            """)
        elif vendor == "sqlite":
            try:
                cursor.execute("PRAGMA table_info(maintenance_maintenanceschedule)")
                existing_cols = {row[1] for row in cursor.fetchall()}
                if "interval" in existing_cols and "interval_count" in existing_cols:
                    cursor.execute("""
                        UPDATE maintenance_maintenanceschedule
                        SET interval_count = interval
                        WHERE interval_count IS NULL AND interval IS NOT NULL
                    """)
                if "interval_count" in existing_cols:
                    cursor.execute("""
                        UPDATE maintenance_maintenanceschedule
                        SET interval_count = 1
                        WHERE trigger_type = 'TIME' AND interval_count IS NULL
                    """)
            except Exception:
                pass


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0006_ensure_schedule_window_columns"),
    ]

    operations = [
        migrations.RunPython(clean_interval_column_and_constraints, reverse_code=reverse_noop),
    ]
