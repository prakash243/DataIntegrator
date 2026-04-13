"""
EDI to CSV file mapper.

Parses EDI X12 content, optionally applies a user-defined apply_rules function,
and outputs CSV.
"""

import csv
import io

from apps.mapping.executor import execute_rules
from apps.mapping.maps.edi_parser import parse_edi


def edi_to_csv_file_mapper(content: str, rules_code: str = "", **kwargs) -> dict:
    """
    Convert EDI X12 content to CSV with optional user-defined transform.

    Args:
        content: Raw EDI string
        rules_code: User's Python code with a def apply_rules(row): function
        **kwargs:
            transaction_set: e.g. '850', '810' (auto-detected if omitted)
            include_envelope: Whether to include envelope fields (default: True)
            delimiter: CSV delimiter (default: ',')
            quote_data: Whether to quote data fields (default: True)
            quote_header: Whether to quote header row (default: False)
            quotechar: Quote character (default: '"')

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
