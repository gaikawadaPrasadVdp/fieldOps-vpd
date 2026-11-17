from django.db import migrations


def ensure_client_portal_permissions_and_grants(apps, schema_editor):
    Permission = apps.get_model("rbac", "Permission")
    Role = apps.get_model("rbac", "Role")
    RolePermission = apps.get_model("rbac", "RolePermission")
    Membership = apps.get_model("tenancy", "Membership")
    MembershipRole = apps.get_model("rbac", "MembershipRole")
    Organization = apps.get_model("tenancy", "Organization")
    PortalAccount = apps.get_model("portal", "PortalAccount")
    PortalAssetGrant = apps.get_model("portal", "PortalAssetGrant")
    Asset = apps.get_model("assets", "Asset")

    # 1. Ensure permissions exist in Permission catalog
    portal_perms_data = [
        ("portal.request.create", "portal", "Submit client service requests through the portal"),
        ("portal.request.view", "portal", "View own client portal requests and dashboard"),
        ("portal.request.confirm", "portal", "Confirm resolution or request rework on own portal requests"),
        ("portal.manage", "portal", "Manage client portal accounts and access"),
    ]
    perm_objs = {}
    for code, mod, desc in portal_perms_data:
        p, _ = Permission.objects.get_or_create(code=code, defaults={"module": mod, "description": desc})
        perm_objs[code] = p

    # 2. For every organization, ensure client_requester has the portal permissions
    for org in Organization.objects.all():
        role = Role.objects.filter(organization=org, system_key="client_requester").first()
        if not role:
            role = Role.objects.create(
                organization=org,
                name="Client / Requester",
                description="External requester raising service requests and tracking status in the client portal.",
                system_key="client_requester",
                is_owner=False,
            )
        for code in ["portal.request.create", "portal.request.view", "portal.request.confirm"]:
            if code in perm_objs:
                RolePermission.objects.get_or_create(role=role, permission=perm_objs[code])

        # Also ensure Owner role has portal permissions
        owner_role = Role.objects.filter(organization=org, is_owner=True).first()
        if owner_role:
            for code in ["portal.request.create", "portal.request.view", "portal.request.confirm", "portal.manage"]:
                if code in perm_objs:
                    RolePermission.objects.get_or_create(role=owner_role, permission=perm_objs[code])

    # 3. For any membership with client_requester role or client.requester email, ensure PortalAccount & asset grants
    client_memberships = list(
        Membership.objects.filter(membership_roles__role__system_key="client_requester").select_related("user", "organization")
    )
    # Also find any user with client.requester in email
    for mem in Membership.objects.filter(user__email__icontains="client.requester").select_related("user", "organization"):
        if mem not in client_memberships:
            client_memberships.append(mem)

    for mem in client_memberships:
        org = mem.organization
        acc, _ = PortalAccount.objects.get_or_create(
            organization=org,
            membership=mem,
            defaults={
                "company_name": getattr(mem.user, "full_name", "") or org.name,
                "is_enabled": True,
            },
        )
        if not acc.is_enabled:
            acc.is_enabled = True
            acc.save(update_fields=["is_enabled"])

        # Grant active assets
        for ast in Asset.objects.filter(organization=org).exclude(status__in=["RETIRED", "DISPOSED"]):
            PortalAssetGrant.objects.get_or_create(
                organization=org,
                portal_account=acc,
                asset=ast,
            )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0005_auto_provision_client_portal_accounts"),
        ("rbac", "0001_initial"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(ensure_client_portal_permissions_and_grants, reverse_code=reverse_noop),
    ]
