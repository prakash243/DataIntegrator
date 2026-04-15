"""
EDI (X12) Parser — lxml-inspired object model.

Parses raw EDI content into a navigable document tree (like lxml parses XML
into an ElementTree). The document preserves the full segment hierarchy so
callers can navigate, query, and flatten as needed.

Design inspired by lxml:
    lxml:  tree = etree.parse(file)  →  root.find('Item')  →  elem.text
    EDI:   doc  = EDIDocument.parse(content)  →  doc.find('BEG')  →  seg.fields

Key classes:
    EDISegment  — A single parsed segment (like lxml Element)
    EDILoop     — A group of related segments (like a parent Element with children)
    EDIDocument — The full parsed document (like lxml ElementTree)
"""

import json
import os


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
# EDISegment — like lxml Element
# ---------------------------------------------------------------------------

class EDISegment:
    """
    A single parsed EDI segment — analogous to an lxml Element.

    Attributes:
        tag:      Segment ID (e.g. 'BEG', 'N1', 'PO1')
        elements: Raw element values as a list of strings
        fields:   Schema-mapped dict of {field_name: value}
        name:     Human-readable segment name from schema (e.g. 'Purchase Order Line Item')
    """

    __slots__ = ("tag", "elements", "fields", "name")

    def __init__(self, tag: str, elements: list[str], fields: dict | None = None, name: str = ""):
        self.tag = tag
        self.elements = elements
        self.fields = fields or {}
        self.name = name

    def get(self, field_name: str, default: str = "") -> str:
        """Get a field value by schema-mapped name."""
        return self.fields.get(field_name, default)

    def __repr__(self):
        return f"EDISegment({self.tag!r}, fields={self.fields})"

    def __getitem__(self, field_name: str) -> str:
        return self.fields[field_name]

    def __contains__(self, field_name: str) -> bool:
        return field_name in self.fields


# ---------------------------------------------------------------------------
# EDILoop — a group of related segments (like a parent Element with children)
# ---------------------------------------------------------------------------

class EDILoop:
    """
    A group of related segments that form a logical unit.

    For example, an N1 party loop groups:  N1 + N2 + N3 + N4
    A PO1 line item loop groups:           PO1 + PID + MEA + ...

    Attributes:
        tag:       The segment ID that starts this loop (e.g. 'N1', 'PO1')
        trigger:   The trigger segment (the first EDISegment in the loop)
        children:  List of child EDISegments that belong to this loop
        fields:    Merged dict of all fields from trigger + children
    """

    __slots__ = ("tag", "trigger", "children")

    def __init__(self, trigger: EDISegment):
        self.tag = trigger.tag
        self.trigger = trigger
        self.children = []

    def add_child(self, segment: EDISegment):
        self.children.append(segment)

    @property
    def fields(self) -> dict:
        """Merge all fields from trigger + children into one dict."""
        merged = dict(self.trigger.fields)
        for child in self.children:
            merged.update(child.fields)
        return merged

    def find(self, tag: str) -> EDISegment | None:
        """Find first child segment by tag."""
        for child in self.children:
            if child.tag == tag:
                return child
        return None

    def findall(self, tag: str) -> list[EDISegment]:
        """Find all child segments by tag."""
        return [child for child in self.children if child.tag == tag]

    def get(self, field_name: str, default: str = "") -> str:
        """Get a field value from the merged fields."""
        return self.fields.get(field_name, default)

    def __repr__(self):
        child_tags = [c.tag for c in self.children]
        return f"EDILoop({self.tag!r}, children={child_tags})"


# ---------------------------------------------------------------------------
# EDIDocument — like lxml ElementTree
# ---------------------------------------------------------------------------

# Segments that are part of N1 party loops (follow an N1 trigger)
_N1_CHILD_TAGS = {"N2", "N3", "N4", "PER"}

# Envelope/control segment IDs
_ENVELOPE_TAGS = {"ISA", "IEA", "GS", "GE", "ST", "SE", "CTT"}


class EDIDocument:
    """
    The full parsed EDI document — analogous to an lxml ElementTree.

    Provides navigation methods (find, findall, iter) to traverse
    the parsed structure without immediate flattening.

    Usage:
        doc = EDIDocument.parse(raw_edi_content)

        # Navigate like lxml
        beg = doc.find('BEG')
        print(beg.get('purchase_order_number'))

        # Get all parties
        for party in doc.findall('N1'):
            print(party.get('name'), party.get('city'))

        # Get all line items
        for item in doc.findall('PO1'):
            print(item.get('product_id'), item.get('quantity_ordered'))

        # Flatten to rows for JSON/CSV output
        rows = doc.to_rows()
    """

    def __init__(self):
        self.envelope = {
            "interchange": {},
            "functional_group": {},
            "transaction_set": {},
        }
        self.segments: list[EDISegment] = []      # all business segments in order
        self.loops: list[EDILoop] = []             # grouped loops (N1, PO1, etc.)
        self.header_segments: list[EDISegment] = []  # non-loop, non-party segments
        self.schema: dict = {}
        self.schema_name: str = "Unknown"
        self.transaction_set: str = ""
        self.delimiters: dict = {}
        self.logs: list[str] = []

    # --- Navigation (lxml-inspired) ---

    def find(self, tag: str) -> EDISegment | EDILoop | None:
        """
        Find the first segment or loop matching a tag.
        For loop-trigger tags (N1, PO1, etc.), returns an EDILoop.
        For other tags, returns an EDISegment.
        """
        tag = tag.upper()
        # Check loops first
        for loop in self.loops:
            if loop.tag == tag:
                return loop
        # Then check individual segments
        for seg in self.header_segments:
            if seg.tag == tag:
                return seg
        for seg in self.segments:
            if seg.tag == tag:
                return seg
        return None

    def findall(self, tag: str) -> list[EDISegment | EDILoop]:
        """
        Find all segments or loops matching a tag.
        For loop-trigger tags, returns list of EDILoop objects.
        For other tags, returns list of EDISegment objects.
        """
        tag = tag.upper()
        # Check if this tag has any loops
        loops = [loop for loop in self.loops if loop.tag == tag]
        if loops:
            return loops
        # Fall back to raw segments
        return [seg for seg in self.segments if seg.tag == tag]

    def iter(self) -> list[EDISegment]:
        """Iterate over all business segments in document order."""
        return list(self.segments)

    @property
    def parties(self) -> list[EDILoop]:
        """Get all N1 party loops."""
        return [loop for loop in self.loops if loop.tag == "N1"]

    @property
    def line_items(self) -> list[EDILoop | EDISegment]:
        """Get all line item loops/segments (PO1, IT1, LIN, SN1)."""
        item_tags = {"PO1", "IT1", "LIN", "SN1"}
        results = []
        for loop in self.loops:
            if loop.tag in item_tags:
                results.append(loop)
        if results:
            return results
        # Fallback: return raw segments
        for seg in self.segments:
            if seg.tag in item_tags:
                results.append(seg)
        return results

    # --- Flattening to rows ---

    def to_rows(self, include_envelope: bool = True) -> list[dict]:
        """
        Flatten the document tree into a list of row dicts suitable
        for JSON/CSV output.

        Strategy:
          1. Collect header fields from non-loop, non-party segments
          2. Collect party fields with entity-type prefix (BY_name, ST_city, etc.)
          3. For each line item loop → one output row with header + party + item data
          4. If no line items exist → single row with header + party data
        """
        # 1. Header fields from non-loop segments
        header = {}
        for seg in self.header_segments:
            header.update(seg.fields)

        # 2. Party fields — prefix EVERY field with entity identifier
        party_data = {}
        for party_loop in self.parties:
            entity = party_loop.trigger.get("entity_identifier", "")
            if not entity:
                entity = f"party_{len(party_data)}"

            # Prefix all fields from the party loop (N1 + N3 + N4 + ...)
            for field_name, value in party_loop.fields.items():
                if field_name == "entity_identifier":
                    continue
                party_data[f"{entity}_{field_name}"] = value

        # 3. Line items
        items = self.line_items
        if not items:
            # No line items — single row with header + party data
            row = {}
            if include_envelope:
                row.update(self._envelope_fields())
            row.update(header)
            row.update(party_data)
            return [row] if row else []

        # One row per line item, header + party fields repeated
        rows = []
        for item in items:
            row = {}
            if include_envelope:
                row.update(self._envelope_fields())
            row.update(header)
            row.update(party_data)

            # Add item fields
            if isinstance(item, EDILoop):
                row.update(item.fields)
            else:
                row.update(item.fields)

            rows.append(row)

        return rows

    def _envelope_fields(self) -> dict:
        """Extract key envelope fields into a flat dict."""
        fields = {}
        ic = self.envelope.get("interchange", {})
        if ic.get("sender_id"):
            fields["edi_sender"] = ic["sender_id"]
        if ic.get("receiver_id"):
            fields["edi_receiver"] = ic["receiver_id"]

        ts = self.envelope.get("transaction_set", {})
        if ts.get("type"):
            fields["edi_transaction_type"] = ts["type"]
        if ts.get("control_number"):
            fields["edi_control_number"] = ts["control_number"]

        return fields

    # --- Factory: parse raw EDI content ---

    @classmethod
    def parse(cls, content: str, transaction_set: str | None = None) -> "EDIDocument":
        """
        Parse raw EDI X12 content into an EDIDocument.

        Like lxml's etree.parse() — creates the full object tree first,
        then you navigate and flatten as needed.

        Args:
            content: Raw EDI string
            transaction_set: e.g. '850', '810'. Auto-detected if None.

        Returns:
            EDIDocument instance with all segments parsed and grouped
        """
        doc = cls()

        if not content or not content.strip():
            raise ValueError("EDI content is empty")

        # Detect delimiters from ISA header
        doc.delimiters = _detect_delimiters(content)
        doc.logs.append(
            f"Detected delimiters: element='{doc.delimiters['element_sep']}' "
            f"segment='{doc.delimiters['segment_term']}' "
            f"sub-element='{doc.delimiters['sub_element_sep']}'"
        )

        # Tokenize into raw segment arrays
        raw_segments = _tokenize(content, doc.delimiters)
        doc.logs.append(f"Tokenized {len(raw_segments)} segment(s)")

        if not raw_segments:
            raise ValueError("No segments found in EDI content")

        # Parse envelope and separate business segments
        business_raw = _parse_envelope(raw_segments, doc.envelope)
        doc.logs.append(f"Parsed envelope: {len(business_raw)} business segment(s)")

        # Auto-detect transaction set
        detected_ts = doc.envelope.get("transaction_set", {}).get("type", "")
        if not transaction_set:
            transaction_set = detected_ts
        doc.transaction_set = transaction_set or ""

        if doc.transaction_set:
            doc.logs.append(f"Transaction set: {doc.transaction_set}")
        else:
            doc.logs.append("Warning: Could not detect transaction set type")

        # Load schema
        doc.schema = load_schema(doc.transaction_set) if doc.transaction_set else {}
        doc.schema_name = doc.schema.get("name", "Unknown")
        if doc.schema:
            doc.logs.append(f"Loaded schema: {doc.schema_name}")
        else:
            doc.logs.append(f"No schema found for '{doc.transaction_set}' — using generic field names")

        # Parse each raw segment into EDISegment objects
        for raw_seg in business_raw:
            seg = _make_segment(raw_seg, doc.schema)
            doc.segments.append(seg)

        # Group segments into loops (N1 loops, PO1 loops, etc.)
        _group_into_loops(doc)

        doc.logs.append(
            f"Parsed into {len(doc.header_segments)} header segment(s), "
            f"{len(doc.parties)} party loop(s), "
            f"{len(doc.line_items)} line item(s)"
        )

        return doc

    def __repr__(self):
        return (
            f"EDIDocument(transaction_set={self.transaction_set!r}, "
            f"segments={len(self.segments)}, "
            f"loops={len(self.loops)})"
        )


# ---------------------------------------------------------------------------
# Internal parsing functions
# ---------------------------------------------------------------------------

def _detect_delimiters(content: str) -> dict:
    """Detect X12 delimiters from the ISA segment header (fixed positions)."""
    raw = content.lstrip("\ufeff \t\r\n")

    if not raw.upper().startswith("ISA"):
        raise ValueError("Not a valid X12 EDI file: content must start with 'ISA' segment")

    if len(raw) < 106:
        raise ValueError("ISA segment is too short (expected at least 106 characters)")

    return {
        "element_sep": raw[3],
        "sub_element_sep": raw[104],
        "segment_term": raw[105],
    }


def _tokenize(content: str, delimiters: dict) -> list[list[str]]:
    """Split raw EDI into a list of segments (each a list of element strings)."""
    raw = content.strip("\ufeff \t\r\n")
    raw_segments = raw.split(delimiters["segment_term"])

    segments = []
    for seg in raw_segments:
        seg = seg.strip()
        if seg:
            segments.append(seg.split(delimiters["element_sep"]))

    return segments


def _safe_get(lst: list, index: int, strip: bool = False) -> str:
    if index < len(lst):
        val = lst[index]
        return val.strip() if strip else val
    return ""


def _parse_envelope(raw_segments: list[list[str]], envelope: dict) -> list[list[str]]:
    """Extract envelope segments, populate envelope dict, return business segments."""
    business = []

    for seg in raw_segments:
        seg_id = seg[0].upper().strip()

        if seg_id == "ISA":
            envelope["interchange"] = {
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
        elif seg_id == "IEA":
            envelope["interchange"]["ack_count"] = _safe_get(seg, 1)
            envelope["interchange"]["control_number_trailer"] = _safe_get(seg, 2)
        elif seg_id == "GS":
            envelope["functional_group"] = {
                "functional_id": _safe_get(seg, 1),
                "sender_code": _safe_get(seg, 2),
                "receiver_code": _safe_get(seg, 3),
                "date": _safe_get(seg, 4),
                "time": _safe_get(seg, 5),
                "control_number": _safe_get(seg, 6),
                "responsible_agency": _safe_get(seg, 7),
                "version": _safe_get(seg, 8),
            }
        elif seg_id == "GE":
            envelope["functional_group"]["transaction_count"] = _safe_get(seg, 1)
            envelope["functional_group"]["control_number_trailer"] = _safe_get(seg, 2)
        elif seg_id == "ST":
            envelope["transaction_set"] = {
                "type": _safe_get(seg, 1),
                "control_number": _safe_get(seg, 2),
            }
        elif seg_id == "SE":
            envelope["transaction_set"]["segment_count"] = _safe_get(seg, 1)
            envelope["transaction_set"]["control_number_trailer"] = _safe_get(seg, 2)
        elif seg_id == "CTT":
            envelope["transaction_set"]["total_line_items"] = _safe_get(seg, 1)
        else:
            business.append(seg)

    return business


def _make_segment(raw_seg: list[str], schema: dict) -> EDISegment:
    """Create an EDISegment from a raw element list, applying schema mapping."""
    tag = raw_seg[0].upper().strip()
    seg_defs = schema.get("segments", {})

    if tag in seg_defs:
        seg_schema = seg_defs[tag]
        elements_map = seg_schema.get("elements", {})
        fields = {}
        for pos_str, field_name in elements_map.items():
            fields[field_name] = _safe_get(raw_seg, int(pos_str))
        return EDISegment(tag, raw_seg, fields, name=seg_schema.get("name", ""))

    # Fallback: generic positional mapping
    fields = {}
    for i, val in enumerate(raw_seg[1:], 1):
        fields[f"element_{i}"] = val
    return EDISegment(tag, raw_seg, fields)


def _group_into_loops(doc: EDIDocument) -> None:
    """
    Walk the flat segment list and group related segments into EDILoops.

    Grouping logic (mirrors how lxml groups children under parent elements):
      - N1 starts a party loop; following N2/N3/N4/PER segments are its children
      - PO1/IT1/LIN/SN1 (schema "loop": true) start line item loops;
        following PID/MEA/SAC/REF/DTM segments are their children (until next
        loop trigger or another N1)
      - All other segments are header segments
    """
    seg_defs = doc.schema.get("segments", {})

    # Identify loop trigger tags from schema
    loop_trigger_tags = set()
    for seg_id, seg_def in seg_defs.items():
        if seg_def.get("loop", False):
            loop_trigger_tags.add(seg_id)

    # Segment IDs that are children of an N1 party loop
    n1_child_tags = {"N2", "N3", "N4", "PER"}

    # Segment IDs that are children of a line-item loop
    item_child_tags = {"PID", "MEA", "SAC", "REF", "DTM", "PO4", "MAN", "TXI"}

    current_loop: EDILoop | None = None
    current_loop_type: str = ""  # "party" or "item"

    for seg in doc.segments:
        tag = seg.tag

        if tag == "N1":
            # Start a new N1 party loop
            if current_loop is not None:
                doc.loops.append(current_loop)
            current_loop = EDILoop(seg)
            current_loop_type = "party"

        elif tag in n1_child_tags and current_loop_type == "party":
            # Child of the current N1 loop
            current_loop.add_child(seg)

        elif tag in loop_trigger_tags:
            # Start a new line-item loop
            if current_loop is not None:
                doc.loops.append(current_loop)
            current_loop = EDILoop(seg)
            current_loop_type = "item"

        elif tag in item_child_tags and current_loop_type == "item":
            # Child of the current line-item loop
            current_loop.add_child(seg)

        else:
            # Not part of any loop — it's a header segment
            if current_loop is not None:
                doc.loops.append(current_loop)
                current_loop = None
                current_loop_type = ""
            doc.header_segments.append(seg)

    # Flush the last open loop
    if current_loop is not None:
        doc.loops.append(current_loop)


# ---------------------------------------------------------------------------
# High-level parse function (backward-compatible API)
# ---------------------------------------------------------------------------

def parse_edi(
    content: str,
    transaction_set: str | None = None,
    include_envelope: bool = True,
) -> dict:
    """
    Parse raw EDI X12 content into structured data.

    This is the high-level API used by the mapper modules.
    Internally creates an EDIDocument and flattens to rows.

    Args:
        content: Raw EDI string
        transaction_set: e.g. '850', '810'. If None, auto-detect from ST segment.
        include_envelope: Whether to include envelope fields in output rows.

    Returns:
        dict with keys:
            - rows: list of flat row dicts
            - doc: the EDIDocument object (for advanced access)
            - envelope: parsed envelope metadata
            - transaction_set: detected/used transaction set code
            - schema_name: human-readable name of the transaction set
            - segment_count: number of business segments parsed
            - logs: list of processing log messages
    """
    doc = EDIDocument.parse(content, transaction_set=transaction_set)
    rows = doc.to_rows(include_envelope=include_envelope)

    return {
        "rows": rows,
        "doc": doc,
        "envelope": doc.envelope,
        "transaction_set": doc.transaction_set,
        "schema_name": doc.schema_name,
        "segment_count": len(doc.segments),
        "logs": doc.logs,
    }
