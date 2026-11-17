from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sla", "0009_ensure_sample_sla_breach"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE sla_slatarget
                DROP COLUMN IF EXISTS response_unit CASCADE,
                DROP COLUMN IF EXISTS resolution_unit CASCADE,
                DROP COLUMN IF EXISTS response_completion_event CASCADE,
                DROP COLUMN IF EXISTS resolution_completion_event CASCADE;

            ALTER TABLE sla_escalationrule
                DROP COLUMN IF EXISTS notification_channel CASCADE,
                DROP COLUMN IF EXISTS notification_message CASCADE,
                DROP COLUMN IF EXISTS repeat_interval_minutes CASCADE,
                DROP COLUMN IF EXISTS stop_condition CASCADE;
            """,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
