# DEF-001 fix: add is_internal to workspace_worknote
# Repair: render.com DB schema has this column but migration was missing
from django.db import migrations, models


def add_is_internal_column(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor
    with connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(
                "ALTER TABLE workspace_worknote ADD COLUMN IF NOT EXISTS is_internal BOOLEAN DEFAULT FALSE NOT NULL;"
            )
        elif vendor == "sqlite":
            cursor.execute("PRAGMA table_info(workspace_worknote);")
            columns = [row[1] for row in cursor.fetchall()]
            if "is_internal" not in columns:
                cursor.execute("ALTER TABLE workspace_worknote ADD COLUMN is_internal bool DEFAULT 0 NOT NULL;")


def remove_is_internal_column(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0004_ensure_worknote_table"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="worknote",
                    name="is_internal",
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunPython(add_is_internal_column, reverse_code=remove_is_internal_column),
            ],
        ),
    ]

