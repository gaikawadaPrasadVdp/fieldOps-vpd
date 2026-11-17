import importlib
import pytest
from apps.contracts import services as contract_services
from apps.contracts.models import ServiceProvider
from apps.contracts.forms import ProviderForm
from apps.contracts.api_views import ProviderWriteSerializer
from apps.core.exceptions import ValidationFailed
from django.core.exceptions import ValidationError


@pytest.mark.django_db
def test_create_provider_blocks_xss_script_payload(org_a, owner_a):
    xss_payload = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    
    # 1. Service layer blocks XSS
    with pytest.raises(ValidationFailed) as exc:
        contract_services.create_provider(org_a, name=xss_payload, actor=owner_a)
    assert "HTML tags or script injection patterns" in str(exc.value)

    # 2. Form layer blocks XSS
    form = ProviderForm(data={"name": xss_payload})
    assert not form.is_valid()
    assert any("HTML tags or script injection patterns" in str(err) for err in form.errors.get("name", []))

    # 3. Serializer layer blocks XSS
    serializer = ProviderWriteSerializer(data={"name": xss_payload})
    assert not serializer.is_valid()
    assert any("HTML tags or script injection patterns" in str(err) for err in serializer.errors.get("name", []))


@pytest.mark.django_db
def test_create_provider_blocks_repetitive_fuzzing_buffer_overflow(org_a, owner_a):
    repetitive_payload = "1106142900BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
    
    # 1. Service layer blocks repetitive characters
    with pytest.raises(ValidationFailed) as exc:
        contract_services.create_provider(org_a, name=repetitive_payload, actor=owner_a)
    assert "repetitive" in str(exc.value)

    # 2. Form layer blocks repetitive characters
    form = ProviderForm(data={"name": repetitive_payload})
    assert not form.is_valid()
    assert any("repetitive" in str(err) for err in form.errors.get("name", []))


@pytest.mark.django_db
def test_create_provider_blocks_invalid_characters(org_a, owner_a):
    invalid_name = "Provider $$$ %%%"
    with pytest.raises(ValidationFailed) as exc:
        contract_services.create_provider(org_a, name=invalid_name, actor=owner_a)
    assert "invalid characters" in str(exc.value)


@pytest.mark.django_db
def test_create_provider_accepts_valid_business_names(org_a, owner_a):
    valid_names = [
        "Apex Industrial Technologies Ltd.",
        "Siemens & Co. (UK)",
        "GE Healthcare - Service Division",
        "A-1 Machinery & Equipment Co.",
        "BAPI Provider 1106142839",
    ]
    for name in valid_names:
        p = contract_services.create_provider(org_a, name=name, actor=owner_a)
        assert p.pk is not None
        assert p.name == name
        assert p.is_active is True


@pytest.mark.django_db
def test_cleanup_fuzzed_providers_migration(org_a):
    mig = importlib.import_module("apps.contracts.migrations.0004_cleanup_fuzzed_providers")
    cleanup_fuzzed_providers = mig.cleanup_fuzzed_providers
    from django.apps import apps

    # Create test fuzzed providers
    bad_xss = ServiceProvider.objects.create(
        organization=org_a,
        name='<script>alert(1)</script>"><img src=x onerror=alert(2)>',
        is_active=True,
    )
    bad_repetition = ServiceProvider.objects.create(
        organization=org_a,
        name="1106142900BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        is_active=True,
    )
    good_provider = ServiceProvider.objects.create(
        organization=org_a,
        name="Apex Industrial Technologies",
        is_active=True,
    )

    # Run cleanup migration function
    cleanup_fuzzed_providers(apps, None)

    # Verify bad ones without agreements were deleted
    assert not ServiceProvider.objects.filter(pk=bad_xss.pk).exists()
    assert not ServiceProvider.objects.filter(pk=bad_repetition.pk).exists()
    # Verify good one remained
    assert ServiceProvider.objects.filter(pk=good_provider.pk).exists()


@pytest.mark.django_db
def test_cleanup_fuzzed_providers_management_command(org_a):
    from io import StringIO
    from django.core.management import call_command

    bad_xss = ServiceProvider.objects.create(
        organization=org_a,
        name='<script>alert(1)</script>"><img src=x onerror=alert(2)>',
        is_active=True,
    )
    bapi_prov = ServiceProvider.objects.create(
        organization=org_a,
        name="BAPI Provider 1106142839",
        is_active=True,
    )

    out = StringIO()
    call_command("cleanup_fuzzed_providers", "--include-bapi", stdout=out)
    output = out.getvalue()

    assert "Deleted unlinked fuzzed provider" in output
    assert not ServiceProvider.objects.filter(pk=bad_xss.pk).exists()
    assert not ServiceProvider.objects.filter(pk=bapi_prov.pk).exists()

