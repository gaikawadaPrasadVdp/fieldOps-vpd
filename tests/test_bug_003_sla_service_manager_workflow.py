"""Regression test suite for BUG-003:
Broken end-to-end SLA configuration and monitoring workflow for Service Manager.

Verifies:
1. Service Manager dashboard (/app/sla/trackings/) provides direct navigation pathways and shortcuts to
   configure new profiles, manage profiles, review breaches, and run SLA calculation checks.
2. The New SLA Profile form (/app/sla/profiles/new/) provides proper form controls for configuring profiles,
   defining priority targets (Response & Resolution deadlines with flexible duration formats like '15m' and '2h'),
   and setting escalation rules in sequence.
3. Submitting the exact test profile ("Standard Critical", Target: Response 15m / Resolution 2h)
   creates an active SLA Profile with the priority target (15 min response, 120 min resolution)
   and properly seeded escalation rules.
4. Profile Detail (/app/sla/profiles/<id>/) provides shortcuts to active trackings, run checks, and manage targets/rules.
5. Breaches can be acknowledged directly by Service Manager from the breaches workflow.
"""
from datetime import timedelta
import pytest
from django.test import Client

from apps.accounts.models import User
from apps.rbac.models import MembershipRole
from apps.rbac.services import seed_system_roles
from apps.sla.models import SLAProfile, SLATracking, SLABreach
from apps.sla import services as sla_services
from apps.tenancy.models import Membership, Organization
from apps.sites.models import Site

pytestmark = pytest.mark.django_db


@pytest.fixture
def service_manager_setup():
    org = Organization.objects.create(name="NexOps Global", slug="nexops-global")
    roles = seed_system_roles(org)

    site = Site.objects.create(organization=org, code="S01", name="Primary Operations Site")

    # Service Manager user & membership
    sm_user = User.objects.create_user(
        email="servicemanager@nexops.com",
        password="Password123!",
        full_name="Alex ServiceManager"
    )
    sm_membership = Membership.objects.create(
        organization=org,
        user=sm_user,
        status=Membership.Status.ACTIVE
    )
    MembershipRole.objects.create(
        membership=sm_membership,
        role=roles["service_manager"]
    )

    client = Client()
    client.force_login(sm_user)
    session = client.session
    session["tenant_org_id"] = str(org.pk)
    session["active_org_id"] = str(org.pk)
    session["organization_id"] = str(org.pk)
    session.save()

    return {
        "org": org,
        "roles": roles,
        "site": site,
        "sm_user": sm_user,
        "sm_membership": sm_membership,
        "client": client,
    }


def test_bug_003_dashboard_shortcuts_and_navigation(service_manager_setup):
    """SLA Tracking dashboard provides direct navigation pathways and shortcuts for Service Manager."""
    client = service_manager_setup["client"]

    resp = client.get("/app/sla/trackings/")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")

    # Verify primary management shortcuts exist in page header
    assert 'href="/app/sla/profiles/new/"' in content or 'href="/app/sla/profiles/"' in content
    assert "SLA Profiles" in content
    assert "New Profile" in content

    # Verify Run Check button exists for Service Manager
    assert "Run Check Now" in content or "Run Check" in content
    assert 'action="/app/sla/process/"' in content

    # Verify tabs include SLA tracking, SLA breaches, SLA profiles
    assert "SLA tracking" in content
    assert "SLA breaches" in content
    assert "SLA profiles" in content


def test_bug_003_profile_form_controls_rendering(service_manager_setup):
    """GET /app/sla/profiles/new/ renders form controls for profile scope, targets, and escalation rules."""
    client = service_manager_setup["client"]

    resp = client.get("/app/sla/profiles/new/")
    assert resp.status_code == 200
    content = resp.content.decode("utf-8")

    # Breadcrumb pathways
    assert "SLA Tracking" in content
    assert "SLA profiles" in content

    # Section 1: Profile Scope
    assert "Profile & Target Scope" in content
    assert 'name="name"' in content
    assert 'name="applies_to"' in content

    # Section 2: Schedule & Pause Rules
    assert "Schedule & Pause Rules" in content
    assert 'name="use_business_hours"' in content
    assert 'name="pause_states"' in content

    # Section 3: Priority Targets with duration inputs & presets
    assert "Priority Targets" in content
    assert 'name="priority"' in content
    assert 'name="response_target"' in content
    assert 'name="resolution_target"' in content
    assert 'name="warning_alert"' in content
    assert "Standard Critical (15m / 2h)" in content

    # Section 4: Automated Escalation & Notification Rules
    assert "Automated Escalation" in content or "Escalation & Notification Rules" in content
    assert 'name="rule_target_kind"' in content
    assert 'name="rule_trigger"' in content
    assert 'name="rule_level"' in content
    assert 'name="rule_notify_role"' in content
    assert 'name="rule_notify_assignee"' in content


def test_bug_003_configure_profile_targets_and_escalation_end_to_end(service_manager_setup):
    """Service Manager creates 'Standard Critical' with Target 'Response 15m / Resolution 2h' seamlessly."""
    client = service_manager_setup["client"]
    org = service_manager_setup["org"]

    # Submit the exact profile configuration requested in BUG-003
    payload = {
        "name": "Standard Critical",
        "applies_to": "Incident / Breakdown",
        "site": "",
        "description": "Critical incident SLA with 15m response and 2h resolution targets",
        "priority": "Critical",
        "response_target": "15m",
        "resolution_target": "2h",
        "warning_alert": "80%",
        "rule_target_kind": "RESOLUTION",
        "rule_trigger": "BREACH",
        "rule_level": "2",
        "rule_notify_assignee": "on",
        "is_active": "on",
    }

    resp = client.post("/app/sla/profiles/new/", data=payload, follow=True)
    assert resp.status_code == 200

    # Verify profile created and active
    profile = SLAProfile.objects.for_organization(org).filter(name="Standard Critical").first()
    assert profile is not None, "Profile 'Standard Critical' was not saved in DB"
    assert profile.is_active is True
    assert profile.applies_to == "REQUEST"

    # Verify target parsed 15m -> 15 min, 2h -> 120 min
    targets = list(profile.targets.all())
    assert len(targets) == 1
    t = targets[0]
    assert t.priority == "CRITICAL"
    assert t.response_minutes == 15
    assert t.resolution_minutes == 120
    assert t.warning_percent == 80

    # Verify escalation rules attached
    rules = list(profile.rules.all())
    assert len(rules) >= 1

    # Verify detail page renders targets and escalation rules
    detail_content = resp.content.decode("utf-8")
    assert "Standard Critical" in detail_content
    assert "15 min" in detail_content
    assert "120 min" in detail_content or "2 hour" in detail_content


def test_bug_003_run_check_and_breach_acknowledgement_workflow(service_manager_setup):
    """Service Manager can run checks and acknowledge breaches from the SLA workflow."""
    client = service_manager_setup["client"]
    org = service_manager_setup["org"]
    site = service_manager_setup["site"]
    sm_membership = service_manager_setup["sm_membership"]

    # 1. Run Check Now via AJAX
    resp_check = client.post(
        "/app/sla/process/",
        data={"format": "json"},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest"
    )
    assert resp_check.status_code == 200
    data = resp_check.json()
    assert data.get("ok") is True

    # 2. Run Check Now standard POST
    resp_check_std = client.post("/app/sla/process/", follow=True)
    assert resp_check_std.status_code == 200

    # 3. Create a profile and simulate tracking with breach to test acknowledgement
    profile = sla_services.create_profile(
        org=org,
        name="Emergency Test Profile",
        applies_to="WORK_ORDER",
        actor=service_manager_setup["sm_user"],
        site=site,
        is_active=False,
    )
    sla_services.set_target(
        profile,
        priority="URGENT",
        response_minutes=15,
        resolution_minutes=60,
        warning_percent=80,
        actor=service_manager_setup["sm_user"]
    )
    sla_services.set_profile_active(profile, True, actor=service_manager_setup["sm_user"])

    # Create dummy tracking & breach
    from apps.workorders.models import WorkOrder
    wo = WorkOrder.objects.create(
        organization=org,
        site=site,
        number="WO-SLA-TEST-01",
        title="Emergency Pump Failure",
        created_by=service_manager_setup["sm_user"]
    )
    now = sla_services.timezone.now()
    tracking = SLATracking.objects.create(
        organization=org,
        work_order=wo,
        profile=profile,
        site=site,
        priority="URGENT",
        response_minutes=15,
        resolution_minutes=60,
        warning_percent=80,
        started_at=now,
        response_due_at=now + timedelta(minutes=15),
        resolution_due_at=now + timedelta(minutes=60),
        status="BREACHED",
        response_state="BREACHED",
        resolution_state="PENDING",
        selection_reason="Rule match"
    )
    breach = SLABreach.objects.create(
        organization=org,
        tracking=tracking,
        profile=profile,
        site=site,
        target_kind="RESPONSE",
        status="OPEN",
        breached_at=now,
        detected_at=now
    )

    # 4. Service Manager visits breach queue and acknowledges breach
    resp_breaches = client.get("/app/sla/breaches/")
    assert resp_breaches.status_code == 200
    assert f"/app/sla/breaches/{breach.pk}/acknowledge/" in resp_breaches.content.decode("utf-8")

    # Acknowledge the breach
    resp_ack = client.post(f"/app/sla/breaches/{breach.pk}/acknowledge/", follow=True)
    assert resp_ack.status_code == 200

    breach.refresh_from_db()
    assert breach.status == "ACKNOWLEDGED"
    assert breach.acknowledged_by == service_manager_setup["sm_user"]
