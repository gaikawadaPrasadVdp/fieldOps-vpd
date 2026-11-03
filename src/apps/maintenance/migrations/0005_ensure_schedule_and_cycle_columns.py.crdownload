from django.db import migrations


def add_columns_if_missing(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("""
                DO $$
                BEGIN
                    -- 1. interval_count on maintenance_maintenanceschedule
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'interval_count'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN interval_count integer NULL;
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'interval'
                        ) THEN
                            EXECUTE 'UPDATE maintenance_maintenanceschedule SET interval_count = interval WHERE interval_count IS NULL';
                        END IF;
                        EXECUTE 'UPDATE maintenance_maintenanceschedule SET interval_count = 1 WHERE trigger_type = ''TIME'' AND interval_count IS NULL';
                    END IF;

                    -- 2. sequence_offset on maintenance_maintenanceschedule
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenanceschedule' AND column_name = 'sequence_offset'
                    ) THEN
                        ALTER TABLE maintenance_maintenanceschedule ADD COLUMN sequence_offset integer NOT NULL DEFAULT 0;
                    END IF;

                    -- 3. skipped on maintenance_maintenancecycle
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenancecycle' AND column_name = 'skipped'
                    ) THEN
                        ALTER TABLE maintenance_maintenancecycle ADD COLUMN skipped integer NOT NULL DEFAULT 0;
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns
                            WHERE table_name = 'maintenance_maintenancecycle' AND column_name = 'is_skipped'
                        ) THEN
                            IF EXISTS (
                                SELECT 1 FROM information_schema.columns
                                WHERE table_name = 'maintenance_maintenancecycle' AND column_name = 'is_skipped' AND data_type = 'boolean'
                            ) THEN
                                EXECUTE 'UPDATE maintenance_maintenancecycle SET skipped = CASE WHEN is_skipped = true THEN 1 ELSE 0 END WHERE skipped = 0';
                            ELSE
                                EXECUTE 'UPDATE maintenance_maintenancecycle SET skipped = COALESCE(is_skipped, 0) WHERE skipped = 0';
                            END IF;
                        END IF;
                    END IF;

                    -- 4. trigger on maintenance_maintenancecycle
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name = 'maintenance_maintenancecycle' AND column_name = 'trigger'
                    ) THEN
                        ALTER TABLE maintenance_maintenancecycle ADD COLUMN trigger varchar(10) NOT NULL DEFAULT 'scheduler';
                    END IF;
                END $$;
            """)
        elif vendor == "sqlite":
            cursor.execute("PRAGMA table_info(maintenance_maintenanceschedule)")
            existing_sched_cols = {row[1] for row in cursor.fetchall()}
            if "interval_count" not in existing_sched_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN interval_count integer NULL")
                if "interval" in existing_sched_cols:
                    cursor.execute("UPDATE maintenance_maintenanceschedule SET interval_count = interval WHERE interval_count IS NULL")
                cursor.execute("UPDATE maintenance_maintenanceschedule SET interval_count = 1 WHERE trigger_type = 'TIME' AND interval_count IS NULL")
            if "sequence_offset" not in existing_sched_cols:
                cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN sequence_offset integer NOT NULL DEFAULT 0")

            cursor.execute("PRAGMA table_info(maintenance_maintenancecycle)")
            existing_cycle_cols = {row[1] for row in cursor.fetchall()}
            if "skipped" not in existing_cycle_cols:
                cursor.execute("ALTER TABLE maintenance_maintenancecycle ADD COLUMN skipped integer NOT NULL DEFAULT 0")
                if "is_skipped" in existing_cycle_cols:
                    cursor.execute("UPDATE maintenance_maintenancecycle SET skipped = CASE WHEN is_skipped = 1 THEN 1 ELSE 0 END WHERE skipped = 0")
            if "trigger" not in existing_cycle_cols:
                cursor.execute("ALTER TABLE maintenance_maintenancecycle ADD COLUMN trigger varchar(10) NOT NULL DEFAULT 'scheduler'")
        else:
            try:
                sched_desc = connection.introspection.get_table_description(cursor, "maintenance_maintenanceschedule")
                sched_cols = {col.name for col in sched_desc}
                if "interval_count" not in sched_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN interval_count integer NULL")
                if "sequence_offset" not in sched_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenanceschedule ADD COLUMN sequence_offset integer NOT NULL DEFAULT 0")

                cycle_desc = connection.introspection.get_table_description(cursor, "maintenance_maintenancecycle")
                cycle_cols = {col.name for col in cycle_desc}
                if "skipped" not in cycle_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenancecycle ADD COLUMN skipped integer NOT NULL DEFAULT 0")
                if "trigger" not in cycle_cols:
                    cursor.execute("ALTER TABLE maintenance_maintenancecycle ADD COLUMN trigger varchar(10) NOT NULL DEFAULT 'scheduler'")
            except Exception:
                pass


def reverse_migration(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("maintenance", "0004_ensure_created_by_columns"),
    ]

    operations = [
        migrations.RunPython(add_columns_if_missing, reverse_code=reverse_migration),
    ]
