import uuid

from django.db import models


def input_upload_path(instance, filename):
    return f"conversions/{instance.id}/input/{filename}"


def output_upload_path(instance, filename):
    return f"conversions/{instance.id}/output/{filename}"


class ConversionJob(models.Model):
    """Tracks a file conversion job with input/output files and rules."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    DIRECTION_CHOICES = [
        ("csv_to_json", "CSV to JSON"),
        ("json_to_csv", "JSON to CSV"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Files
    input_file = models.FileField(upload_to=input_upload_path)
    input_filename = models.CharField(max_length=255)
    output_file = models.FileField(upload_to=output_upload_path, blank=True, null=True)
    output_filename = models.CharField(max_length=255, blank=True, default="")

    # Rules (stored as JSON)
    rules = models.JSONField(default=dict, blank=True)

    # Processing info
    rows_processed = models.IntegerField(default=0)
    columns_count = models.IntegerField(default=0)
    logs = models.TextField(blank=True, default="")
    error_message = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.direction} - {self.input_filename} ({self.status})"
