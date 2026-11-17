"""DB-backed query-count and O(1) scaling regression tests for assets and location hierarchies."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.assets import hierarchy
from apps.assets import services as asset_services
from apps.sites import services as site_services
from apps.sites.forms import ZoneForm

pytestmark = pytest.mark.django_db


def _non_savepoint_count(ctx: CaptureQueriesContext) -> int:
    return sum(
        1
        for q in ctx.captured_queries
        if not q["sql"].lstrip().upper().startswith(("SAVEPOINT ", "RELEASE SAVEPOINT "))
    )


def test_asset_list_view_constant_queries_and_htmx_bypass(
    client, org_a, site_a1, make_category, make_asset, owner_a
):
    cat = make_category(org_a, "Rotating")
    client.force_login(owner_a)

    # Small dataset: 2 roots, each with 2 children (6 assets total)
    for idx in range(2):
        root = make_asset(org_a, site_a1, f"LIST-R-{idx}", category=cat)
        for j in range(2):
            child = make_asset(org_a, site_a1, f"LIST-R-{idx}-C-{j}", category=cat)
            hierarchy.add_component(parent=root, child=child, actor=owner_a)

    # Warm up session / template cache
    client.get("/app/assets/")
    with CaptureQueriesContext(connection) as q_small:
        r_small = client.get("/app/assets/")
    assert r_small.status_code == 200
    assert b"Assembly Root (2)" in r_small.content

    with CaptureQueriesContext(connection) as q_small_htmx:
        r_htmx = client.get(
            "/app/assets/",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="asset-list-card",
        )
    assert r_htmx.status_code == 200
    assert _non_savepoint_count(q_small_htmx) < _non_savepoint_count(q_small)

    # Larger dataset: add 8 more roots + children on page 1 (up to 10 roots total)
    for idx in range(2, 10):
        root = make_asset(org_a, site_a1, f"LIST-R-{idx}", category=cat)
        child = make_asset(org_a, site_a1, f"LIST-R-{idx}-C-0", category=cat)
        hierarchy.add_component(parent=root, child=child, actor=owner_a)

    with CaptureQueriesContext(connection) as q_large:
        r_large = client.get("/app/assets/")
    assert r_large.status_code == 200
    assert _non_savepoint_count(q_large) == _non_savepoint_count(q_small)


def test_asset_hierarchy_hub_constant_queries_across_roots(
    client, org_a, site_a1, make_category, make_asset, owner_a
):
    cat = make_category(org_a, "Pumps")
    client.force_login(owner_a)

    roots = []
    for idx in range(2):
        root = make_asset(org_a, site_a1, f"HUB-R-{idx}", category=cat)
        child = make_asset(org_a, site_a1, f"HUB-C-{idx}", category=cat)
        hierarchy.add_component(parent=root, child=child, relationship_type="REPLACEABLE_PART", actor=owner_a)
        roots.append(root)

    client.get(f"/app/assets/hierarchy/?root={roots[0].pk}")
    with CaptureQueriesContext(connection) as q_small:
        r_small = client.get(f"/app/assets/hierarchy/?root={roots[0].pk}")
    assert r_small.status_code == 200
    assert b"Root Assemblies (2)" in r_small.content

    for idx in range(2, 8):
        root = make_asset(org_a, site_a1, f"HUB-R-{idx}", category=cat)
        child = make_asset(org_a, site_a1, f"HUB-C-{idx}", category=cat)
        hierarchy.add_component(parent=root, child=child, relationship_type="COMPONENT", actor=owner_a)

    with CaptureQueriesContext(connection) as q_large:
        r_large = client.get(f"/app/assets/hierarchy/?root={roots[0].pk}")
    assert r_large.status_code == 200
    assert b"Root Assemblies (8)" in r_large.content
    assert _non_savepoint_count(q_large) == _non_savepoint_count(q_small)


def test_asset_tree_view_constant_queries_with_manage_actions(
    client, org_a, site_a1, make_category, make_asset, owner_a
):
    """Owner renders Detach button referencing node.link.parent.asset_tag without per-node queries."""
    cat = make_category(org_a, "Skids")
    client.force_login(owner_a)

    root = make_asset(org_a, site_a1, "TREE-ROOT", category=cat)
    for j in range(2):
        c = make_asset(org_a, site_a1, f"TREE-C-{j:02d}", category=cat)
        hierarchy.add_component(parent=root, child=c, actor=owner_a)

    client.get(f"/app/assets/{root.pk}/tree/")
    with CaptureQueriesContext(connection) as q_small:
        r_small = client.get(f"/app/assets/{root.pk}/tree/")
    assert r_small.status_code == 200
    assert b"Detach TREE-C-00 from TREE-ROOT?" in r_small.content

    for j in range(2, 12):
        c = make_asset(org_a, site_a1, f"TREE-C-{j:02d}", category=cat)
        hierarchy.add_component(parent=root, child=c, actor=owner_a)

    with CaptureQueriesContext(connection) as q_large:
        r_large = client.get(f"/app/assets/{root.pk}/tree/")
    assert r_large.status_code == 200
    assert b"Detach TREE-C-11 from TREE-ROOT?" in r_large.content
    assert _non_savepoint_count(q_large) == _non_savepoint_count(q_small)


def test_component_list_view_constant_queries(client, org_a, site_a1, make_category, make_asset, owner_a):
    cat = make_category(org_a, "Bearings")
    client.force_login(owner_a)

    root = make_asset(org_a, site_a1, "COMP-PARENT", category=cat)
    for j in range(2):
        c = asset_services.create_asset(
            org_a, site=site_a1, category=cat, actor=owner_a, asset_tag=f"COMP-{j:02d}", name=f"Comp {j}"
        )
        hierarchy.add_component(parent=root, child=c, actor=owner_a)

    client.get("/app/assets/components/")
    with CaptureQueriesContext(connection) as q_small:
        r_small = client.get("/app/assets/components/")
    assert r_small.status_code == 200

    for j in range(2, 12):
        c = asset_services.create_asset(
            org_a, site=site_a1, category=cat, actor=owner_a, asset_tag=f"COMP-{j:02d}", name=f"Comp {j}"
        )
        hierarchy.add_component(parent=root, child=c, actor=owner_a)

    with CaptureQueriesContext(connection) as q_large:
        r_large = client.get("/app/assets/components/")
    assert r_large.status_code == 200
    assert _non_savepoint_count(q_large) == _non_savepoint_count(q_small)


def test_site_list_api_and_zone_hierarchy_queries(
    client, as_user, org_a, owner_a, make_site, make_zone, make_asset
):
    s1 = make_site(org_a, "SQ-1")
    z_root = make_zone(s1, "Bldg", zone_type="BUILDING")
    cur = z_root
    for i in range(4):
        cur = make_zone(s1, f"Floor {i}", parent=cur)
    make_asset(org_a, s1, "SQ-AST-1", zone=cur)

    # SiteListView HTMX vs full render
    client.force_login(owner_a)
    client.get("/app/sites/")
    with CaptureQueriesContext(connection) as q_full:
        r_full = client.get("/app/sites/")
    with CaptureQueriesContext(connection) as q_htmx:
        r_htmx = client.get(
            "/app/sites/",
            HTTP_HX_REQUEST="true",
            HTTP_HX_TARGET="site-list-card",
        )
    assert r_full.status_code == 200 and r_htmx.status_code == 200
    assert _non_savepoint_count(q_htmx) < _non_savepoint_count(q_full)

    # API create / retrieve / deactivate / reactivate keep accurate annotated counts without extra fallback queries
    api = as_user(owner_a, org_a)
    r_ret = api.get(f"/api/v1/sites/{s1.pk}/")
    assert r_ret.status_code == 200
    assert r_ret.json()["zone_count"] == 5
    assert r_ret.json()["asset_count"] == 1

    with CaptureQueriesContext(connection) as q_create:
        r_create = api.post(
            "/api/v1/sites/",
            {
                "code": "SQ-NEW",
                "name": "Site New",
                "city": "Pune",
                "country": "IN",
                "timezone": "Asia/Kolkata",
            },
            format="json",
        )
    assert r_create.status_code == 201
    assert r_create.json()["zone_count"] == 0 and r_create.json()["asset_count"] == 0
    assert not any("COUNT(" in q["sql"] and "sites_zone" in q["sql"] for q in q_create.captured_queries)

    # ZoneForm excludes root and all 4 descendants in constant queries
    with CaptureQueriesContext(connection) as q_form:
        form = ZoneForm(site=s1, zone=z_root)
        list(form.fields["parent"].queryset)
    assert _non_savepoint_count(q_form) <= 2

    # validate_zone_parent checks depth/cycle across 5-level chain cleanly
    with CaptureQueriesContext(connection) as q_val:
        site_services.validate_zone_parent(s1, None, cur, "ZONE")
    assert _non_savepoint_count(q_val) == 1
