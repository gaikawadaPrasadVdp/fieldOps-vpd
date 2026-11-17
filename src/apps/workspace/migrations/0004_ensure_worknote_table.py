# Migration to guarantee workspace_worknote table exists with all required columns
from django.db import migrations


def ensure_worknote_table(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspace_worknote (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    organization_id UUID NOT NULL REFERENCES tenancy_organization(id) ON DELETE RESTRICT,
                    work_order_id UUID NOT NULL REFERENCES workorders_workorder(id) ON DELETE RESTRICT,
                    author_id UUID NOT NULL REFERENCES tenancy_membership(id) ON DELETE RESTRICT,
                    body TEXT NOT NULL DEFAULT ''
                );
                CREATE INDEX IF NOT EXISTS workspace_worknote_org_idx ON workspace_worknote(organization_id);
                CREATE INDEX IF NOT EXISTS workspace_worknote_wo_idx ON workspace_worknote(work_order_id);
                CREATE INDEX IF NOT EXISTS workspace_worknote_author_idx ON workspace_worknote(author_id);
            """)
        elif vendor == "sqlite":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workspace_worknote (
                    id char(32) NOT NULL PRIMARY KEY,
                    created_at datetime NOT NULL,
                    updated_at datetime NOT NULL,
                    body text NOT NULL,
                    author_id char(32) NOT NULL REFERENCES tenancy_membership (id) DEFERRABLE INITIALLY DEFERRED,
                    organization_id char(32) NOT NULL REFERENCES tenancy_organization (id) DEFERRABLE INITIALLY DEFERRED,
                    work_order_id char(32) NOT NULL REFERENCES workorders_workorder (id) DEFERRABLE INITIALLY DEFERRED
                );
            """)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0003_shift_technicianprofile_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_worknote_table, reverse_code=reverse_noop),
    ]
