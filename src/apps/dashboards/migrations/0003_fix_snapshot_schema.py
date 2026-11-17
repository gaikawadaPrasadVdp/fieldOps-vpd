"""
Migration 0003: Idempotently repair ``dashboards_reportsnapshot`` schema drift.

Why this exists (QA run 2026-11-10, DEF-001): on the shared Render QA database the
snapshot endpoints (GET/POST ``/api/v1/dashboards/snapshots/``, GET ``.../{id}/``)
returned HTTP 500 for every call, while the same code passes against a schema built
straight from the migration chain. The deployed database therefore carries drift:
the table is missing entirely, or columns/constraints are missing (partial or
out-of-order application of 0001/0002 on a restored database).

This migration makes the table whole again, no matter which of those states it is in:

* ``CREATE TABLE IF NOT EXISTS`` with the full 0001 schema (safe when absent);
* ``ADD COLUMN IF NOT EXISTS`` for every column (safe when the table pre-exists);
* missing FK constraints are re-added when no FK exists on that column yet;
* missing 0001 indexes are re-created;
* the ``uniq_report_snapshot_period`` constraint is re-added only when no duplicate
  rows would violate it, so a drifted table cannot abort the deploy.

Every statement is static SQL with hard-coded identifiers and no bind parameters:
psycopg substitutes ``%s`` textually even inside SQL string literals, which makes
mixing parameter binding with PL/pgSQL ``format()`` unsafe (the first draft of this
migration failed on apply for exactly that reason).

The migration is a no-op when the schema is already correct.
"""
from django.db import migrations

_TABLE = "dashboards_reportsnapshot"

# (column, referenced table, ON DELETE rule)
_FOREIGN_KEYS = [
    ("created_by_id", "accounts_user", "SET NULL"),
    ("organization_id", "tenancy_organization", "RESTRICT"),
    ("site_id", "sites_site", "SET NULL"),
]


def repair_reportsnapshot_schema(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        # 1. Full table when it is missing entirely.
        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {_TABLE} (
                id uuid PRIMARY KEY,
                created_at timestamptz NOT NULL DEFAULT NOW(),
                updated_at timestamptz NOT NULL DEFAULT NOW(),
                snapshot_type varchar(20) NOT NULL DEFAULT 'DAILY',
                section varchar(50) NOT NULL DEFAULT 'OPERATIONS',
                period_start date NOT NULL,
                period_end date NOT NULL,
                metrics jsonb NOT NULL DEFAULT '{{}}'::jsonb,
                notes text NOT NULL DEFAULT '',
                created_by_id uuid NULL,
                organization_id uuid NOT NULL,
                site_id uuid NULL
            )
            """
        )

        # 2. Columns missing from a drifted/partial table. Defaults make the NOT NULL
        #    additions safe when rows already exist; UUID/date columns are added
        #    nullable so a partial table is repaired instead of failing the deploy
        #    (Django enforces NOT NULL at the application layer on every write).
        for ddl in (
            "created_at timestamptz NOT NULL DEFAULT NOW()",
            "updated_at timestamptz NOT NULL DEFAULT NOW()",
            "snapshot_type varchar(20) NOT NULL DEFAULT 'DAILY'",
            "section varchar(50) NOT NULL DEFAULT 'OPERATIONS'",
            "period_start date",
            "period_end date",
            "metrics jsonb NOT NULL DEFAULT '{}'::jsonb",
            "notes text NOT NULL DEFAULT ''",
            "created_by_id uuid",
            "organization_id uuid",
            "site_id uuid",
        ):
            cursor.execute(f"ALTER TABLE {_TABLE} ADD COLUMN IF NOT EXISTS {ddl}")

        # 3. Missing FK constraints, detected per column (constraint names generated
        #    by Django contain hashes, so names are not a stable check).
        for column, ref_table, on_delete in _FOREIGN_KEYS:
            cursor.execute(
                f"""
                DO $do$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1
                        FROM pg_constraint AS c
                        JOIN pg_attribute AS a
                          ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
                        WHERE c.conrelid = '{_TABLE}'::regclass
                          AND c.contype = 'f'
                          AND a.attname = '{column}'
                          AND c.confrelid = '{ref_table}'::regclass
                    ) THEN
                        EXECUTE 'ALTER TABLE {_TABLE} '
                                'ADD CONSTRAINT {_TABLE}_{column}_fkey '
                                'FOREIGN KEY ({column}) REFERENCES {ref_table}(id) '
                                'ON DELETE {on_delete} '
                                'DEFERRABLE INITIALLY DEFERRED';
                    END IF;
                END
                $do$;
                """
            )

        # 4. Missing indexes (0001 names).
        for column in ("created_by_id", "organization_id", "site_id"):
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {_TABLE}_{column}_idx ON {_TABLE} ({column})")

        # 5. Unique constraint — only when it is missing AND no duplicate rows
        #    would violate it, so drifted data cannot abort the deploy.
        cursor.execute(
            f"""
            DO $do$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = 'uniq_report_snapshot_period'
                      AND conrelid = '{_TABLE}'::regclass
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM {_TABLE}
                    WHERE organization_id IS NOT NULL
                    GROUP BY organization_id, snapshot_type, section, period_start, period_end
                    HAVING count(*) > 1
                ) THEN
                    ALTER TABLE {_TABLE}
                        ADD CONSTRAINT uniq_report_snapshot_period
                        UNIQUE (organization_id, snapshot_type, section, period_start, period_end);
                END IF;
            END
            $do$;
            """
        )


class Migration(migrations.Migration):
    dependencies = [
        ("dashboards", "0002_sync_schema"),
    ]

    operations = [
        migrations.RunPython(repair_reportsnapshot_schema, migrations.RunPython.noop),
    ]
