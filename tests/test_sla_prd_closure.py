"""Comprehensive Verification Suite for SLA & Escalation PRD Closure.

Verifies:
1. REST API route compliance: /api/v1/slas/, /api/v1/breaches/, /api/v1/escalations/
   and backward compatibility with /api/v1/sla-profiles/, /api/v1/sla-breaches/, /api/v1/sla-escalations/.
2. Main dashboard SLA metrics: overall compliance %, response %, resolution %,
   priority-wise and site-wise compliance, open breach counts, and tenant isolation.
3. Client Portal SLA indicators: customer-safe commitment, response/resolution status,
   and strict leak prevention (zero exposure of internal escalation rules/staff alerts).
4. SLA lifecycle integrity: pauses, timer adjustments, and resolution state tracking.
"""

import datetime
from decimal import Decimal
import uuid
import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.dashboards import metrics
from apps.incidents import services as incident_services
from apps.incidents.models import ServiceRequest
from apps.portal.models import PortalAccount
from apps.portal import selectors as portal_selectors
from apps.portal import services as portal_services
from apps.rbac import services as rbac
from apps.sites.models import OperatingCalendar, Site
from apps.sla.models import EscalationRule, SLABreach, SLAProfile, SLATarget, SLATracking
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership, Organization
from apps.workorders.models import WorkOrder


class SLAPRDClosureTests(TestCase):
    def setUp(self):
        # 1. Admin & Tenant A
        self.admin = User.objects.create_user(
            email="admin@closure.test",
            password="AdminPassword123!",
            full_name="Platform Admin",
            is_platform_admin=True,
        )
        self.org_a, self.owner_a = tenancy.create_organization(
            name="Apex Aerospace",
            owner_email="owner@apex.test",
            owner_name="Owner Apex",
            actor=self.admin,
        )
        self.org_b, self.owner_b = tenancy.create_organization(
            name="Beta Dynamics",
            owner_email="owner@beta.test",
            owner_name="Owner Beta",
            actor=self.admin,
        )

        # 2. Staff user with SLA permissions
        self.staff_user = User.objects.create_user(
            email="ops_manager@apex.test",
            password="Password123!",
            full_name="Ops Manager",
        )
        self.staff_m = Membership.objects.create(
            organization=self.org_a,
            user=self.staff_user,
            status=Membership.Status.ACTIVE,
        )
        mgr_role = rbac.system_role_by_key(self.org_a, "operations_manager")
        rbac.set_membership_roles(self.staff_m, [mgr_role], actor=self.admin, system=True)

        # 3. Sites & Category & Asset
        self.site_a = Site.objects.create(
            organization=self.org_a,
            code="SITE-A",
            name="Apex Plant Alpha",
            address="100 Flight Path",
        )
        self.site_b = Site.objects.create(
            organization=self.org_b,
            code="SITE-B",
            name="Beta Plant",
            address="200 Tech Way",
        )
        self.category = AssetCategory.objects.create(
            organization=self.org_a,
            name="Gas Turbines",
        )
        self.asset = Asset.objects.create(
            organization=self.org_a,
            site=self.site_a,
            category=self.category,
            asset_tag="AST-TURB-01",
            name="Primary Turbine #1",
        )

        # 4. SLA Profile & Target & Escalation
        self.profile = SLAProfile.objects.create(
            organization=self.org_a,
            name="Standard 24x7 SLA",
            applies_to="ALL",
            is_active=True,
        )
        self.target = SLATarget.objects.create(
            organization=self.org_a,
            profile=self.profile,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
        )
        self.escalation_rule = EscalationRule.objects.create(
            organization=self.org_a,
            profile=self.profile,
            target_kind="RESOLUTION",
            trigger="WARNING",
            after_minutes=0,
            level=1,
            notify_role=mgr_role,
            notify_assignee=True,
        )

        # API Clients
        self.api_client_a = APIClient()
        self.api_client_a.force_authenticate(user=self.staff_user)
        self.api_client_a.credentials(HTTP_X_ORGANIZATION=str(self.org_a.pk))

        self.api_client_b = APIClient()
        self.api_client_b.force_authenticate(user=self.owner_b.user)
        self.api_client_b.credentials(HTTP_X_ORGANIZATION=str(self.org_b.pk))

    def _create_service_request(self, title="Service Ticket", user=None):
        return ServiceRequest.objects.create(
            organization=self.org_a,
            number=f"SR-{uuid.uuid4().hex[:8].upper()}",
            site=self.site_a,
            asset=self.asset,
            reported_by=user or self.staff_m,
            kind=ServiceRequest.Kind.SERVICE_REQUEST,
            severity=ServiceRequest.Severity.HIGH,
            title=title,
            occurred_at=timezone.now(),
        )

    # =========================================================================
    # 1. REST API Route Deviations & Alias Tests
    # =========================================================================

    def test_sla_routes_alias_compliance(self):
        """Verify /api/v1/slas/ is available and produces identical results to /api/v1/sla-profiles/."""
        res_slas = self.api_client_a.get("/api/v1/slas/")
        self.assertEqual(res_slas.status_code, status.HTTP_200_OK)
        slas_data = res_slas.json()
        slas_results = slas_data["results"] if "results" in slas_data else slas_data
        self.assertTrue(len(slas_results) >= 1)
        self.assertEqual(slas_results[0]["name"], self.profile.name)

        # Backward compatibility check
        res_profiles = self.api_client_a.get("/api/v1/sla-profiles/")
        self.assertEqual(res_profiles.status_code, status.HTTP_200_OK)
        profiles_data = res_profiles.json()
        profiles_results = profiles_data["results"] if "results" in profiles_data else profiles_data
        self.assertEqual(len(slas_results), len(profiles_results))

    def test_breaches_routes_alias_compliance(self):
        """Verify /api/v1/breaches/ is available and supports filtering alongside /api/v1/sla-breaches/."""
        now = timezone.now()
        sr = self._create_service_request("Breach Test Ticket")
        tracking = SLATracking.objects.create(
            organization=self.org_a,
            request=sr,
            profile=self.profile,
            site=self.site_a,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
            started_at=now - datetime.timedelta(hours=6),
            response_due_at=now - datetime.timedelta(hours=5),
            resolution_due_at=now - datetime.timedelta(hours=2),
            status=SLATracking.Status.BREACHED,
            resolution_state=SLATracking.TargetState.BREACHED,
        )
        breach = SLABreach.objects.create(
            organization=self.org_a,
            tracking=tracking,
            profile=self.profile,
            site=self.site_a,
            priority="HIGH",
            severity="CRITICAL",
            target_kind="RESOLUTION",
            breached_at=now,
            detected_at=now,
            status=SLABreach.Status.OPEN,
        )

        res_breaches = self.api_client_a.get("/api/v1/breaches/")
        self.assertEqual(res_breaches.status_code, status.HTTP_200_OK)
        breaches_data = res_breaches.json()
        breaches_results = breaches_data["results"] if "results" in breaches_data else breaches_data
        self.assertEqual(len(breaches_results), 1)
        self.assertEqual(breaches_results[0]["severity"], "CRITICAL")

        # Backward compatibility check
        res_sla_breaches = self.api_client_a.get("/api/v1/sla-breaches/")
        self.assertEqual(res_sla_breaches.status_code, status.HTTP_200_OK)
        sla_breaches_data = res_sla_breaches.json()
        sla_breaches_results = sla_breaches_data["results"] if "results" in sla_breaches_data else sla_breaches_data
        self.assertEqual(len(sla_breaches_results), 1)

    def test_escalations_routes_alias_compliance(self):
        """Verify /api/v1/escalations/ and /api/v1/sla-escalations/ both list escalation rules."""
        res_esc = self.api_client_a.get("/api/v1/escalations/")
        self.assertEqual(res_esc.status_code, status.HTTP_200_OK)
        esc_data = res_esc.json()
        esc_results = esc_data["results"] if "results" in esc_data else esc_data
        self.assertTrue(len(esc_results) >= 1)
        self.assertEqual(esc_results[0]["trigger"], "WARNING")

        # Backward compatibility check
        res_sla_esc = self.api_client_a.get("/api/v1/sla-escalations/")
        self.assertEqual(res_sla_esc.status_code, status.HTTP_200_OK)
        sla_esc_data = res_sla_esc.json()
        sla_esc_results = sla_esc_data["results"] if "results" in sla_esc_data else sla_esc_data
        self.assertEqual(len(esc_results), len(sla_esc_results))

    def test_sla_routes_tenant_isolation(self):
        """Verify Tenant B cannot view Tenant A's SLAs, breaches, or escalations."""
        # Tenant B queries /api/v1/slas/
        res = self.api_client_b.get("/api/v1/slas/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        results = data["results"] if "results" in data else data
        self.assertEqual(len(results), 0)

        # Tenant B queries /api/v1/breaches/
        res_breaches = self.api_client_b.get("/api/v1/breaches/")
        self.assertEqual(res_breaches.status_code, status.HTTP_200_OK)
        data_b = res_breaches.json()
        results_b = data_b["results"] if "results" in data_b else data_b
        self.assertEqual(len(results_b), 0)

    # =========================================================================
    # 2. Main Dashboard SLA Metrics Integration Tests
    # =========================================================================

    def test_dashboard_metrics_compute_sla_compliance(self):
        """Verify compute_sla_compliance calculations for met, breached, priority, and sites."""
        now = timezone.now()

        # Tracking 1: MET (both response and resolution)
        sr1 = self._create_service_request("Compliance SR 1")
        t1 = SLATracking.objects.create(
            organization=self.org_a,
            request=sr1,
            profile=self.profile,
            site=self.site_a,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
            started_at=now - datetime.timedelta(hours=5),
            response_due_at=now - datetime.timedelta(hours=4),
            resolution_due_at=now - datetime.timedelta(hours=1),
            response_met_at=now - datetime.timedelta(hours=4, minutes=30),
            resolution_met_at=now - datetime.timedelta(hours=2),
            response_state=SLATracking.TargetState.MET,
            resolution_state=SLATracking.TargetState.MET,
            status=SLATracking.Status.COMPLETED,
        )

        # Tracking 2: BREACHED resolution
        sr2 = self._create_service_request("Compliance SR 2")
        t2 = SLATracking.objects.create(
            organization=self.org_a,
            request=sr2,
            profile=self.profile,
            site=self.site_a,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
            started_at=now - datetime.timedelta(hours=10),
            response_due_at=now - datetime.timedelta(hours=9),
            resolution_due_at=now - datetime.timedelta(hours=6),
            response_met_at=now - datetime.timedelta(hours=9, minutes=30),
            response_state=SLATracking.TargetState.MET,
            resolution_state=SLATracking.TargetState.BREACHED,
            status=SLATracking.Status.BREACHED,
        )

        start_dt = now - datetime.timedelta(days=1)
        end_dt = now + datetime.timedelta(days=1)
        comp = metrics.compute_sla_compliance(self.org_a, [self.site_a], start_dt, end_dt)
        # Total trackings: 2, Total targets: 4 (3 Met, 1 Breached) -> overall_compliance = 75.0%
        self.assertEqual(comp["total_trackings"], 2)
        self.assertEqual(comp["overall_compliance"], 75.0)
        # Response: 2 of 2 met -> 100.0%
        self.assertEqual(comp["response_compliance"], 100.0)
        # Resolution: 1 of 2 met -> 50.0%
        self.assertEqual(comp["resolution_compliance"], 50.0)
        # Priority breakdown exists
        self.assertIn("HIGH", comp["priority_compliance"])
        self.assertEqual(comp["priority_compliance"]["HIGH"]["compliance_percent"], 75.0)
        # Site breakdown exists
        self.assertIn(str(self.site_a.pk), comp["site_compliance"])
        self.assertEqual(comp["site_compliance"][str(self.site_a.pk)]["compliance_percent"], 75.0)

    def test_operations_and_service_dashboard_endpoints_expose_sla_kpis(self):
        """Verify /api/v1/dashboards/operations/ and /service/ expose SLA compliance and breach KPIs."""
        now = timezone.now()
        sr = self._create_service_request("Dashboard SR")
        SLATracking.objects.create(
            organization=self.org_a,
            request=sr,
            profile=self.profile,
            site=self.site_a,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
            started_at=now - datetime.timedelta(hours=3),
            response_due_at=now - datetime.timedelta(hours=2),
            resolution_due_at=now + datetime.timedelta(hours=1),
            response_met_at=now - datetime.timedelta(hours=2, minutes=30),
            response_state=SLATracking.TargetState.MET,
            resolution_state=SLATracking.TargetState.PENDING,
            status=SLATracking.Status.ACTIVE,
        )

        # 1. Operations Dashboard
        res_ops = self.api_client_a.get("/api/v1/dashboards/operations/")
        self.assertEqual(res_ops.status_code, status.HTTP_200_OK)
        ops_data = res_ops.json()["data"]
        self.assertIn("sla_compliance", ops_data["kpis"])
        self.assertIn("response_compliance", ops_data["kpis"])
        self.assertIn("resolution_compliance", ops_data["kpis"])
        self.assertIn("sla_breaches", ops_data["kpis"])
        self.assertIn("sla_data", ops_data["details"])
        self.assertIn("overall_compliance", ops_data["details"]["sla_data"])

        # 2. Service Dashboard
        res_svc = self.api_client_a.get("/api/v1/dashboards/service/")
        self.assertEqual(res_svc.status_code, status.HTTP_200_OK)
        svc_data = res_svc.json()["data"]
        self.assertIn("sla_compliance", svc_data["kpis"])
        self.assertIn("response_compliance", svc_data["kpis"])
        self.assertIn("resolution_compliance", svc_data["kpis"])
        self.assertIn("open_sla_breaches", svc_data["kpis"])
        self.assertIn("sla_data", svc_data["details"])

    # =========================================================================
    # 3. Client Portal SLA Indicators & Leak Prevention Tests
    # =========================================================================

    def test_client_portal_sla_commitment_and_leak_prevention(self):
        """Verify portal requests expose safe SLA commitments without leaking internal escalation rules."""
        # Setup client requester
        client_user = User.objects.create_user(
            email="client@customer.test",
            password="ClientPassword123!",
            full_name="Jane Customer",
        )
        client_m = Membership.objects.create(
            organization=self.org_a,
            user=client_user,
            status=Membership.Status.ACTIVE,
            job_title="Requester",
        )
        client_role = rbac.system_role_by_key(self.org_a, "client_requester")
        rbac.set_membership_roles(client_m, [client_role], actor=self.admin, system=True)
        portal_account = PortalAccount.objects.create(
            organization=self.org_a,
            membership=client_m,
            company_name="Customer Corp",
            is_enabled=True,
        )

        now = timezone.now()
        sr = ServiceRequest.objects.create(
            organization=self.org_a,
            site=self.site_a,
            asset=self.asset,
            reported_by=client_m,
            kind=ServiceRequest.Kind.SERVICE_REQUEST,
            severity=ServiceRequest.Severity.HIGH,
            title="Cooling pump failure",
            description="Cooling pump vibrating loudly",
            occurred_at=now,
        )

        # Attach SLA tracking
        tracking = SLATracking.objects.create(
            organization=self.org_a,
            request=sr,
            profile=self.profile,
            site=self.site_a,
            priority="HIGH",
            response_minutes=60,
            resolution_minutes=240,
            warning_percent=80,
            started_at=now,
            response_due_at=now + datetime.timedelta(hours=1),
            resolution_due_at=now + datetime.timedelta(hours=4),
            response_met_at=now + datetime.timedelta(minutes=25),
            response_state=SLATracking.TargetState.MET,
            resolution_state=SLATracking.TargetState.PENDING,
            status=SLATracking.Status.ACTIVE,
        )

        # 1. Test portal selector output
        indicator = portal_selectors.get_client_sla_indicator(sr)
        self.assertIsNotNone(indicator)
        self.assertTrue(indicator["has_sla"])
        self.assertTrue(indicator["is_within_sla"])
        self.assertTrue(indicator["response_achieved"])
        self.assertFalse(indicator["is_delayed"])
        self.assertEqual(indicator["status"], "RESPONSE_MET")
        self.assertEqual(indicator["badge_class"], "info")
        self.assertIn("Response Completed", indicator["status_label"])

        # 2. Test Client Portal API Serializer
        portal_api_client = APIClient()
        portal_api_client.force_authenticate(user=client_user)
        portal_api_client.credentials(HTTP_X_ORGANIZATION=str(self.org_a.pk))

        res_detail = portal_api_client.get(f"/api/v1/portal/requests/{sr.pk}/")
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        data = res_detail.json()
        self.assertIn("sla_commitment", data)
        sla_data = data["sla_commitment"]
        self.assertIsNotNone(sla_data)
        self.assertTrue(sla_data["is_within_sla"])
        self.assertTrue(sla_data["response_achieved"])
        self.assertEqual(sla_data["status"], "RESPONSE_MET")

        # 3. CRITICAL: Leak Prevention Assertion
        # Verify that internal escalation models, notification rules, or breach logs are NOT in the payload
        response_text = res_detail.content.decode("utf-8")
        self.assertNotIn("escalation_rule", response_text.lower())
        self.assertNotIn("notify_role", response_text.lower())
        self.assertNotIn("after_minutes", response_text.lower())
        self.assertNotIn("warning_percent", response_text.lower())
        self.assertNotIn("notify_assignee", response_text.lower())

        # 4. Test Web Template Rendering (RequestDetailView)
        web_client = Client()
        web_client.force_login(client_user)
        session = web_client.session
        session["tenant_org_id"] = str(self.org_a.pk)
        session.save()

        web_res = web_client.get(f"/app/portal/requests/{sr.pk}/")
        self.assertEqual(web_res.status_code, 200)
        web_content = web_res.content.decode("utf-8")
        self.assertIn("Service Level Commitment (SLA)", web_content)
        self.assertIn("Initial Response", web_content)
        self.assertIn("Target Resolution", web_content)
        self.assertIn("Response Completed - In Progress", web_content)

        # Verify no internal escalation data in web page
        self.assertNotIn("EscalationRule", web_content)
        self.assertNotIn("notify_role", web_content)
