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
