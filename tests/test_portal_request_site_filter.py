import pytest
from django.contrib.auth import get_user_model
from apps.assets.models import Asset
from apps.portal.forms import PortalServiceRequestForm
from apps.portal.models import PortalAccount
from apps.portal import services as portal_services
from apps.rbac import services as rbac
from apps.tenancy.models import Membership

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "Correct-Horse-Battery-9"


@pytest.fixture
def make_portal_client(db):
    def _make(org, email="client.filter@acme.test", company_name="Acme Corporation"):
        user = User.objects.filter(email=email).first() or User.objects.create_user(
            email=email,
            password=PASSWORD,
            full_name="Portal Tester",
        )
        membership, _ = Membership.objects.unscoped().get_or_create(
            organization=org,
            user=user,
            defaults={"status": Membership.Status.ACTIVE, "job_title": "Requester"},
        )
        membership.status = Membership.Status.ACTIVE
        membership.save(update_fields=["status"])

        role = rbac.system_role_by_key(org, "client_requester")
        rbac.set_membership_roles(membership, [role], actor=None, system=True)

        account, _ = PortalAccount.objects.unscoped().get_or_create(
            organization=org,
            membership=membership,
            defaults={"company_name": company_name, "is_enabled": True},
        )
        account.is_enabled = True
        account.save(update_fields=["is_enabled"])
        return user, membership, account

    return _make


def test_portal_form_populates_sites_from_granted_assets(org_a, site_a1, site_a2, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.site1@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-S1-01")
    asset_2 = make_asset(org_a, site_a2, "ASSET-S2-01")

    # Grant only asset_1 (from site_a1)
    portal_services.grant_portal_asset(account, asset_1)

    form = PortalServiceRequestForm(organization=org_a, membership=membership)
    site_choices = list(form.fields["site"].queryset)
    assert site_a1 in site_choices
    assert site_a2 not in site_choices

    # Grant asset_2 (from site_a2)
    portal_services.grant_portal_asset(account, asset_2)
    form2 = PortalServiceRequestForm(organization=org_a, membership=membership)
    site_choices2 = list(form2.fields["site"].queryset)
    assert site_a1 in site_choices2
    assert site_a2 in site_choices2


def test_portal_form_asset_widget_has_data_site_id(org_a, site_a1, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.widget@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-WIDGET-01")
    portal_services.grant_portal_asset(account, asset_1)

    form = PortalServiceRequestForm(organization=org_a, membership=membership)
    rendered_asset = form["asset"].as_widget()
    assert f'data-site-id="{site_a1.pk}"' in rendered_asset


def test_portal_form_validation_succeeds_with_matching_site(org_a, site_a1, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.valid@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-MATCH-01")
    portal_services.grant_portal_asset(account, asset_1)

    data = {
        "title": "HVAC Fan Failure",
        "description": "HVAC unit fan failure observed during inspection",
        "site": str(site_a1.pk),
        "asset": str(asset_1.pk),
        "severity": "MEDIUM",
        "service_impact": "NONE",
    }
    form = PortalServiceRequestForm(data, organization=org_a, membership=membership)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["site"] == site_a1
    assert form.cleaned_data["asset"] == asset_1


def test_portal_form_validation_fails_with_mismatched_site(org_a, site_a1, site_a2, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.mismatch@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-SITE1")
    asset_2 = make_asset(org_a, site_a2, "ASSET-SITE2")
    portal_services.grant_portal_asset(account, asset_1)
    portal_services.grant_portal_asset(account, asset_2)

    # Pick site_a2, but asset_1 (which is at site_a1)
    data = {
        "title": "Wrong Site Asset Selection",
        "site": str(site_a2.pk),
        "asset": str(asset_1.pk),
        "severity": "MEDIUM",
        "service_impact": "NONE",
    }
    form = PortalServiceRequestForm(data, organization=org_a, membership=membership)
    assert not form.is_valid()
    assert "asset" in form.errors
    assert "The selected asset does not belong to the chosen site / location." in form.errors["asset"]


def test_portal_form_validation_fails_without_site(org_a, site_a1, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.nosite@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-NOSITE")
    portal_services.grant_portal_asset(account, asset_1)

    data = {
        "title": "General Maintenance Without Site Filter",
        "description": "General maintenance required for scheduled check",
        "site": "",
        "asset": str(asset_1.pk),
        "severity": "LOW",
        "service_impact": "NONE",
    }
    form = PortalServiceRequestForm(data, organization=org_a, membership=membership)
    assert not form.is_valid()
    assert "site" in form.errors
    assert "Please select a site / location." in str(form.errors["site"])


def test_portal_request_create_view_submits_with_site(client, org_a, site_a1, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.view@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-VIEW-01")
    portal_services.grant_portal_asset(account, asset_1)

    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org_a.id)
    session.save()

    # GET page
    res_get = client.get("/app/portal/requests/new/")
    assert res_get.status_code == 200
    assert b"Site / Location" in res_get.content
    assert f'data-site-id="{site_a1.pk}"'.encode() in res_get.content

    # POST submission
    post_data = {
        "title": "Pressure gauge replacement",
        "description": "Pressure gauge replacement needed immediately",
        "site": str(site_a1.pk),
        "asset": str(asset_1.pk),
        "severity": "HIGH",
        "service_impact": "PARTIAL_OUTAGE",
        "impact_notes": "Line operates at half capacity",
    }
    res_post = client.post("/app/portal/requests/new/", post_data)
    form_errors = res_post.context["form"].errors if res_post.context else None
    assert res_post.status_code == 302, f"POST failed with errors: {form_errors}"
    assert "/app/portal/?created=" in res_post.url


def test_portal_form_includes_newly_added_site_without_assets(org_a, site_a1, make_asset, make_portal_client):
    from apps.sites.models import Site
    user, membership, account = make_portal_client(org_a, "client.newsite@acme.test")
    asset_1 = make_asset(org_a, site_a1, "ASSET-S1-01")
    portal_services.grant_portal_asset(account, asset_1)

    # Newly added site with 0 assets
    new_site = Site.objects.create(
        organization=org_a,
        code="NEW-FAC-01",
        name="Newly Added Facility",
        status=Site.Status.ACTIVE,
    )

    form = PortalServiceRequestForm(organization=org_a, membership=membership)
    site_choices = list(form.fields["site"].queryset)
    assert site_a1 in site_choices
    assert new_site in site_choices


def test_portal_form_new_organization_scenario_populates_all_active_sites(make_portal_client):
    from apps.tenancy.models import Organization
    from apps.sites.models import Site
    new_org = Organization.objects.create(name="Fresh Client Org", slug="fresh-client-org")
    site_1 = Site.objects.create(organization=new_org, code="FRESH-01", name="Fresh Site 1", status=Site.Status.ACTIVE)
    site_2 = Site.objects.create(organization=new_org, code="FRESH-02", name="Fresh Site 2", status=Site.Status.ACTIVE)
    site_inactive = Site.objects.create(organization=new_org, code="INACT-01", name="Inactive Site", status=Site.Status.INACTIVE)

    user, membership, account = make_portal_client(new_org, "client.fresh@fresh.test")

    form = PortalServiceRequestForm(organization=new_org, membership=membership)
    site_choices = list(form.fields["site"].queryset)
    assert site_1 in site_choices
    assert site_2 in site_choices
    assert site_inactive not in site_choices


def test_portal_dashboard_success_banner_renders_only_up_to_token(client, org_a, site_a1, make_asset, make_portal_client):
    user, membership, account = make_portal_client(org_a, "client.banner@acme.test")
    client.force_login(user)
    session = client.session
    session["active_org_id"] = str(org_a.id)
    session.save()

    res = client.get("/app/portal/?created=SR-000099")
    assert res.status_code == 200
    html = res.content.decode("utf-8")
    assert "SR-000099" in html
    assert "Service Request Created Successfully!" in html
    assert "Reference number:" in html
    assert "PostgreSQL" not in html
    assert "queued for operations triage" not in html

