from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.assets import hierarchy, services
from apps.assets.models import (
    AssetCategory,
    AssetComponent,
    AssetStatus,
    AssetStatusHistory,
)
from apps.core.exceptions import InvalidTransition, ValidationFailed
from apps.rbac.models import MembershipRole, Role
from apps.sites.models import Site, Zone
from apps.tenancy.models import Membership, Organization


class AssetHierarchyAndLifecycleTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="manager@fieldops.local",
            password="Password123!",
            full_name="Alice Manager"
        )
        self.org = Organization.objects.create(
            name="Apex Engineering Corp",
            slug="apex-engineering-corp"
        )
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.user,
            status=Membership.Status.ACTIVE
        )
        self.site = Site.objects.create(
            organization=self.org,
            name="Colombo Mega Plant",
            code="SITE-CMB-01",
            city="Colombo",
            timezone="Asia/Colombo"
        )
        self.zone_a = Zone.objects.create(
            organization=self.org,
            site=self.site,
            name="Zone A - Power & HVAC Wing",
            code="ZN-A-PWR"
        )
        self.cat_hvac = AssetCategory.objects.create(
            organization=self.org,
            name="HVAC & Climate Control"
        )
        self.cat_pump = AssetCategory.objects.create(
            organization=self.org,
            name="Pumps & Compressors"
        )

    def test_create_asset_hierarchy_tree(self):
        """Test creating 3-tier hierarchy: Root Chiller Plant -> Compressor Unit -> Impeller Part."""
        root_plant = services.create_asset(
            self.org,
            asset_tag="AST-CHL-001",
            name="Central Chiller Plant A",
            category=self.cat_hvac,
            site=self.site,
            zone=self.zone_a,
            actor=self.user
        )

        compressor = services.create_asset(
            self.org,
            asset_tag="AST-CMP-001",
            name="Screw Compressor Unit 1",
            category=self.cat_pump,
            site=self.site,
            zone=self.zone_a,
            actor=self.user
        )

        bearing = services.create_asset(
            self.org,
            asset_tag="AST-BRG-001",
            name="Magnetic Bearing Module",
            category=self.cat_pump,
            site=self.site,
            zone=self.zone_a,
            actor=self.user
        )

        # Link Root -> Compressor (ASSEMBLY)
        link1 = hierarchy.add_component(
            parent=root_plant,
            child=compressor,
            relationship_type="ASSEMBLY",
            quantity=1,
            actor=self.user
        )
        self.assertEqual(link1.parent, root_plant)
        self.assertEqual(link1.child, compressor)

        # Attempting to link Compressor (already a child) -> Bearing must fail: child_cannot_be_parent
        with self.assertRaises(ValidationFailed) as ctx:
            hierarchy.add_component(
                parent=compressor,
                child=bearing,
                relationship_type="REPLACEABLE_PART",
                quantity=2,
                part_number="SKF-6205-2RS",
                actor=self.user
            )
        self.assertEqual(ctx.exception.code, "child_cannot_be_parent")

        # Link Root -> Bearing (REPLACEABLE_PART)
        link2 = hierarchy.add_component(
            parent=root_plant,
            child=bearing,
            relationship_type="REPLACEABLE_PART",
            quantity=2,
            part_number="SKF-6205-2RS",
            actor=self.user
        )
        self.assertEqual(link2.parent, root_plant)
        self.assertEqual(link2.child, bearing)

        # Build tree from root
        tree = hierarchy.build_tree(root_plant)
        self.assertEqual(tree["asset"].asset_tag, "AST-CHL-001")
        self.assertEqual(len(tree["children"]), 2)
        child_tags = [c["asset"].asset_tag for c in tree["children"]]
        self.assertIn("AST-CMP-001", child_tags)
        self.assertIn("AST-BRG-001", child_tags)

        # Ancestors of bearing
        ancs = hierarchy.ancestors(bearing)
        self.assertEqual([a.asset_tag for a in ancs], ["AST-CHL-001"])

    def test_cycle_prevention(self):
        """Test that linking an ancestor as a child raises ValidationFailed."""
        asset_a = services.create_asset(
            self.org,
            asset_tag="AST-A",
            name="Asset A",
            category=self.cat_hvac,
            site=self.site,
            actor=self.user
        )
        asset_b = services.create_asset(
            self.org,
            asset_tag="AST-B",
            name="Asset B",
            category=self.cat_hvac,
            site=self.site,
            actor=self.user
        )

        # Link A -> B
        hierarchy.add_component(parent=asset_a, child=asset_b, actor=self.user)

        # Attempting B -> A must fail with hierarchy_cycle
        with self.assertRaises(ValidationFailed):
            hierarchy.add_component(parent=asset_b, child=asset_a, actor=self.user)

        # Attempting A -> A must fail with self_parent
        with self.assertRaises(ValidationFailed):
            hierarchy.add_component(parent=asset_a, child=asset_a, actor=self.user)

    def test_move_component_subtree(self):
        """Test reparenting a component under a new parent."""
        root1 = services.create_asset(
            self.org, asset_tag="ROOT-1", name="Root 1",
            category=self.cat_hvac, site=self.site, actor=self.user
        )
        root2 = services.create_asset(
            self.org, asset_tag="ROOT-2", name="Root 2",
            category=self.cat_hvac, site=self.site, actor=self.user
        )
        child = services.create_asset(
            self.org, asset_tag="CHILD-1", name="Child 1",
            category=self.cat_pump, site=self.site, actor=self.user
        )

        link = hierarchy.add_component(parent=root1, child=child, actor=self.user)
        self.assertEqual(link.parent, root1)

        # Move child to root2
        moved_link = hierarchy.move_component(link, root2, actor=self.user)
        self.assertEqual(moved_link.parent, root2)
        self.assertEqual(hierarchy.ancestors(child)[0], root2)

    def test_remove_component(self):
        """Test detaching a component from its parent."""
        root = services.create_asset(
            self.org, asset_tag="ROOT-X", name="Root X",
            category=self.cat_hvac, site=self.site, actor=self.user
        )
        child = services.create_asset(
            self.org, asset_tag="CHILD-X", name="Child X",
            category=self.cat_pump, site=self.site, actor=self.user
        )
        link = hierarchy.add_component(parent=root, child=child, actor=self.user)
        self.assertTrue(AssetComponent.objects.filter(pk=link.pk).exists())

        hierarchy.remove_component(link, actor=self.user)
        self.assertFalse(AssetComponent.objects.filter(pk=link.pk).exists())
        self.assertEqual(hierarchy.ancestors(child), [])

    def test_meters_and_telemetry(self):
        """Test creating telemetry meters and logging readings."""
        asset = services.create_asset(
            self.org, asset_tag="GEN-001", name="Diesel Generator",
            category=self.cat_hvac, site=self.site, actor=self.user
        )
        meter = services.create_meter(asset, name="Running Hours", unit="h", actor=self.user)
        self.assertEqual(meter.name, "Running Hours")
        self.assertEqual(meter.unit, "h")

        reading = services.record_reading(meter, value=Decimal("1250.5"), notes="Routine reading", actor=self.user)
        self.assertEqual(reading.value, Decimal("1250.5"))
        self.assertEqual(reading.meter, meter)

    def test_status_workflow_transitions(self):
        """Test asset status changes and history recording."""
        asset = services.create_asset(
            self.org, asset_tag="CHL-002", name="Chiller 2",
            category=self.cat_hvac, site=self.site, actor=self.user
        )
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

        # Transition to UNDER_MAINTENANCE
        services.change_status(
            asset, action="start_maintenance", reason="Overhaul", actor=self.user
        )
        asset.refresh_from_db()
        self.assertEqual(asset.status, AssetStatus.UNDER_MAINTENANCE)

        history = AssetStatusHistory.objects.filter(asset=asset).order_by("created_at", "id")
        self.assertEqual(history.count(), 2)
        self.assertEqual(history[0].action, "register")
        self.assertEqual(history[0].to_status, AssetStatus.ACTIVE)
        self.assertEqual(history[1].from_status, AssetStatus.ACTIVE)
        self.assertEqual(history[1].to_status, AssetStatus.UNDER_MAINTENANCE)

    def test_invalid_status_transition_rejected(self):
        """TC_M02_120: Invalid state transition (e.g. complete_maintenance on ACTIVE asset) must be rejected."""
        asset = services.create_asset(
            self.org, asset_tag="CHL-INV-001", name="Chiller Invalid Test",
            category=self.cat_hvac, site=self.site, actor=self.user
        )
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

        # complete_maintenance is only allowed from UNDER_MAINTENANCE -> ACTIVE
        with self.assertRaises(InvalidTransition) as ctx:
            services.change_status(
                asset, action="complete_maintenance", reason="FT Invalid Transition", actor=self.user
            )
        self.assertEqual(ctx.exception.code, "invalid_transition")

    def test_api_invalid_transition_returns_409(self):
        """TC_M02_120 (API): POST /api/v1/assets/{id}/transition/ with invalid action returns HTTP 409 Conflict."""
        owner_role = Role.objects.create(organization=self.org, name="Owner Role", is_owner=True)
        MembershipRole.objects.create(membership=self.membership, role=owner_role)

        asset = services.create_asset(
            self.org, asset_tag="CHL-INV-002", name="Chiller API Invalid Test",
            category=self.cat_hvac, site=self.site, actor=self.user
        )

        self.client.force_authenticate(user=self.user)
        url = f"/api/v1/assets/{asset.pk}/transition/"
        response = self.client.post(
            url,
            {"action": "complete_maintenance", "reason": "FT test invalid transition"},
            format="json",
            HTTP_X_ORGANIZATION_ID=str(self.org.pk),
        )
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["error"]["code"], "invalid_transition")
