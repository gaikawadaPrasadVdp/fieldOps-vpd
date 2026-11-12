import pytest
from apps.ui.context_processors import _build_tenant_nav, shell
from apps.tenancy.models import Membership
from apps.rbac.models import Role, MembershipRole
from django.test import RequestFactory
from apps.accounts.models import User

@pytest.mark.django_db
def test_verify_all_roles_sidebar_menus(org_a, make_member, owner_a):
    factory = RequestFactory()

    # Define the expected specification from the user's prompt:
    # (role_key, is_owner, expected_sections_count, expected_items_count, expected_sections)
    specs = {
        "owner": {
            "name": "Super Admin / Organization Owner",
            "is_owner": True,
            "role_key": "owner",
        },
        "admin": {
            "name": "Admin",
            "is_owner": False,
            "role_key": "admin",
        },
        "asset_manager": {
            "name": "Asset Manager",
            "is_owner": False,
            "role_key": "asset_manager",
        },
        "maintenance_planner": {
            "name": "Maintenance Planner",
            "is_owner": False,
            "role_key": "maintenance_planner",
        },
        "service_dispatcher": {
            "name": "Service Dispatcher",
            "is_owner": False,
            "role_key": "service_dispatcher",
        },
        "technician": {
            "name": "Field Technician",
            "is_owner": False,
            "role_key": "technician",
        },
        "supervisor": {
            "name": "Supervisor",
            "is_owner": False,
            "role_key": "supervisor",
        },
        "stores_manager": {
            "name": "Stores / Inventory",
            "is_owner": False,
            "role_key": "stores_manager",
        },
        "service_manager": {
            "name": "Service Manager",
            "is_owner": False,
            "role_key": "service_manager",
        },
        "auditor": {
            "name": "Auditor / Compliance",
            "is_owner": False,
            "role_key": "auditor",
        },
        "operations_manager": {
            "name": "Legacy Operations Manager",
            "is_owner": False,
            "role_key": "operations_manager",
        },
    }

    results = {}
    for key, spec in specs.items():
        if key == "owner":
            member = Membership.objects.get(organization=org_a, user=owner_a)
        else:
            member = make_member(org_a, f"{key}-test@alpha.test", key)

        nav = _build_tenant_nav(member, is_owner=spec["is_owner"])
        total_items = sum(len(items) for items in nav.values())
        results[key] = {
            "name": spec["name"],
            "sections_count": len(nav),
            "total_items": total_items,
            "sections": {sec: [it["label"] for it in items] for sec, items in nav.items()},
            "urls": {sec: [it["url"] for it in items] for sec, items in nav.items()},
        }

    # Also test Platform Super Admin
    platform_admin_user = User.objects.create(email="platform-super@nexus.test", is_platform_admin=True)
    req = factory.get("/platform/organizations/")
    req.user = platform_admin_user
    req.membership = None
    res_platform = shell(req)
    results["platform_super_admin"] = {
        "name": "Platform Super Admin",
        "sections_count": len(res_platform.get("shell_nav_sections", {})),
        "total_items": sum(len(items) for items in res_platform.get("shell_nav_sections", {}).values()),
        "sections": {sec: [it["label"] for it in items] for sec, items in res_platform.get("shell_nav_sections", {}).items()},
        "urls": {sec: [it["url"] for it in items] for sec, items in res_platform.get("shell_nav_sections", {}).items()},
    }

    # Also test Client / Requester
    client_member = make_member(org_a, "client-test@alpha.test", "client_requester")
    req_client = factory.get("/app/portal/")
    req_client.user = client_member.user
    req_client.membership = client_member
    req_client.organization = org_a
    res_client = shell(req_client)
    results["client_requester"] = {
        "name": "Client / Requester",
        "sections_count": len(res_client.get("shell_nav_sections", {})),
        "total_items": sum(len(items) for items in res_client.get("shell_nav_sections", {}).values()),
        "sections": {sec: [it["label"] for it in items] for sec, items in res_client.get("shell_nav_sections", {}).items()},
        "urls": {sec: [it["url"] for it in items] for sec, items in res_client.get("shell_nav_sections", {}).items()},
    }

    import json
    with open("sidebar_audit_results.json", "w") as f:
        json.dump(results, f, indent=2)

    assert len(results) >= 12
