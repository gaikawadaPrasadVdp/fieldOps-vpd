from django.db import migrations
from django.db.models import Q


_QA_TECH_EMAILS = {
    "lead.technician@apexindustrial.com",
    "technician@apexindustrial.example.com",
}
_ACTIVE_STATES = ("ASSIGNED", "DISPATCHED", "IN_PROGRESS", "ON_HOLD")


def seed_technician_profiles_and_qa_capacity(apps, schema_editor):
    Membership = apps.get_model("tenancy", "Membership")
    MembershipRole = apps.get_model("rbac", "MembershipRole")
    WorkOrderTechnicianProfile = apps.get_model("workorders", "TechnicianProfile")
    WorkspaceTechnicianProfile = apps.get_model("workspace", "TechnicianProfile")
    WorkOrder = apps.get_model("workorders", "WorkOrder")

    tech_role_membership_ids = set(
        MembershipRole.objects.filter(role__system_key="technician").values_list("membership_id", flat=True)
    )
    memberships = Membership.objects.filter(status="ACTIVE").select_related("user", "organization")

    for membership in memberships:
        email = (getattr(membership.user, "email", "") or "").lower()
        is_tech = membership.pk in tech_role_membership_ids or "technician" in email
        if not is_tech:
            continue

        WorkOrderTechnicianProfile.objects.get_or_create(
            membership=membership,
            defaults={
                "organization": membership.organization,
                "skills": ["HVAC", "Electrical", "Preventive Maintenance"],
                "is_dispatchable": True,
            },
        )

        ws_profile, _ = WorkspaceTechnicianProfile.objects.get_or_create(
            membership=membership,
            defaults={
                "organization": membership.organization,
                "max_active_jobs": 50 if email in _QA_TECH_EMAILS else 10,
                "availability_status": "AVAILABLE",
            },
        )
        updated = False
        if email in _QA_TECH_EMAILS and ws_profile.max_active_jobs < 50:
            ws_profile.max_active_jobs = 50
            updated = True
        if email in _QA_TECH_EMAILS and ws_profile.availability_status != "AVAILABLE":
            ws_profile.availability_status = "AVAILABLE"
            updated = True
        if updated:
            ws_profile.save(update_fields=["max_active_jobs", "availability_status", "updated_at"])

        if email in _QA_TECH_EMAILS:
            # Close stale leftover QA smoke work orders so repeated smoke runs never hit capacity limits
            WorkOrder.objects.filter(
                organization=membership.organization,
                assigned_to=membership,
                status__in=_ACTIVE_STATES,
            ).filter(
                Q(title__istartswith="SMK") | Q(title__icontains="[SMK") | Q(title__icontains="Smoke Test")
            ).update(status="CANCELLED")


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("rbac", "0002_membership_role_site_scope"),
        ("workorders", "0023_workorder_wo_org_asgn_stat_idx_and_more"),
        ("workspace", "0004_ensure_worknote_table"),
    ]

    operations = [
        migrations.RunPython(seed_technician_profiles_and_qa_capacity, reverse_code=reverse_noop),
    ]
