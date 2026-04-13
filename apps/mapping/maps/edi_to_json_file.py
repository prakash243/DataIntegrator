"""
EDI to JSON file mapper.

Parses EDI X12 content, optionally applies a user-defined apply_rules function,
and outputs JSON.
"""

import json

from apps.mapping.executor import execute_rules
from apps.mapping.maps.edi_parser import parse_edi


def edi_to_json_file_mapper(content: str, rules_code: str = "", **kwargs) -> dict:
    """
    Convert EDI X12 content to JSON with optional user-defined transform.

    Args:
        content: Raw EDI string
        rules_code: User's Python code with a def apply_rules(row): function
        **kwargs:
            transaction_set: e.g. '850', '810' (auto-detected if omitted)
            include_envelope: Whether to include envelope fields (default: True)
            indent: JSON indentation (default: 2)

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("EDI content is empty")

    transaction_set = kwargs.get("transaction_set", "") or None
    include_envelope = kwargs.get("include_envelope", True)

    # Parse EDI
    parsed = parse_edi(
        content,
        transaction_set=transaction_set,
        include_envelope=include_envelope,
    )

    data = parsed["rows"]
    logs.extend(parsed["logs"])

    if not data:
        raise ValueError("No data rows could be extracted from the EDI content")

    original_count = len(data)
    original_columns = _collect_all_keys(data)
    logs.append(f"Parsed {original_count} row(s) with {len(original_columns)} column(s)")
    logs.append(f"Input columns: {', '.join(original_columns)}")

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
