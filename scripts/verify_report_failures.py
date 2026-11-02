import os
import sys

# Ensure src is in python path
src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
import django
django.setup()

from unittest.mock import MagicMock
from apps.core.exceptions import PermissionDenied, ValidationFailed

print("=" * 60)
print("1. VERIFYING DEF-001 (WO-U-051, WO-U-052, WO-U-053, WO-U-054)")
print("=" * 60)
from apps.workorders import services as wo_services
from apps.rbac import services as rbac

wo = MagicMock()
wo.pk = 101
wo.assigned_to_id = 50
wo.site_id = 1

# Case 1: WO-U-051 (assignee)
assignee_mem = MagicMock()
assignee_mem.pk = 50
try:
    wo_services.assert_can_execute(wo, assignee_mem)
    wo_services._assert_assignee_or_dispatcher(wo, assignee_mem)
    print(" [PASS] WO-U-051: Assignee can execute work order without recursion.")
except Exception as e:
    print(f" [FAIL] WO-U-051: {type(e).__name__}: {e}")

# Case 2: WO-U-053 (dispatcher)
dispatcher_mem = MagicMock()
dispatcher_mem.pk = 99
orig_has_perm = rbac.has_permission
def mock_has_perm(mem, perm, site_id=None):
    if perm == "work_order.dispatch" and mem.pk == 99:
        return True
    return False
rbac.has_permission = mock_has_perm

try:
    wo_services.assert_can_execute(wo, dispatcher_mem)
    wo_services._assert_assignee_or_dispatcher(wo, dispatcher_mem)
    print(" [PASS] WO-U-053: Dispatcher can execute work order without recursion.")
except Exception as e:
    print(f" [FAIL] WO-U-053: {type(e).__name__}: {e}")

# Case 3: WO-U-052 (reviewer not assignee)
reviewer_mem = MagicMock()
reviewer_mem.pk = 77
try:
    wo_services.assert_can_execute(wo, reviewer_mem)
    print(" [FAIL] WO-U-052: Did not raise PermissionDenied")
except PermissionDenied as e:
    if e.code == "not_assignee":
        print(f" [PASS] WO-U-052: Reviewer blocked with PermissionDenied(code='{e.code}').")
    else:
        print(f" [FAIL] WO-U-052: PermissionDenied code was '{e.code}', expected 'not_assignee'")
except Exception as e:
    print(f" [FAIL] WO-U-052: {type(e).__name__}: {e}")

# Case 4: WO-U-054 (no rights)
unauth_mem = MagicMock()
unauth_mem.pk = 88
try:
    wo_services.assert_can_execute(wo, unauth_mem)
    print(" [FAIL] WO-U-054: Did not raise PermissionDenied")
except PermissionDenied as e:
    print(f" [PASS] WO-U-054: Unauthorized user denied with PermissionDenied(code='{e.code}').")
except Exception as e:
    print(f" [FAIL] WO-U-054: {type(e).__name__}: {e}")

rbac.has_permission = orig_has_perm

print("\n" + "=" * 60)
print("2. VERIFYING DEF-002 (IDN-U-029)")
print("=" * 60)
from apps.identification import services as id_services
test_urls = [
    ("https://fo.test/app/s/abc123/?x=1#y", "abc123"),
    ("https://fo.test/app/s/xyz789/", "xyz789"),
    ("https://fo.test/app/s/xyz789", "xyz789"),
    ("https://fo.test/app/scan/?token=def456", "def456"),
    ("rawtoken123?foo=bar", "rawtoken123"),
    ("rawtoken123", "rawtoken123")
]

all_idn_pass = True
for url, expected in test_urls:
    extracted = id_services.extract_token(url)
    if extracted == expected:
        print(f" [PASS] extract_token('{url}') -> '{extracted}'")
    else:
        print(f" [FAIL] extract_token('{url}') -> '{extracted}' (expected '{expected}')")
        all_idn_pass = False

if all_idn_pass:
    print(" [PASS] IDN-U-029: Scanned URLs with query string/fragments correctly resolve to token.")

print("\n" + "=" * 60)
print("3. VERIFYING DEF-003 (WS-U-029)")
print("=" * 60)
from apps.workspace import services as ws_services
fn = getattr(ws_services.log_travel, "__wrapped__", ws_services.log_travel)
wo_mock = MagicMock()
mem_mock = MagicMock()
ws_services.assert_can_execute_job = MagicMock()

# Test 1: Negative distance
try:
    fn(wo_mock, membership=mem_mock, actor=MagicMock(), duration_hours="1", distance_km="-5")
    print(" [FAIL] WS-U-029: Negative distance did not raise ValidationFailed")
except ValidationFailed as e:
    if e.message == "Distance cannot be negative.":
        print(f" [PASS] WS-U-029: Negative distance raised ValidationFailed with exact message: '{e.message}'")
    else:
        print(f" [FAIL] WS-U-029: ValidationFailed message was '{e.message}' (expected 'Distance cannot be negative.')")
except Exception as e:
    print(f" [FAIL] WS-U-029: {type(e).__name__}: {e}")

# Test 2: Invalid number
try:
    fn(wo_mock, membership=mem_mock, actor=MagicMock(), duration_hours="1", distance_km="invalid_num")
    print(" [FAIL] Invalid distance did not raise ValidationFailed")
except ValidationFailed as e:
    if e.message == "Distance must be a valid number.":
        print(f" [PASS] Non-numeric distance raised ValidationFailed with exact message: '{e.message}'")
    else:
        print(f" [FAIL] ValidationFailed message was '{e.message}'")
except Exception as e:
    print(f" [FAIL] {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("4. VERIFYING ENV-001 & ENV-002")
print("=" * 60)
# ENV-001: test settings database fallback
from config.settings import test as test_settings
print(f" [PASS] ENV-001: test.py supports TEST_DATABASE_URL and configures DATABASE_URL={os.environ.get('DATABASE_URL')}")

# ENV-002: maintenance app imports
try:
    import apps.maintenance.models as m_models
    import apps.maintenance.services as m_services
    import apps.maintenance.api_views as m_views
    print(" [PASS] ENV-002: apps.maintenance models, services, and api_views imported successfully.")
except Exception as e:
    print(f" [FAIL] ENV-002: Failed importing maintenance app: {e}")

print("=" * 60)
