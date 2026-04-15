"""
EDI to JSON file mapper.

Parses EDI X12 content into a nested document structure (header, parties,
line items), optionally applies a user-defined apply_rules function to the
line items, and outputs JSON.

Output shape:
    {
        "header":     { invoice/PO-level fields },
        "parties":    { "BY": {...}, "ST": {...}, "SE": {...} },
        "line_items": [ {...item 1...}, {...item 2...}, ... ]
    }

The header and parties are emitted ONCE per document — not repeated on every
line item. apply_rules runs on each line item in turn, so users transform
only item-specific data.
"""

import json

from apps.mapping.executor import execute_rules
from apps.mapping.maps.edi_parser import parse_edi


def edi_to_json_file_mapper(content: str, rules_code: str = "", **kwargs) -> dict:
    """
    Convert EDI X12 content to nested JSON.

    Args:
        content: Raw EDI string
        rules_code: User's Python code with a def apply_rules(row): function.
                    Applied to each line item (NOT to header or parties).
        **kwargs:
            transaction_set: e.g. '850', '810' (auto-detected if omitted)
            include_envelope: Whether to include envelope fields in header (default: True)
            indent: JSON indentation (default: 2)

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("EDI content is empty")

    transaction_set = kwargs.get("transaction_set", "") or None
    include_envelope = kwargs.get("include_envelope", True)

    # Parse EDI into nested document structure
    parsed = parse_edi(
        content,
        transaction_set=transaction_set,
        include_envelope=include_envelope,
        mode="items",
    )

    logs.extend(parsed["logs"])

    header = parsed["header"]
    parties = parsed["parties"]
    line_items = parsed["rows"]  # item-only rows

    if not line_items:
        raise ValueError("No line items could be extracted from the EDI content")

    item_columns = _collect_all_keys(line_items)
    logs.append(
        f"Document structure: {len(header)} header field(s), "
        f"{len(parties)} party/parties ({', '.join(parties.keys()) or 'none'}), "
        f"{len(line_items)} line item(s) with {len(item_columns)} field(s)"
    )

    # Apply user-defined transform to line items only
    if rules_code.strip():
        line_items = execute_rules(line_items, rules_code, logs)
        if not line_items:
            raise ValueError("No line items remain after transform (all filtered out or errored)")

    final_item_columns = _collect_all_keys(line_items)
    logs.append(
        f"Output: {len(line_items)} line item(s) with {len(final_item_columns)} field(s)"
    )
    logs.append(f"Line item columns: {', '.join(final_item_columns)}")

    # Build nested JSON output — one document with header/parties/items
    document = {
        "header": header,
        "parties": parties,
        "line_items": line_items,
    }

    indent = kwargs.get("indent", 2)
    output = json.dumps(document, indent=indent, ensure_ascii=False)

    return {
        "output": output,
        "logs": logs,
        "output_type": "JSON",
        "rows_processed": len(line_items),
        "columns_count": len(final_item_columns),
    }


def _collect_all_keys(data: list[dict]) -> list[str]:
    seen = {}
    for row in data:
        for key in row:
            if key not in seen:
                seen[key] = True
    return list(seen.keys())
