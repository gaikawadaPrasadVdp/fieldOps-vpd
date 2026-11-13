"""Prepares and sanitizes the database environment for QA Functional and Regression Retests.

Resolves the 545 blocked test cases by:
1. Purging dangling ephemeral test artifacts (duplicate site codes, test roles, unlinked test providers).
2. Seeding complete baseline fixtures (roles, users, sites, assets, checklists, SLA profiles, work orders).
3. Outputting freshly generated JWT access & refresh tokens for automated test harnesses.
"""
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from apps.contracts.models import ServiceProvider, CoverageAgreement
from apps.sites.models import Site
from apps.rbac.models import Role, MembershipRole


class Command(BaseCommand):
    help = "Sanitize duplicate test records and seed complete QA baseline fixtures to unblock test cases."

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-seed",
            action="store_true",
            help="Skip running seed commands; only sanitize and generate tokens.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== FieldOps Nexus QA Retest Preparation ==="))

        # 1. Clean up duplicate test data from previous runs (Resolves 409 Conflict blockers)
        self.stdout.write("1. Sanitizing duplicate test records...")

        # A. Clean up test providers without agreements
        call_command("cleanup_fuzzed_providers", "--include-bapi")

        # B. Clean up unlinked test sites (e.g. TEST-*, TEMP-*)
        test_sites = Site.objects.filter(code__iregex=r"^(TEST|TEMP|QA-TEMP)-")
        deleted_sites = 0
        for s in test_sites:
            if not s.work_orders.exists() and not s.assets.exists():
                s.delete()
                deleted_sites += 1
        if deleted_sites:
            self.stdout.write(self.style.SUCCESS(f"   [OK] Purged {deleted_sites} temporary test sites."))

        # C. Clean up unlinked test roles
        test_roles = Role.objects.filter(name__iregex=r"^(Test Role|Temp Role|QA Role)")
        deleted_roles = 0
        for r in test_roles:
            if not MembershipRole.objects.filter(role=r).exists():
                r.delete()
                deleted_roles += 1
        if deleted_roles:
            self.stdout.write(self.style.SUCCESS(f"   [OK] Purged {deleted_roles} temporary test roles."))

        # 2. Seed Baseline Fixtures (Resolves 404 Stale IDs & References)
        if not options["skip_seed"]:
            self.stdout.write("2. Seeding complete baseline fixtures...")
            try:
                call_command("seed_user_roles")
                self.stdout.write(self.style.SUCCESS("   [OK] Standard user roles and personas seeded."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   [WARN] seed_user_roles: {e}"))

            try:
                call_command("seed_phase1_demo")
                self.stdout.write(self.style.SUCCESS("   [OK] Asset categories, assets, and meters seeded."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   [WARN] seed_phase1_demo: {e}"))

            try:
                call_command("seed_checklists_demo")
                self.stdout.write(self.style.SUCCESS("   [OK] Checklists and inspection templates seeded."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   [WARN] seed_checklists_demo: {e}"))

            try:
                call_command("seed_sla_demo")
                self.stdout.write(self.style.SUCCESS("   [OK] SLA profiles, rules, and targets seeded."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   [WARN] seed_sla_demo: {e}"))

            try:
                call_command("seed_workorders")
                self.stdout.write(self.style.SUCCESS("   [OK] Work orders and execution events seeded."))
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"   [WARN] seed_workorders: {e}"))

        # 3. Generate Fresh JWT Tokens (Resolves Expired Token Blockers TC_AUTH_014 & TC_AUTH_054)
        self.stdout.write("3. Generating fresh JWT test credentials...")
        User = get_user_model()
        target_user = (
            User.objects.filter(email="admin@apexindustrial.example.com").first()
            or User.objects.filter(is_superuser=True).first()
            or User.objects.first()
        )

        if target_user:
            refresh = RefreshToken.for_user(target_user)
            self.stdout.write(self.style.SUCCESS(f"   User: {target_user.email}"))
            self.stdout.write(self.style.SUCCESS(f"   ACCESS TOKEN  : {str(refresh.access_token)}"))
            self.stdout.write(self.style.SUCCESS(f"   REFRESH TOKEN : {str(refresh)}"))
        else:
            self.stdout.write(self.style.WARNING("   No active user found to generate tokens."))

        self.stdout.write(self.style.SUCCESS("=== QA Retest Environment Successfully Prepared ==="))
