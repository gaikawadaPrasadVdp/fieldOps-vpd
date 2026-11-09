from django.db import migrations


def ensure_reportsnapshot_table(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS dashboards_reportsnapshot (
                id uuid PRIMARY KEY,
                created_at timestamptz NOT NULL DEFAULT NOW(),
                updated_at timestamptz NOT NULL DEFAULT NOW(),
                snapshot_type varchar(20) NOT NULL DEFAULT 'DAILY',
                section varchar(50) NOT NULL DEFAULT 'OPERATIONS',
                period_start date NOT NULL,
                period_end date NOT NULL,
                metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
                notes text NOT NULL DEFAULT '',
                created_by_id uuid NULL REFERENCES accounts_user(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED,
                organization_id uuid NOT NULL REFERENCES tenancy_organization(id) DEFERRABLE INITIALLY DEFERRED,
                site_id uuid NULL REFERENCES sites_site(id) ON DELETE SET NULL DEFERRABLE INITIALLY DEFERRED
            );

            CREATE INDEX IF NOT EXISTS dashboards_reportsnapshot_created_by_id_idx
                ON dashboards_reportsnapshot (created_by_id);
            CREATE INDEX IF NOT EXISTS dashboards_reportsnapshot_organization_id_idx
                ON dashboards_reportsnapshot (organization_id);
            CREATE INDEX IF NOT EXISTS dashboards_reportsnapshot_site_id_idx
                ON dashboards_reportsnapshot (site_id);

            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uniq_report_snapshot_period'
                      AND conrelid = 'dashboards_reportsnapshot'::regclass
                ) THEN
                    ALTER TABLE dashboards_reportsnapshot
                        ADD CONSTRAINT uniq_report_snapshot_period
                        UNIQUE (organization_id, snapshot_type, section, period_start, period_end);
                END IF;
            END $$;
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("dashboards", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_reportsnapshot_table, reverse_code=migrations.RunPython.noop),
    ]

