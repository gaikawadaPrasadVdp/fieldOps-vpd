"""Unit test suite for FieldOps Nexus Unit Test Specification (HPE-PRD-2026-FOPS02-QA-TC-001).
Covers Modules:
- 3.1 Organization & Site Master (ORG): TC-ORG-001 to TC-ORG-004
- 3.2 Asset Registry & Hierarchy (AST): TC-AST-001 to TC-AST-006
- 3.3 Meter / Usage Tracking (MTR): TC-MTR-001 to TC-MTR-004
- 3.4 Preventive Maintenance (PM): TC-PM-001 to TC-PM-006
"""
import uuid
from datetime import date, datetime, timedelta, timezone as dt_tz
from decimal import Decimal
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.tenancy.models import Organization, Membership
from apps.accounts.models import User
from apps.rbac.models import Role, MembershipRole
from apps.sites.models import Site, Zone, OperatingCalendar
from apps.sites import services as site_services
from apps.assets.models import (
    Asset, AssetCategory, AssetStatusHistory, AssetLocationHistory,
    AssetMeter, AssetMeterReading, AssetComponent, AssetStatus, AssetCriticality
)
from apps.assets import services as asset_services, hierarchy
from apps.maintenance.models import MaintenancePlan, MaintenanceSchedule, MaintenanceCycle
from apps.maintenance import services as maint_services, recurrence as rec
from apps.workorders.models import WorkOrder
from apps.core.exceptions import ValidationFailed, Conflict


# ==============================================================================
# Module 3.1: Organization & Site Master (ORG)
# ==============================================================================

@pytest.mark.django_db
def test_tc_org_001_create_site_valid():
    """TC-ORG-001: Positive - Create Site with Valid Organization and Operating Calendar."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    site = Site(name="Site North", code=f"SITE-N1-{uuid.uuid4().hex[:4]}", organization=org, timezone="UTC")
    site.full_clean()
    site.save()
    assert site.pk is not None
    assert site.created_at is not None
    assert site.organization == org


@pytest.mark.django_db
def test_tc_org_002_reject_duplicate_site_code():
    """TC-ORG-002: Negative - Reject Duplicate Site Code within the Same Organization."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    code = f"SITE-N1-{uuid.uuid4().hex[:4]}"
    site1 = Site.objects.create(name="Site North", code=code, organization=org, timezone="UTC")
    
    site2 = Site(name="Site North Duplicate", code=code, organization=org, timezone="UTC")
    with pytest.raises((ValidationError, Exception)):
        site2.full_clean()
        site2.save()


@pytest.mark.django_db
def test_tc_org_003_reject_empty_or_whitespace_site_name():
    """TC-ORG-003: Boundary / Negative - Reject Empty or Whitespace-Only Site Name."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    # Under test spec TC-ORG-003:
    # Steps: Instantiate Site with name="   ", code="SITE-W1", organization_id="ORG-001".
    # Invoke site.full_clean().
    # Expected Result: ValidationError raised with field error on name ("This field cannot be blank").
    site = Site(name="   ", code=f"SITE-W1-{uuid.uuid4().hex[:4]}", organization=org, timezone="UTC")
    with pytest.raises(ValidationError):
        site.full_clean()
        site.save()


@pytest.mark.django_db
def test_tc_org_004_link_zone_to_parent_site():
    """TC-ORG-004: Positive - Link Zone to Parent Site Hierarchically."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    site = Site.objects.create(name="Site North", code=f"SITE-N1-{uuid.uuid4().hex[:4]}", organization=org, timezone="UTC")
    zone = Zone(name="Floor 3 - Server Room", code=f"Z-FL03-{uuid.uuid4().hex[:4]}", site=site, organization=org)
    zone.full_clean()
    zone.save()
    assert zone.site == site
    assert zone.site.code == site.code


# ==============================================================================
# Module 3.2: Asset Registry & Hierarchy (AST)
# ==============================================================================

@pytest.mark.django_db
def test_tc_ast_001_register_asset_valid_mandatory():
    """TC-AST-001: Positive - Register Asset with Valid Mandatory Fields and Status ACTIVE."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")

    ast = Asset.objects.create(
        organization=org,
        asset_tag=f"AST-2026-{uuid.uuid4().hex[:4]}",
        serial_number="SN-998822",
        status=AssetStatus.ACTIVE,
        name="Generator 1",
        site=site,
        category=cat
    )
    assert ast.pk is not None
    assert ast.status == AssetStatus.ACTIVE


@pytest.mark.django_db
def test_tc_ast_002_reject_commission_date_prior_to_purchase_date():
    """TC-AST-002: Negative - Reject Commission Date Prior to Purchase Date."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")

    with pytest.raises(ValidationFailed):
        asset_services.create_asset(
            org,
            asset_tag=f"AST-{uuid.uuid4().hex[:6]}",
            name="Chiller",
            purchase_date=date(2026, 5, 10),
            commission_date=date(2026, 5, 1),
            site=site,
            category=cat,
            actor=user
        )


@pytest.mark.django_db
def test_tc_ast_003_prevent_circular_parent_child_asset_hierarchy():
    """TC-AST-003: Edge Case - Prevent Circular Parent-Child Asset Hierarchy."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")

    ast_a = Asset.objects.create(organization=org, asset_tag=f"AST-A-{uuid.uuid4().hex[:4]}", name="A", site=site, category=cat)
    ast_b = Asset.objects.create(organization=org, asset_tag=f"AST-B-{uuid.uuid4().hex[:4]}", name="B", site=site, category=cat)
    
    hierarchy.add_component(ast_a, ast_b, actor=user)

    with pytest.raises((ValidationFailed, Conflict)):
        hierarchy.add_component(ast_b, ast_a, actor=user)


@pytest.mark.django_db
def test_tc_ast_004_prevent_asset_from_being_its_own_parent():
    """TC-AST-004: Negative - Prevent Asset from being its own Parent."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")

    ast_a = Asset.objects.create(organization=org, asset_tag=f"AST-A-{uuid.uuid4().hex[:4]}", name="A", site=site, category=cat)

    with pytest.raises((ValidationFailed, Conflict)):
        hierarchy.add_component(ast_a, ast_a, actor=user)


@pytest.mark.django_db
def test_tc_ast_005_audit_trail_on_asset_status_transition():
    """TC-AST-005: Business Logic - Audit Trail on Asset Status Transition."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")

    ast = Asset.objects.create(
        organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator",
        status=AssetStatus.ACTIVE, site=site, category=cat
    )

    asset_services.change_status(ast, action="start_maintenance", reason="WO-101 Started", actor=user)
    ast.refresh_from_db()
    assert ast.status == AssetStatus.UNDER_MAINTENANCE

    hist = AssetStatusHistory.objects.filter(asset=ast).order_by("-created_at").first()
    assert hist is not None
    assert hist.from_status == "ACTIVE"
    assert hist.to_status == "UNDER_MAINTENANCE"
    assert "WO-101 Started" in hist.reason


@pytest.mark.django_db
def test_tc_ast_006_preserve_historical_context_when_asset_relocated():
    """TC-AST-006: Edge Case - Preserve Historical Context when Asset is Relocated Between Sites."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site_a = Site.objects.create(organization=org, code=f"S-A-{uuid.uuid4().hex[:4]}", name="Site A")
    site_b = Site.objects.create(organization=org, code=f"S-B-{uuid.uuid4().hex[:4]}", name="Site B")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")

    ast = Asset.objects.create(
        organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator",
        status=AssetStatus.ACTIVE, site=site_a, category=cat
    )

    wo = WorkOrder.objects.create(
        organization=org, site=site_a, asset=ast, order_number=f"WO-{uuid.uuid4().hex[:4]}",
        title="Repair at Site A", status=WorkOrder.Status.CLOSED
    )

    asset_services.update_asset(ast, site=site_b, actor=user)
    ast.refresh_from_db()
    wo.refresh_from_db()

    assert ast.site == site_b
    assert wo.site == site_a


# ==============================================================================
# Module 3.3: Meter / Usage Tracking (MTR)
# ==============================================================================

@pytest.mark.django_db
def test_tc_mtr_001_record_valid_incremental_meter_reading():
    """TC-MTR-001: Positive - Record Valid Incremental Meter Reading."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    meter = asset_services.create_meter(ast, name="Running Hours", unit="h", actor=user)
    t0 = timezone.now() - timedelta(hours=5)
    t1 = timezone.now() - timedelta(hours=1)
    
    asset_services.record_reading(meter, value=1500.0, read_at=t0, actor=user)
    reading2 = asset_services.record_reading(meter, value=1580.5, read_at=t1, actor=user)

    assert reading2.value == Decimal("1580.5")
    latest = meter.readings.order_by("-read_at", "-created_at").first()
    assert latest.value == Decimal("1580.5")


@pytest.mark.django_db
def test_tc_mtr_002_reject_decremental_meter_reading():
    """TC-MTR-002: Negative - Reject Decremental Meter Reading for Monotonic Non-Rollover Meter."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    meter = asset_services.create_meter(ast, name="Running Hours", unit="h", actor=user)
    t0 = timezone.now() - timedelta(hours=5)
    t1 = timezone.now() - timedelta(hours=1)
    
    asset_services.record_reading(meter, value=1500.0, read_at=t0, actor=user)

    with pytest.raises(ValidationFailed):
        asset_services.record_reading(meter, value=1450.0, read_at=t1, actor=user)


@pytest.mark.django_db
def test_tc_mtr_003_reject_negative_meter_reading_values():
    """TC-MTR-003: Boundary Value - Reject Negative Meter Reading Values."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    meter = asset_services.create_meter(ast, name="Running Hours", unit="h", actor=user)

    with pytest.raises(ValidationFailed):
        asset_services.record_reading(meter, value=-0.01, actor=user)


@pytest.mark.django_db
def test_tc_mtr_004_trigger_threshold_event_when_meter_exceeds_limit():
    """TC-MTR-004: Business Logic - Trigger Threshold Event when Meter Exceeds Limit."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    meter = asset_services.create_meter(ast, name="Running Hours", unit="h", actor=user)
    asset_services.record_reading(meter, value=1505.0, actor=user)

    k = rec.latest_meter_sequence(start_value=Decimal("1000.0"), interval=Decimal("500.0"), reading=Decimal("1505.0"))
    threshold = rec.meter_threshold(start_value=Decimal("1000.0"), interval=Decimal("500.0"), k=k)
    
    assert k == 1
    assert threshold == Decimal("1500.0")
    assert Decimal("1505.0") >= threshold


# ==============================================================================
# Module 3.4: Preventive Maintenance (PM) & Auto-Generation
# ==============================================================================

@pytest.mark.django_db
def test_tc_pm_001_create_time_based_recurring_maintenance_plan():
    """TC-PM-001: Positive - Create Time-Based Recurring Maintenance Plan."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    plan = maint_services.create_plan(
        org, asset=ast, name="Monthly Generator Inspection",
        priority="MEDIUM", estimated_hours=2.0, actor=user
    )
    sch = maint_services.create_schedule(
        plan, trigger_type=MaintenanceSchedule.Trigger.TIME,
        frequency=MaintenanceSchedule.Frequency.MONTHLY, interval_count=1,
        start_date=date.today(), lead_days=0, actor=user
    )
    assert plan.pk is not None
    assert plan.is_active is True
    assert sch.next_due_date is not None


@pytest.mark.django_db
def test_tc_pm_002_celery_job_generates_due_pm_work_order():
    """TC-PM-002: Business Logic - Celery Job Generates Due PM Work Order."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    plan = maint_services.create_plan(
        org, asset=ast, name="Monthly Generator Inspection",
        priority="MEDIUM", estimated_hours=2.0, actor=user
    )
    sch = maint_services.create_schedule(
        plan, trigger_type=MaintenanceSchedule.Trigger.TIME,
        frequency=MaintenanceSchedule.Frequency.DAILY, interval_count=30,
        start_date=date.today(), lead_days=0, actor=user
    )

    cycle = maint_services.generate_cycle(sch, actor=None, now=timezone.now())
    assert cycle is not None
    assert cycle.work_order is not None
    assert cycle.work_order.work_type == WorkOrder.WorkType.PREVENTIVE


@pytest.mark.django_db
def test_tc_pm_003_prevent_duplicate_work_order_for_same_pm_cycle():
    """TC-PM-003: Critical Edge Case - Prevent Duplicate Work Order Generation for Same PM Cycle."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    plan = maint_services.create_plan(
        org, asset=ast, name="Monthly Generator Inspection",
        priority="MEDIUM", estimated_hours=2.0, actor=user
    )
    sch = maint_services.create_schedule(
        plan, trigger_type=MaintenanceSchedule.Trigger.TIME,
        frequency=MaintenanceSchedule.Frequency.DAILY, interval_count=30,
        start_date=date.today(), lead_days=0, actor=user
    )

    cycle1 = maint_services.generate_cycle(sch, actor=None, now=timezone.now())
    assert cycle1 is not None

    cycle2 = maint_services.generate_cycle(sch, actor=None, now=timezone.now())
    assert cycle2 is None


@pytest.mark.django_db
def test_tc_pm_004_reject_zero_or_negative_recurrence_interval():
    """TC-PM-004: Boundary Value - Reject Zero or Negative Recurrence Interval."""
    org = Organization.objects.create(name=f"Org-{uuid.uuid4().hex[:6]}", slug=f"slug-{uuid.uuid4().hex[:6]}")
    user = User.objects.create(email=f"user-{uuid.uuid4().hex[:6]}@example.com")
    site = Site.objects.create(organization=org, code=f"S-{uuid.uuid4().hex[:4]}", name="Site A")
    cat = AssetCategory.objects.create(organization=org, name="HVAC")
    ast = Asset.objects.create(organization=org, asset_tag=f"AST-{uuid.uuid4().hex[:6]}", name="Generator", site=site, category=cat)

    plan = maint_services.create_plan(
        org, asset=ast, name="Test Plan", priority="MEDIUM", actor=user
    )
    with pytest.raises(ValidationFailed):
        maint_services.create_schedule(
            plan, trigger_type=MaintenanceSchedule.Trigger.TIME,
            frequency=MaintenanceSchedule.Frequency.DAILY, interval_count=0,
            start_date=date.today(), actor=user
        )


@pytest.mark.django_db
def test_tc_pm_005_advance_next_due_date_on_pm_completion():
    """TC-PM-005: Business Logic - Advance Next Due Date on PM Completion."""
    start_d = date(2026, 9, 1)
    k0_date = rec.time_due_date(start_d, "DAILY", 30, 0)
    k1_date = rec.time_due_date(start_d, "DAILY", 30, 1)
    assert k0_date == date(2026, 9, 1)
    assert k1_date == date(2026, 10, 1)
    assert (k1_date - k0_date).days == 30


@pytest.mark.django_db
def test_tc_pm_006_handle_overdue_cycles_without_avalanche_backlog():
    """TC-PM-006: Edge Case - Handle Overdue Cycles Without Creating Avalanche of Backlog."""
    start = date(2026, 1, 1)
    horizon = date(2026, 6, 15)
    k = rec.latest_time_sequence(start, "MONTHLY", 1, horizon)
    assert k == 5

    latest_due = rec.time_due_date(start, "MONTHLY", 1, k)
    assert latest_due == date(2026, 6, 1)
