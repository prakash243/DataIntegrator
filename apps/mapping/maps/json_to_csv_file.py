"""
JSON to CSV file mapper.

Reads JSON content, optionally applies a user-defined apply_rules function,
and outputs CSV.
"""

import csv
import io
import json

from apps.mapping.executor import execute_rules


def json_to_csv_file_mapper(content: str, rules_code: str = "", **kwargs) -> dict:
    """
    Convert JSON content to CSV with optional user-defined transform.

    Args:
        content: Raw JSON string (array of objects or single object)
        rules_code: User's Python code with a def apply_rules(row): function
        **kwargs: CSV options (delimiter, quotechar, quote_header, quote_data)

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []

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

    # Apply user-defined transform if provided
    if rules_code.strip():
        data = execute_rules(data, rules_code, logs)
        if not data:
            raise ValueError("No rows remain after transform (all filtered out or errored)")

    # Get CSV options
    delimiter = kwargs.get("delimiter", ",")
    quotechar = kwargs.get("quotechar", '"')
    quote_header = kwargs.get("quote_header", False)
    quote_data = kwargs.get("quote_data", True)

    # Determine final columns
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
