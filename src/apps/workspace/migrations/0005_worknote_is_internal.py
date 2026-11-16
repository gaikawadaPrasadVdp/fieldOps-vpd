# DEF-001 fix: add is_internal to workspace_worknote
# Repair: render.com DB schema has this column but migration was missing
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workspace", "0004_ensure_worknote_table"),
    ]

    operations = [
        migrations.AddField(
            model_name="worknote",
            name="is_internal",
            field=models.BooleanField(default=False),
        ),
    ]

