"""Automated Regression and Schedule Validation Tests for Celery Beat Tasks (D3).

Verifies that:
1. All tasks in CELERY_BEAT_SCHEDULE are valid, imported, and registered in Celery's task registry.
2. fan_out_sla_monitor executes end-to-end under CELERY_TASK_ALWAYS_EAGER.
3. An overdue SLA tracking correctly creates an SLABreach record.
4. Multiple executions of fan_out_sla_monitor are completely idempotent (no duplicate breaches).
5. Renewal alerts and inventory reorder alerts execute cleanly under Celery eager mode.
"""
import datetime
from django.conf import settings
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.contracts.tasks import fan_out_renewal_alerts
from apps.inventory.tasks import fan_out_reorder_alerts
from apps.sites.models import Site
from apps.sla.models import SLABreach, SLAProfile, SLATarget, SLATracking
from apps.sla.tasks import fan_out_sla_monitor
from apps.tenancy import services as tenancy
from apps.workorders.models import WorkOrder
from config.celery import app


class CeleryBeatScheduleRegistrationTests(TestCase):
    def test_all_beat_schedule_tasks_are_registered_in_celery(self):
        """Every task configured in CELERY_BEAT_SCHEDULE must exist in app.tasks."""
        app.loader.import_default_modules()
        registered_tasks = set(app.tasks.keys())

        beat_schedule = getattr(settings, "CELERY_BEAT_SCHEDULE", {})
        self.assertTrue(len(beat_schedule) > 0, "CELERY_BEAT_SCHEDULE must not be empty.")

        fan_out_tasks = []
        for name, entry in beat_schedule.items():
            task_name = entry.get("task")
            self.assertIsNotNone(task_name, f"Entry '{name}' in CELERY_BEAT_SCHEDULE is missing 'task'.")
            self.assertIn(
                task_name,
                registered_tasks,
                f"Task '{task_name}' in CELERY_BEAT_SCHEDULE (entry '{name}') is not registered in Celery tasks!",
            )
            if "fan_out" in task_name:
                fan_out_tasks.append(task_name)

        # Explicitly verify the required fan-out tasks are part of the schedule
        expected_fan_outs = {
            "apps.sla.tasks.fan_out_sla_monitor",
            "apps.contracts.tasks.fan_out_renewal_alerts",
            "apps.inventory.tasks.fan_out_reorder_alerts",
            "apps.maintenance.tasks.fan_out_maintenance",
        }
        for expected in expected_fan_outs:
            self.assertIn(expected, fan_out_tasks, f"Expected '{expected}' to be in CELERY_BEAT_SCHEDULE.")


class FanOutSLAMonitorTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin.celery@nexus.test",
            password="TestPassword123!",
            full_name="Celery Test Admin",
            is_platform_admin=True,
        )
        self.org, self.owner = tenancy.create_organization(
            name="Apex Dynamics",
            owner_email="owner@apexdynamics.test",
            owner_name="Owner Apex",
            actor=self.admin,
        )
        self.site = Site.objects.create(
            organization=self.org,
            name="Apex Manufacturing Plant",
            code="AMP-01",
            status=Site.Status.ACTIVE,
        )
        self.profile = SLAProfile.objects.create(
            organization=self.org,
            name="Default Work Order SLA",
            applies_to="WORK_ORDER",
            is_active=True,
        )
        self.target = SLATarget.objects.create(
            organization=self.org,
            profile=self.profile,
            priority="HIGH",
            response_minutes=30,
            resolution_minutes=120,
        )
        self.work_order = WorkOrder.objects.create(
            organization=self.org,
            site=self.site,
            order_number="WO-SLA-TEST-001",
            title="Cooling Tower Bearing Replacement",
            work_type="CORRECTIVE",
            status="ASSIGNED",
        )

    def test_overdue_tracking_produces_breach_and_is_idempotent(self):
        """Verifies fan_out_sla_monitor detects an overdue tracking, creates breach, and avoids duplicates."""
        now = timezone.now()
        started_at = now - datetime.timedelta(hours=4)
        response_due = now - datetime.timedelta(hours=2)
        resolution_due = now + datetime.timedelta(hours=1)

        tracking = SLATracking.objects.create(
            organization=self.org,
            profile=self.profile,
            work_order=self.work_order,
            site=self.site,
            priority="HIGH",
            response_minutes=30,
            resolution_minutes=120,
            warning_percent=80,
            started_at=started_at,
            response_due_at=response_due,
            resolution_due_at=resolution_due,
            status=SLATracking.Status.ACTIVE,
            response_state=SLATracking.TargetState.PENDING,
            resolution_state=SLATracking.TargetState.PENDING,
        )

        self.assertEqual(SLABreach.objects.filter(tracking=tracking).count(), 0)

        # 1. First execution of fan_out_sla_monitor
        res1 = fan_out_sla_monitor()
        self.assertGreaterEqual(res1["dispatched"], 1)

        # Assert breach was created and recorded
        breaches = SLABreach.objects.filter(tracking=tracking)
        self.assertEqual(breaches.count(), 1, "Exactly one breach should have been created for overdue response.")
        breach = breaches.first()
        self.assertEqual(breach.target_kind, "RESPONSE")
        self.assertEqual(breach.status, SLABreach.Status.OPEN)

        # Reload tracking and check state
        tracking.refresh_from_db()
        self.assertEqual(tracking.status, SLATracking.Status.BREACHED)
        self.assertEqual(tracking.response_state, SLATracking.TargetState.BREACHED)

        # 2. Second execution must be idempotent (no duplicate breaches or events)
        res2 = fan_out_sla_monitor()
        self.assertGreaterEqual(res2["dispatched"], 1)

        self.assertEqual(
            SLABreach.objects.filter(tracking=tracking).count(),
            1,
            "Re-running fan_out_sla_monitor must not create duplicate breaches.",
        )

    def test_other_fan_out_tasks_execute_cleanly(self):
        """Verifies renewal alerts and inventory reorder alerts run with CELERY_TASK_ALWAYS_EAGER."""
        renewal_res = fan_out_renewal_alerts()
        self.assertIn("dispatched", renewal_res)
        self.assertGreaterEqual(renewal_res["dispatched"], 1)

        reorder_res = fan_out_reorder_alerts()
        self.assertIn("dispatched", reorder_res)
        self.assertGreaterEqual(reorder_res["dispatched"], 1)
