from django.urls import path

from . import api_views

urlpatterns = [
    path("dashboards/", api_views.DashboardCatalogAPIView.as_view(), name="api_dashboards_catalog"),
    path("dashboards/snapshots/", api_views.SnapshotListAPIView.as_view(), name="api_snapshots_list"),
    path("dashboards/snapshots/<uuid:pk>/", api_views.SnapshotDetailAPIView.as_view(), name="api_snapshot_detail"),
    path("dashboards/<str:section>/", api_views.DashboardSectionAPIView.as_view(), name="api_dashboards_section"),
]
