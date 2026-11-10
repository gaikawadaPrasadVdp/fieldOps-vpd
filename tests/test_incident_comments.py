import datetime
from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.core.exceptions import Conflict, DomainError, NotFound, PermissionDenied, ValidationFailed
from apps.incidents import selectors as incident_selectors
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest, ServiceRequestComment
from apps.notifications.models import Notification
from apps.portal.models import PortalAccount
from apps.rbac.models import MembershipRole, Permission, Role, RolePermission
from apps.sites.models import Site
from apps.tenancy.models import Membership, Organization


class IncidentCommentsTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(name="Nexus Industrial Org", slug="nexus-industrial")
        self.site = Site.objects.create(organization=self.org, name="Main Facility", code="MF-01")
        self.category = AssetCategory.objects.create(organization=self.org, name="Turbines")
        self.asset = Asset.objects.create(
            organization=self.org,
            site=self.site,
            category=self.category,
            asset_tag="TURB-01",
            name="Gas Turbine Unit 1",
            status=Asset.Status.ACTIVE,
        )

        # 1. Staff user (Maintenance Supervisor)
        self.staff_user = User.objects.create_user(
            email="supervisor@nexusindustrial.com",
            full_name="Sam Supervisor",
            password="password123",
        )
        self.staff_membership = Membership.objects.create(
            organization=self.org, user=self.staff_user, status=Membership.Status.ACTIVE
        )
        self.staff_role = Role.objects.create(organization=self.org, name="Supervisor", system_key="supervisor")
        for code in ("incident.view", "incident.view_assigned", "incident.update", "incident.manage"):
            perm = Permission.objects.filter(code=code).first()
            if perm:
                RolePermission.objects.create(role=self.staff_role, permission=perm)
        MembershipRole.objects.create(membership=self.staff_membership, role=self.staff_role)

        # 2. Client user (Requester)
        self.client_user = User.objects.create_user(
            email="client.requester@clientorg.com",
            full_name="Clara Client",
            password="password123",
        )
        self.client_membership = Membership.objects.create(
            organization=self.org, user=self.client_user, status=Membership.Status.ACTIVE
        )
        self.client_role = Role.objects.create(
            organization=self.org, name="Client Requester", system_key="client_requester"
        )
        client_perm = Permission.objects.filter(code="incident.report_owned").first()
        if client_perm:
            RolePermission.objects.create(role=self.client_role, permission=client_perm)
        MembershipRole.objects.create(membership=self.client_membership, role=self.client_role)
        self.portal_account = PortalAccount.objects.create(
            organization=self.org,
            membership=self.client_membership,
            company_name="Client Industries Ltd",
            is_enabled=True,
        )

        # Create Service Request reported by client
        self.sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.client_membership,
            title="Turbine bearing overheating and noise",
            occurred_at=timezone.now() - datetime.timedelta(hours=1),
            actor=self.client_user,
            kind="INCIDENT",
            severity="HIGH",
            description="Loud grinding heard during cycle 3.",
        )

        # Clients for HTTP testing
        self.staff_client = Client()
        self.staff_client.force_login(self.staff_user)
        session = self.staff_client.session
        session["organization_id"] = str(self.org.id)
        session["membership_id"] = str(self.staff_membership.id)
        session.save()

        self.portal_client = Client()
        self.portal_client.force_login(self.client_user)
        portal_session = self.portal_client.session
        portal_session["organization_id"] = str(self.org.id)
        portal_session["membership_id"] = str(self.client_membership.id)
        portal_session.save()

    def test_create_comment_client_visible_and_notifications(self):
        comment = incident_services.add_comment(
            self.sr,
            body="Technician team has been dispatched to inspect bearing lubrication.",
            actor=self.staff_user,
            membership=self.staff_membership,
            is_internal=False,
        )
        self.assertIsNotNone(comment.pk)
        self.assertEqual(comment.body, "Technician team has been dispatched to inspect bearing lubrication.")
        self.assertFalse(comment.is_internal)
        self.assertEqual(comment.author, self.staff_user)
        self.assertEqual(comment.author_name, self.staff_user.display_name or self.staff_user.email)

        # Notification should have been sent to client reporter
        notifs = Notification.objects.filter(organization=self.org, recipient=self.client_user)
        self.assertEqual(notifs.count(), 1)
        self.assertIn("New comment on", notifs.first().title)
        self.assertIn("portal/requests", notifs.first().link)

    def test_create_internal_staff_note_hidden_from_client_and_no_client_notification(self):
        note = incident_services.add_comment(
            self.sr,
            body="Internal note: suspecting severe metallurgical wear. Check warranty claims.",
            actor=self.staff_user,
            membership=self.staff_membership,
            is_internal=True,
        )
        self.assertTrue(note.is_internal)

        # Notification should NOT be delivered to client
        client_notifs = Notification.objects.filter(organization=self.org, recipient=self.client_user)
        self.assertEqual(client_notifs.count(), 0)

        # Selector visibility check
        staff_comments = incident_selectors.comments_for(self.staff_membership, self.org, self.sr)
        self.assertIn(note, staff_comments)

        client_comments = incident_selectors.comments_for(self.client_membership, self.org, self.sr)
        self.assertNotIn(note, client_comments)

    def test_client_cannot_create_internal_note(self):
        with self.assertRaises(ValidationFailed) as ctx:
            incident_services.add_comment(
                self.sr,
                body="Client attempting to make internal note",
                actor=self.client_user,
                membership=self.client_membership,
                is_internal=True,
            )
        self.assertEqual(ctx.exception.code, "client_internal_note_forbidden")

    def test_chronological_ordering(self):
        c1 = incident_services.add_comment(
            self.sr, body="First comment", actor=self.client_user, membership=self.client_membership
        )
        c2 = incident_services.add_comment(
            self.sr, body="Second comment", actor=self.staff_user, membership=self.staff_membership
        )
        c3 = incident_services.add_comment(
            self.sr, body="Third comment", actor=self.staff_user, membership=self.staff_membership
        )

        comments = list(incident_selectors.comments_for(self.staff_membership, self.org, self.sr))
        self.assertEqual([c.pk for c in comments], [c1.pk, c2.pk, c3.pk])

    def test_input_validation_empty_and_max_length(self):
        # Empty message
        with self.assertRaises(ValidationFailed) as ctx_empty:
            incident_services.add_comment(
                self.sr, body="   ", actor=self.staff_user, membership=self.staff_membership
            )
        self.assertEqual(ctx_empty.exception.code, "empty_comment")

        # Exceeds max length
        long_body = "A" * 5001
        with self.assertRaises(ValidationFailed) as ctx_len:
            incident_services.add_comment(
                self.sr, body=long_body, actor=self.staff_user, membership=self.staff_membership
            )
        self.assertEqual(ctx_len.exception.code, "comment_too_long")

    def test_xss_protection_and_sanitization(self):
        malicious_input = "<script>alert('xss')</script><b>Warning: High heat</b>"
        comment = incident_services.add_comment(
            self.sr, body=malicious_input, actor=self.staff_user, membership=self.staff_membership
        )
        # Should be escaped, not raw executable script
        self.assertNotIn("<script>", comment.body)
        self.assertIn("&lt;script&gt;", comment.body)

    def test_tenant_isolation_cross_tenant_blocked(self):
        org2 = Organization.objects.create(name="Tenant 2 Org", slug="tenant-2-org")
        user2 = User.objects.create_user(email="other.supervisor@tenant2.com", password="password123")
        m2 = Membership.objects.create(organization=org2, user=user2, status=Membership.Status.ACTIVE)

        # Cross-tenant comments selection returns empty
        c_tenant2 = incident_selectors.comments_for(m2, org2, self.sr)
        self.assertEqual(c_tenant2.count(), 0)

        # Cross-tenant comment delete rejected
        c = incident_services.add_comment(
            self.sr, body="Valid tenant 1 note", actor=self.staff_user, membership=self.staff_membership
        )
        with self.assertRaises(NotFound):
            incident_services.delete_comment(org2, c.pk, actor=user2, membership=m2)

    def test_delete_comment_permissions(self):
        c_staff = incident_services.add_comment(
            self.sr, body="Note to be deleted", actor=self.staff_user, membership=self.staff_membership
        )
        # Client cannot delete staff comment
        with self.assertRaises(PermissionDenied):
            incident_services.delete_comment(
                self.org, c_staff.pk, actor=self.client_user, membership=self.client_membership
            )

        # Staff author can delete it
        incident_services.delete_comment(
            self.org, c_staff.pk, actor=self.staff_user, membership=self.staff_membership
        )
        self.assertFalse(ServiceRequestComment.objects.filter(pk=c_staff.pk).exists())

    def test_handling_deleted_author_gracefully(self):
        c = incident_services.add_comment(
            self.sr, body="Diagnostics recorded.", actor=self.staff_user, membership=self.staff_membership
        )
        self.assertEqual(c.author_display, self.staff_user.display_name)

        # Simulate author account being deleted (author foreign key set to null)
        c.author = None
        c.save()
        c.refresh_from_db()
        self.assertIsNone(c.author)
        # author_name snapshot persists and author_display handles null safely
        self.assertEqual(c.author_display, self.staff_user.display_name)

    def test_ui_comments_tab_view_and_post(self):
        # GET comments tab
        resp_get = self.staff_client.get(
            f"{reverse('incidents:detail', kwargs={'pk': self.sr.pk})}?tab=comments",
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp_get.status_code, 200)
        self.assertContains(resp_get, "Communication Thread")
        self.assertContains(resp_get, "Internal note (staff only, hidden from client)")

        # POST comment via UI
        resp_post = self.staff_client.post(
            reverse("incidents:comments", kwargs={"pk": self.sr.pk}),
            {"body": "Parts have arrived on site.", "is_internal": "on"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp_post.status_code, 302)
        saved = ServiceRequestComment.objects.filter(request=self.sr, body="Parts have arrived on site.").first()
        self.assertIsNotNone(saved)
        self.assertTrue(saved.is_internal)

    def test_portal_client_comment_flow(self):
        # Client sends message from portal
        resp_post = self.portal_client.post(
            reverse("portal:request_comments", kwargs={"pk": str(self.sr.pk)}),
            {"body": "Can you provide an estimated arrival time for the field engineer?"},
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp_post.status_code, 302)

        saved = ServiceRequestComment.objects.filter(
            request=self.sr,
            body="Can you provide an estimated arrival time for the field engineer?",
        ).first()
        self.assertIsNotNone(saved)
        self.assertFalse(saved.is_internal)
        self.assertEqual(saved.author, self.client_user)

        # Client view renders this comment
        resp_detail = self.portal_client.get(
            reverse("portal:request_detail", kwargs={"pk": str(self.sr.pk)}),
            HTTP_HOST="localhost",
        )
        self.assertEqual(resp_detail.status_code, 200)
        self.assertContains(resp_detail, "estimated arrival time")

    def test_rest_api_comments_endpoints(self):
        api_client = Client()
        api_client.force_login(self.staff_user)
        session = api_client.session
        session["organization_id"] = str(self.org.id)
        session["membership_id"] = str(self.staff_membership.id)
        session.save()

        # POST via API
        url = f"/api/v1/service-requests/{self.sr.pk}/comments/"
        post_resp = api_client.post(
            url,
            {"body": "API posted note", "is_internal": True},
            content_type="application/json",
            HTTP_HOST="localhost",
        )
        self.assertEqual(post_resp.status_code, 201)
        data = post_resp.json()
        self.assertEqual(data["body"], "API posted note")
        self.assertTrue(data["is_internal"])
        comment_id = data["id"]

        # GET via API
        get_resp = api_client.get(url, HTTP_HOST="localhost")
        self.assertEqual(get_resp.status_code, 200)
        comments_list = get_resp.json()
        self.assertTrue(any(c["id"] == comment_id for c in comments_list))

        # DELETE via API
        del_url = f"/api/v1/service-requests/{self.sr.pk}/comments/{comment_id}/"
        del_resp = api_client.delete(del_url, HTTP_HOST="localhost")
        self.assertEqual(del_resp.status_code, 204)
        self.assertFalse(ServiceRequestComment.objects.filter(pk=comment_id).exists())
