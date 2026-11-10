import datetime
from django.test import TestCase, Client
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.contracts.models import CoverageAgreement, CoveredAsset, CoverageExclusion, ServiceProvider, CoverageCheck
from apps.contracts import services as contracts_services
from apps.incidents.models import ServiceRequest
from apps.incidents import services as incident_services
from apps.rbac.models import Role, MembershipRole
from apps.sites.models import Site
from apps.tenancy.models import Organization, Membership
from apps.workorders.models import WorkOrder
from apps.workorders import services as wo_services
from apps.workorders.assignment_rules import schedule_warnings


class CoverageAutomationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="coverage.admin@example.com", password="password123")
        self.org = Organization.objects.create(name="Coverage Test Org", slug="coverage-test-org")
        self.membership = Membership.objects.create(
            organization=self.org, user=self.user, status=Membership.Status.ACTIVE
        )
        self.owner_role = Role.objects.create(
            organization=self.org, name="Owner", system_key="owner", is_owner=True
        )
        MembershipRole.objects.create(membership=self.membership, role=self.owner_role)

        self.site = Site.objects.create(
            organization=self.org, name="Coverage Site", code="COV-01"
        )
        self.category = AssetCategory.objects.create(
            organization=self.org, name="Machinery"
        )
        self.asset = Asset.objects.create(
            organization=self.org, site=self.site, category=self.category, asset_tag="AST-COV-01", name="Covered Generator",
            status=Asset.Status.ACTIVE
        )

        self.provider = ServiceProvider.objects.create(
            organization=self.org, name="Acme Care Services", contact_name="John Doe", is_active=True
        )

        self.today = datetime.date.today()
        self.warranty = CoverageAgreement.objects.create(
            organization=self.org,
            provider=self.provider,
            site=self.site,
            reference="WAR-2026-001",
            title="Standard Factory Warranty",
            kind=CoverageAgreement.Kind.WARRANTY,
            start_date=self.today - datetime.timedelta(days=30),
            end_date=self.today + datetime.timedelta(days=30),
            is_active=True,
        )
        CoveredAsset.objects.create(
            organization=self.org,
            agreement=self.warranty,
            asset=self.asset
        )

    def test_automatic_coverage_check_on_work_order_creation(self):
        wo = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Repair generator coolant leak",
            work_type="CORRECTIVE",
            priority="HIGH",
            actor=self.user,
            membership=self.membership
        )

        self.assertTrue(wo.coverage_checks.exists())
        check = wo.latest_coverage_check
        self.assertIsNotNone(check)
        self.assertTrue(check.eligible)
        self.assertEqual(check.agreement, self.warranty)
        self.assertIn("covered by warranty", check.reason.lower())

    def test_automatic_coverage_check_on_work_order_update(self):
        wo = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Inspect generator belts",
            work_type="CORRECTIVE",
            priority="LOW",
            actor=self.user,
            membership=self.membership
        )
        self.assertEqual(wo.coverage_checks.count(), 1)

        # Update work order title and priority
        wo_services.update_work_order(
            wo,
            title="Inspect generator belts - updated",
            priority="MEDIUM",
            actor=self.user,
            membership=self.membership
        )
        # Check re-evaluated and recorded
        self.assertEqual(wo.coverage_checks.count(), 2)
        latest = wo.latest_coverage_check
        self.assertTrue(latest.eligible)

    def test_excluded_work_type_marks_check_ineligible(self):
        CoverageExclusion.objects.create(
            organization=self.org,
            agreement=self.warranty,
            work_type="INSTALLATION"
        )
        wo = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Install new expansion tank",
            work_type="INSTALLATION",
            priority="MEDIUM",
            actor=self.user,
            membership=self.membership
        )
        check = wo.latest_coverage_check
        self.assertIsNotNone(check)
        self.assertFalse(check.eligible)
        self.assertIn("excludes installation work", check.reason.lower())

    def test_expired_and_inactive_agreements_handled_correctly(self):
        # 1. Inactive agreement
        self.warranty.is_active = False
        self.warranty.save()

        wo_inactive = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Routine repair",
            work_type="CORRECTIVE",
            priority="MEDIUM",
            actor=self.user,
            membership=self.membership
        )
        check_inactive = wo_inactive.latest_coverage_check
        self.assertFalse(check_inactive.eligible)
        self.assertIn("agreement is inactive", check_inactive.reason.lower())

        # 2. Expired agreement
        self.warranty.is_active = True
        self.warranty.end_date = self.today - datetime.timedelta(days=1)
        self.warranty.save()

        wo_expired = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Routine repair after expiry",
            work_type="CORRECTIVE",
            priority="MEDIUM",
            actor=self.user,
            membership=self.membership
        )
        check_expired = wo_expired.latest_coverage_check
        self.assertFalse(check_expired.eligible)
        self.assertIn("coverage expired", check_expired.reason.lower())

    def test_overlapping_coverage_prefers_warranty_over_amc(self):
        amc = CoverageAgreement.objects.create(
            organization=self.org,
            provider=self.provider,
            site=self.site,
            reference="AMC-2026-001",
            title="Annual Maintenance Contract",
            kind=CoverageAgreement.Kind.AMC,
            start_date=self.today - datetime.timedelta(days=10),
            end_date=self.today + datetime.timedelta(days=100),
            is_active=True,
        )
        CoveredAsset.objects.create(
            organization=self.org,
            agreement=amc,
            asset=self.asset
        )

        wo = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Dual covered fix",
            work_type="CORRECTIVE",
            priority="HIGH",
            actor=self.user,
            membership=self.membership
        )
        check = wo.latest_coverage_check
        self.assertTrue(check.eligible)
        # Should pick Warranty first according to KIND_ORDER
        self.assertEqual(check.agreement, self.warranty)

    def test_mid_job_expiry_warning_in_assignment_rules(self):
        # Warranty expires in 2 days
        self.warranty.end_date = self.today + datetime.timedelta(days=2)
        self.warranty.save()

        # Work order planned for 1 day to 4 days from now (agreement expires on day 2, before day 4)
        planned_start = timezone.now() + datetime.timedelta(days=1)
        planned_end = timezone.now() + datetime.timedelta(days=4)

        wo = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="Multi-day overhaul",
            work_type="CORRECTIVE",
            priority="MEDIUM",
            planned_start=planned_start,
            planned_end=planned_end,
            actor=self.user,
            membership=self.membership
        )

        warning = wo.coverage_expiry_warning
        self.assertTrue(bool(warning))
        self.assertIn("expires on", warning)

        # Assignment rules should surface this warning
        warnings = schedule_warnings(wo)
        self.assertTrue(any("Coverage Warning" in w for w in warnings))

    def test_service_request_coverage_evaluation(self):
        sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.membership,
            title="Generator vibration alarm",
            description="Abnormal vibrations during peak load",
            actor=self.user
        )

        cov = sr.coverage
        self.assertIsNotNone(cov)
        self.assertTrue(cov.covered)
        self.assertTrue(cov.eligible)
        self.assertEqual(cov.best.agreement, self.warranty)

    def test_tenant_isolation_cross_tenant_coverage_blocked(self):
        org2 = Organization.objects.create(name="Competitor Org", slug="competitor-org")
        cat2 = AssetCategory.objects.create(organization=org2, name="Other Machinery")
        asset2 = Asset.objects.create(
            organization=org2, site=self.site, category=cat2, asset_tag="AST-COMP-01", name="Alien Asset",
            status=Asset.Status.ACTIVE
        )

        res = contracts_services.evaluate(org2, self.asset, on=self.today, work_type="CORRECTIVE")
        self.assertFalse(res.covered)
        self.assertFalse(res.eligible)
        self.assertEqual(len(res.entries), 0)

    def test_ui_work_order_overview_displays_coverage(self):
        wo = wo_services.create_work_order(
            self.org,
            site=self.site,
            asset=self.asset,
            title="UI Overview Coverage Check",
            work_type="CORRECTIVE",
            priority="HIGH",
            actor=self.user,
            membership=self.membership
        )

        client = Client()
        client.force_login(self.user)
        session = client.session
        session["organization_id"] = str(self.org.id)
        session["membership_id"] = str(self.membership.id)
        session.save()

        resp = client.get(f"/app/work-orders/{wo.pk}/?tab=overview", HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Warranty / AMC")
        self.assertContains(resp, "Covered")
        self.assertContains(resp, self.warranty.reference)

    def test_ui_service_request_detail_displays_coverage(self):
        sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.membership,
            title="UI Incident Coverage Check",
            description="Inspection required",
            actor=self.user
        )

        client = Client()
        client.force_login(self.user)
        session = client.session
        session["organization_id"] = str(self.org.id)
        session["membership_id"] = str(self.membership.id)
        session.save()

        resp = client.get(f"/app/incidents/{sr.pk}/", HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Warranty / AMC")
        self.assertContains(resp, "Covered")
        self.assertContains(resp, self.warranty.reference)
