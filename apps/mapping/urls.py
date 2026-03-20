from django.urls import path

from . import views
from . import views_file

app_name = "mapping"

urlpatterns = [
    # List available mapping functions
    path("registry/", views.MappingRegistryListView.as_view(), name="registry-list"),

    # Dedicated conversion endpoints (raw content in body)
    path("csv-to-json/", views.CsvToJsonView.as_view(), name="csv-to-json"),
    path("json-to-csv/", views.JsonToCsvView.as_view(), name="json-to-csv"),

    # Generic conversion endpoint (pass mapping_function in body)
    path("convert/", views.ConvertView.as_view(), name="convert"),

    # File upload conversion endpoints (multipart/form-data)
    path("file/csv-to-json/", views_file.FileUploadCsvToJsonView.as_view(), name="file-csv-to-json"),
    path("file/json-to-csv/", views_file.FileUploadJsonToCsvView.as_view(), name="file-json-to-csv"),

    # Conversion job management
    path("file/jobs/", views_file.ConversionJobListView.as_view(), name="job-list"),
    path("file/jobs/<uuid:job_id>/", views_file.ConversionJobDetailView.as_view(), name="job-detail"),
    path("file/jobs/<uuid:job_id>/download/", views_file.ConversionJobDownloadView.as_view(), name="job-download"),
]
