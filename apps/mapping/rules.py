"""
Rules engine for data transformation during conversion.

Rules are a JSON dict applied to rows (list of dicts) before final output.

Supported rules:
    column_mapping   : {"old_name": "new_name"}  — Rename columns
    include_columns  : ["col1", "col2"]           — Keep only these columns
    exclude_columns  : ["col3"]                   — Drop these columns
    column_order     : ["col2", "col1"]           — Reorder output columns
    default_values   : {"col": "N/A"}             — Fill missing/empty values
    transforms       : {"col": "uppercase"}       — Transform values per column
    filter_rules     : {"col": "value"}           — Keep rows where col == value
    delimiter        : ";"                        — CSV delimiter (json_to_csv only)
    quote_header     : false                      — Quote CSV header row
    quote_data       : true                       — Quote CSV data fields

Transform types: uppercase, lowercase, trim, title, strip
"""

import logging

logger = logging.getLogger(__name__)


def apply_rules(rows: list[dict], rules: dict, logs: list[str]) -> tuple[list[dict], list[str]]:
    """
    Apply transformation rules to a list of row dicts.

    Args:
        rows: List of row dictionaries
        rules: Rules configuration dict
        logs: List to append processing messages to

    Returns:
        Tuple of (transformed_rows, column_order)
        column_order is a list of column names for the final output,
        or empty list if not specified.
    """
    if not rules:
        return rows, []

    # Step 1: Filter rows
    filter_rules = rules.get("filter_rules", {})
    if filter_rules:
        before_count = len(rows)
        rows = _apply_filter(rows, filter_rules)
        logs.append(f"Rule [filter]: {before_count} -> {len(rows)} rows (filter: {filter_rules})")

    # Step 2: Rename columns
    column_mapping = rules.get("column_mapping", {})
    if column_mapping:
        rows = _apply_column_rename(rows, column_mapping)
        logs.append(f"Rule [column_mapping]: Renamed {len(column_mapping)} column(s): {column_mapping}")

    # Step 3: Include columns (keep only these)
    include_columns = rules.get("include_columns", [])
    if include_columns:
        rows = _apply_include_columns(rows, include_columns)
        logs.append(f"Rule [include_columns]: Keeping {len(include_columns)} column(s): {include_columns}")

    # Step 4: Exclude columns (drop these)
    exclude_columns = rules.get("exclude_columns", [])
    if exclude_columns:
        rows = _apply_exclude_columns(rows, exclude_columns)
        logs.append(f"Rule [exclude_columns]: Dropping column(s): {exclude_columns}")

    # Step 5: Default values for missing/empty fields
    default_values = rules.get("default_values", {})
    if default_values:
        rows = _apply_defaults(rows, default_values)
        logs.append(f"Rule [default_values]: Applied defaults for: {list(default_values.keys())}")

    # Step 6: Value transforms
    transforms = rules.get("transforms", {})
    if transforms:
        rows = _apply_transforms(rows, transforms)
        logs.append(f"Rule [transforms]: Applied transforms: {transforms}")

    # Step 7: Column order
    column_order = rules.get("column_order", [])
    if column_order:
        logs.append(f"Rule [column_order]: Output order: {column_order}")

    return rows, column_order


def _apply_filter(rows: list[dict], filter_rules: dict) -> list[dict]:
    """Keep rows where every filter condition matches (case-insensitive equality)."""
    filtered = []
    for row in rows:
        match = True
        for col, expected in filter_rules.items():
            actual = str(row.get(col, "")).strip().lower()
            if actual != str(expected).strip().lower():
                match = False
                break
        if match:
            filtered.append(row)
    return filtered


def _apply_column_rename(rows: list[dict], mapping: dict) -> list[dict]:
    """Rename columns based on mapping."""
    result = []
    for row in rows:
        new_row = {}
        for key, value in row.items():
            new_key = mapping.get(key, key)
            new_row[new_key] = value
        result.append(new_row)
    return result


def _apply_include_columns(rows: list[dict], include: list[str]) -> list[dict]:
    """Keep only specified columns."""
    include_set = set(include)
    return [{k: v for k, v in row.items() if k in include_set} for row in rows]


def _apply_exclude_columns(rows: list[dict], exclude: list[str]) -> list[dict]:
    """Drop specified columns."""
    exclude_set = set(exclude)
    return [{k: v for k, v in row.items() if k not in exclude_set} for row in rows]


def _apply_defaults(rows: list[dict], defaults: dict) -> list[dict]:
    """Fill missing or empty values with defaults."""
    result = []
    for row in rows:
        new_row = dict(row)
        for col, default_val in defaults.items():
            if col not in new_row or new_row[col] is None or str(new_row[col]).strip() == "":
                new_row[col] = default_val
        result.append(new_row)
    return result


TRANSFORM_FUNCTIONS = {
    "uppercase": lambda v: v.upper() if isinstance(v, str) else v,
    "lowercase": lambda v: v.lower() if isinstance(v, str) else v,
    "trim": lambda v: v.strip() if isinstance(v, str) else v,
    "strip": lambda v: v.strip() if isinstance(v, str) else v,
    "title": lambda v: v.title() if isinstance(v, str) else v,
}


def _apply_transforms(rows: list[dict], transforms: dict) -> list[dict]:
    """Apply value transformations per column."""
    result = []
    for row in rows:
        new_row = dict(row)
        for col, transform_name in transforms.items():
            if col in new_row:
                func = TRANSFORM_FUNCTIONS.get(transform_name)
                if func:
                    new_row[col] = func(new_row[col])
        result.append(new_row)
    return result
