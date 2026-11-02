from django.db import migrations


def add_columns_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceplan' AND column_name = 'estimated_hours'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceplan ADD COLUMN estimated_hours numeric(6, 2) NULL;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceplan' AND column_name = 'checklist_key'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceplan ADD COLUMN checklist_key varchar(60) NOT NULL DEFAULT '';
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'last_run_at'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_run_at timestamp with time zone NULL;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'last_error'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_error varchar(300) NOT NULL DEFAULT '';
                    END IF;
                END $$;
            """)
        elif vendor == "sqlite":
            cursor.execute("PRAGMA table_info(maintenance_maintenanceplan)")
            existing_plan_cols = {row[1] for row in cursor.fetchall()}
            if "estimated_hours" not in existing_plan_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceplan ADD COLUMN estimated_hours decimal(6, 2) NULL")
            if "checklist_key" not in existing_plan_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceplan ADD COLUMN checklist_key varchar(60) NOT NULL DEFAULT ''")

            cursor.execute("PRAGMA table_info(maintenance_maintenanceschedule)")
            existing_sched_cols = {row[1] for row in cursor.fetchall()}
            if "last_run_at" not in existing_sched_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_run_at datetime NULL")
            if "last_error" not in existing_sched_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN last_error varchar(300) NOT NULL DEFAULT ''")
        else:
            try:
                table_desc = connection.introspection.get_table_description(cursor, "maintenance_maintenanceplan")
                existing_columns = {col.name for col in table_desc}
                if "estimated_hours" not in existing_columns:
                    cursor.execute("ALTER TABLE maintenance_maintenanceplan ADD COLUMN estimated_hours numeric(6, 2) NULL")
                if "checklist_key" not in existing_columns:
                    cursor.execute("ALTER TABLE maintenance_maintenanceplan ADD COLUMN checklist_key varchar(60) NOT NULL DEFAULT ''")
            except Exception:
                pass


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0002_schedule_sequence_offset"),
    ]

    operations = [
        migrations.RunPython(add_columns_if_missing, reverse_code=reverse_migration),
    ]
