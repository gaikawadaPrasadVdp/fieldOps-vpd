from django.urls import path

from apps.incidents.dashboard_views import platform_dashboard

from . import platform_views

app_name = "platform_admin"
urlpatterns = [
    path("overview/", platform_views.platform_overview, name="overview"),
    path("incidents/", platform_dashboard, name="incident_dashboard"),
    path("organizations/", platform_views.organizations, name="organizations"),
    path("organizations/new/", platform_views.organization_create, name="organization_create"),
    path("organizations/<uuid:org_id>/status/", platform_views.organization_toggle_status, name="organization_toggle_status"),
    path("organizations/<uuid:org_id>/delete/", platform_views.organization_delete, name="organization_delete"),
    path("organizations/<uuid:org_id>/delete-now/", platform_views.organization_delete_now, name="organization_delete_now"),
    path("organizations/<uuid:org_id>/cancel-deletion/", platform_views.organization_cancel_deletion, name="organization_cancel_deletion"),
    path("organizations/<uuid:org_id>/owner-credentials/", platform_views.organization_owner_credentials, name="organization_owner_credentials"),
    path("audit/", platform_views.audit, name="audit"),
]
