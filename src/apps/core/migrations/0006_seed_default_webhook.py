from django.db import migrations


def seed_default_webhooks(apps, schema_editor):
    Organization = apps.get_model("tenancy", "Organization")
    WebhookEndpoint = apps.get_model("core", "WebhookEndpoint")

    for org in Organization.objects.all():
        if not WebhookEndpoint.objects.filter(organization=org).exists():
            WebhookEndpoint.objects.create(
                organization=org,
                name="Default Integration Webhook",
                target_url="https://hooks.example.invalid/fieldops-events",
                event_pattern="work_order.*",
                is_active=False,
            )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0005_remove_webhookendpoint_core_webhoo_organiz_6dd066_idx_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_default_webhooks, reverse_code=reverse_noop),
    ]
