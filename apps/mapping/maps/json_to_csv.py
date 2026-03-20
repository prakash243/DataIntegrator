"""
JSON to CSV mapper.

Converts a JSON array of objects into CSV content.
Keys from the first object are used as CSV headers.
"""

import csv
import io
import json


def json_to_csv_mapper(content: str, **kwargs) -> dict:
    """
    Convert a JSON array of objects to CSV string.

    Args:
        content: Raw JSON string (must be an array of objects)
        **kwargs: Optional overrides
            - delimiter: CSV delimiter (default: ',')
            - quotechar: Quote character (default: '"')
            - columns: Explicit column order (default: keys from first object)
            - quote_header: Whether to quote header row (default: False)
            - quote_data: Whether to quote all data fields (default: True)

    Returns:
        dict with keys: output, logs, output_type
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("JSON content is empty")

    data = json.loads(content)

    if isinstance(data, dict):
        # If a single object is passed, wrap it in a list
        data = [data]
        logs.append("Input was a single JSON object, wrapped into an array")

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of objects, got {type(data).__name__}")

    if not data:
        raise ValueError("JSON array is empty")

    if not isinstance(data[0], dict):
        raise ValueError(f"Expected JSON objects in the array, got {type(data[0]).__name__}")

    delimiter = kwargs.get("delimiter", ",")
    quotechar = kwargs.get("quotechar", '"')
    columns = kwargs.get("columns", None)
    quote_header = kwargs.get("quote_header", False)
    quote_data = kwargs.get("quote_data", True)

    # Determine column order
    if columns:
        fieldnames = columns
    else:
        # Collect all unique keys across all objects preserving order
        fieldnames = _collect_all_keys(data)

    logs.append(f"Converting {len(data)} row(s) with {len(fieldnames)} column(s)")
    logs.append(f"Columns: {', '.join(fieldnames)}")

    output = io.StringIO()

    # Write header row
    if quote_header:
        header_writer = csv.writer(output, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_ALL)
    else:
        header_writer = csv.writer(output, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_NONE,
                                   escapechar="\\")
    header_writer.writerow(fieldnames)

    # Write data rows
    data_quoting = csv.QUOTE_ALL if quote_data else csv.QUOTE_MINIMAL
    data_writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=delimiter,
        quotechar=quotechar,
        quoting=data_quoting,
        extrasaction="ignore",
    )

    for row in data:
        # Ensure all values are strings for consistent output
        clean_row = {k: str(v) if v is not None else "" for k, v in row.items()}
        data_writer.writerow(clean_row)

    return {
        "output": output.getvalue(),
        "logs": logs,
        "output_type": "CSV",
    }


def _collect_all_keys(data: list[dict]) -> list[str]:
    """
    Collect all unique keys from a list of dicts, preserving insertion order.
    """
    seen = {}
    for row in data:
        for key in row:
            if key not in seen:
                seen[key] = True
    return list(seen.keys())
