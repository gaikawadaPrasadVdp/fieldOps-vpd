import datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.core.exceptions import ValidationFailed
from apps.dashboards.models import ReportSnapshot
from apps.dashboards import services as db_services
from apps.dashboards.tasks import archive_periodic_report_snapshots
from apps.rbac import services as rbac
from apps.sites.models import Site
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership, Organization
from apps.workorders.models import WorkOrder
from apps.workorders import services as wo_services


class ReportSnapshotTests(TestCase):
    def setUp(self):
        # Admin & Organization
        self.admin = User.objects.create_user(
            email="admin@snapshot.test",
            password="TestPassword123!",
            full_name="Admin Snapshot",
            is_platform_admin=True,
        )
        self.org, self.owner_m = tenancy.create_organization(
            name="Snapshot Analytics Org",
            owner_email="owner@snapshot.test",
            owner_name="Owner User",
            actor=self.admin,
        )
        self.owner_m.status = Membership.Status.ACTIVE
        self.owner_m.save(update_fields=["status"])

        self.site = Site.objects.create(
            organization=self.org,
            code="SITE-SNAP-01",
            name="Snapshot Power Station",
            timezone="UTC",
        )
        self.category = AssetCategory.objects.create(
            organization=self.org,
            name="Heavy Turbines",
        )
        self.asset = Asset.objects.create(
            organization=self.org,
            site=self.site,
            category=self.category,
            asset_tag="AST-SNP-001",
            name="Main Generator Unit",
        )

    def test_create_report_snapshot_computes_and_persists_metrics(self):
        """create_report_snapshot should compute KPIs and save frozen JSON metrics."""
        today = timezone.localdate()
        yesterday = today - datetime.timedelta(days=1)

        snapshot = db_services.create_report_snapshot(
            self.org,
            snapshot_type=ReportSnapshot.SnapshotType.DAILY,
            section=ReportSnapshot.Section.OPERATIONS,
            period_start=yesterday,
            period_end=yesterday,
            actor=self.owner_m.user,
            notes="Daily Operations Freeze",
        )

        self.assertIsNotNone(snapshot.pk)
        self.assertEqual(snapshot.snapshot_type, ReportSnapshot.SnapshotType.DAILY)
        self.assertEqual(snapshot.section, ReportSnapshot.Section.OPERATIONS)
        self.assertEqual(snapshot.period_start, yesterday)
        self.assertEqual(snapshot.period_end, yesterday)
        self.assertIsInstance(snapshot.metrics, dict)
        self.assertIn("kpis", snapshot.metrics)

    def test_invalid_period_raises_validation_failed(self):
        """End date before start date should fail validation."""
        today = timezone.localdate()
        with self.assertRaises(ValidationFailed):
            db_services.create_report_snapshot(
                self.org,
                period_start=today,
                period_end=today - datetime.timedelta(days=2),
            )

    def test_archive_snapshots_for_organization(self):
        """Archive across all sections generates snapshots for yesterday."""
        snaps = db_services.archive_snapshots_for_organization(self.org)
        self.assertTrue(len(snaps) >= 1)
        sections = {s.section for s in snaps}
        self.assertIn(ReportSnapshot.Section.OPERATIONS, sections)

    def test_celery_task_archive_periodic_report_snapshots(self):
        """Celery periodic task should run without error across active organizations."""
        stats = archive_periodic_report_snapshots()
        self.assertTrue(stats["organizations"] >= 1)
        self.assertTrue(stats["snapshots_created"] >= 1)

    def test_api_report_snapshots_list_and_generate(self):
        """REST API should support listing and generating report snapshots."""
        client = APIClient()
        client.force_authenticate(user=self.owner_m.user)
        client.credentials(HTTP_X_ORGANIZATION=str(self.org.slug))

        # GET snapshots list
        res = client.get("/api/v1/dashboards/snapshots/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # POST generate snapshot
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        payload = {
            "snapshot_type": "DAILY",
            "section": "OPERATIONS",
            "period_start": yesterday.isoformat(),
            "period_end": yesterday.isoformat(),
            "notes": "API triggered snapshot",
        }
        res = client.post("/api/v1/dashboards/snapshots/", data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["section"], "OPERATIONS")

        # GET detail
        snap_id = res.data["id"]
        res_detail = client.get(f"/api/v1/dashboards/snapshots/{snap_id}/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data["id"], snap_id)

    def test_ui_snapshots_views_and_export(self):
        """Verify UI list, detail, and JSON export views."""
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        snapshot = db_services.create_report_snapshot(
            self.org,
            snapshot_type=ReportSnapshot.SnapshotType.DAILY,
            section=ReportSnapshot.Section.OPERATIONS,
            period_start=yesterday,
            period_end=yesterday,
            actor=self.owner_m.user,
        )

        client = Client(headers={"host": "localhost"})
        client.force_login(self.owner_m.user)
        session = client.session
        session["active_org_id"] = str(self.org.pk)
        session.save()

        # 1. List view
        res = client.get("/app/dashboards/snapshots/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("KPI Report Snapshots", res.content.decode("utf-8"))

        # 2. Detail view
        res = client.get(f"/app/dashboards/snapshots/{snapshot.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("KPI Snapshot", res.content.decode("utf-8"))

        # 3. Export view
        res = client.get(f"/app/dashboards/snapshots/{snapshot.pk}/export/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "application/json")
        self.assertIn("attachment; filename=", res["Content-Disposition"])
