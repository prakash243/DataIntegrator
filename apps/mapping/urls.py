from django.urls import path

from . import views_file

app_name = "mapping"

urlpatterns = [
    # File upload conversion endpoints (multipart/form-data)
    path("file/json-to-csv/", views_file.FileUploadJsonToCsvView.as_view(), name="file-json-to-csv"),
    path("file/csv-to-json/", views_file.FileUploadCsvToJsonView.as_view(), name="file-csv-to-json"),

    # Conversion job management
    path("file/jobs/", views_file.ConversionJobListView.as_view(), name="job-list"),
    path("file/jobs/<uuid:job_id>/", views_file.ConversionJobDetailView.as_view(), name="job-detail"),
    path("file/jobs/<uuid:job_id>/download/", views_file.ConversionJobDownloadView.as_view(), name="job-download"),

    # Interactive JSON transform
    path("transform/upload/", views_file.TransformUploadView.as_view(), name="transform-upload"),
    path("transform/apply/", views_file.TransformApplyView.as_view(), name="transform-apply"),
]
