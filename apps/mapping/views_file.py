"""
File upload conversion views.

These views accept file uploads (CSV or JSON), apply transformation rules,
create output files, and store the job history.
"""

import json
import logging
import os

from django.core.files.base import ContentFile
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .maps.csv_to_json_file import csv_to_json_file_mapper
from .maps.json_to_csv_file import json_to_csv_file_mapper
from .models import ConversionJob

logger = logging.getLogger(__name__)


class FileUploadCsvToJsonView(APIView):
    """
    Upload a CSV file with optional rules, convert to JSON, and create an output file.

    POST /api/mapping/file/csv-to-json/
    Content-Type: multipart/form-data

    Fields:
        file (required): CSV file to convert
        rules (optional): JSON string with transformation rules
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "No file uploaded. Send a CSV file in the 'file' field."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate file extension
        filename = uploaded_file.name
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".csv", ".tsv", ".txt"):
            return Response(
                {"error": f"Invalid file type '{ext}'. Expected .csv, .tsv, or .txt"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse rules
        rules = _parse_rules(request.data.get("rules", "{}"))
        if isinstance(rules, Response):
            return rules  # Error response

        # Create job record
        job = ConversionJob.objects.create(
            direction="csv_to_json",
            input_filename=filename,
            rules=rules,
        )

        # Read file content first (before save consumes the stream)
        content = uploaded_file.read().decode("utf-8")
        uploaded_file.seek(0)

        # Save input file
        job.input_file.save(filename, uploaded_file, save=True)

        try:
            job.status = "processing"
            job.save(update_fields=["status"])

            # Run conversion with rules
            result = csv_to_json_file_mapper(content, rules=rules)

            # Generate output filename
            base_name = os.path.splitext(filename)[0]
            output_filename = f"{base_name}.json"

            # Save output file
            job.output_file.save(output_filename, ContentFile(result["output"].encode("utf-8")), save=False)
            job.output_filename = output_filename
            job.status = "completed"
            job.rows_processed = result.get("rows_processed", 0)
            job.columns_count = result.get("columns_count", 0)
            job.logs = "\n".join(result["logs"])
            job.completed_at = timezone.now()
            job.save()

            return Response({
                "job_id": str(job.id),
                "status": job.status,
                "direction": job.direction,
                "input_filename": job.input_filename,
                "output_filename": job.output_filename,
                "rows_processed": job.rows_processed,
                "columns_count": job.columns_count,
                "rules_applied": rules,
                "logs": result["logs"],
                "output": result["output"],
                "download_url": request.build_absolute_uri(f"/api/mapping/file/jobs/{job.id}/download/"),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()

            logger.exception(f"CSV to JSON file conversion failed for job {job.id}")
            return Response({
                "job_id": str(job.id),
                "error": "Conversion failed",
                "details": str(e),
            }, status=status.HTTP_400_BAD_REQUEST)


class FileUploadJsonToCsvView(APIView):
    """
    Upload a JSON file with optional rules, convert to CSV, and create an output file.

    POST /api/mapping/file/json-to-csv/
    Content-Type: multipart/form-data

    Fields:
        file (required): JSON file to convert
        rules (optional): JSON string with transformation rules
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"error": "No file uploaded. Send a JSON file in the 'file' field."},
                            status=status.HTTP_400_BAD_REQUEST)

        # Validate file extension
        filename = uploaded_file.name
        ext = os.path.splitext(filename)[1].lower()
        if ext not in (".json",):
            return Response(
                {"error": f"Invalid file type '{ext}'. Expected .json"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Parse rules
        rules = _parse_rules(request.data.get("rules", "{}"))
        if isinstance(rules, Response):
            return rules

        # Create job record
        job = ConversionJob.objects.create(
            direction="json_to_csv",
            input_filename=filename,
            rules=rules,
        )

        # Read file content first (before save consumes the stream)
        content = uploaded_file.read().decode("utf-8")
        uploaded_file.seek(0)

        # Save input file
        job.input_file.save(filename, uploaded_file, save=True)

        try:
            job.status = "processing"
            job.save(update_fields=["status"])

            # Run conversion with rules
            result = json_to_csv_file_mapper(content, rules=rules)

            # Generate output filename
            base_name = os.path.splitext(filename)[0]
            output_filename = f"{base_name}.csv"

            # Save output file
            job.output_file.save(output_filename, ContentFile(result["output"].encode("utf-8")), save=False)
            job.output_filename = output_filename
            job.status = "completed"
            job.rows_processed = result.get("rows_processed", 0)
            job.columns_count = result.get("columns_count", 0)
            job.logs = "\n".join(result["logs"])
            job.completed_at = timezone.now()
            job.save()

            return Response({
                "job_id": str(job.id),
                "status": job.status,
                "direction": job.direction,
                "input_filename": job.input_filename,
                "output_filename": job.output_filename,
                "rows_processed": job.rows_processed,
                "columns_count": job.columns_count,
                "rules_applied": rules,
                "logs": result["logs"],
                "output": result["output"],
                "download_url": request.build_absolute_uri(f"/api/mapping/file/jobs/{job.id}/download/"),
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save()

            logger.exception(f"JSON to CSV file conversion failed for job {job.id}")
            return Response({
                "job_id": str(job.id),
                "error": "Conversion failed",
                "details": str(e),
            }, status=status.HTTP_400_BAD_REQUEST)


class ConversionJobListView(APIView):
    """
    List all conversion jobs.

    GET /api/mapping/file/jobs/
    Optional query params:
        - status: filter by status (pending, processing, completed, failed)
        - direction: filter by direction (csv_to_json, json_to_csv)
    """

    def get(self, request):
        queryset = ConversionJob.objects.all()

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        direction_filter = request.query_params.get("direction")
        if direction_filter:
            queryset = queryset.filter(direction=direction_filter)

        jobs = []
        for job in queryset[:50]:
            jobs.append({
                "job_id": str(job.id),
                "direction": job.direction,
                "status": job.status,
                "input_filename": job.input_filename,
                "output_filename": job.output_filename,
                "rows_processed": job.rows_processed,
                "columns_count": job.columns_count,
                "rules": job.rules,
                "error_message": job.error_message,
                "created_at": job.created_at.isoformat(),
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "download_url": request.build_absolute_uri(
                    f"/api/mapping/file/jobs/{job.id}/download/"
                ) if job.output_file else None,
            })

        return Response({"count": len(jobs), "results": jobs})


class ConversionJobDetailView(APIView):
    """
    Get details of a specific conversion job.

    GET /api/mapping/file/jobs/<job_id>/
    """

    def get(self, request, job_id):
        job = get_object_or_404(ConversionJob, id=job_id)
        return Response({
            "job_id": str(job.id),
            "direction": job.direction,
            "status": job.status,
            "input_filename": job.input_filename,
            "output_filename": job.output_filename,
            "rows_processed": job.rows_processed,
            "columns_count": job.columns_count,
            "rules": job.rules,
            "logs": job.logs,
            "error_message": job.error_message,
            "created_at": job.created_at.isoformat(),
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "download_url": request.build_absolute_uri(
                f"/api/mapping/file/jobs/{job.id}/download/"
            ) if job.output_file else None,
        })


class ConversionJobDownloadView(APIView):
    """
    Download the output file of a completed conversion job.

    GET /api/mapping/file/jobs/<job_id>/download/
    """

    def get(self, request, job_id):
        job = get_object_or_404(ConversionJob, id=job_id)

        if job.status != "completed":
            return Response(
                {"error": f"Job is not completed (status: {job.status})"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not job.output_file:
            return Response(
                {"error": "No output file available for this job"},
                status=status.HTTP_404_NOT_FOUND,
            )

        response = FileResponse(job.output_file.open("rb"), as_attachment=True, filename=job.output_filename)
        return response


def _parse_rules(rules_str: str) -> dict | Response:
    """Parse rules JSON string. Returns dict on success, Response on error."""
    if not rules_str or rules_str.strip() == "":
        return {}
    try:
        rules = json.loads(rules_str)
        if not isinstance(rules, dict):
            return Response(
                {"error": "Rules must be a JSON object"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return rules
    except json.JSONDecodeError as e:
        return Response(
            {"error": "Invalid rules JSON", "details": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
