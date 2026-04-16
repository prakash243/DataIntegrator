"""
EDI to JSON file mapper.

Parses EDI X12 content into a nested document structure (header, parties,
line items), optionally applies a user-defined apply_rules function to the
line items, and outputs JSON.

Supports a no-code field_config for removing/renaming keys across all
sections (header, parties, line_items) without writing apply_rules code.

Output shape:
    {
        "header":     { invoice/PO-level fields },
        "parties":    { "BY": {...}, "ST": {...}, "SE": {...} },
        "line_items": [ {...item 1...}, {...item 2...}, ... ]
    }
"""

import json

from apps.mapping.executor import execute_rules
from apps.mapping.maps.edi_parser import parse_edi


def _apply_field_config(data: dict, config: dict) -> dict:
    """
    Apply field_config to include/exclude/rename fields in a flat dict.

    Config format:
        {
            "exclude": ["field_a", "field_b"],
            "rename":  {"old_name": "new_name", ...}
        }
    """
    if not config:
        return data

    exclude = set(config.get("exclude", []))
    rename = config.get("rename", {})

    result = {}
    for key, value in data.items():
        if key in exclude:
            continue
        new_key = rename.get(key, key)
        result[new_key] = value
    return result


def _apply_field_config_to_parties(parties: dict, config: dict) -> dict:
    """Apply field_config to every party's inner fields."""
    if not config:
        return parties

    exclude = set(config.get("exclude", []))
    rename = config.get("rename", {})
    exclude_parties = set(config.get("exclude_parties", []))

    result = {}
    for entity, fields in parties.items():
        if entity in exclude_parties:
            continue
        cleaned = {}
        for key, value in fields.items():
            if key in exclude:
                continue
            new_key = rename.get(key, key)
            cleaned[new_key] = value
        result[entity] = cleaned
    return result


def _apply_field_config_to_items(items: list[dict], config: dict) -> list[dict]:
    """Apply field_config to each line item dict."""
    if not config:
        return items

    exclude = set(config.get("exclude", []))
    rename = config.get("rename", {})

    result = []
    for row in items:
        cleaned = {}
        for key, value in row.items():
            if key in exclude:
                continue
            new_key = rename.get(key, key)
            cleaned[new_key] = value
        result.append(cleaned)
    return result


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
            field_config: No-code field configuration dict:
                {
                    "header":  {"exclude": [...], "rename": {...}},
                    "parties": {"exclude": [...], "rename": {...}, "exclude_parties": [...]},
                    "items":   {"exclude": [...], "rename": {...}}
                }

    Returns:
        dict with keys: output, logs, output_type, rows_processed, columns_count
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("EDI content is empty")

    transaction_set = kwargs.get("transaction_set", "") or None
    include_envelope = kwargs.get("include_envelope", True)
    field_config = kwargs.get("field_config") or {}

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
    line_items = parsed["rows"]

    if not line_items:
        raise ValueError("No line items could be extracted from the EDI content")

    item_columns = _collect_all_keys(line_items)
    logs.append(
        f"Document structure: {len(header)} header field(s), "
        f"{len(parties)} party/parties ({', '.join(parties.keys()) or 'none'}), "
        f"{len(line_items)} line item(s) with {len(item_columns)} field(s)"
    )

    # Apply no-code field_config (exclude/rename) — runs BEFORE apply_rules
    if field_config:
        header_cfg = field_config.get("header")
        parties_cfg = field_config.get("parties")
        items_cfg = field_config.get("items")

        if header_cfg:
            before = len(header)
            header = _apply_field_config(header, header_cfg)
            renames = len(header_cfg.get("rename", {}))
            excludes = before - len(header)
            if excludes or renames:
                logs.append(f"Field config (header): {excludes} removed, {renames} renamed")

        if parties_cfg:
            excluded_parties = len(parties_cfg.get("exclude_parties", []))
            parties = _apply_field_config_to_parties(parties, parties_cfg)
            renames = len(parties_cfg.get("rename", {}))
            excludes = len(parties_cfg.get("exclude", []))
            if excludes or renames or excluded_parties:
                logs.append(f"Field config (parties): {excluded_parties} parties removed, {excludes} fields removed, {renames} renamed")

        if items_cfg:
            line_items = _apply_field_config_to_items(line_items, items_cfg)
            renames = len(items_cfg.get("rename", {}))
            excludes = len(items_cfg.get("exclude", []))
            if excludes or renames:
                logs.append(f"Field config (items): {excludes} removed, {renames} renamed")

    # Apply user-defined transform to line items only (runs AFTER field_config)
    if rules_code.strip():
        line_items = execute_rules(line_items, rules_code, logs)
        if not line_items:
            raise ValueError("No line items remain after transform (all filtered out or errored)")

    final_item_columns = _collect_all_keys(line_items)
    logs.append(
        f"Output: {len(line_items)} line item(s) with {len(final_item_columns)} field(s)"
    )
    logs.append(f"Line item columns: {', '.join(final_item_columns)}")

    # Build nested JSON output
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
