import re
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.contracts.models import CoverageAgreement, ServiceProvider

_FUZZ_PATTERN = re.compile(r"<[^>]*>|[<>]|script|onerror|alert\(|(.)\1{4,}", re.IGNORECASE)


class Command(BaseCommand):
    help = "Purge fuzzed, XSS, and repetitive test records from the ServiceProvider table."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the cleanup without modifying the database.",
        )
        parser.add_argument(
            "--include-bapi",
            action="store_true",
            help="Also purge synthetic 'BAPI Provider ...' test records.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_bapi = options["include_bapi"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Running in DRY-RUN mode. No changes will be saved."))

        deleted_count = 0
        sanitized_count = 0
        total_inspected = 0

        qs = ServiceProvider.objects.all()

        for provider in qs:
            total_inspected += 1
            name = provider.name or ""
            is_fuzzed = bool(_FUZZ_PATTERN.search(name))
            is_bapi = include_bapi and name.lower().startswith("bapi provider")

            if is_fuzzed or is_bapi:
                has_agreements = CoverageAgreement.objects.filter(provider=provider).exists()

                if not has_agreements:
                    if not dry_run:
                        provider.delete()
                    deleted_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"Deleted unlinked fuzzed provider (ID {provider.pk}): {repr(name[:60])}")
                    )
                else:
                    clean_name = re.sub(r"<[^>]*>|[<>]|alert\([^)]*\)", "", name).strip()
                    clean_name = re.sub(r"(.)\1{4,}", r"\1", clean_name).strip()
                    if not clean_name or len(clean_name) < 2:
                        clean_name = f"Service Provider {str(provider.id)[:8]}"
                    clean_name = clean_name[:150]

                    if not dry_run:
                        provider.name = clean_name
                        provider.is_active = False
                        provider.save(update_fields=["name", "is_active"])
                    sanitized_count += 1
                    self.stdout.write(
                        self.style.NOTICE(
                            f"Sanitized linked provider (ID {provider.pk}): {repr(name[:40])} -> {repr(clean_name)}"
                        )
                    )

        summary = (
            f"Finished: {total_inspected} providers checked, "
            f"{deleted_count} deleted, {sanitized_count} sanitized."
        )
        if dry_run:
            summary += " (DRY-RUN - no changes saved)"

        self.stdout.write(self.style.SUCCESS(summary))
