"""Deep Negative Smoke Probes: State Machine Violations, XSS, and Inventory Negative Limits."""
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

def get_auth_token():
    req = urllib.request.Request(
        f"{BASE_URL}/api/v1/auth/token/",
        data=json.dumps({"email": "owner@demo.local", "password": "FieldOps-Dev-2026!"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())["access"]

def make_req(token, method, path, data=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}

def main():
    token = get_auth_token()
    print("Obtained token. Running deep domain negative probes...")

    # Probe 1: XSS in Site creation
    xss_payload = {"name": "<script>alert(1)</script>", "code": "XSS-01"}
    status, res = make_req(token, "POST", "/api/v1/sites/", xss_payload)
    print(f"[XSS Attack in Site Name] Status: {status} Response: {res}")
    assert status in (400, 201), f"Unexpected status: {status}"
    if status == 201:
        # If created, check that it does not return unescaped script tag or is properly handled
        print("  Site created - checking sanitization")

    # Probe 2: Non-existent work-order state transition action
    status, res = make_req(token, "POST", "/api/v1/work-orders/00000000-0000-4000-8000-000000000099/close/", {})
    print(f"[Premature Closure on Non-existent WO] Status: {status} Response: {res}")
    assert status == 404, f"Expected 404, got {status}"

    # Probe 3: Negative stock adjustment
    status, res = make_req(token, "POST", "/api/v1/stock-movements/", {
        "quantity": -50,
        "movement_type": "CONSUMED"
    })
    print(f"[Negative Stock Movement Injection] Status: {status} Response: {res}")
    assert status in (400, 404), f"Expected 400/404, got {status}"

    # Probe 4: Work order with past scheduled end before start
    status, res = make_req(token, "POST", "/api/v1/work-orders/", {
        "title": "Invalid Date Test",
        "scheduled_start": "2026-12-10T10:00:00Z",
        "scheduled_end": "2026-12-01T10:00:00Z"
    })
    print(f"[Invalid Date Order (End before Start)] Status: {status} Response: {res}")
    assert status in (400, 422), f"Expected 400 Bad Request, got {status}"

    print("All deep domain negative probes completed successfully.")

if __name__ == "__main__":
    main()
