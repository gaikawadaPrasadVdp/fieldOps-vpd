from datetime import time, timedelta, timezone as dt_timezone, datetime
from decimal import Decimal
from django.test import TestCase, Client
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets.models import Asset, AssetCategory
from apps.core.exceptions import ValidationFailed
from apps.rbac.models import Role, MembershipRole
from apps.rbac import services as rbac
from apps.sites.models import Site
from apps.tenancy import services as tenancy
from apps.tenancy.models import Membership, Organization
from apps.workorders.models import WorkOrder
from apps.workorders import services as wo_services
from apps.workspace.models import Shift, TechnicianProfile
from apps.workspace import selectors, services as ws_services


class TechnicianProfileAndShiftTests(TestCase):
    def setUp(self):
        # Admin & Organization
        self.admin = User.objects.create_user(
            email="admin@techshift.test",
            password="TestPassword123!",
            full_name="Admin TechShift",
            is_platform_admin=True,
        )
        self.org, self.owner_m = tenancy.create_organization(
            name="Alpha Maintenance Org",
            owner_email="owner@techshift.test",
            owner_name="Owner User",
            actor=self.admin,
        )
        self.owner_m.status = Membership.Status.ACTIVE
        self.owner_m.save(update_fields=["status"])
        self.site = Site.objects.create(
            organization=self.org,
            code="SITE-01",
            name="Main Plant",
            timezone="UTC",
        )
        self.category = AssetCategory.objects.create(
            organization=self.org,
            name="Generators",
        )
        self.asset = Asset.objects.create(
            organization=self.org,
            site=self.site,
            category=self.category,
            asset_tag="GEN-01",
            name="Backup Generator A",
        )

        # Create Technician user & membership
        self.tech_user = User.objects.create_user(
            email="tech1@techshift.test",
            password="TestPassword123!",
            full_name="Bob Technician",
        )
        self.tech_m = Membership.objects.create(
            organization=self.org,
            user=self.tech_user,
            status=Membership.Status.ACTIVE,
        )
        tech_role = rbac.system_role_by_key(self.org, "technician")
        rbac.set_membership_roles(self.tech_m, [tech_role], actor=None, system=True)

        # Create Planner
        self.planner_user = User.objects.create_user(
            email="planner@techshift.test",
            password="TestPassword123!",
            full_name="Alice Planner",
        )
        self.planner_m = Membership.objects.create(
            organization=self.org,
            user=self.planner_user,
            status=Membership.Status.ACTIVE,
        )
        planner_role = rbac.system_role_by_key(self.org, "maintenance_planner")
        rbac.set_membership_roles(self.planner_m, [planner_role], actor=None, system=True)

    def test_shift_creation_and_duration_property(self):
        """Test regular shift and overnight shift duration calculation."""
        # Regular daytime shift: 08:00 to 16:30 (8.5 hrs)
        day_shift = ws_services.create_shift(
            self.org,
            code="DAY-01",
            name="Day Shift",
            start_time=time(8, 0),
            end_time=time(16, 30),
            days_of_week=[0, 1, 2, 3, 4],
            site=self.site,
            actor=self.admin,
        )
        self.assertEqual(day_shift.duration_hours, Decimal("8.50"))
        self.assertTrue(day_shift.is_active)

        # Overnight shift: 22:00 to 06:00 (8.0 hrs)
        night_shift = ws_services.create_shift(
            self.org,
            code="NIGHT-01",
            name="Night Shift",
            start_time=time(22, 0),
            end_time=time(6, 0),
            days_of_week=[0, 1, 2, 3, 4],
            site=self.site,
            actor=self.admin,
        )
        self.assertEqual(night_shift.duration_hours, Decimal("8.00"))

    def test_shift_duplicate_code_prevented(self):
        """Duplicate shift code within the same org should raise ValidationFailed."""
        ws_services.create_shift(
            self.org,
            code="UNIQUE-CODE",
            name="Original Shift",
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        with self.assertRaises(ValidationFailed):
            ws_services.create_shift(
                self.org,
                code="UNIQUE-CODE",
                name="Duplicate Code Shift",
                start_time=time(9, 0),
                end_time=time(17, 0),
            )

    def test_technician_profile_get_or_create_and_update(self):
        """Profile creation, skills, certifications, and availability status."""
        profile, created = ws_services.get_or_create_technician_profile(
            self.tech_m,
            actor=self.admin,
        )
        self.assertTrue(created)
        self.assertEqual(profile.availability_status, TechnicianProfile.AvailabilityStatus.AVAILABLE)

        # Update profile
        shift = ws_services.create_shift(
            self.org,
            code="MORNING",
            name="Morning Shift",
            start_time=time(7, 0),
            end_time=time(15, 30),
        )
        ws_services.update_technician_profile(
            profile,
            shift=shift,
            primary_site=self.site,
            skills=["Electrical", "Hydraulics"],
            certifications=["OSHA 30"],
            hourly_rate=Decimal("45.00"),
            max_active_jobs=2,
            actor=self.admin,
        )

        profile.refresh_from_db()
        self.assertEqual(profile.shift, shift)
        self.assertEqual(profile.primary_site, self.site)
        self.assertIn("Electrical", profile.skills)
        self.assertEqual(profile.hourly_rate, Decimal("45.00"))
        self.assertEqual(profile.max_active_jobs, 2)

    def test_technician_shift_eligibility(self):
        """Check whether technician is on shift based on days and hours."""
        shift = ws_services.create_shift(
            self.org,
            code="WEEKDAY-MORN",
            name="Weekday Morning",
            start_time=time(8, 0),
            end_time=time(16, 0),
            days_of_week=[0, 1, 2, 3, 4],  # Mon-Fri
        )
        profile, _ = ws_services.get_or_create_technician_profile(self.tech_m)
        ws_services.update_technician_profile(profile, shift=shift)

        # Monday 10:00 UTC -> On shift
        mon_dt = datetime(2026, 11, 2, 10, 0, tzinfo=dt_timezone.utc)
        eligible, msg = ws_services.check_technician_shift_eligibility(self.tech_m, mon_dt)
        self.assertTrue(eligible)

        # Monday 18:00 UTC -> Outside hours
        mon_late = datetime(2026, 11, 2, 18, 0, tzinfo=dt_timezone.utc)
        eligible, msg = ws_services.check_technician_shift_eligibility(self.tech_m, mon_late)
        self.assertFalse(eligible)
        self.assertIn("outside technician shift", msg)

        # Saturday 10:00 UTC -> Off day
        sat_dt = datetime(2026, 11, 7, 10, 0, tzinfo=dt_timezone.utc)
        eligible, msg = ws_services.check_technician_shift_eligibility(self.tech_m, sat_dt)
        self.assertFalse(eligible)
        self.assertIn("not scheduled on Sat", msg)

    def test_work_order_assignment_rejected_when_technician_on_leave(self):
        """Technician with availability_status ON_LEAVE cannot be assigned."""
        profile, _ = ws_services.get_or_create_technician_profile(self.tech_m)
        ws_services.set_technician_availability(
            self.tech_m,
            TechnicianProfile.AvailabilityStatus.ON_LEAVE,
            actor=self.admin,
        )

        t_start = timezone.now() + timedelta(hours=1)
        t_end = t_start + timedelta(hours=2)
        wo = wo_services.create_work_order(
            self.org,
            site_id=self.site.pk,
            asset=self.asset,
            actor=self.planner_user,
            title="Inspect Generator",
            work_type="CORRECTIVE",
            priority=WorkOrder.Priority.MEDIUM,
            membership=self.planner_m,
        )
        wo = wo_services.plan_work_order(
            wo,
            membership=self.planner_m,
            actor=self.planner_user,
            planned_start=t_start,
            planned_end=t_end,
            estimated_hours=Decimal("2.00"),
            due_at=t_start + timedelta(days=2),
        )

        with self.assertRaises(ValidationFailed) as cm:
            wo_services.assign_work_order(
                wo,
                membership=self.planner_m,
                actor=self.planner_user,
                assignee_id=self.tech_m.pk,
                scheduled_start=t_start,
                scheduled_end=t_end,
            )
        self.assertIn("on leave", str(cm.exception).lower())

    def test_work_order_assignment_rejected_when_max_jobs_exceeded(self):
        """Technician cannot exceed max_active_jobs limit."""
        profile, _ = ws_services.get_or_create_technician_profile(self.tech_m)
        profile.max_active_jobs = 1
        profile.save()

        # Create job 1 and assign
        now = timezone.now()
        t1_start = now + timedelta(hours=1)
        t1_end = now + timedelta(hours=2)
        wo1 = wo_services.create_work_order(
            self.org,
            site_id=self.site.pk,
            asset=self.asset,
            actor=self.planner_user,
            title="Active Job 1",
            work_type="CORRECTIVE",
            priority=WorkOrder.Priority.MEDIUM,
            membership=self.planner_m,
        )
        wo1 = wo_services.plan_work_order(
            wo1,
            membership=self.planner_m,
            actor=self.planner_user,
            planned_start=t1_start,
            planned_end=t1_end,
            estimated_hours=Decimal("1.00"),
            due_at=t1_start + timedelta(days=2),
        )
        wo_services.assign_work_order(
            wo1,
            membership=self.planner_m,
            actor=self.planner_user,
            assignee_id=self.tech_m.pk,
            scheduled_start=t1_start,
            scheduled_end=t1_end,
        )

        # Create job 2 with non-overlapping window
        t2_start = now + timedelta(hours=4)
        t2_end = now + timedelta(hours=5)
        wo2 = wo_services.create_work_order(
            self.org,
            site_id=self.site.pk,
            asset=self.asset,
            actor=self.planner_user,
            title="Active Job 2",
            work_type="CORRECTIVE",
            priority=WorkOrder.Priority.MEDIUM,
            membership=self.planner_m,
        )
        wo2 = wo_services.plan_work_order(
            wo2,
            membership=self.planner_m,
            actor=self.planner_user,
            planned_start=t2_start,
            planned_end=t2_end,
            estimated_hours=Decimal("1.00"),
            due_at=t2_start + timedelta(days=2),
        )
        with self.assertRaises(ValidationFailed) as cm:
            wo_services.assign_work_order(
                wo2,
                membership=self.planner_m,
                actor=self.planner_user,
                assignee_id=self.tech_m.pk,
                scheduled_start=t2_start,
                scheduled_end=t2_end,
            )
        self.assertIn("maximum active jobs limit", str(cm.exception).lower())

    def test_api_shifts_and_technicians_endpoints(self):
        """REST API endpoints for listing shifts and updating technician availability."""
        client = APIClient()
        client.force_authenticate(user=self.owner_m.user)
        client.credentials(HTTP_X_ORGANIZATION=str(self.org.slug))

        # GET shifts list
        res = client.get("/api/v1/workspace/shifts/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # POST new shift
        payload = {
            "code": "API-SHIFT-01",
            "name": "API Standard Shift",
            "start_time": "08:30:00",
            "end_time": "17:00:00",
            "days_of_week": [0, 1, 2, 3, 4],
            "is_active": True,
        }
        res = client.post("/api/v1/workspace/shifts/", data=payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["code"], "API-SHIFT-01")

        # GET technicians list
        res = client.get("/api/v1/workspace/technicians/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(len(res.data) >= 1)

        # Toggle availability via API
        avail_payload = {"availability_status": "OFF_DUTY"}
        res = client.post(
            f"/api/v1/workspace/technicians/{self.tech_m.pk}/availability/",
            data=avail_payload,
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["availability_status"], "OFF_DUTY")

    def test_ui_shifts_and_technicians_views(self):
        """Verify UI screens for shifts and technician profiles render 200 with HTML context."""
        client = Client(headers={"host": "localhost"})
        client.force_login(self.owner_m.user)
        session = client.session
        session["active_org_id"] = str(self.org.pk)
        session.save()

        # 1. Shifts list
        res = client.get("/app/workspace/shifts/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Technician Shifts", res.content.decode("utf-8"))

        # 2. Shift create GET and POST
        res = client.get("/app/workspace/shifts/new/")
        self.assertEqual(res.status_code, 200)

        shift_post_data = {
            "code": "UI-SHIFT-1",
            "name": "Morning UI Shift",
            "start_time": "08:00",
            "end_time": "16:30",
            "days": ["0", "1", "2", "3", "4"],
            "is_active": "on",
            "notes": "Created via UI test",
        }
        res = client.post("/app/workspace/shifts/new/", data=shift_post_data)
        self.assertEqual(res.status_code, 302)
        created_shift = Shift.objects.filter(organization=self.org, code="UI-SHIFT-1").first()
        self.assertIsNotNone(created_shift)

        # 3. Shift edit
        res = client.get(f"/app/workspace/shifts/{created_shift.pk}/")
        self.assertEqual(res.status_code, 200)

        # 4. Technician list
        res = client.get("/app/workspace/technicians/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Technician Directory & Availability", res.content.decode("utf-8"))

        # 5. Technician detail & edit
        res = client.get(f"/app/workspace/technicians/{self.tech_m.pk}/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Technician Profile", res.content.decode("utf-8"))

        # 6. Technician self-service profile (login as tech)
        tech_client = Client(headers={"host": "localhost"})
        tech_client.force_login(self.tech_m.user)
        t_session = tech_client.session
        t_session["active_org_id"] = str(self.org.pk)
        t_session.save()

        res = tech_client.get("/app/workspace/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("My Shift & Availability", res.content.decode("utf-8"))

        # Toggle own availability
        res = tech_client.post("/app/workspace/profile/", data={"availability_status": "OFF_DUTY"})
        self.assertEqual(res.status_code, 302)
        profile = TechnicianProfile.objects.get(membership=self.tech_m)
        self.assertEqual(profile.availability_status, TechnicianProfile.AvailabilityStatus.OFF_DUTY)
