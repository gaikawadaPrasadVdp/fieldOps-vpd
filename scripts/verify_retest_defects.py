import os
import sys
import json

src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
import django
django.setup()

from apps.core.net import axes_username
from rest_framework.test import APIRequestFactory
from apps.core.middleware import RequestIdMiddleware

print("=" * 70)
print("1. VERIFYING DEF-001 (TC_AUTH_051: Per-user lockout in API token requests)")
print("=" * 70)
factory = APIRequestFactory()

# Brute force attempt
req1 = factory.post("/api/v1/auth/token/", {"email": "brute@force.example.com", "password": "wrong"}, format="json")
user1 = axes_username(req1)
print(f"req1 (attacker) extracted username: '{user1}'")
assert user1 == "brute@force.example.com", f"Expected brute@force.example.com, got {user1}"

# Legitimate owner attempt
req2 = factory.post("/api/v1/auth/token/", {"email": "owner@apexindustrial.example.com", "password": "correct"}, format="json")
user2 = axes_username(req2)
print(f"req2 (owner) extracted username:    '{user2}'")
assert user2 == "owner@apexindustrial.example.com", f"Expected owner@apexindustrial.example.com, got {user2}"

print(" [PASS] DEF-001: Distinct usernames correctly extracted from JSON request body!")
print("        Failed logins for brute@force.example.com will NO LONGER lock out other accounts behind the same IP.")

print("\n" + "=" * 70)
print("2. VERIFYING DEF-004 (TC_SEC_039 & TC_SEC_040: Oversized body rejection)")
print("=" * 70)
middleware = RequestIdMiddleware(lambda r: None)

# 5 MB request (TC_SEC_039)
req_5mb = factory.post("/api/v1/sites/", {"data": "x"}, format="json")
req_5mb.META["CONTENT_LENGTH"] = str(5 * 1024 * 1024 + 100) # 5MB + 100 bytes
resp_5mb = middleware(req_5mb)
print(f"5 MB request status code:       {resp_5mb.status_code}")
print(f"5 MB request Content-Type:      {resp_5mb['Content-Type']}")
print(f"5 MB request Connection header: {resp_5mb.get('Connection')}")
body_5mb = json.loads(resp_5mb.content)
print(f"5 MB error envelope:            {body_5mb['error']}")

assert resp_5mb.status_code == 413, f"Expected 413, got {resp_5mb.status_code}"
assert "error" in body_5mb, "Missing error key in response"
assert body_5mb["error"]["code"] == "request_entity_too_large", "Wrong error code"
assert "request_id" in body_5mb["error"], "Missing request_id inside error object"
assert resp_5mb.get("Connection") == "close", "Missing Connection: close header"

# 6 MB request (TC_SEC_040)
req_6mb = factory.post("/api/v1/sites/", {"data": "x"}, format="json")
req_6mb.META["CONTENT_LENGTH"] = str(6 * 1024 * 1024)
resp_6mb = middleware(req_6mb)
print(f"\n6 MB request status code:       {resp_6mb.status_code}")
print(f"6 MB request Connection header: {resp_6mb.get('Connection')}")
assert resp_6mb.status_code == 413
assert resp_6mb.get("Connection") == "close"

print(" [PASS] DEF-004: 5MB & 6MB oversized payloads immediately rejected with HTTP 413 JSON error envelope and Connection: close!")

print("\n" + "=" * 70)
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
print("=" * 70)
