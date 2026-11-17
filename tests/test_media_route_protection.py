import os
import pytest
from django.conf import settings
from django.test import override_settings
from rest_framework_simplejwt.tokens import RefreshToken

@pytest.mark.django_db
def test_media_route_protection_sec05(client, org_a, org_b, owner_a, owner_b, tmp_path):
    # Set up a test media file in tmp_path under org_a's directory
    org_a_dir = tmp_path / "organizations" / str(org_a.pk) / "2026"
    org_a_dir.mkdir(parents=True, exist_ok=True)
    test_file = org_a_dir / "secret_document.txt"
    test_file.write_text("Confidential Enterprise Asset Report")

    relative_media_path = f"/media/organizations/{org_a.pk}/2026/secret_document.txt"

    with override_settings(DEBUG=True, MEDIA_ROOT=str(tmp_path)):
        # 1. Unauthenticated request via browser -> redirect to login (SEC-05)
        res_anon = client.get(relative_media_path)
        assert res_anon.status_code == 302
        assert "/accounts/login/" in res_anon["Location"]

        # 2. Unauthenticated request via API (Accept: application/json) -> 401 Unauthorized
        res_anon_api = client.get(relative_media_path, HTTP_ACCEPT="application/json")
        assert res_anon_api.status_code == 401

        # 3. Authenticated request from org_a member -> 200 OK
        client.force_login(owner_a)
        res_owner_a = client.get(relative_media_path)
        assert res_owner_a.status_code == 200
        assert b"Confidential Enterprise Asset Report" in b"".join(res_owner_a.streaming_content)

        # 4. Cross-tenant request from org_b member -> 403 Forbidden
        client.force_login(owner_b)
        res_owner_b = client.get(relative_media_path)
        assert res_owner_b.status_code == 403

        # 5. Bearer token authenticated API request from org_a member -> 200 OK
        client.logout()
        token_a = str(RefreshToken.for_user(owner_a).access_token)
        res_token_a = client.get(
            relative_media_path,
            HTTP_AUTHORIZATION=f"Bearer {token_a}",
            HTTP_X_ORGANIZATION=str(org_a.pk),
        )
        assert res_token_a.status_code == 200

        # 6. Bearer token authenticated API request from org_b member -> 403 Forbidden
        token_b = str(RefreshToken.for_user(owner_b).access_token)
        res_token_b = client.get(
            relative_media_path,
            HTTP_AUTHORIZATION=f"Bearer {token_b}",
            HTTP_X_ORGANIZATION=str(org_b.pk),
        )
        assert res_token_b.status_code == 403

        # 7. Malformed organization ID in path -> 404 Not Found
        client.force_login(owner_a)
        res_bad_uuid = client.get("/media/organizations/not-a-uuid/2026/secret_document.txt")
        assert res_bad_uuid.status_code == 404

        # 8. Superuser can access media cross-tenant
        owner_a.is_superuser = True
        owner_a.save()
        res_super = client.get(relative_media_path)
        assert res_super.status_code == 200
