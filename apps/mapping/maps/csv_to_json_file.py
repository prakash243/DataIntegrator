"""
CSV to JSON file mapper.

Reads CSV content, optionally applies a user-defined apply_rules function,
and outputs JSON.
"""

import csv
import io
import json

from apps.mapping.executor import execute_rules


def csv_to_json_file_mapper(content: str, rules_code: str = "", **kwargs) -> dict:
    """
    Convert CSV content to JSON with optional user-defined transform.

    Args:
        content: Raw CSV string
        rules_code: User's Python code with a def apply_rules(row): function
        **kwargs: CSV options (delimiter)

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("CSV content is empty")

    delimiter = kwargs.get("delimiter", ",") or ","

    # Parse CSV
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    fieldnames = reader.fieldnames

    if not fieldnames:
        raise ValueError("CSV file has no header row")

    data = []
    for row in reader:
        # Convert OrderedDict to plain dict
        data.append(dict(row))

    if not data:
        raise ValueError("CSV file has no data rows")

    original_count = len(data)
    logs.append(f"Parsed {original_count} row(s) with {len(fieldnames)} column(s)")
    logs.append(f"Input columns: {', '.join(fieldnames)}")

    # Apply user-defined transform if provided
    if rules_code.strip():
        data = execute_rules(data, rules_code, logs)
        if not data:
            raise ValueError("No rows remain after transform (all filtered out or errored)")

    # Collect final column names
    final_columns = _collect_all_keys(data)
    logs.append(f"Output: {len(data)} row(s) with {len(final_columns)} column(s)")
    logs.append(f"Output columns: {', '.join(final_columns)}")

    # Build JSON output
    indent = kwargs.get("indent", 2)
    output = json.dumps(data, indent=indent, ensure_ascii=False)

    return {
        "output": output,
        "logs": logs,
        "output_type": "JSON",
        "rows_processed": len(data),
        "columns_count": len(final_columns),
    }


def _collect_all_keys(data: list[dict]) -> list[str]:
    seen = {}
    for row in data:
        for key in row:
            if key not in seen:
                seen[key] = True
    return list(seen.keys())
