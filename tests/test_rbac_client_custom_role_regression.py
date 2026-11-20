"""Regression tests for RBAC Matrix Client Custom Role Permissions.

Covers:
- RBM-196: Client / Requester with custom role reads /users/ (needs 'user.view') -> HTTP 200
- RBM-197: Client / Requester with custom role reads /roles/ (needs 'role.view') -> HTTP 200
- RBM-203: Client / Requester with custom role reads /checklist-templates/ (needs 'checklist.view') -> HTTP 200
- RBM-204: Client / Requester with custom role reads /organization/ (needs 'organization.view') -> HTTP 200
"""
import uuid
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.portal.models import PortalAccount
from apps.rbac.models import MembershipRole, Permission, Role, RolePermission
from apps.tenancy.models import Membership, Organization

pytestmark = pytest.mark.django_db


def test_rbac_client_custom_role_access():
    """Verify that a client user with custom granted permissions can access tenant API endpoints."""
    org = Organization.objects.create(name="RBM Test Org", slug=f"rbm-test-{uuid.uuid4().hex[:6]}")
    user = User.objects.create_user(email=f"raveen-{uuid.uuid4().hex[:6]}@client.test", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    PortalAccount.objects.create(organization=org, membership=membership, company_name="Client Corp")

    # Create custom role granting user.view, role.view, checklist.view, organization.view
    custom_role = Role.objects.create(
        organization=org,
        name="Custom - Raveen Fernando",
        system_key=f"custom_raveen_{uuid.uuid4().hex[:6]}",
    )
    test_perms = ["user.view", "role.view", "checklist.view", "organization.view"]
    for code in test_perms:
        perm = Permission.objects.get(code=code)
        RolePermission.objects.create(role=custom_role, permission=perm)
    MembershipRole.objects.create(membership=membership, role=custom_role)

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # RBM-196: GET /api/v1/users/
    resp_users = client.get("/api/v1/users/")
    assert resp_users.status_code == 200, f"RBM-196 failed: {resp_users.status_code} {resp_users.data}"

    # RBM-197: GET /api/v1/roles/
    resp_roles = client.get("/api/v1/roles/")
    assert resp_roles.status_code == 200, f"RBM-197 failed: {resp_roles.status_code} {resp_roles.data}"

    # RBM-203: GET /api/v1/checklist-templates/
    resp_checklists = client.get("/api/v1/checklist-templates/")
    assert resp_checklists.status_code == 200, f"RBM-203 failed: {resp_checklists.status_code} {resp_checklists.data}"

    # RBM-204: GET /api/v1/organization/
    resp_org = client.get("/api/v1/organization/")
    assert resp_org.status_code == 200, f"RBM-204 failed: {resp_org.status_code} {resp_org.data}"


def test_rbac_site_scoped_custom_role_honours_org_level_permissions():
    """DEF-024 / RBM-196, RBM-197, RBM-203, RBM-204:
    Site-scoped role assignments honour organization-level permissions granted through custom role."""
    from apps.sites.models import Site

    org = Organization.objects.create(name="Site-Scoped RBAC Org", slug=f"site-scoped-{uuid.uuid4().hex[:6]}")
    site = Site.objects.create(organization=org, name="Alpha Site", code=f"site-{uuid.uuid4().hex[:4]}")
    user = User.objects.create_user(email=f"scoped-{uuid.uuid4().hex[:6]}@client.test", password="Password123!")
    membership = Membership.objects.create(organization=org, user=user, status=Membership.Status.ACTIVE)
    PortalAccount.objects.create(organization=org, membership=membership, company_name="Scoped Client Corp")

    custom_role = Role.objects.create(
        organization=org,
        name="Custom Site Scoped Role",
        system_key=f"custom_site_scoped_{uuid.uuid4().hex[:6]}",
    )
    test_perms = ["user.view", "role.view", "checklist.view", "organization.view"]
    for code in test_perms:
        perm = Permission.objects.get(code=code)
        RolePermission.objects.create(role=custom_role, permission=perm)

    # Assign role scoped to a specific site
    MembershipRole.objects.create(membership=membership, role=custom_role, site=site)

    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION"] = org.slug

    # RBM-196: GET /api/v1/users/ -> HTTP 200
    resp_users = client.get("/api/v1/users/")
    assert resp_users.status_code == 200, f"RBM-196 site-scoped failed: {resp_users.status_code} {resp_users.data}"

    # RBM-197: GET /api/v1/roles/ -> HTTP 200
    resp_roles = client.get("/api/v1/roles/")
    assert resp_roles.status_code == 200, f"RBM-197 site-scoped failed: {resp_roles.status_code} {resp_roles.data}"

    # RBM-203: GET /api/v1/checklist-templates/ -> HTTP 200
    resp_checklists = client.get("/api/v1/checklist-templates/")
    assert resp_checklists.status_code == 200, f"RBM-203 site-scoped failed: {resp_checklists.status_code} {resp_checklists.data}"

    # RBM-204: GET /api/v1/organization/ -> HTTP 200
    resp_org = client.get("/api/v1/organization/")
    assert resp_org.status_code == 200, f"RBM-204 site-scoped failed: {resp_org.status_code} {resp_org.data}"

    # Denied scenario: User without role gets 403
    unauth_user = User.objects.create_user(email=f"unauth-{uuid.uuid4().hex[:6]}@client.test", password="Password123!")
    Membership.objects.create(organization=org, user=unauth_user, status=Membership.Status.ACTIVE)
    unauth_client = APIClient()
    unauth_client.force_authenticate(user=unauth_user)
    unauth_client.defaults["HTTP_X_ORGANIZATION"] = org.slug
    assert unauth_client.get("/api/v1/users/").status_code == 403
    assert unauth_client.get("/api/v1/roles/").status_code == 403
    assert unauth_client.get("/api/v1/checklist-templates/").status_code == 403
