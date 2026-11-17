from django.urls import path

from . import views

app_name = "dashboards"

urlpatterns = [
    path("dashboards/", views.DashboardHubView.as_view(), name="hub"),
    path("dashboards/my-work/", views.MyWorkDashboardView.as_view(), name="my_work"),
    path("dashboards/snapshots/", views.SnapshotListView.as_view(), name="snapshot_list"),
    path("dashboards/snapshots/<uuid:pk>/", views.SnapshotDetailView.as_view(), name="snapshot_detail"),
    path("dashboards/snapshots/<uuid:pk>/export/", views.SnapshotExportView.as_view(), name="snapshot_export"),
    path("snapshots/", views.SnapshotListView.as_view()),
    path("snapshots/<uuid:pk>/", views.SnapshotDetailView.as_view()),
]
