# Generated migration to ensure workorders_workorderlabor notes column is nullable
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("workorders", "0018_sync_workorder_number_column"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="workorderlabor",
                    name="notes",
                    field=models.CharField(blank=True, default="", max_length=500),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql="""
                    DO $$
                    BEGIN
                        IF EXISTS (
                            SELECT 1 FROM information_schema.columns 
                            WHERE table_name = 'workorders_workorderlabor' AND column_name = 'notes'
                        ) THEN
                            ALTER TABLE workorders_workorderlabor ALTER COLUMN notes DROP NOT NULL;
                            ALTER TABLE workorders_workorderlabor ALTER COLUMN notes SET DEFAULT '';
                        ELSE
                            ALTER TABLE workorders_workorderlabor ADD COLUMN notes VARCHAR(500) DEFAULT '' NOT NULL;
                            ALTER TABLE workorders_workorderlabor ALTER COLUMN notes DROP NOT NULL;
                        END IF;
                    END $$;
                    """,
                    reverse_sql="""
                    -- No-op reverse
                    """,
                ),
            ],
        ),
    ]
