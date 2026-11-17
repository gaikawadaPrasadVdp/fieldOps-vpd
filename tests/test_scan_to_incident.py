import datetime
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.identification.models import AssetIdentifier
from apps.identification import services as id_services
from apps.incidents.models import ServiceRequest
from apps.rbac.models import Permission, Role, RolePermission, MembershipRole
from apps.sites.models import Site
from apps.tenancy.models import Organization, Membership


class ScanToIncidentTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Scan Incident Org", slug="scan-incident-org")
        self.user = User.objects.create_user(email="technician.scanner@example.com", password="password123")
        self.membership = Membership.objects.create(
            organization=self.org, user=self.user, status=Membership.Status.ACTIVE
        )

        self.site = Site.objects.create(organization=self.org, name="Central Plant", code="CP-01")
        self.category = AssetCategory.objects.create(organization=self.org, name="Pumping Systems")
        self.asset = Asset.objects.create(
            organization=self.org,
            site=self.site,
            category=self.category,
            asset_tag="PUMP-001",
            name="Main Chilled Water Pump",
            status=Asset.Status.ACTIVE,
        )

        # Create active QR label for asset
        self.qr_ident = id_services.generate_identifier(
            self.asset, kind="QR", actor=self.user
        )

        # Grant role with asset.view, incident.create, qr.scan
        self.role = Role.objects.create(organization=self.org, name="Maintenance Tech")
        for code in ("asset.view", "incident.create", "incident.view", "incident.attach"):
            perm = Permission.objects.filter(code=code).first()
            if perm:
                RolePermission.objects.create(role=self.role, permission=perm)
        MembershipRole.objects.create(membership=self.membership, role=self.role)

        self.client = Client()
        self.client.force_login(self.user)
        session = self.client.session
        session["organization_id"] = str(self.org.id)
        session["membership_id"] = str(self.membership.id)
        session.save()

    def test_scan_page_renders_mode_selector(self):
        resp = self.client.get(reverse("identification:scan"), HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "View Asset")
        self.assertContains(resp, "Report Incident")

        # Test scan page in report mode
        resp_report = self.client.get(f"{reverse('identification:scan')}?action=report", HTTP_HOST="localhost")
        self.assertEqual(resp_report.status_code, 200)
        self.assertContains(resp_report, "Scan Asset to Report Incident")
        self.assertContains(resp_report, "Report Mode Active")

    def test_manual_scan_form_in_report_mode_redirects_to_resolve_report(self):
        resp = self.client.post(
            reverse("identification:scan"),
            {"token": self.qr_ident.token, "action": "report"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        expected_url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        self.assertEqual(resp.url, expected_url)

    def test_resolve_with_action_report_redirects_to_resolve_report(self):
        resp = self.client.get(
            f"{reverse('identification:resolve', kwargs={'token': self.qr_ident.token})}?action=report",
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp.status_code, 302)
        expected_url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        self.assertEqual(resp.url, expected_url)

    def test_get_resolve_report_renders_scanned_asset_and_form(self):
        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        resp = self.client.get(url, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.asset.name)
        self.assertContains(resp, self.asset.asset_tag)
        self.assertContains(resp, "Verified Equipment")
        self.assertContains(resp, "Submit Incident Report")

    def test_post_resolve_report_creates_incident_associated_with_scanned_asset(self):
        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        data = {
            "title": "Severe vibration in water pump casing",
            "severity": "HIGH",
            "service_impact": "DEGRADED",
            "failure_category": "Mechanical",
            "description": "Excessive bearing noise and heating observed during morning walkaround.",
        }
        resp = self.client.post(url, data=data, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 302)

        sr = ServiceRequest.objects.filter(organization=self.org, asset=self.asset).first()
        self.assertIsNotNone(sr)
        self.assertEqual(sr.title, data["title"])
        self.assertEqual(sr.severity, "HIGH")
        self.assertEqual(sr.service_impact, "DEGRADED")
        self.assertEqual(sr.failure_category, "Mechanical")
        self.assertEqual(sr.asset, self.asset)
        self.assertEqual(sr.site, self.site)
        self.assertEqual(sr.status, "NEW")
        self.assertEqual(resp.url, reverse("incidents:detail", kwargs={"pk": sr.pk}))

    def test_post_resolve_report_with_photo_attachment(self):
        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        fake_attachment = SimpleUploadedFile("damage_notes.txt", b"Oil seal damaged and leaking. See notes.", content_type="text/plain")
        data = {
            "title": "Leaking seal on pump",
            "severity": "MEDIUM",
            "service_impact": "NONE",
            "description": "Oil seal damaged. See attached notes.",
            "attachment": fake_attachment,
        }
        resp = self.client.post(url, data=data, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 302)

        sr = ServiceRequest.objects.filter(organization=self.org, title="Leaking seal on pump").first()
        self.assertIsNotNone(sr)
        from apps.files.models import Attachment
        att = Attachment.objects.filter(organization=self.org, original_name="damage_notes.txt").first()
        self.assertIsNotNone(att)

    def test_reporting_on_revoked_qr_code_blocked(self):
        # Revoke the label
        id_services.revoke_identifier(self.qr_ident, reason="Damaged label replaced", actor=self.user)

        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        resp = self.client.get(url, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "label was revoked or replaced", status_code=400)

        # POST should also be rejected
        post_resp = self.client.post(url, data={"title": "Test on revoked"}, HTTP_HOST="localhost")
        self.assertEqual(post_resp.status_code, 302)  # Redirects back to resolve showing revocation alert
        self.assertFalse(ServiceRequest.objects.filter(title="Test on revoked").exists())

    def test_reporting_on_retired_or_disposed_asset_blocked(self):
        self.asset.status = Asset.Status.RETIRED
        self.asset.save()

        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        resp = self.client.get(url, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 400)
        self.assertContains(resp, "no new requests can be opened", status_code=400)

        post_resp = self.client.post(url, data={"title": "Test on retired"}, HTTP_HOST="localhost")
        self.assertEqual(post_resp.status_code, 302)
        self.assertFalse(ServiceRequest.objects.filter(title="Test on retired").exists())

    def test_invalid_or_manipulated_token_returns_404(self):
        bad_url = reverse("identification:resolve_report", kwargs={"token": "NON_EXISTENT_QR_TOKEN_12345"})
        resp = self.client.get(bad_url, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "Label not found", status_code=404)

    def test_tenant_isolation_cross_tenant_scan_blocked(self):
        org2 = Organization.objects.create(name="Tenant Two", slug="tenant-two")
        user2 = User.objects.create_user(email="other.user@tenant2.com", password="password123")
        m2 = Membership.objects.create(organization=org2, user=user2, status=Membership.Status.ACTIVE)

        role2 = Role.objects.create(organization=org2, name="Tech Two")
        perm_view = Permission.objects.filter(code="asset.view").first()
        if perm_view:
            RolePermission.objects.create(role=role2, permission=perm_view)
        MembershipRole.objects.create(membership=m2, role=role2)

        client2 = Client()
        client2.force_login(user2)
        session = client2.session
        session["organization_id"] = str(org2.id)
        session["membership_id"] = str(m2.id)
        session.save()

        # Attempt to scan Tenant 1 asset QR code from Tenant 2
        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        resp = client2.get(url, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "Label not found", status_code=404)

    def test_permission_denied_without_incident_create(self):
        # Create user without incident.create permission
        user_readonly = User.objects.create_user(email="viewer@example.com", password="password123")
        m_ro = Membership.objects.create(organization=self.org, user=user_readonly, status=Membership.Status.ACTIVE)
        role_ro = Role.objects.create(organization=self.org, name="Viewer")
        perm_view = Permission.objects.filter(code="asset.view").first()
        if perm_view:
            RolePermission.objects.create(role=role_ro, permission=perm_view)
        MembershipRole.objects.create(membership=m_ro, role=role_ro)

        client_ro = Client()
        client_ro.force_login(user_readonly)
        session = client_ro.session
        session["organization_id"] = str(self.org.id)
        session["membership_id"] = str(m_ro.id)
        session.save()

        url = reverse("identification:resolve_report", kwargs={"token": self.qr_ident.token})
        resp = client_ro.get(url, HTTP_HOST="localhost")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "do not have permission", status_code=403)
