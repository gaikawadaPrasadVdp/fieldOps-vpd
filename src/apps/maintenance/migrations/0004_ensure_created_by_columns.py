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
                        WHERE table_name = 'maintenance_maintenanceplan' AND column_name = 'created_by_id'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceplan 
                        ADD COLUMN created_by_id uuid NULL 
                        REFERENCES accounts_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

                        CREATE INDEX IF NOT EXISTS maintenance_maintenanceplan_created_by_id_idx 
                        ON maintenance_maintenanceplan (created_by_id);
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenancecycle' AND column_name = 'generated_by_id'
                    ) THEN
                        ALTER TABLE maintenance_maintenancecycle 
                        ADD COLUMN generated_by_id uuid NULL 
                        REFERENCES accounts_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED;

                        CREATE INDEX IF NOT EXISTS maintenance_maintenancecycle_generated_by_id_idx 
                        ON maintenance_maintenancecycle (generated_by_id);
                    END IF;
                END $$;
            """)
        elif vendor == "sqlite":
            cursor.execute("PRAGMA table_info(maintenance_maintenanceplan)")
            existing_plan_cols = {row[1] for row in cursor.fetchall()}
            if "created_by_id" not in existing_plan_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceplan ADD COLUMN created_by_id char(32) NULL")

            cursor.execute("PRAGMA table_info(maintenance_maintenancecycle)")
            existing_cycle_cols = {row[1] for row in cursor.fetchall()}
            if "generated_by_id" not in existing_cycle_cols:
                cursor.execute("ALTER TABLE maintenance_maintenancecycle ADD COLUMN generated_by_id char(32) NULL")
        else:
            try:
                table_desc = connection.introspection.get_table_description(cursor, "maintenance_maintenanceplan")
                existing_columns = {col.name for col in table_desc}
                if "created_by_id" not in existing_columns:
                    cursor.execute("ALTER TABLE maintenance_maintenanceplan ADD COLUMN created_by_id uuid NULL")
            except Exception:
                pass


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0003_ensure_estimated_hours"),
    ]

    operations = [
        migrations.RunPython(add_columns_if_missing, reverse_code=reverse_migration),
    ]
