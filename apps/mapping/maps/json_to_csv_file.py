"""
JSON to CSV file mapper with rules support.

Reads a JSON file, applies transformation rules, and writes a CSV output file.
"""

import csv
import io
import json

from apps.mapping.rules import apply_rules


def json_to_csv_file_mapper(content: str, rules: dict | None = None) -> dict:
    """
    Convert JSON content to CSV with optional transformation rules.

    Args:
        content: Raw JSON string (array of objects or single object)
        rules: Transformation rules dict (see rules.py for supported rules)

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []
    rules = rules or {}

    if not content or not content.strip():
        raise ValueError("JSON content is empty")

    data = json.loads(content)

    if isinstance(data, dict):
        data = [data]
        logs.append("Input was a single JSON object, wrapped into an array")

    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON array of objects, got {type(data).__name__}")

    if not data:
        raise ValueError("JSON array is empty")

    if not isinstance(data[0], dict):
        raise ValueError(f"Expected JSON objects in the array, got {type(data[0]).__name__}")

    original_count = len(data)
    original_columns = _collect_all_keys(data)
    logs.append(f"Parsed {original_count} row(s) with {len(original_columns)} column(s)")
    logs.append(f"Input columns: {', '.join(original_columns)}")

    # Apply transformation rules
    data, column_order = apply_rules(data, rules, logs)

    if not data:
        raise ValueError("No rows remain after applying filter rules")

    # Get CSV-specific settings from rules
    delimiter = rules.get("delimiter", ",")
    quotechar = rules.get("quotechar", '"')
    quote_header = rules.get("quote_header", False)
    quote_data = rules.get("quote_data", True)

    # Determine final column order
    if column_order:
        fieldnames = column_order
    else:
        fieldnames = _collect_all_keys(data)

    logs.append(f"Output: {len(data)} row(s) with {len(fieldnames)} column(s)")
    logs.append(f"Output columns: {', '.join(fieldnames)}")

    # Build CSV output
    output = io.StringIO()

    if quote_header:
        header_writer = csv.writer(output, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_ALL)
    else:
        header_writer = csv.writer(output, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_NONE,
                                   escapechar="\\")
    header_writer.writerow(fieldnames)

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
        clean_row = {k: str(v) if v is not None else "" for k, v in row.items()}
        data_writer.writerow(clean_row)

    return {
        "output": output.getvalue(),
        "logs": logs,
        "output_type": "CSV",
        "rows_processed": len(data),
        "columns_count": len(fieldnames),
    }


def _collect_all_keys(data: list[dict]) -> list[str]:
    seen = {}
    for row in data:
        for key in row:
            if key not in seen:
                seen[key] = True
    return list(seen.keys())
