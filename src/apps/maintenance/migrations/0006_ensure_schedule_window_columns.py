from django.db import migrations


def add_window_columns_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("""
                DO $$
                BEGIN
                    -- 1. window_start_time on maintenance_maintenanceschedule
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'window_start_time'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN window_start_time time without time zone NOT NULL DEFAULT '08:00:00';
                    END IF;

                    -- 2. window_hours on maintenance_maintenanceschedule
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'window_hours'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN window_hours smallint NOT NULL DEFAULT 8;
                    END IF;

                    -- 3. reminder_days on maintenance_maintenanceschedule
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'reminder_days'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN reminder_days smallint NOT NULL DEFAULT 0;
                    END IF;

                    -- 4. last_reminded_sequence on maintenance_maintenanceschedule
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'last_reminded_sequence'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_reminded_sequence integer NULL;
                    END IF;
                END $$;
            """)
        elif vendor == "sqlite":
            cursor.execute("PRAGMA table_info(maintenance_maintenanceschedule)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "window_start_time" not in existing_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN window_start_time time NOT NULL DEFAULT '08:00:00'")
            if "window_hours" not in existing_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN window_hours integer NOT NULL DEFAULT 8")
            if "reminder_days" not in existing_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN reminder_days integer NOT NULL DEFAULT 0")
            if "last_reminded_sequence" not in existing_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_reminded_sequence integer NULL")
        else:
            try:
                sched_desc = connection.introspection.get_table_description(cursor, "maintenance_maintenanceschedule")
                sched_cols = {col.name for col in sched_desc}
                if "window_start_time" not in sched_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN window_start_time time NOT NULL DEFAULT '08:00:00'")
                if "window_hours" not in sched_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN window_hours integer NOT NULL DEFAULT 8")
                if "reminder_days" not in sched_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN reminder_days integer NOT NULL DEFAULT 0")
                if "last_reminded_sequence" not in sched_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_reminded_sequence integer NULL")
            except Exception:
                pass


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0005_ensure_schedule_and_cycle_columns"),
    ]

    operations = [
        migrations.RunPython(add_window_columns_if_missing, reverse_code=reverse_migration),
    ]
