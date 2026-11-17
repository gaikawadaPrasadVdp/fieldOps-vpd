from django.urls import re_path

from . import api_views

urlpatterns = [
    re_path(r"^workspace/jobs/?$", api_views.MyJobsAPIView.as_view(), name="api_my_jobs"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/?$", api_views.JobDetailAPIView.as_view(), name="api_job_detail"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/drawer/?$", api_views.JobExecutionDrawerAPIView.as_view(), name="api_job_drawer"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/start/?$", api_views.JobStartAPIView.as_view(), name="api_job_start"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/pause/?$", api_views.JobPauseAPIView.as_view(), name="api_job_pause"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/resume/?$", api_views.JobResumeAPIView.as_view(), name="api_job_resume"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/travel/?$", api_views.JobTravelLogAPIView.as_view(), name="api_job_travel"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/complete/?$", api_views.JobCompleteAPIView.as_view(), name="api_job_complete"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/notes/?$", api_views.JobWorkNoteAPIView.as_view(), name="api_job_notes"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/labor/?$", api_views.JobLaborAPIView.as_view(), name="api_job_labor"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/materials/?$", api_views.JobMaterialAPIView.as_view(), name="api_job_materials"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/parts/consume/?$", api_views.JobPartConsumeAPIView.as_view(), name="api_job_parts_consume"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/parts/return/?$", api_views.JobPartReturnAPIView.as_view(), name="api_job_parts_return"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/evidence/?$", api_views.JobEvidenceAPIView.as_view(), name="api_job_evidence"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/meters/reading/?$", api_views.JobMeterReadingAPIView.as_view(), name="api_job_meter_reading"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/verify-asset/?$", api_views.JobAssetVerifyAPIView.as_view(), name="api_job_verify_asset"),
    re_path(r"^workspace/jobs/(?P<pk>[0-9a-fA-F-]+)/defects/?$", api_views.JobReportDefectAPIView.as_view(), name="api_job_report_defect"),
    re_path(r"^workspace/capacity/?$", api_views.TechnicianCapacityAPIView.as_view(), name="api_technician_capacity"),
    re_path(r"^workspace/shifts/?$", api_views.ShiftListCreateAPIView.as_view(), name="api_shifts"),
    re_path(r"^workspace/shifts/(?P<pk>[0-9a-fA-F-]+)/?$", api_views.ShiftDetailAPIView.as_view(), name="api_shift_detail"),
    re_path(r"^workspace/technicians/?$", api_views.TechnicianProfileListAPIView.as_view(), name="api_technicians"),
    re_path(r"^workspace/technicians/(?P<pk>[0-9a-fA-F-]+)/?$", api_views.TechnicianProfileDetailAPIView.as_view(), name="api_technician_detail"),
    re_path(r"^workspace/technicians/(?P<pk>[0-9a-fA-F-]+)/availability/?$", api_views.TechnicianAvailabilityAPIView.as_view(), name="api_technician_availability"),
    re_path(r"^workspace/profile/availability/?$", api_views.TechnicianAvailabilityAPIView.as_view(), name="api_my_availability"),
]
