import re
from pathlib import Path

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.rbac.models import MembershipRole
from apps.rbac.services import seed_system_roles
from apps.sla.models import SLAProfile
from apps.tenancy.models import Membership, Organization


class SlaProfileFormTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(
            name="Apex Industrial",
            slug="apex-industrial"
        )
        self.roles = seed_system_roles(self.org)
        self.user = User.objects.create_user(
            email="admin@apexindustrial.com",
            password="Password123!",
            full_name="Apex Admin"
        )
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.user,
            status=Membership.Status.ACTIVE
        )
        # Assign owner role to membership
        MembershipRole.objects.create(
            membership=self.membership,
            role=self.roles["owner"]
        )
        self.client = Client()
        self.client.force_login(self.user)
        # Set active organization in session
        session = self.client.session
        session["tenant_org_id"] = str(self.org.pk)
        session.save()

    def test_new_sla_profile_form_rendering_and_business_terms(self):
        """Verify GET /app/sla/profiles/new/ renders with official business terms and zero module codes."""
        response = self.client.get("/app/sla/profiles/new/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Official business terms
        self.assertIn("New SLA Profile", content)
        self.assertIn("Incident / Breakdown", content)
        self.assertIn("Work Order", content)
        self.assertIn("Pause the timers", content)

        # Zero internal module numbers in visible text (e.g. M05, M06, M10, M11, M14)
        visible_text = re.sub(r"<svg[\s\S]*?</svg>", "", content)
        module_number_matches = re.findall(r"\bM\d\d\b", visible_text)
        self.assertEqual(module_number_matches, [], f"Found internal module numbers in UI: {module_number_matches}")

    def test_create_required_example_sla_profile_exact(self):
        """The form must support this exact example:
        Profile name: Critical Breakdown SLA
        Applies to: Incident / Breakdown
        Priority: Critical
        Response target: 15 minutes
        Resolution target: 4 hours
        Warning alert: 75%
        """
        payload = {
            "name": "Critical Breakdown SLA",
            "applies_to": "Incident / Breakdown",
            "priority": "Critical",
            "response_target": "15 minutes",
            "resolution_target": "4 hours",
            "warning_alert": "75%",
            "is_active": "on",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload, follow=True)
        if response.status_code != 200:
            form = response.context.get("form")
            form_errors = form.errors if form else "no form"
            t_formset = response.context.get("target_formset")
            t_errors = t_formset.errors if t_formset else "no t_formset"
            self.fail(f"Form submission failed: form={form_errors}, targets={t_errors}")
        self.assertEqual(response.status_code, 200)

        # Verify DB persistence
        profile = SLAProfile.objects.for_organization(self.org).filter(name="Critical Breakdown SLA").first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.applies_to, "REQUEST")
        self.assertTrue(profile.is_active)

        targets = list(profile.targets.all())
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual(target.priority, "CRITICAL")
        self.assertEqual(target.response_minutes, 15)
        self.assertEqual(target.resolution_minutes, 240)  # 4 hours = 240 minutes
        self.assertEqual(target.warning_percent, 75)

        # Verify profile detail page rendering
        detail_resp = self.client.get(f"/app/sla/profiles/{profile.pk}/")
        self.assertEqual(detail_resp.status_code, 200)
        detail_content = detail_resp.content.decode("utf-8")
        self.assertIn("Critical Breakdown SLA", detail_content)
        self.assertIn("Incident / Breakdown", detail_content)
        self.assertIn("CRITICAL", detail_content)
        self.assertIn("15 min", detail_content)
        self.assertIn("240 min", detail_content)
        self.assertIn("75%", detail_content)
        self.assertIn("Response Target", detail_content)
        self.assertIn("Resolution Target", detail_content)
        self.assertIn("Warning Alert", detail_content)

        # Zero internal module numbers in visible detail page
        visible_detail = re.sub(r"<svg[\s\S]*?</svg>", "", detail_content)
        module_matches = re.findall(r"\bM\d\d\b", visible_detail)
        self.assertEqual(module_matches, [], f"Found module numbers: {module_matches}")

    def test_create_via_formset_with_blank_rows_ignored(self):
        """Formset submission where only Critical row is filled and other rows left blank."""
        payload = {
            "name": "Mixed Formset SLA",
            "applies_to": "REQUEST",
            "targets-TOTAL_FORMS": "4",
            "targets-INITIAL_FORMS": "0",
            "targets-MIN_NUM_FORMS": "0",
            "targets-MAX_NUM_FORMS": "4",
            # Row 0: Critical filled
            "targets-0-priority": "CRITICAL",
            "targets-0-response_minutes": "15 minutes",
            "targets-0-resolution_minutes": "4 hours",
            "targets-0-warning_percent": "75%",
            # Rows 1-3: Blank
            "targets-1-priority": "",
            "targets-1-response_minutes": "",
            "targets-1-resolution_minutes": "",
            "targets-1-warning_percent": "80",
            "targets-2-priority": "",
            "targets-2-response_minutes": "",
            "targets-2-resolution_minutes": "",
            "targets-2-warning_percent": "80",
            "targets-3-priority": "",
            "targets-3-response_minutes": "",
            "targets-3-resolution_minutes": "",
            "targets-3-warning_percent": "80",
            "rules-TOTAL_FORMS": "0",
            "rules-INITIAL_FORMS": "0",
            "rules-MIN_NUM_FORMS": "0",
            "rules-MAX_NUM_FORMS": "6",
            "is_active": "on",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        profile = SLAProfile.objects.for_organization(self.org).filter(name="Mixed Formset SLA").first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.targets.count(), 1)
        target = profile.targets.first()
        self.assertEqual(target.priority, "CRITICAL")
        self.assertEqual(target.response_minutes, 15)
        self.assertEqual(target.resolution_minutes, 240)
        self.assertEqual(target.warning_percent, 75)

    def test_create_work_order_sla_profile(self):
        """Test creating an SLA Profile for Work Orders."""
        payload = {
            "name": "Emergency Work Order SLA",
            "applies_to": "Work Order",
            "priority": "Urgent",
            "response_target": "30 minutes",
            "resolution_target": "2 hours",
            "warning_alert": "80%",
            "is_active": "on",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        profile = SLAProfile.objects.for_organization(self.org).filter(name="Emergency Work Order SLA").first()
        self.assertIsNotNone(profile)
        self.assertEqual(profile.applies_to, "WORK_ORDER")
        target = profile.targets.first()
        self.assertEqual(target.priority, "URGENT")
        self.assertEqual(target.response_minutes, 30)
        self.assertEqual(target.resolution_minutes, 120)
        self.assertEqual(target.warning_percent, 80)

    def test_validation_resolution_less_than_response(self):
        """Resolution Target cannot be less than Response Target."""
        payload = {
            "name": "Invalid Timing SLA",
            "applies_to": "Incident / Breakdown",
            "priority": "Critical",
            "response_target": "4 hours",
            "resolution_target": "15 minutes",
            "warning_alert": "75%",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SLAProfile.objects.for_organization(self.org).filter(name="Invalid Timing SLA").exists())

    def test_validation_at_least_one_target_required(self):
        """SLA Profile must have at least one priority target."""
        payload = {
            "name": "No Targets SLA",
            "applies_to": "Incident / Breakdown",
            "targets-TOTAL_FORMS": "0",
            "targets-INITIAL_FORMS": "0",
            "targets-MIN_NUM_FORMS": "0",
            "targets-MAX_NUM_FORMS": "4",
            "rules-TOTAL_FORMS": "0",
            "rules-INITIAL_FORMS": "0",
            "rules-MIN_NUM_FORMS": "0",
            "rules-MAX_NUM_FORMS": "6",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)

    def test_target_set_on_detail_page_with_durations(self):
        """Setting a target on the profile detail page accepts duration and percentage strings."""
        profile = SLAProfile.objects.create(
            organization=self.org,
            name="Detail Target SLA",
            applies_to="REQUEST",
            is_active=True
        )
        payload = {
            "priority": "HIGH",
            "response_minutes": "45 minutes",
            "resolution_minutes": "6 hours",
            "warning_percent": "70%",
        }
        response = self.client.post(f"/app/sla/profiles/{profile.pk}/targets/", data=payload, follow=True)
        self.assertEqual(response.status_code, 200)

        target = profile.targets.filter(priority="HIGH").first()
        self.assertIsNotNone(target)
        self.assertEqual(target.response_minutes, 45)
        self.assertEqual(target.resolution_minutes, 360)
        self.assertEqual(target.warning_percent, 70)

    def test_no_module_numbers_in_any_sla_template(self):
        """Verify that zero user-facing SLA templates contain internal module numbers like M05, M06, M11."""
        templates_dir = Path(__file__).resolve().parent.parent.parent / "templates" / "sla"
        for template_file in templates_dir.glob("*.html"):
            content = template_file.read_text(encoding="utf-8")
            matches = re.findall(r"\bM\d\d\b", content)
            self.assertEqual(matches, [], f"Template {template_file.name} contains module numbers: {matches}")

    def test_applies_to_dropdown_options_unique(self):
        """Verify that the 'Applies to' dropdown renders exactly 2 unique options with no duplicate values or labels."""
        response = self.client.get("/app/sla/profiles/new/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Find the <select name="applies_to" ...> ... </select>
        match = re.search(r'<select[^>]*name=["\']applies_to["\'][^>]*>([\s\S]*?)</select>', content)
        self.assertIsNotNone(match, "Could not find applies_to select element")
        options = re.findall(r'<option[^>]*value=["\']([^"\']*)["\'][^>]*>([^<]*)</option>', match.group(1))

        # Check values and labels
        values = [val for val, text in options]
        labels = [text.strip() for val, text in options]
        self.assertEqual(len(values), len(set(values)), f"Duplicate applies_to values: {values}")
        self.assertEqual(len(labels), len(set(labels)), f"Duplicate applies_to labels: {labels}")
        self.assertEqual(len(values), 2)
        self.assertIn("REQUEST", values)
        self.assertIn("WORK_ORDER", values)

    def test_duplicate_priority_targets_rejected(self):
        """Submitting two rows with the same priority (e.g. Critical and Critical) raises a clear duplicate error."""
        payload = {
            "name": "Duplicate Priority SLA",
            "applies_to": "REQUEST",
            "targets-TOTAL_FORMS": "2",
            "targets-INITIAL_FORMS": "0",
            "targets-MIN_NUM_FORMS": "0",
            "targets-MAX_NUM_FORMS": "4",
            "targets-0-priority": "CRITICAL",
            "targets-0-response_minutes": "15 minutes",
            "targets-0-resolution_minutes": "4 hours",
            "targets-0-warning_percent": "75%",
            "targets-1-priority": "CRITICAL",
            "targets-1-response_minutes": "30 minutes",
            "targets-1-resolution_minutes": "8 hours",
            "targets-1-warning_percent": "80%",
            "action": "activate",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)
        target_formset = response.context.get("target_formset")
        self.assertTrue(target_formset.non_form_errors())
        error_msg = str(target_formset.non_form_errors()[0])
        self.assertIn("Duplicate priority target detected", error_msg)
        self.assertIn("Critical", error_msg)

    def test_duplicate_escalation_rules_rejected(self):
        """Submitting two rows with the same escalation rule step raises a clear duplicate error."""
        sup_role = self.roles.get("supervisor") or self.roles.get("operations_manager")
        payload = {
            "name": "Duplicate Rule SLA",
            "applies_to": "REQUEST",
            "targets-TOTAL_FORMS": "1",
            "targets-INITIAL_FORMS": "0",
            "targets-MIN_NUM_FORMS": "0",
            "targets-MAX_NUM_FORMS": "4",
            "targets-0-priority": "CRITICAL",
            "targets-0-response_minutes": "15 minutes",
            "targets-0-resolution_minutes": "4 hours",
            "targets-0-warning_percent": "75%",
            "rules-TOTAL_FORMS": "2",
            "rules-INITIAL_FORMS": "0",
            "rules-MIN_NUM_FORMS": "0",
            "rules-MAX_NUM_FORMS": "6",
            "rules-0-target_kind": "RESOLUTION",
            "rules-0-trigger": "WARNING",
            "rules-0-level": "1",
            "rules-0-notify_role": str(sup_role.pk) if sup_role else "",
            "rules-0-notify_assignee": "on",
            "rules-1-target_kind": "RESOLUTION",
            "rules-1-trigger": "WARNING",
            "rules-1-level": "2",
            "rules-1-notify_role": str(sup_role.pk) if sup_role else "",
            "rules-1-notify_assignee": "on",
            "action": "activate",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)
        rule_formset = response.context.get("rule_formset")
        self.assertTrue(rule_formset.non_form_errors())
        error_msg = str(rule_formset.non_form_errors()[0])
        self.assertIn("Duplicate escalation rule detected", error_msg)

    def test_duplicate_scope_conflict_message(self):
        """Creating an active profile with duplicate scope raises clear message indicating existing profile."""
        SLAProfile.objects.create(
            organization=self.org,
            name="Existing Active SLA",
            applies_to="REQUEST",
            is_active=True
        )
        payload = {
            "name": "Another Active SLA",
            "applies_to": "REQUEST",
            "priority": "Critical",
            "response_target": "15 minutes",
            "resolution_target": "4 hours",
            "warning_alert": "75%",
            "action": "activate",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)
        content = response.content.decode("utf-8")
        self.assertIn("Existing Active SLA", content)
        self.assertIn("already covers", content)

    def test_duplicate_name_rejected_with_clear_error(self):
        """Creating a profile with an identical name raises a clear validation error."""
        SLAProfile.objects.create(
            organization=self.org,
            name="Alpha Unique SLA",
            applies_to="REQUEST",
            is_active=False
        )
        payload = {
            "name": "Alpha Unique SLA",
            "applies_to": "WORK_ORDER",
            "priority": "Urgent",
            "response_target": "15 minutes",
            "resolution_target": "4 hours",
            "warning_alert": "80%",
            "is_active": "on",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)
        content = response.content.decode("utf-8")
        self.assertIn("already exists", content)

    def test_save_as_draft_without_targets(self):
        """Saving with action='draft' creates an inactive draft even when no targets are specified."""
        payload = {
            "name": "Draft Incomplete SLA",
            "applies_to": "REQUEST",
            "action": "draft",
            "targets-TOTAL_FORMS": "0",
            "targets-INITIAL_FORMS": "0",
            "targets-MIN_NUM_FORMS": "0",
            "targets-MAX_NUM_FORMS": "4",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload, follow=True)
        self.assertEqual(response.status_code, 200)
        profile = SLAProfile.objects.for_organization(self.org).filter(name="Draft Incomplete SLA").first()
        self.assertIsNotNone(profile)
        self.assertFalse(profile.is_active)
        self.assertEqual(profile.targets.count(), 0)

    def test_activate_without_targets_rejected(self):
        """Activating an incomplete profile without priority targets is rejected with a clear error."""
        payload = {
            "name": "Active Incomplete SLA",
            "applies_to": "REQUEST",
            "action": "activate",
            "targets-TOTAL_FORMS": "0",
            "targets-INITIAL_FORMS": "0",
            "targets-MIN_NUM_FORMS": "0",
            "targets-MAX_NUM_FORMS": "4",
        }
        response = self.client.post("/app/sla/profiles/new/", data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertFalse(SLAProfile.objects.for_organization(self.org).filter(name="Active Incomplete SLA").exists())

    def test_run_check_now_standard_post_renders_report(self):
        """POST /app/sla/process/ redirects to /app/sla/trackings/ without hash anchor and displays execution report."""
        response = self.client.post("/app/sla/process/", follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/app/sla/trackings/")

        # Follow redirect to trackings list
        redirect_resp = self.client.get(response.url)
        self.assertEqual(redirect_resp.status_code, 200)
        content = redirect_resp.content.decode("utf-8")
        self.assertIn("SLA Check completed", content)
        self.assertIn("running SLA timer", content)
        self.assertIn("warning alert", content)
        # Verify checklist report card is removed, only message is displayed
        self.assertNotIn("SLA Check Execution Report", content)
        self.assertEqual(content.count("<table"), 1, "There should only be one tracking table, no duplicate second table")

    def test_run_check_now_preserves_filters_and_page(self):
        """POST /app/sla/process/ with next parameter preserves filters and page on redirect."""
        target_url = "/app/sla/trackings/?q=INC-001&status=ACTIVE&page=1"
        response = self.client.post("/app/sla/process/", data={"next": target_url}, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, target_url)

    def test_run_check_now_ajax_returns_json_report(self):
        """AJAX POST to /app/sla/process/ returns JSON with execution summary."""
        response = self.client.post(
            "/app/sla/process/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("ok"))
        self.assertIn("result", data)
        res = data["result"]
        self.assertIn("checked", res)
        self.assertIn("warnings", res)
        self.assertIn("breaches", res)
        self.assertIn("escalations", res)
        self.assertIn("notifications", res)
        self.assertIn("timestamp", res)

    def test_sla_tracking_search_by_number_and_title(self):
        """Verify search query in SLA tracking works with request number, request title, WO number, and WO title without FieldError."""
        from django.utils import timezone

        from apps.assets.models import Asset, AssetCategory
        from apps.incidents.models import ServiceRequest
        from apps.sites.models import Site
        from apps.sla.models import SLATracking
        from apps.workorders.models import WorkOrder

        site = Site.objects.create(organization=self.org, name="Main Facility", code="MF-01")
        category = AssetCategory.objects.create(organization=self.org, name="Pumps")
        asset = Asset.objects.create(organization=self.org, site=site, category=category, name="Pump 101", serial_number="SN-01")

        req = ServiceRequest.objects.create(
            organization=self.org,
            site=site,
            asset=asset,
            number="INC-9901",
            title="Overheating Hydraulic Pump",
            severity="CRITICAL",
            reported_by=self.membership,
            occurred_at=timezone.now(),
        )

        wo = WorkOrder.objects.create(
            organization=self.org,
            site=site,
            asset=asset,
            created_by=self.user,
            order_number="WO-8802",
            title="Bearing Replacement Routine",
            work_type="CORRECTIVE",
            priority="HIGH",
        )

        profile = SLAProfile.objects.create(
            organization=self.org,
            name="General Policy",
            applies_to="REQUEST",
            is_active=True,
        )

        now = timezone.now()
        SLATracking.objects.create(
            organization=self.org,
            site=site,
            profile=profile,
            request=req,
            priority="CRITICAL",
            response_minutes=15,
            resolution_minutes=60,
            warning_percent=80,
            started_at=now,
            response_due_at=now + timezone.timedelta(minutes=15),
            resolution_due_at=now + timezone.timedelta(minutes=60),
            status=SLATracking.Status.ACTIVE,
        )

        SLATracking.objects.create(
            organization=self.org,
            site=site,
            profile=profile,
            work_order=wo,
            priority="HIGH",
            response_minutes=30,
            resolution_minutes=120,
            warning_percent=80,
            started_at=now,
            response_due_at=now + timezone.timedelta(minutes=30),
            resolution_due_at=now + timezone.timedelta(minutes=120),
            status=SLATracking.Status.ACTIVE,
        )

        # 1. Search by Request Number
        resp1 = self.client.get("/app/sla/trackings/?q=INC-9901")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("INC-9901", resp1.content.decode("utf-8"))
        self.assertNotIn("WO-8802", resp1.content.decode("utf-8"))

        # 2. Search by Request Title
        resp2 = self.client.get("/app/sla/trackings/?q=Overheating")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("INC-9901", resp2.content.decode("utf-8"))
        self.assertNotIn("WO-8802", resp2.content.decode("utf-8"))

        # 3. Search by Work Order Number
        resp3 = self.client.get("/app/sla/trackings/?q=WO-8802")
        self.assertEqual(resp3.status_code, 200)
        self.assertIn("WO-8802", resp3.content.decode("utf-8"))
        self.assertNotIn("INC-9901", resp3.content.decode("utf-8"))

        # 4. Search by Work Order Title
        resp4 = self.client.get("/app/sla/trackings/?q=Bearing")
        self.assertEqual(resp4.status_code, 200)
        self.assertIn("WO-8802", resp4.content.decode("utf-8"))
        self.assertNotIn("INC-9901", resp4.content.decode("utf-8"))

    def test_sla_tracking_reset_and_auto_filter_ui_elements(self):
        """Verify the Reset button and automatic filter attributes exist on the tracking page."""
        response = self.client.get("/app/sla/trackings/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")

        # Reset button
        self.assertIn('id="reset-filter-btn"', content)
        self.assertIn("Reset", content)

        # Automatic filter and table container
        self.assertIn('id="trackings-table-container"', content)
        self.assertIn('id="tracking-filter-form"', content)
        self.assertIn('hx-target="#trackings-table-container"', content)


class SlaFullWorkflowLifecycleTests(TestCase):
    """End-to-end verification of the full SLA lifecycle matching the exact workflow diagram:
    Client creates Incident (NEW) -> Triage / Approval -> Create Work Order (DRAFT)
    -> Apply SLA Profile (Work order type, Site, Priority) -> Start SLA Timers (Response & Resolution)
    -> Plan Work Order (DRAFT -> PLANNED)
    -> Assign Technician (PLANNED -> ASSIGNED) -> Response Achieved!
    -> Dispatch (ASSIGNED -> DISPATCHED) -> Start (DISPATCHED -> IN_PROGRESS)
    -> SLA Tracking monitors time -> Warnings / Breaches / Escalations / Acknowledge Breach
    -> Put work ON_HOLD with reason -> SLA Timers Paused!
    -> Resume work (ON_HOLD -> IN_PROGRESS) -> Timers continue (due dates shifted)
    -> Complete work (COMPLETED) -> Resolution Met!
    -> Submit for Review (COMPLETED -> SUPERVISOR_REVIEW)
    -> Supervisor reviews: Return for rework with reason -> IN_PROGRESS back to technician (Resolution timer reopened)
    -> Re-complete work -> Resubmit for review
    -> Supervisor accepts & closes -> Work Order CLOSED
    -> Request RESOLVED -> Client confirms -> Request CONFIRMED -> Request CLOSED
    -> Audit Trail records every milestone.
    """

    def setUp(self):
        from apps.assets.models import Asset, AssetCategory
        from apps.sites.models import Site
        from apps.sla.models import EscalationRule, SLAProfile, SLATarget
        from apps.sla import services as sla_services

        self.org = Organization.objects.create(name="Apex Industrial Ltd", slug="apex-sla-e2e")
        self.roles = seed_system_roles(self.org)

        # 1. Owner
        self.owner = User.objects.create_user(email="owner@apex.test", password="Password123!", full_name="Apex Owner")
        self.owner_mem = Membership.objects.create(organization=self.org, user=self.owner, status=Membership.Status.ACTIVE)
        MembershipRole.objects.create(membership=self.owner_mem, role=self.roles["owner"])

        # 2. Dispatcher / Operations Manager / Supervisor
        self.dispatcher = User.objects.create_user(email="dispatcher@apex.test", password="Password123!", full_name="Apex Dispatcher")
        self.dispatcher_mem = Membership.objects.create(organization=self.org, user=self.dispatcher, status=Membership.Status.ACTIVE)
        MembershipRole.objects.create(membership=self.dispatcher_mem, role=self.roles["operations_manager"])
        MembershipRole.objects.create(membership=self.dispatcher_mem, role=self.roles["maintenance_planner"])
        MembershipRole.objects.create(membership=self.dispatcher_mem, role=self.roles["supervisor"])

        # 3. Technician
        self.tech = User.objects.create_user(email="tech@apex.test", password="Password123!", full_name="Field Technician")
        self.tech_mem = Membership.objects.create(organization=self.org, user=self.tech, status=Membership.Status.ACTIVE)
        MembershipRole.objects.create(membership=self.tech_mem, role=self.roles["technician"])

        # 4. Client / Requester
        self.client_user = User.objects.create_user(email="client@clientcorp.test", password="Password123!", full_name="Client Requester")
        self.client_mem = Membership.objects.create(organization=self.org, user=self.client_user, status=Membership.Status.ACTIVE)
        MembershipRole.objects.create(membership=self.client_mem, role=self.roles["client_requester"])

        # Site & Asset
        self.site = Site.objects.create(organization=self.org, name="Pune Assembly Plant", code="PUNE-1")
        self.category = AssetCategory.objects.create(organization=self.org, name="Generators")
        self.asset = Asset.objects.create(organization=self.org, site=self.site, category=self.category,
                                          name="Diesel Generator 500kVA", serial_number="GEN-PUNE-01",
                                          asset_tag="GEN-001")

        # SLA Profile for Requests
        self.req_profile = sla_services.create_profile(
            self.org,
            name="Emergency Incident SLA",
            applies_to="REQUEST",
            site=self.site,
            actor=self.owner,
        )
        self.req_target = sla_services.set_target(
            self.req_profile,
            priority="CRITICAL",
            response_minutes=15,
            resolution_minutes=120,
            warning_percent=80,
            actor=self.owner,
        )

        # SLA Profile for Work Orders (site-scoped)
        self.wo_profile = sla_services.create_profile(
            self.org,
            name="Corrective Work Order SLA",
            applies_to="WORK_ORDER",
            site=self.site,
            pause_states=["WORK_ORDER:ON_HOLD"],
            actor=self.owner,
        )
        self.wo_target = sla_services.set_target(
            self.wo_profile,
            priority="CRITICAL",
            response_minutes=30,
            resolution_minutes=180,
            warning_percent=80,
            actor=self.owner,
        )

        # Escalation rules
        self.rule_warn = sla_services.create_rule(
            self.wo_profile,
            target_kind="RESOLUTION",
            trigger="WARNING",
            notify_role=self.roles["operations_manager"],
            notify_assignee=True,
            actor=self.owner,
        )
        self.rule_breach = sla_services.create_rule(
            self.wo_profile,
            target_kind="RESOLUTION",
            trigger="BREACH",
            notify_role=self.roles["operations_manager"],
            notify_assignee=True,
            actor=self.owner,
        )
        self.rule_escalate = sla_services.create_rule(
            self.wo_profile,
            target_kind="RESOLUTION",
            trigger="ESCALATION",
            after_minutes=30,
            level=2,
            notify_role=self.roles["owner"],
            notify_assignee=False,
            actor=self.owner,
        )

    def test_end_to_end_full_sla_workflow(self):
        """Execute and verify the complete end-to-end SLA workflow diagram."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.audit.models import AuditLog
        from apps.incidents import services as incident_services
        from apps.sla.models import SLAPauseEvent, SLATracking, SLAEvent
        from apps.sla import services as sla_services
        from apps.workorders import services as wo_services
        from apps.workorders.models import WorkOrder

        now = timezone.now()

        # Step 1: Client creates Incident Request (Incident = NEW)
        sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.client_mem,
            title="Generator Smoke Detected",
            severity="CRITICAL",
            kind="INCIDENT",
            actor=self.client_user,
        )
        self.assertEqual(sr.status, "NEW")

        t_req = SLATracking.objects.filter(request=sr).first()
        self.assertIsNotNone(t_req, "SLA Tracking must start upon Incident creation")
        self.assertEqual(t_req.status, SLATracking.Status.ACTIVE)
        self.assertEqual(t_req.response_minutes, 15)
        self.assertEqual(t_req.resolution_minutes, 120)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_req, event_type="STARTED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.tracking_started", organization=self.org).exists())

        # Step 2: Dispatcher triages and approves request
        sr = incident_services.transition(sr, action="triage", actor=self.dispatcher)
        self.assertEqual(sr.status, "TRIAGED")
        sr = incident_services.transition(sr, action="approve", actor=self.dispatcher)
        self.assertEqual(sr.status, "APPROVED")

        # Step 3: Create Work Order (Work Order = DRAFT)
        # Apply SLA Profile based on Work order type, Site, Priority
        wo = incident_services.create_work_order_for_request(
            sr,
            work_type="CORRECTIVE",
            actor=self.dispatcher,
            membership=self.dispatcher_mem,
        )
        self.assertEqual(wo.status, "DRAFT")
        self.assertEqual(wo.priority, "CRITICAL")
        self.assertEqual(wo.work_type, "CORRECTIVE")

        t_wo = SLATracking.objects.filter(work_order=wo).first()
        self.assertIsNotNone(t_wo, "SLA Tracking must be created for Work Order matching WORK_ORDER profile")
        self.assertEqual(t_wo.profile, self.wo_profile)
        self.assertEqual(t_wo.status, SLATracking.Status.ACTIVE)
        self.assertEqual(t_wo.response_minutes, 30)
        self.assertEqual(t_wo.resolution_minutes, 180)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="STARTED").exists())

        # Step 4: Plan Work Order (DRAFT -> PLANNED)
        start = now + timedelta(days=1)
        end = start + timedelta(hours=3)
        wo = wo_services.plan_work_order(
            wo,
            membership=self.dispatcher_mem,
            actor=self.dispatcher,
            planned_start=start,
            planned_end=end,
            due_at=end + timedelta(days=1),
            estimated_hours=3,
            work_type="CORRECTIVE",
            priority="CRITICAL",
        )
        self.assertEqual(wo.status, "PLANNED")

        # Step 5: Assign Technician (PLANNED -> ASSIGNED) -> Response Achieved!
        wo = wo_services.assign_work_order(
            wo,
            assignee_id=self.tech_mem.pk,
            membership=self.dispatcher_mem,
            actor=self.dispatcher,
        )
        self.assertEqual(wo.status, "ASSIGNED")

        t_wo.refresh_from_db()
        self.assertIsNotNone(t_wo.response_met_at, "Response timer must be met upon technician assignment")
        self.assertEqual(t_wo.response_state, SLATracking.TargetState.MET)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="RESPONSE_MET").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.response_met", organization=self.org).exists())

        # Step 6: Dispatch Work Order (ASSIGNED -> DISPATCHED)
        wo = wo_services.dispatch_work_order(
            wo,
            membership=self.dispatcher_mem,
            actor=self.dispatcher,
        )
        self.assertEqual(wo.status, "DISPATCHED")

        # Step 7: Technician Starts Work (DISPATCHED -> IN_PROGRESS)
        wo = wo_services.start_work_order(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
        )
        self.assertEqual(wo.status, "IN_PROGRESS")
        sr.refresh_from_db()
        self.assertEqual(sr.status, "IN_SERVICE", "Request must transition to IN_SERVICE when work starts")

        # Step 8: SLA Tracking monitors time -> Warning triggered when nearly reached
        simulated_warn_time = t_wo.started_at + timedelta(minutes=int(t_wo.resolution_minutes * 0.85))
        sla_services.process_tracking(t_wo, now=simulated_warn_time)

        t_wo.refresh_from_db()
        self.assertEqual(t_wo.status, SLATracking.Status.AT_RISK)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="WARNING").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.warning_issued", organization=self.org).exists())

        # Step 9: Work waiting? Put work ON_HOLD with reason -> SLA Timers Paused!
        hold_time = simulated_warn_time + timedelta(minutes=5)
        wo_services.hold_work_order(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
            reason="Waiting for specialized replacement seal kit",
        )
        wo.refresh_from_db()
        self.assertEqual(wo.status, "ON_HOLD")

        t_wo.refresh_from_db()
        self.assertEqual(t_wo.status, SLATracking.Status.PAUSED, "SLA timer must pause when ON_HOLD")
        self.assertIsNotNone(t_wo.paused_at)

        pause_ev = SLAPauseEvent.objects.filter(tracking=t_wo).last()
        self.assertIsNotNone(pause_ev)
        self.assertIn("seal kit", pause_ev.reason)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="PAUSED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.tracking_paused", organization=self.org).exists())

        # Step 10: Resume Work (ON_HOLD -> IN_PROGRESS) -> Timers continue
        orig_reso_due = t_wo.resolution_due_at
        resume_time = hold_time + timedelta(minutes=60)
        wo_services.resume_work_order(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
        )
        wo.refresh_from_db()
        self.assertEqual(wo.status, "IN_PROGRESS")

        t_wo.refresh_from_db()
        self.assertEqual(t_wo.status, SLATracking.Status.ACTIVE)
        self.assertIsNone(t_wo.paused_at)
        self.assertGreaterEqual(t_wo.resolution_due_at, orig_reso_due)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="RESUMED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.tracking_resumed", organization=self.org).exists())

        # Step 11: Technician completes work (adds checklist, notes and evidence) -> Resolution Met!
        wo.checklist_required = False
        wo.save(update_fields=["checklist_required"])
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.files import services as file_services
        evidence_attachment = file_services.attach(
            SimpleUploadedFile("completion_evidence.txt", b"Turbine test passed, pressure nominal."),
            target=wo,
            organization=self.org,
            user=self.tech,
            description="Completion evidence",
            read_permission="work_order.view",
        )
        wo_services.add_evidence(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
            attachment_id=evidence_attachment.pk,
        )
        wo_services.record_labor(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
            work_date=now.date(),
            hours="2.5",
            notes="Installed new seal kit and calibrated injectors",
        )
        wo = wo_services.complete_work_order(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
            resolution_notes="Replaced defective seal kit and verified exhaust clarity",
        )
        self.assertEqual(wo.status, "COMPLETED")

        t_wo.refresh_from_db()
        self.assertIsNotNone(t_wo.resolution_met_at, "Resolution target must be met upon completion")
        self.assertEqual(t_wo.resolution_state, SLATracking.TargetState.MET)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="RESOLUTION_MET").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.resolution_met", organization=self.org).exists())

        # Step 12: Submit for Supervisor Review (COMPLETED -> SUPERVISOR_REVIEW)
        wo = wo_services.submit_for_review(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
        )
        self.assertEqual(wo.status, "SUPERVISOR_REVIEW")

        t_wo.refresh_from_db()
        self.assertEqual(t_wo.status, SLATracking.Status.UNDER_REVIEW)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="SUPERVISOR_REVIEW").exists())

        # Step 13: Supervisor reviews work -> Not accepted: Return for rework with reason
        wo = wo_services.return_for_rework(
            wo,
            membership=self.dispatcher_mem,
            actor=self.dispatcher,
            comment="Exhaust temperature log missing from notes",
        )
        self.assertEqual(wo.status, "IN_PROGRESS")

        t_wo.refresh_from_db()
        self.assertIsNone(t_wo.resolution_met_at, "Resolution timer must reopen on rework return")
        self.assertEqual(t_wo.status, SLATracking.Status.ACTIVE)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="REOPENED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.tracking_reopened", organization=self.org).exists())

        # Step 14: Technician addresses feedback and resubmits
        wo = wo_services.complete_work_order(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
            resolution_notes="Added exhaust temperature log: operating nominal at 380 deg C",
        )
        wo = wo_services.submit_for_review(
            wo,
            membership=self.tech_mem,
            actor=self.tech,
        )
        self.assertEqual(wo.status, "SUPERVISOR_REVIEW")

        # Step 15: Supervisor reviews work -> Accepted: Close work order
        wo = wo_services.close_work_order(
            wo,
            membership=self.dispatcher_mem,
            actor=self.dispatcher,
            comment="Verified temperature log, work approved and closed",
        )
        self.assertEqual(wo.status, "CLOSED")

        t_wo.refresh_from_db()
        self.assertEqual(t_wo.status, SLATracking.Status.CLOSED)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="CLOSED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.tracking_closed", organization=self.org).exists())

        # Step 16: Request = RESOLVED -> Client confirms -> Request = CONFIRMED / CLOSED
        sr.refresh_from_db()
        self.assertEqual(sr.status, "RESOLVED")

        sr = incident_services.transition(
            sr,
            action="confirm",
            actor=self.client_user,
        )
        self.assertEqual(sr.status, "CONFIRMED")
        t_req.refresh_from_db()
        self.assertTrue(SLAEvent.objects.filter(tracking=t_req, event_type="CLIENT_CONFIRMED").exists())

        sr = incident_services.transition(
            sr,
            action="close",
            actor=self.owner,
        )
        self.assertEqual(sr.status, "CLOSED")
        t_req.refresh_from_db()
        self.assertEqual(t_req.status, SLATracking.Status.CLOSED)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_req, event_type="CLOSED").exists())

        # Step 17: Comprehensive Audit Trail Verification
        audit_events = list(AuditLog.objects.filter(organization=self.org).values_list("action", flat=True))
        expected_audit_milestones = [
            "sla.profile_created",
            "sla.target_set",
            "sla.rule_created",
            "sla.tracking_started",
            "sla.response_met",
            "sla.warning_issued",
            "sla.tracking_paused",
            "sla.tracking_resumed",
            "sla.resolution_met",
            "sla.tracking_reopened",
            "sla.tracking_closed",
        ]
        for milestone in expected_audit_milestones:
            self.assertIn(milestone, audit_events, f"Missing audit trail milestone: {milestone}")

    def test_sla_breach_detection_escalation_and_acknowledgement(self):
        """Verify SLA breach detection, multi-tier escalation, and manager acknowledgement."""
        from datetime import timedelta
        from django.utils import timezone
        from apps.audit.models import AuditLog
        from apps.incidents import services as incident_services
        from apps.sla.models import SLABreach, SLATracking, SLAEvent
        from apps.sla import services as sla_services
        from apps.workorders import services as wo_services

        sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.client_mem,
            title="Coolant Leak Critical",
            severity="CRITICAL",
            kind="INCIDENT",
            actor=self.client_user,
        )
        sr = incident_services.transition(sr, action="triage", actor=self.dispatcher)
        sr = incident_services.transition(sr, action="approve", actor=self.dispatcher)
        wo = incident_services.create_work_order_for_request(
            sr,
            work_type="CORRECTIVE",
            actor=self.dispatcher,
            membership=self.dispatcher_mem,
        )
        t_wo = SLATracking.objects.filter(work_order=wo).first()

        # Simulate breach time: resolution due date exceeded
        breach_time = t_wo.resolution_due_at + timedelta(minutes=5)
        sla_services.process_tracking(t_wo, now=breach_time)

        t_wo.refresh_from_db()
        self.assertEqual(t_wo.status, SLATracking.Status.BREACHED)
        self.assertEqual(t_wo.resolution_state, SLATracking.TargetState.BREACHED)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="BREACHED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.breach_detected", organization=self.org).exists())

        breach = SLABreach.objects.filter(tracking=t_wo, target_kind="RESOLUTION").first()
        self.assertIsNotNone(breach)
        self.assertEqual(breach.status, SLABreach.Status.OPEN)

        # Simulate escalation delay: 35 minutes after breach (rule threshold is 30m)
        escalate_time = breach_time + timedelta(minutes=35)
        sla_services.process_tracking(t_wo, now=escalate_time)

        breach.refresh_from_db()
        self.assertEqual(breach.escalation_level, 2)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="ESCALATED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.escalated", organization=self.org).exists())

        # Manager acknowledges breach
        sla_services.acknowledge_breach(breach, actor=self.dispatcher)
        breach.refresh_from_db()
        self.assertEqual(breach.status, SLABreach.Status.ACKNOWLEDGED)
        self.assertEqual(breach.acknowledged_by, self.dispatcher)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_wo, event_type="ACKNOWLEDGED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.breach_acknowledged", organization=self.org).exists())

    def test_dispatcher_rejection_cancels_sla(self):
        """Dispatcher rejecting request cancels the active SLA tracking."""
        from apps.audit.models import AuditLog
        from apps.incidents import services as incident_services
        from apps.sla.models import SLATracking, SLAEvent

        sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.client_mem,
            title="Non-actionable request",
            severity="CRITICAL",
            kind="INCIDENT",
            actor=self.client_user,
        )
        t_req = SLATracking.objects.filter(request=sr).first()
        self.assertEqual(t_req.status, SLATracking.Status.ACTIVE)

        sr = incident_services.transition(sr, action="triage", actor=self.dispatcher)
        sr = incident_services.transition(sr, action="reject", reason="Duplicate submission of earlier issue",
                                          actor=self.dispatcher)
        self.assertEqual(sr.status, "REJECTED")

        t_req.refresh_from_db()
        self.assertEqual(t_req.status, SLATracking.Status.CANCELLED)
        self.assertTrue(SLAEvent.objects.filter(tracking=t_req, event_type="CANCELLED").exists())
        self.assertTrue(AuditLog.objects.filter(action="sla.tracking_cancelled", organization=self.org).exists())

    def test_sla_panel_rendered_in_work_order_and_incident_views(self):
        """Verify SLA tracking panel renders directly inside Work Order and Incident UI templates."""
        from apps.incidents import services as incident_services

        sr = incident_services.create_request(
            self.org,
            asset=self.asset,
            reporter=self.client_mem,
            title="Turbine Bearing Wear",
            severity="CRITICAL",
            kind="INCIDENT",
            actor=self.client_user,
        )
        sr = incident_services.transition(sr, action="triage", actor=self.dispatcher)
        sr = incident_services.transition(sr, action="approve", actor=self.dispatcher)
        wo = incident_services.create_work_order_for_request(
            sr,
            work_type="CORRECTIVE",
            actor=self.dispatcher,
            membership=self.dispatcher_mem,
        )

        self.client.force_login(self.dispatcher)
        session = self.client.session
        session["tenant_org_id"] = str(self.org.pk)
        session.save()

        # 1. Check Incident page includes SLA panel
        inc_resp = self.client.get(f"/app/incidents/{sr.pk}/")
        self.assertEqual(inc_resp.status_code, 200)
        inc_content = inc_resp.content.decode("utf-8")
        self.assertIn('id="sla-panel"', inc_content)
        self.assertIn("Emergency Incident SLA", inc_content)
        self.assertIn("Response", inc_content)
        self.assertIn("Resolution", inc_content)

        # 2. Check Work Order overview tab includes SLA panel & header countdown badge
        wo_resp = self.client.get(f"/app/work-orders/{wo.pk}/?tab=overview")
        self.assertEqual(wo_resp.status_code, 200)
        wo_content = wo_resp.content.decode("utf-8")
        self.assertIn('id="sla-panel"', wo_content)
        self.assertIn("Corrective Work Order SLA", wo_content)
        self.assertIn("Response", wo_content)
        self.assertIn("Resolution", wo_content)
        self.assertIn('id="sla-countdown-badge"', wo_content)
        self.assertIn("sla-countdown-text", wo_content)

        # 3. Verify SLA Breach Indicator renders in Work Order header upon breach
        from apps.sla.models import SLATracking
        t_wo = SLATracking.objects.filter(work_order=wo).first()
        t_wo.status = SLATracking.Status.BREACHED
        t_wo.resolution_state = SLATracking.TargetState.BREACHED
        t_wo.save(update_fields=["status", "resolution_state"])

        wo_breach_resp = self.client.get(f"/app/work-orders/{wo.pk}/")
        self.assertEqual(wo_breach_resp.status_code, 200)
        wo_breach_content = wo_breach_resp.content.decode("utf-8")
        self.assertIn('id="sla-breach-indicator"', wo_breach_content)
        self.assertIn("SLA BREACHED", wo_breach_content)

        # 4. Verify new SLA Profile form does not display Contract / AMC
        self.client.force_login(self.owner)
        profile_form_resp = self.client.get("/app/sla/profiles/new/")
        self.assertEqual(profile_form_resp.status_code, 200)
        form_content = profile_form_resp.content.decode("utf-8")
        self.assertNotIn("Contract / AMC", form_content)




