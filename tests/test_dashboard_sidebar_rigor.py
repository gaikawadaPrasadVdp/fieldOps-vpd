import pytest
from django.test import Client
from django.urls import reverse
from apps.tenancy.models import Membership
from apps.rbac.models import Role, MembershipRole
from apps.accounts.models import User
from apps.portal.models import PortalAccount

@pytest.mark.django_db
def test_all_dashboards_render_sidebar_for_roles(org_a, make_member, owner_a):
    client = Client()

    dashboards = [
        ("ui:home", "Operations Overview", "/app/"),
        ("incidents:dashboard", "Incident Dashboard", "/app/incidents/dashboard/"),
        ("dashboards:hub", "Analytics Hub", "/app/dashboards/"),
        ("dashboards:snapshot_list", "KPI Snapshots", "/app/dashboards/snapshots/"),
        ("dashboards:my_work", "My Work Cockpit", "/app/dashboards/my-work/"),
    ]

    roles_to_test = [
        ("owner", True),
        ("admin", False),
        ("asset_manager", False),
        ("maintenance_planner", False),
        ("service_dispatcher", False),
        ("technician", False),
        ("supervisor", False),
        ("stores_manager", False),
        ("service_manager", False),
        ("auditor", False),
        ("operations_manager", False),
    ]

    for role_key, is_owner in roles_to_test:
        if role_key == "owner":
            member = Membership.objects.get(organization=org_a, user=owner_a)
        else:
            member = make_member(org_a, f"dash-{role_key}@alpha.test", role_key)

        client.force_login(member.user)

        # Check each dashboard page
        for view_name, label, path in dashboards:
            url = reverse(view_name)
            resp = client.get(url)

            # If user has access (200), verify the sidebar contains sections and items
            if resp.status_code == 200:
                assert "fx-sidebar" in resp.content.decode()
                sections = resp.context.get("shell_nav_sections", {})
                assert len(sections) > 0, f"Role {role_key} has no sidebar sections on {view_name}"

                # Verify each section in the sidebar is rendered in HTML
                for sec_name, items in sections.items():
                    assert sec_name.encode() in resp.content or sec_name.replace("&", "&amp;").encode() in resp.content
                    for item in items:
                        assert item["label"].encode() in resp.content or item["label"].replace("&", "&amp;").encode() in resp.content

    # Also test Client Portal dashboard
    client_member = make_member(org_a, "dash-client@alpha.test", "client_requester")
    PortalAccount.objects.create(organization=org_a, membership=client_member, company_name="Acme Corp")
    client.force_login(client_member.user)
    portal_resp = client.get(reverse("portal:dashboard"))
    assert portal_resp.status_code == 200
    assert "fx-sidebar" in portal_resp.content.decode()
    sections = portal_resp.context.get("shell_nav_sections", {})
    assert "Portal" in sections
    assert len(sections["Portal"]) == 3
    assert b"Client Portal" in portal_resp.content
    assert b"My Requests" in portal_resp.content
    assert b"New Request" in portal_resp.content
