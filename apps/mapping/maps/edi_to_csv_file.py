"""
EDI to CSV file mapper.

Parses EDI X12 content, optionally applies a user-defined apply_rules function
to line items, and outputs CSV with only line-item columns (no header repetition).

Document-level header and party info are emitted as a comment preamble at the
top of the CSV file so no information is lost.

Example output:
    # EDI Document: Purchase Order (850)
    # Header: purchase_order_number=PO-2023-0451, order_date=20230615, ...
    # Party BY (Buyer): name=Acme Corporation, city=Springfield, state=IL
    # Party ST (ShipTo): name=Acme Warehouse West, city=Phoenix, state=AZ
    line_number,quantity_ordered,unit_price,product_id,description
    1,100,25.50,WIDGET-A-100,High-performance industrial widget
    2,50,45.00,WIDGET-B-200,Premium grade connector
    ...
"""

import csv
import io

from apps.mapping.executor import execute_rules
from apps.mapping.maps.edi_parser import parse_edi


def edi_to_csv_file_mapper(content: str, rules_code: str = "", **kwargs) -> dict:
    """
    Convert EDI X12 content to CSV.

    Args:
        content: Raw EDI string
        rules_code: User's Python code with a def apply_rules(row): function.
                    Applied to each line item (NOT to header or parties).
        **kwargs:
            transaction_set: e.g. '850', '810' (auto-detected if omitted)
            include_envelope: Whether to include envelope fields in header preamble
            include_header_preamble: Whether to prepend # comment lines with header
                                     and party info (default: True)
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
    include_preamble = kwargs.get("include_header_preamble", True)

    # Parse EDI into document structure
    parsed = parse_edi(
        content,
        transaction_set=transaction_set,
        include_envelope=include_envelope,
        mode="items",
    )

    logs.extend(parsed["logs"])

    header = parsed["header"]
    parties = parsed["parties"]
    line_items = parsed["rows"]
    schema_name = parsed.get("schema_name", "")
    ts = parsed.get("transaction_set", "")

    if not line_items:
        raise ValueError("No line items could be extracted from the EDI content")

    item_columns = _collect_all_keys(line_items)
    logs.append(
        f"Document structure: {len(header)} header field(s), "
        f"{len(parties)} party/parties, "
        f"{len(line_items)} line item(s)"
    )

    # Apply user-defined transform to line items only
    if rules_code.strip():
        line_items = execute_rules(line_items, rules_code, logs)
        if not line_items:
            raise ValueError("No line items remain after transform (all filtered out or errored)")

    # Get CSV options
    delimiter = kwargs.get("delimiter", ",")
    quotechar = kwargs.get("quotechar", '"')
    quote_header = kwargs.get("quote_header", False)
    quote_data = kwargs.get("quote_data", True)

    fieldnames = _collect_all_keys(line_items)
    logs.append(f"Output: {len(line_items)} line item(s) with {len(fieldnames)} field(s)")
    logs.append(f"Line item columns: {', '.join(fieldnames)}")

    # Build output
    output = io.StringIO()

    # Optional preamble with header and party info as comments
    if include_preamble:
        if ts and schema_name:
            output.write(f"# EDI Document: {schema_name} ({ts})\n")
        if header:
            header_line = ", ".join(f"{k}={v}" for k, v in header.items() if v)
            output.write(f"# Header: {header_line}\n")
        for entity, fields in parties.items():
            party_line = ", ".join(f"{k}={v}" for k, v in fields.items() if v)
            output.write(f"# Party {entity}: {party_line}\n")
        output.write("#\n")

    # Header row
    if quote_header:
        header_writer = csv.writer(output, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_ALL)
    else:
        header_writer = csv.writer(output, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_NONE,
                                   escapechar="\\")
    header_writer.writerow(fieldnames)

    # Data rows
    data_quoting = csv.QUOTE_ALL if quote_data else csv.QUOTE_MINIMAL
    data_writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        delimiter=delimiter,
        quotechar=quotechar,
        quoting=data_quoting,
        extrasaction="ignore",
    )
    for row in line_items:
        clean_row = {k: str(v) if v is not None else "" for k, v in row.items()}
        data_writer.writerow(clean_row)

    return {
        "output": output.getvalue(),
        "logs": logs,
        "output_type": "CSV",
        "rows_processed": len(line_items),
        "columns_count": len(fieldnames),
    }


def _collect_all_keys(data: list[dict]) -> list[str]:
    seen = {}
    for row in data:
        for key in row:
            if key not in seen:
                seen[key] = True
    return list(seen.keys())
