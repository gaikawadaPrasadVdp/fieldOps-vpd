from decimal import Decimal
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.rbac.models import MembershipRole, Role
from apps.sites.models import Site
from apps.tenancy.models import Membership, Organization
from apps.workorders.models import WorkOrder
from apps.workspace.models import WorkNote
from apps.workspace import services


class WorkspaceWorkNoteAndDefectTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="tech@fieldops.local",
            password="Password123!",
            full_name="Tech Tester"
        )
        self.org = Organization.objects.create(
            name="FieldOps Utilities",
            slug="fieldops-utilities"
        )
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.user,
            status=Membership.Status.ACTIVE
        )
        self.owner_role = Role.objects.create(
            organization=self.org,
            name="Owner Role",
            is_owner=True
        )
        MembershipRole.objects.create(
            membership=self.membership,
            role=self.owner_role
        )
        self.site = Site.objects.create(
            organization=self.org,
            name="Central Depot",
            code="DEP-01"
        )
        self.category = AssetCategory.objects.create(
            organization=self.org,
            name="HVAC"
        )
        self.asset = Asset.objects.create(
            organization=self.org,
            site=self.site,
            category=self.category,
            asset_tag="AST-PMP-001",
            name="Primary Water Pump"
        )
        self.work_order = WorkOrder.objects.create(
            organization=self.org,
            site=self.site,
            asset=self.asset,
            order_number="WO-2026-0001",
            title="Inspect water pump",
            status=WorkOrder.Status.IN_PROGRESS,
            assigned_to=self.membership
        )

    def test_worknote_is_internal_field_defaults_false(self):
        """DEF-001 / TC_M07_061: WorkNote model has is_internal column defaulting to False."""
        note = WorkNote.objects.create(
            organization=self.org,
            work_order=self.work_order,
            author=self.membership,
            body="Test routine note"
        )
        note.refresh_from_db()
        self.assertFalse(note.is_internal)

    def test_api_add_work_note(self):
        """DEF-001 / TC_M07_061: POST /api/v1/workspace/jobs/{id}/notes/ returns 201 Created."""
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/workspace/jobs/{self.work_order.pk}/notes/"
        resp = self.client.post(
            url,
            {"body": "FT work note from technician"},
            format="json",
            HTTP_X_ORGANIZATION_ID=str(self.org.pk),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["body"], "FT work note from technician")
        self.assertTrue(WorkNote.objects.filter(work_order=self.work_order, body="FT work note from technician").exists())

    def test_report_auxiliary_defect_service(self):
        """DEF-002 / TC_M07_021: report_auxiliary_defect creates service request and cross-links note without 500."""
        sr = services.report_auxiliary_defect(
            self.work_order,
            title="FT worn coupling",
            membership=self.membership,
            actor=self.user,
            asset=self.asset,
            description="found while working"
        )
        self.assertIsNotNone(sr.pk)
        self.assertEqual(sr.title, "FT worn coupling")
        # Verify cross-link note was created
        self.assertTrue(
            WorkNote.objects.filter(
                work_order=self.work_order,
                body__contains="FT worn coupling"
            ).exists()
        )

    def test_api_report_defect(self):
        """DEF-002 / TC_M07_021: POST /api/v1/workspace/jobs/{id}/defects/ returns 201 Created."""
        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/workspace/jobs/{self.work_order.pk}/defects/"
        resp = self.client.post(
            url,
            {
                "title": "FT worn coupling",
                "description": "found while working",
                "asset_id": str(self.asset.pk),
            },
            format="json",
            HTTP_X_ORGANIZATION_ID=str(self.org.pk),
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertEqual(resp.data["title"], "FT worn coupling")
        self.assertEqual(resp.data["work_order_id"], str(self.work_order.pk))

