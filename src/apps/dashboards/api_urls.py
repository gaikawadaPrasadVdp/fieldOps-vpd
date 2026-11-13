from django.urls import re_path

from . import api_views

urlpatterns = [
    re_path(r"^dashboards/?$", api_views.DashboardCatalogAPIView.as_view(), name="api_dashboards_catalog"),
    re_path(r"^dashboards/snapshots/?$", api_views.SnapshotListAPIView.as_view(), name="api_snapshots_list"),
    re_path(r"^dashboards/snapshots/(?P<pk>[0-9a-fA-F-]+)/?$", api_views.SnapshotDetailAPIView.as_view(), name="api_snapshot_detail"),
    re_path(r"^dashboards/(?P<section>[a-zA-Z0-9_-]+)/?$", api_views.DashboardSectionAPIView.as_view(), name="api_dashboards_section"),
]
