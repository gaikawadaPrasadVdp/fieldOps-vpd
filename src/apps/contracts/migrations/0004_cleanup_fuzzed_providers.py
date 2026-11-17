import re
from django.db import migrations

_FUZZ_PATTERN = re.compile(r"<[^>]*>|[<>]|script|onerror|alert\(|(.)\1{4,}", re.IGNORECASE)


def cleanup_fuzzed_providers(apps, schema_editor):
    ServiceProvider = apps.get_model("contracts", "ServiceProvider")
    CoverageAgreement = apps.get_model("contracts", "CoverageAgreement")

    for p in ServiceProvider.objects.all():
        name = p.name or ""
        if _FUZZ_PATTERN.search(name):
            has_agreements = CoverageAgreement.objects.filter(provider=p).exists()
            if not has_agreements:
                p.delete()
            else:
                clean_name = re.sub(r"<[^>]*>|[<>]|alert\([^)]*\)", "", name).strip()
                clean_name = re.sub(r"(.)\1{4,}", r"\1", clean_name).strip()
                if not clean_name or len(clean_name) < 2:
                    clean_name = f"Service Provider {str(p.id)[:8]}"
                p.name = clean_name[:150]
                p.is_active = False
                p.save(update_fields=["name", "is_active"])


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0003_sync_schema"),
    ]

    operations = [
        migrations.RunPython(cleanup_fuzzed_providers, reverse_code=reverse_noop),
    ]
