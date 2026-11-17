from django.db import migrations, models


def enable_auto_grant_and_sync_existing_portal_accounts(apps, schema_editor):
    PortalAccount = apps.get_model("portal", "PortalAccount")
    PortalAssetGrant = apps.get_model("portal", "PortalAssetGrant")
    Asset = apps.get_model("assets", "Asset")
    MembershipRole = apps.get_model("rbac", "MembershipRole")

    for account in PortalAccount.objects.select_related("membership", "organization").all():
        if not account.auto_grant_assets:
            account.auto_grant_assets = True
            account.save(update_fields=["auto_grant_assets"])

        role_sites = list(
            MembershipRole.objects.filter(
                membership=account.membership,
                role__system_key="client_requester",
            ).values_list("site_id", flat=True)
        )
        assets_qs = Asset.objects.filter(organization=account.organization).exclude(
            status__in=["RETIRED", "DISPOSED"]
        )
        if role_sites and None not in role_sites:
            assets_qs = assets_qs.filter(site_id__in=role_sites)

        for asset in assets_qs:
            PortalAssetGrant.objects.get_or_create(
                organization=account.organization,
                portal_account=account,
                asset=asset,
            )


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0006_ensure_client_portal_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="portalaccount",
            name="auto_grant_assets",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            enable_auto_grant_and_sync_existing_portal_accounts,
            reverse_code=reverse_noop,
        ),
    ]
