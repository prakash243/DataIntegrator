"""
CSV to JSON file mapper with rules support.

Reads a CSV file, applies transformation rules, and writes a JSON output file.
"""

import csv
import io
import json

from apps.mapping.rules import apply_rules


def csv_to_json_file_mapper(content: str, rules: dict | None = None) -> dict:
    """
    Convert CSV content to JSON with optional transformation rules.

    Args:
        content: Raw CSV string
        rules: Transformation rules dict (see rules.py for supported rules)

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []
    rules = rules or {}

    if not content or not content.strip():
        raise ValueError("CSV content is empty")

    # Get CSV-specific settings from rules
    delimiter = rules.get("delimiter", "")
    quotechar = rules.get("quotechar", '"')

    # Auto-detect delimiter if not provided
    if not delimiter:
        delimiter = _detect_delimiter(content)
        logs.append(f"Auto-detected delimiter: {repr(delimiter)}")

    reader = csv.DictReader(
        io.StringIO(content),
        delimiter=delimiter,
        quotechar=quotechar,
    )

    rows = []
    for row in reader:
        clean_row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
        rows.append(clean_row)

    if not rows:
        raise ValueError("CSV content has headers but no data rows")

    original_count = len(rows)
    original_columns = list(rows[0].keys())
    logs.append(f"Parsed {original_count} row(s) with {len(original_columns)} column(s)")
    logs.append(f"Input columns: {', '.join(original_columns)}")

    # Apply transformation rules
    rows, column_order = apply_rules(rows, rules, logs)

    if not rows:
        raise ValueError("No rows remain after applying filter rules")

    # If column_order is specified, reorder keys in each dict
    if column_order:
        reordered = []
        for row in rows:
            new_row = {col: row.get(col, "") for col in column_order}
            # Add any remaining keys not in column_order
            for k, v in row.items():
                if k not in new_row:
                    new_row[k] = v
            reordered.append(new_row)
        rows = reordered

    final_columns = list(rows[0].keys()) if rows else []
    logs.append(f"Output: {len(rows)} row(s) with {len(final_columns)} column(s)")
    logs.append(f"Output columns: {', '.join(final_columns)}")

    output = json.dumps(rows, indent=2, ensure_ascii=False)

    return {
        "output": output,
        "logs": logs,
        "output_type": "JSON",
        "rows_processed": len(rows),
        "columns_count": len(final_columns),
    }


def _detect_delimiter(content: str) -> str:
    first_line = content.strip().split("\n")[0]
    candidates = [
        (",", first_line.count(",")),
        ("\t", first_line.count("\t")),
        (";", first_line.count(";")),
        ("|", first_line.count("|")),
    ]
    candidates.sort(key=lambda x: x[1], reverse=True)
    if candidates[0][1] > 0:
        return candidates[0][0]
    return ","
