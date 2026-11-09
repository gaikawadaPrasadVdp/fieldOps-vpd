from django.db import migrations


def ensure_worknote_table(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != "postgresql":
        return

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_worknote (
                id uuid PRIMARY KEY,
                created_at timestamptz NOT NULL DEFAULT NOW(),
                updated_at timestamptz NOT NULL DEFAULT NOW(),
                body text NOT NULL,
                author_id uuid NOT NULL REFERENCES tenancy_membership(id) DEFERRABLE INITIALLY DEFERRED,
                organization_id uuid NOT NULL REFERENCES tenancy_organization(id) DEFERRABLE INITIALLY DEFERRED,
                work_order_id uuid NOT NULL REFERENCES workorders_workorder(id) DEFERRABLE INITIALLY DEFERRED
            );

            CREATE INDEX IF NOT EXISTS workspace_worknote_author_id_idx
                ON workspace_worknote (author_id);
            CREATE INDEX IF NOT EXISTS workspace_worknote_organization_id_idx
                ON workspace_worknote (organization_id);
            CREATE INDEX IF NOT EXISTS workspace_worknote_work_order_id_idx
                ON workspace_worknote (work_order_id);
            """
        )


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0003_shift_technicianprofile_and_more"),
    ]

    operations = [
        migrations.RunPython(ensure_worknote_table, reverse_code=migrations.RunPython.noop),
    ]

