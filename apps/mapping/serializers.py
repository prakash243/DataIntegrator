from rest_framework import serializers


class MappingRegistryItemSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    description = serializers.CharField(allow_blank=True, allow_null=True, required=False)


class ConvertRequestSerializer(serializers.Serializer):
    """Base serializer for conversion requests."""

    content = serializers.CharField(
        help_text="Raw file content to convert (CSV string or JSON string)",
    )
    delimiter = serializers.CharField(
        required=False,
        allow_blank=True,
        default="",
        help_text="Delimiter character (default: auto-detect for CSV, comma for JSON output)",
    )
    quotechar = serializers.CharField(
        required=False,
        default='"',
        help_text="Quote character (default: double quote)",
    )


class CsvToJsonRequestSerializer(ConvertRequestSerializer):
    """Serializer for CSV to JSON conversion."""
    pass


class JsonToCsvRequestSerializer(ConvertRequestSerializer):
    """Serializer for JSON to CSV conversion."""

    columns = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=None,
        help_text="Explicit column order for CSV output (default: keys from first JSON object)",
    )
    quote_header = serializers.BooleanField(
        required=False,
        default=False,
        help_text="Whether to quote the header row (default: false)",
    )
    quote_data = serializers.BooleanField(
        required=False,
        default=True,
        help_text="Whether to quote all data fields (default: true)",
    )


class ConvertResponseSerializer(serializers.Serializer):
    """Serializer for conversion responses."""

    output = serializers.CharField()
    logs = serializers.ListField(child=serializers.CharField())
    output_type = serializers.CharField()


class ConvertErrorSerializer(serializers.Serializer):
    """Serializer for conversion error responses."""

    error = serializers.CharField()
    details = serializers.CharField(required=False, allow_blank=True)
