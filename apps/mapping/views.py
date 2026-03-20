import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .registry import MAPPING_REGISTRY
from .serializers import (
    ConvertResponseSerializer,
    CsvToJsonRequestSerializer,
    JsonToCsvRequestSerializer,
    MappingRegistryItemSerializer,
)
from .utils.loader import get_mapping_function

logger = logging.getLogger(__name__)


class MappingRegistryListView(APIView):
    """
    List all available mapping functions from the registry.

    GET /api/mapping/registry/
    Optional query params:
        - search: filter by substring in name (case-insensitive)
    """

    def get(self, request):
        search_query = (request.query_params.get("search") or "").strip().lower()

        items = []
        for name, entry in MAPPING_REGISTRY.items():
            func = entry["function"]
            description = getattr(func, "__doc__", None)
            if description:
                # Clean up docstring — take first non-empty line
                description = description.strip().split("\n")[0].strip()
            items.append({
                "id": entry["id"],
                "name": name,
                "description": description,
            })

        items.sort(key=lambda x: x["id"])

        if search_query:
            items = [item for item in items if search_query in item["name"].lower()]

        serializer = MappingRegistryItemSerializer(items, many=True)
        return Response(serializer.data)


class CsvToJsonView(APIView):
    """
    Convert CSV content to JSON.

    POST /api/mapping/csv-to-json/
    Body: { "content": "<csv string>", "delimiter": ",", "quotechar": "\"" }
    """

    def post(self, request):
        serializer = CsvToJsonRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            mapper = get_mapping_function("csv_to_json")
            result = mapper(
                content=serializer.validated_data["content"],
                delimiter=serializer.validated_data.get("delimiter", ""),
                quotechar=serializer.validated_data.get("quotechar", '"'),
            )

            response_serializer = ConvertResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except ValueError as e:
            return Response(
                {"error": "Conversion failed", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("CSV to JSON conversion error")
            return Response(
                {"error": "Unexpected error during conversion", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class JsonToCsvView(APIView):
    """
    Convert JSON content to CSV.

    POST /api/mapping/json-to-csv/
    Body: { "content": "<json string>", "delimiter": ",", "columns": [...], "quote_data": true }
    """

    def post(self, request):
        serializer = JsonToCsvRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            mapper = get_mapping_function("json_to_csv")
            result = mapper(
                content=serializer.validated_data["content"],
                delimiter=serializer.validated_data.get("delimiter") or ",",
                quotechar=serializer.validated_data.get("quotechar", '"'),
                columns=serializer.validated_data.get("columns"),
                quote_header=serializer.validated_data.get("quote_header", False),
                quote_data=serializer.validated_data.get("quote_data", True),
            )

            response_serializer = ConvertResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except (ValueError, TypeError) as e:
            return Response(
                {"error": "Conversion failed", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception("JSON to CSV conversion error")
            return Response(
                {"error": "Unexpected error during conversion", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ConvertView(APIView):
    """
    Generic conversion endpoint using a registry key.

    POST /api/mapping/convert/
    Body: { "mapping_function": "csv_to_json", "content": "...", ... }
    """

    def post(self, request):
        mapping_key = request.data.get("mapping_function")
        content = request.data.get("content")

        if not mapping_key:
            return Response(
                {"error": "mapping_function is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not content:
            return Response(
                {"error": "content is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if mapping_key not in MAPPING_REGISTRY:
            available = ", ".join(sorted(MAPPING_REGISTRY.keys()))
            return Response(
                {"error": f"Unknown mapping function '{mapping_key}'", "available": available},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            mapper = get_mapping_function(mapping_key)

            # Pass through any extra kwargs from the request
            kwargs = {k: v for k, v in request.data.items() if k not in ("mapping_function", "content")}
            result = mapper(content=content, **kwargs)

            response_serializer = ConvertResponseSerializer(result)
            return Response(response_serializer.data, status=status.HTTP_200_OK)

        except (ValueError, TypeError) as e:
            return Response(
                {"error": "Conversion failed", "details": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.exception(f"Conversion error for mapping '{mapping_key}'")
            return Response(
                {"error": "Unexpected error during conversion", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
