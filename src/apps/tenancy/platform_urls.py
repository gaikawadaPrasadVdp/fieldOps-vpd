from django.urls import path

from apps.incidents.dashboard_views import platform_dashboard

from . import platform_views

app_name = "platform_admin"
urlpatterns = [
    path("incidents/", platform_dashboard, name="incident_dashboard"),
    path("organizations/", platform_views.organizations, name="organizations"),
    path("organizations/new/", platform_views.organization_create, name="organization_create"),
    path("organizations/<uuid:org_id>/status/", platform_views.organization_toggle_status, name="organization_toggle_status"),
    path("organizations/<uuid:org_id>/delete/", platform_views.organization_delete, name="organization_delete"),
    path("audit/", platform_views.audit, name="audit"),
]
