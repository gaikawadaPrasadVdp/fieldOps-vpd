import pytest
from apps.sites.models import Shift
from apps.workorders.models import TechnicianProfile

@pytest.mark.django_db
def test_shift_and_technician_profile_api_endpoints(as_user, owner_a, org_a, site_a1, make_member):
    client = as_user(owner_a, org_a)
    tech = make_member(org_a, "tech-api@alpha.test", "technician")

    # 1. Create a Shift via API
    shift_res = client.post("/api/v1/shifts/", {
        "site": str(site_a1.pk),
        "name": "Day Shift",
        "code": "DAY-01",
        "start_time": "08:00:00",
        "end_time": "16:00:00",
        "days_of_week": [0, 1, 2, 3, 4],
        "is_active": True,
    }, format="json")
    assert shift_res.status_code == 201, shift_res.data
    shift_id = shift_res.data["id"]

    # 2. List Shifts
    shifts_list = client.get(f"/api/v1/shifts/?site={site_a1.pk}")
    assert shifts_list.status_code == 200
    assert any(s["code"] == "DAY-01" for s in shifts_list.data.get("results", shifts_list.data))

    # 3. Create / Configure Technician Profile via API
    prof_res = client.post("/api/v1/technician-profiles/", {
        "membership": str(tech.pk),
        "skills": ["Plumbing", "HVAC"],
        "certifications": ["Master Plumber"],
        "daily_capacity_hours": "7.50",
        "primary_shift": shift_id,
        "is_dispatchable": True,
        "notes": "Certified lead plumber",
    }, format="json")
    assert prof_res.status_code in [200, 201], prof_res.data

    # 4. List Technician Profiles
    profs_list = client.get("/api/v1/technician-profiles/")
    assert profs_list.status_code == 200
    items = profs_list.data.get("results", profs_list.data)
    assert any(str(p["membership"]) == str(tech.pk) for p in items)
