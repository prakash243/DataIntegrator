"""
CSV to JSON mapper.

Converts CSV content (string) into a JSON array of objects.
Each row becomes a JSON object keyed by the header columns.
"""

import csv
import io
import json


def csv_to_json_mapper(content: str, **kwargs) -> dict:
    """
    Convert CSV string content to a JSON array of objects.

    Args:
        content: Raw CSV string
        **kwargs: Optional overrides
            - delimiter: CSV delimiter (default: auto-detect or ',')
            - quotechar: Quote character (default: '"')

    Returns:
        dict with keys: output, logs, output_type
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("CSV content is empty")

    delimiter = kwargs.get("delimiter", "")
    quotechar = kwargs.get("quotechar", '"')

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
    for i, row in enumerate(reader, start=1):
        # Convert OrderedDict to regular dict, strip whitespace from keys and values
        clean_row = {k.strip(): v.strip() if isinstance(v, str) else v for k, v in row.items() if k}
        rows.append(clean_row)

    if not rows:
        raise ValueError("CSV content has headers but no data rows")

    logs.append(f"Parsed {len(rows)} row(s) with {len(rows[0])} column(s)")
    logs.append(f"Columns: {', '.join(rows[0].keys())}")

    output = json.dumps(rows, indent=2, ensure_ascii=False)

    return {
        "output": output,
        "logs": logs,
        "output_type": "JSON",
    }


def _detect_delimiter(content: str) -> str:
    """
    Auto-detect the CSV delimiter by inspecting the first line.

    Checks for common delimiters: comma, tab, semicolon, pipe.
    Falls back to comma.
    """
    first_line = content.strip().split("\n")[0]

    candidates = [
        (",", first_line.count(",")),
        ("\t", first_line.count("\t")),
        (";", first_line.count(";")),
        ("|", first_line.count("|")),
    ]

    # Pick the delimiter with the highest count (must be > 0)
    candidates.sort(key=lambda x: x[1], reverse=True)
    if candidates[0][1] > 0:
        return candidates[0][0]

    return ","
