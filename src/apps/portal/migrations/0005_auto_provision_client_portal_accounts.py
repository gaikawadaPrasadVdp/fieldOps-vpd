from django.db import migrations


def auto_provision_existing_clients(apps, schema_editor):
    Membership = apps.get_model("tenancy", "Membership")
    MembershipRole = apps.get_model("rbac", "MembershipRole")
    PortalAccount = apps.get_model("portal", "PortalAccount")
    PortalAssetGrant = apps.get_model("portal", "PortalAssetGrant")
    Asset = apps.get_model("assets", "Asset")

    for mr in MembershipRole.objects.filter(role__system_key="client_requester").select_related("membership", "membership__user", "membership__organization"):
        mem = mr.membership
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

        # Associate available active assets if no grants exist
        if not PortalAssetGrant.objects.filter(portal_account=acc).exists():
            for asset in Asset.objects.filter(organization=org).exclude(status__in=["RETIRED", "DISPOSED"]):
                PortalAssetGrant.objects.get_or_create(
                    organization=org,
                    portal_account=acc,
                    asset=asset,
                )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_provision_fresh_client_account"),
    ]

    operations = [
        migrations.RunPython(auto_provision_existing_clients, noop),
    ]
