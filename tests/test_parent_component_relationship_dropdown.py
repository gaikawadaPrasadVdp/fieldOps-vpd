"""
Tests for PRD M03 2-Level Asset Hierarchy Invariants:
Ensuring Relationship Type dropdown is not selectable when an asset already
has an existing parent component relationship, and parent components cannot
be registered under another parent asset component.
"""
import pytest
from apps.assets import hierarchy, services
from apps.assets.forms import ComponentAddForm, ComponentEditForm, NewChildForm
from apps.assets.models import Asset, AssetComponent

pytestmark = pytest.mark.django_db


def test_component_edit_form_locks_relationship_type(org_a, site_a1, make_category, owner_a):
    """ComponentEditForm must have relationship_type disabled so it is not selectable."""
    cat = make_category(org_a, "Mechanical")
    root = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="AST-001", name="Root Machine")
    alpha = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="AST-005", name="Alpha")
    link = hierarchy.add_component(parent=root, child=alpha, relationship_type="COMPONENT", quantity=1, actor=owner_a)

    form = ComponentEditForm(initial={
        "relationship_type": link.relationship_type,
        "quantity": link.quantity,
        "part_number": link.part_number,
        "notes": link.notes,
    })

    assert form.fields["relationship_type"].disabled is True
    assert "disabled" in form.fields["relationship_type"].widget.attrs
    rendered = str(form["relationship_type"])
    assert "disabled" in rendered

    # When submitted, relationship_type retains its initial value and cannot be altered
    form_post = ComponentEditForm(
        data={"relationship_type": "ASSEMBLY", "quantity": 2, "part_number": "", "notes": "Updated note"},
        initial={"relationship_type": link.relationship_type}
    )
    assert form_post.is_valid(), f"Errors: {form_post.errors}"
    assert form_post.cleaned_data["relationship_type"] == "COMPONENT"


def test_component_add_form_locks_relationship_type_when_no_candidates(org_a, site_a1, make_category, owner_a):
    """When candidates queryset is empty, relationship_type and child dropdowns must be disabled."""
    empty_candidates = Asset.objects.none()
    form = ComponentAddForm(candidates=empty_candidates)

    assert form.fields["relationship_type"].disabled is True
    assert form.fields["child"].disabled is True
    assert "disabled" in str(form["relationship_type"])
    assert "disabled" in str(form["child"])


def test_component_add_form_clean_rejects_assets_with_existing_relationships(org_a, site_a1, make_category, owner_a):
    """ComponentAddForm.clean must reject child assets that are already parents or already have parents."""
    cat = make_category(org_a, "Electrical")
    root = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="ROOT-01", name="Root")
    parent_comp = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="P-COMP-01", name="Parent Comp")
    child_sub = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="C-SUB-01", name="Child Sub")

    # Link parent_comp -> child_sub
    hierarchy.add_component(parent=parent_comp, child=child_sub, actor=owner_a)

    candidates = Asset.objects.filter(pk__in=[parent_comp.pk, child_sub.pk])
    # 1. Reject attaching parent_comp (already a parent with child components)
    form1 = ComponentAddForm(data={"child": str(parent_comp.pk), "relationship_type": "COMPONENT", "quantity": 1}, candidates=candidates)
    assert not form1.is_valid()
    assert "child" in form1.errors
    assert "Nested parent assets are not permitted" in form1.errors["child"][0]

    # 2. Reject attaching child_sub (already has an existing parent component relationship)
    form2 = ComponentAddForm(data={"child": str(child_sub.pk), "relationship_type": "COMPONENT", "quantity": 1}, candidates=candidates)
    assert not form2.is_valid()
    assert "child" in form2.errors
    assert "already has an existing parent component relationship" in form2.errors["child"][0]


def test_new_child_form_locks_relationship_type_if_parent_is_already_component(org_a, site_a1, make_category, owner_a):
    """NewChildForm locks relationship_type if the parent equipment is already a child component."""
    cat = make_category(org_a, "Pumps")
    root = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="ROOT-PUMP", name="Root Pump")
    alpha = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="AST-005", name="Alpha")
    hierarchy.add_component(parent=root, child=alpha, actor=owner_a)

    form = NewChildForm(parent=alpha)
    assert form.fields["relationship_type"].disabled is True
    assert "disabled" in str(form["relationship_type"])


def test_asset_detail_hierarchy_tab_renders_locked_relationship_for_existing_relationship(client, owner_a, org_a, site_a1, make_category):
    """Asset detail page renders locked relationship settings when asset has an existing parent relationship."""
    cat = make_category(org_a, "HVAC")
    root = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="AST-001", name="Root Chiller")
    alpha = services.create_asset(org_a, site=site_a1, category=cat, actor=owner_a, asset_tag="AST-005", name="Alpha")
    hierarchy.add_component(parent=root, child=alpha, relationship_type="COMPONENT", quantity=1, actor=owner_a)

    client.force_login(owner_a)
    response = client.get(f"/app/assets/{alpha.pk}/?tab=hierarchy")
    assert response.status_code == 200
    html = response.content.decode()

    # Relationship Type dropdown must be locked / disabled
    assert "Relationship Type is locked" in html
    assert 'name="relationship_type"' in html
    assert "disabled" in html
