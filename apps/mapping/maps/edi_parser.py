"""
EDI (X12) Parser.

Tokenizes raw EDI content, detects delimiters from the ISA segment,
parses envelope (ISA/GS/ST) and business segments, and maps segment
elements to human-readable field names using transaction-set schemas.
"""

import json
import os
import re


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------

_SCHEMA_DIR = os.path.join(os.path.dirname(__file__), "..", "schemas")
_SCHEMA_CACHE: dict[str, dict] = {}


def load_schema(transaction_set: str) -> dict:
    """
    Load a transaction-set schema (e.g. '850') from the schemas directory.
    Returns the parsed JSON dict, or an empty dict if not found.
    """
    if transaction_set in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[transaction_set]

    path = os.path.join(_SCHEMA_DIR, f"x12_{transaction_set}.json")
    if not os.path.isfile(path):
        return {}

    with open(path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    _SCHEMA_CACHE[transaction_set] = schema
    return schema


def list_schemas() -> list[dict]:
    """Return a list of available schema summaries."""
    schemas = []
    if not os.path.isdir(_SCHEMA_DIR):
        return schemas
    for fname in sorted(os.listdir(_SCHEMA_DIR)):
        if fname.startswith("x12_") and fname.endswith(".json"):
            ts = fname.replace("x12_", "").replace(".json", "")
            try:
                s = load_schema(ts)
                schemas.append({
                    "transaction_set": ts,
                    "name": s.get("name", ts),
                    "description": s.get("description", ""),
                })
            except Exception:
                pass
    return schemas


# ---------------------------------------------------------------------------
# Delimiter detection
# ---------------------------------------------------------------------------

def detect_delimiters(content: str) -> dict:
    """
    Detect X12 delimiters from the ISA segment header.

    The ISA segment is always exactly 106 characters:
      - Position 3:   element separator
      - Position 104: sub-element separator (component separator)
      - Position 105: segment terminator

    Returns dict with keys: element_sep, sub_element_sep, segment_term
    """
    # Strip leading whitespace / BOM
    raw = content.lstrip("\ufeff \t\r\n")

    if not raw.upper().startswith("ISA"):
        raise ValueError(
            "Not a valid X12 EDI file: content must start with 'ISA' segment"
        )

    if len(raw) < 106:
        raise ValueError(
            "ISA segment is too short (expected at least 106 characters)"
        )

    element_sep = raw[3]
    segment_term = raw[105]
    sub_element_sep = raw[104]

    return {
        "element_sep": element_sep,
        "sub_element_sep": sub_element_sep,
        "segment_term": segment_term,
    }


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

def tokenize(content: str, delimiters: dict | None = None) -> list[list[str]]:
    """
    Split raw EDI content into a list of segments, where each segment
    is a list of element strings.
    """
    if delimiters is None:
        delimiters = detect_delimiters(content)

    seg_term = delimiters["segment_term"]
    elem_sep = delimiters["element_sep"]

    # Strip BOM and leading/trailing whitespace
    raw = content.strip("\ufeff \t\r\n")

    # Split by segment terminator
    raw_segments = raw.split(seg_term)

    segments = []
    for seg in raw_segments:
        seg = seg.strip()
        if not seg:
            continue
        elements = seg.split(elem_sep)
        segments.append(elements)

    return segments


# ---------------------------------------------------------------------------
# Envelope parsing
# ---------------------------------------------------------------------------

def parse_envelope(segments: list[list[str]]) -> tuple[dict, list[list[str]]]:
    """
    Extract ISA/IEA, GS/GE, ST/SE envelope data and return the
    business segments separately.

    Returns: (envelope_dict, business_segments_list)
    """
    envelope = {
        "interchange": {},
        "functional_group": {},
        "transaction_set": {},
    }
    business_segments = []

    for seg in segments:
        seg_id = seg[0].upper().strip()

        if seg_id == "ISA":
            envelope["interchange"] = _parse_isa(seg)
        elif seg_id == "IEA":
            envelope["interchange"]["ack_count"] = _safe_get(seg, 1)
            envelope["interchange"]["control_number_trailer"] = _safe_get(seg, 2)
        elif seg_id == "GS":
            envelope["functional_group"] = _parse_gs(seg)
        elif seg_id == "GE":
            envelope["functional_group"]["transaction_count"] = _safe_get(seg, 1)
            envelope["functional_group"]["control_number_trailer"] = _safe_get(seg, 2)
        elif seg_id == "ST":
            envelope["transaction_set"]["type"] = _safe_get(seg, 1)
            envelope["transaction_set"]["control_number"] = _safe_get(seg, 2)
        elif seg_id == "SE":
            envelope["transaction_set"]["segment_count"] = _safe_get(seg, 1)
            envelope["transaction_set"]["control_number_trailer"] = _safe_get(seg, 2)
        elif seg_id == "CTT":
            # Transaction totals — include as metadata
            envelope["transaction_set"]["total_line_items"] = _safe_get(seg, 1)
        else:
            business_segments.append(seg)

    return envelope, business_segments


def _parse_isa(seg: list[str]) -> dict:
    return {
        "auth_qualifier": _safe_get(seg, 1),
        "auth_info": _safe_get(seg, 2, strip=True),
        "security_qualifier": _safe_get(seg, 3),
        "security_info": _safe_get(seg, 4, strip=True),
        "sender_qualifier": _safe_get(seg, 5),
        "sender_id": _safe_get(seg, 6, strip=True),
        "receiver_qualifier": _safe_get(seg, 7),
        "receiver_id": _safe_get(seg, 8, strip=True),
        "date": _safe_get(seg, 9),
        "time": _safe_get(seg, 10),
        "standards_id": _safe_get(seg, 11),
        "version": _safe_get(seg, 12),
        "control_number": _safe_get(seg, 13),
        "ack_requested": _safe_get(seg, 14),
        "usage_indicator": _safe_get(seg, 15),
    }


def _parse_gs(seg: list[str]) -> dict:
    return {
        "functional_id": _safe_get(seg, 1),
        "sender_code": _safe_get(seg, 2),
        "receiver_code": _safe_get(seg, 3),
        "date": _safe_get(seg, 4),
        "time": _safe_get(seg, 5),
        "control_number": _safe_get(seg, 6),
        "responsible_agency": _safe_get(seg, 7),
        "version": _safe_get(seg, 8),
    }


def _safe_get(lst: list, index: int, strip: bool = False) -> str:
    if index < len(lst):
        val = lst[index]
        return val.strip() if strip else val
    return ""


# ---------------------------------------------------------------------------
# Schema-based segment mapping
# ---------------------------------------------------------------------------

def map_segment(seg: list[str], schema: dict) -> dict | None:
    """
    Map a single segment's elements to named fields using a schema.

    If the segment ID is not in the schema, returns a generic dict
    with positional keys (element_1, element_2, ...).
    """
    seg_id = seg[0].upper().strip()
    seg_defs = schema.get("segments", {})

    if seg_id in seg_defs:
        seg_schema = seg_defs[seg_id]
        elements_map = seg_schema.get("elements", {})
        result = {"_segment": seg_id}
        for pos_str, field_name in elements_map.items():
            pos = int(pos_str)
            result[field_name] = _safe_get(seg, pos)
        return result

    # Fallback: generic mapping
    result = {"_segment": seg_id}
    for i, val in enumerate(seg[1:], 1):
        result[f"element_{i}"] = val
    return result


# ---------------------------------------------------------------------------
# Row builder: flatten header + loop segments into rows
# ---------------------------------------------------------------------------

def build_rows(
    envelope: dict,
    business_segments: list[list[str]],
    schema: dict,
    include_envelope: bool = True,
    output_format: str = "flat",
) -> list[dict]:
    """
    Convert parsed EDI segments into a list of flat row dicts suitable
    for JSON/CSV output.

    For 'flat' output_format:
      - Header segments (non-loop) are collected as shared fields
      - Loop segments (e.g. PO1 in 850) produce one row each
      - Header fields are repeated on every row

    For 'nested' output_format:
      - Returns a single-element list with full nested structure
    """
    seg_defs = schema.get("segments", {})

    # Identify which segments are loops (produce multiple rows)
    loop_seg_ids = set()
    for seg_id, seg_def in seg_defs.items():
        if seg_def.get("loop", False):
            loop_seg_ids.add(seg_id)

    # If no loop segments defined in schema, treat every segment as a row
    if not loop_seg_ids:
        # Each segment becomes its own row
        rows = []
        for seg in business_segments:
            mapped = map_segment(seg, schema)
            if mapped:
                mapped.pop("_segment", None)
                if include_envelope:
                    mapped = _prepend_envelope_fields(envelope, mapped)
                rows.append(mapped)
        return rows if rows else _fallback_single_row(envelope, business_segments, schema, include_envelope)

    # Collect header (non-loop) segment data
    header_data = {}
    # Track party segments (N1 loops) with prefixes
    party_counter = 0

    # Collect loop segment rows
    loop_rows = []

    for seg in business_segments:
        seg_id = seg[0].upper().strip()
        mapped = map_segment(seg, schema)
        if mapped is None:
            continue

        mapped.pop("_segment", None)

        if seg_id in loop_seg_ids:
            loop_rows.append(mapped)
        elif seg_id == "N1":
            # Party identification — prefix with entity type
            entity = mapped.get("entity_identifier", f"party_{party_counter}")
            party_counter += 1
            for k, v in mapped.items():
                if k != "entity_identifier":
                    header_data[f"{entity}_{k}"] = v
        else:
            header_data.update(mapped)

    if not loop_rows:
        # No loop items found — return header data as a single row
        row = dict(header_data)
        if include_envelope:
            row = _prepend_envelope_fields(envelope, row)
        return [row]

    # Flatten: repeat header data on each loop row
    rows = []
    for loop_data in loop_rows:
        row = {}
        if include_envelope:
            row.update(_envelope_flat_fields(envelope))
        row.update(header_data)
        row.update(loop_data)
        rows.append(row)

    return rows


def _prepend_envelope_fields(envelope: dict, row: dict) -> dict:
    result = _envelope_flat_fields(envelope)
    result.update(row)
    return result


def _envelope_flat_fields(envelope: dict) -> dict:
    """Extract key envelope fields into a flat dict with prefixed keys."""
    fields = {}
    ic = envelope.get("interchange", {})
    if ic.get("sender_id"):
        fields["edi_sender"] = ic["sender_id"]
    if ic.get("receiver_id"):
        fields["edi_receiver"] = ic["receiver_id"]

    ts = envelope.get("transaction_set", {})
    if ts.get("type"):
        fields["edi_transaction_type"] = ts["type"]
    if ts.get("control_number"):
        fields["edi_control_number"] = ts["control_number"]

    return fields


def _fallback_single_row(envelope, business_segments, schema, include_envelope):
    """When no segments matched, produce a single row with all data."""
    row = {}
    if include_envelope:
        row.update(_envelope_flat_fields(envelope))
    for seg in business_segments:
        mapped = map_segment(seg, schema)
        if mapped:
            seg_id = mapped.pop("_segment", "")
            for k, v in mapped.items():
                key = f"{seg_id}_{k}" if k in row else k
                row[key] = v
    return [row] if row else []


# ---------------------------------------------------------------------------
# High-level parse function
# ---------------------------------------------------------------------------

def parse_edi(
    content: str,
    transaction_set: str | None = None,
    include_envelope: bool = True,
) -> dict:
    """
    Parse raw EDI X12 content into structured data.

    Args:
        content: Raw EDI string
        transaction_set: e.g. '850', '810'. If None, auto-detect from ST segment.
        include_envelope: Whether to include envelope fields in output rows.

    Returns:
        dict with keys:
            - rows: list of flat row dicts
            - envelope: parsed envelope metadata
            - transaction_set: detected/used transaction set code
            - schema_name: human-readable name of the transaction set
            - segment_count: number of business segments parsed
            - logs: list of processing log messages
    """
    logs = []

    if not content or not content.strip():
        raise ValueError("EDI content is empty")

    # Detect delimiters
    delimiters = detect_delimiters(content)
    logs.append(
        f"Detected delimiters: element='{delimiters['element_sep']}' "
        f"segment='{delimiters['segment_term']}' "
        f"sub-element='{delimiters['sub_element_sep']}'"
    )

    # Tokenize
    segments = tokenize(content, delimiters)
    logs.append(f"Tokenized {len(segments)} segment(s)")

    if not segments:
        raise ValueError("No segments found in EDI content")

    # Parse envelope
    envelope, business_segments = parse_envelope(segments)
    logs.append(f"Parsed envelope: {len(business_segments)} business segment(s)")

    # Auto-detect transaction set if not provided
    detected_ts = envelope.get("transaction_set", {}).get("type", "")
    if not transaction_set:
        transaction_set = detected_ts
    if transaction_set:
        logs.append(f"Transaction set: {transaction_set}")
    else:
        logs.append("Warning: Could not detect transaction set type")

    # Load schema
    schema = load_schema(transaction_set) if transaction_set else {}
    schema_name = schema.get("name", "Unknown")
    if schema:
        logs.append(f"Loaded schema: {schema_name}")
    else:
        logs.append(f"No schema found for '{transaction_set}' — using generic field names")

    # Build rows
    rows = build_rows(
        envelope,
        business_segments,
        schema,
        include_envelope=include_envelope,
    )
    logs.append(f"Built {len(rows)} output row(s)")

    return {
        "rows": rows,
        "envelope": envelope,
        "transaction_set": transaction_set,
        "schema_name": schema_name,
        "segment_count": len(business_segments),
        "logs": logs,
    }
