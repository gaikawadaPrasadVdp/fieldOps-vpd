import pytest
from datetime import time
from apps.sites.models import Shift
from apps.sites import services as site_services
from apps.core.exceptions import Conflict, ValidationFailed

@pytest.mark.django_db
def test_create_shift_and_tenant_isolation(org_a, org_b, make_site):
    site_a = make_site(org_a, "SITE-A")
    shift = site_services.create_shift(
        org=org_a,
        site=site_a,
        name="Morning Operations",
        code="SH-MORN",
        start_time=time(6, 0),
        end_time=time(14, 30),
        days_of_week=[0, 1, 2, 3, 4],
    )
    assert shift.pk is not None
    assert shift.organization_id == org_a.pk
    assert shift.is_active is True
    assert Shift.objects.for_organization(org_b).filter(pk=shift.pk).count() == 0

@pytest.mark.django_db
def test_create_shift_cross_tenant_site_rejected(org_a, org_b, make_site):
    site_b = make_site(org_b, "SITE-B")
    with pytest.raises((Conflict, ValidationFailed, ValueError)):
        site_services.create_shift(
            org=org_a,
            site=site_b,
            name="Illegal Shift",
            code="SH-ERR",
            start_time=time(8, 0),
            end_time=time(16, 0),
        )

@pytest.mark.django_db
def test_shift_overnight_flag_calculation(org_a, make_site):
    site_a = make_site(org_a, "SITE-A")
    # 22:00 to 06:00 is overnight
    shift = site_services.create_shift(
        org=org_a,
        site=site_a,
        name="Night Shift",
        code="SH-NIGHT",
        start_time=time(22, 0),
        end_time=time(6, 0),
    )
    assert shift.is_overnight is True
