"""
Sandboxed execution of user-defined Python rule functions.

Users write a `def apply_rules(row):` function in the UI.
This module executes it row-by-row against the data with basic safety checks.
"""

import re
import logging
import copy
import importlib

logger = logging.getLogger(__name__)

# Modules that users are allowed to import in their code
ALLOWED_MODULES = {
    "datetime",
    "math",
    "json",
    "re",
    "string",
    "decimal",
    "collections",
    "itertools",
    "functools",
    "uuid",
    "hashlib",
    "base64",
    "urllib.parse",
    "html",
    "textwrap",
    "random",
}

# Builtins allowed inside user code
SAFE_BUILTINS = {
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
    "len": len,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "round": round,
    "min": min,
    "max": max,
    "abs": abs,
    "sum": sum,
    "any": any,
    "all": all,
    "enumerate": enumerate,
    "zip": zip,
    "sorted": sorted,
    "reversed": reversed,
    "range": range,
    "map": map,
    "filter": filter,
    "isinstance": isinstance,
    "type": type,
    "print": print,
    "None": None,
    "True": True,
    "False": False,
}

# Patterns that are not allowed in user code
BLOCKED_PATTERNS = [
    (r'\bopen\s*\(', "open() is not allowed"),
    (r'\beval\s*\(', "eval() is not allowed"),
    (r'\bexec\s*\(', "exec() is not allowed"),
    (r'\bcompile\s*\(', "compile() is not allowed"),
    (r'\bglobals\s*\(', "globals() is not allowed"),
    (r'\blocals\s*\(', "locals() is not allowed"),
    (r'\bgetattr\s*\(', "getattr() is not allowed"),
    (r'\bsetattr\s*\(', "setattr() is not allowed"),
    (r'\bdelattr\s*\(', "delattr() is not allowed"),
    (r'__\w+__', "dunder attributes are not allowed"),
    (r'\bsubprocess\b', "subprocess is not allowed"),
]

# Modules that are always blocked regardless of ALLOWED_MODULES
BLOCKED_MODULES = {"os", "sys", "subprocess", "shutil", "socket", "ctypes", "signal", "pickle"}


def _validate_imports(code: str) -> None:
    """
    Check that all import statements in user code only reference allowed modules.
    Raises ValueError for any disallowed import.
    """
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # "import modA, modB" or "import modA as x"
        m = re.match(r'^import\s+(.+)$', stripped)
        if m:
            modules = [p.strip().split()[0] for p in m.group(1).split(",")]
            for mod in modules:
                root = mod.split(".")[0]
                if root in BLOCKED_MODULES:
                    raise ValueError(f'Security error: import of "{root}" is not allowed')
                if mod not in ALLOWED_MODULES and root not in ALLOWED_MODULES:
                    raise ValueError(
                        f'Import of "{mod}" is not allowed. '
                        f"Allowed modules: {', '.join(sorted(ALLOWED_MODULES))}"
                    )
            continue

        # "from mod import ..."
        m = re.match(r'^from\s+([\w.]+)\s+import\b', stripped)
        if m:
            mod = m.group(1)
            root = mod.split(".")[0]
            if root in BLOCKED_MODULES:
                raise ValueError(f'Security error: import from "{root}" is not allowed')
            if mod not in ALLOWED_MODULES and root not in ALLOWED_MODULES:
                raise ValueError(
                    f'Import from "{mod}" is not allowed. '
                    f"Allowed modules: {', '.join(sorted(ALLOWED_MODULES))}"
                )


def _auto_inject_modules(safe_globals: dict) -> None:
    """
    Pre-load all allowed modules and their commonly used members into
    safe_globals so users can write `datetime.now()` or `math.sqrt()`
    without any import statement.
    """
    import datetime as _datetime
    import math as _math
    import json as _json
    import re as _re
    import string as _string
    import decimal as _decimal
    import collections as _collections
    import itertools as _itertools
    import functools as _functools
    import uuid as _uuid
    import hashlib as _hashlib
    import base64 as _base64
    import html as _html
    import textwrap as _textwrap
    import random as _random
    import urllib.parse as _urllib_parse

    # Inject modules by name
    # For datetime, inject the class directly so datetime.now() works
    safe_globals["datetime"] = _datetime.datetime
    safe_globals["math"] = _math
    safe_globals["json"] = _json
    safe_globals["re"] = _re
    safe_globals["string"] = _string
    safe_globals["decimal"] = _decimal
    safe_globals["collections"] = _collections
    safe_globals["itertools"] = _itertools
    safe_globals["functools"] = _functools
    safe_globals["uuid"] = _uuid
    safe_globals["hashlib"] = _hashlib
    safe_globals["base64"] = _base64
    safe_globals["html"] = _html
    safe_globals["textwrap"] = _textwrap
    safe_globals["random"] = _random
    safe_globals["urllib"] = importlib.import_module("urllib")

    # Inject commonly used members directly so users can write
    # datetime.now() instead of datetime.datetime.now(), timedelta(days=1), etc.
    safe_globals["timedelta"] = _datetime.timedelta
    safe_globals["date"] = _datetime.date
    safe_globals["time"] = _datetime.time
    safe_globals["timezone"] = _datetime.timezone
    safe_globals["Decimal"] = _decimal.Decimal
    safe_globals["OrderedDict"] = _collections.OrderedDict
    safe_globals["defaultdict"] = _collections.defaultdict
    safe_globals["Counter"] = _collections.Counter
    safe_globals["namedtuple"] = _collections.namedtuple


def _preload_imports(code: str, safe_globals: dict) -> None:
    """
    Parse import statements from user code and pre-load allowed modules
    into safe_globals so the user code can reference them.
    The static validation in _validate_imports() already ensures only
    allowed modules are imported.
    """
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # "import mod" / "import mod as alias"
        m = re.match(r'^import\s+(.+)$', stripped)
        if m:
            for part in m.group(1).split(","):
                part = part.strip()
                tokens = part.split()
                mod_name = tokens[0]
                alias = tokens[2] if len(tokens) >= 3 and tokens[1] == "as" else mod_name.split(".")[0]
                safe_globals[alias] = importlib.import_module(mod_name)
            continue

        # "from mod import name1, name2" / "from mod import name as alias"
        m = re.match(r'^from\s+([\w.]+)\s+import\s+(.+)$', stripped)
        if m:
            mod_name = m.group(1)
            mod = importlib.import_module(mod_name)
            for part in m.group(2).split(","):
                part = part.strip()
                tokens = part.split()
                name = tokens[0]
                alias = tokens[2] if len(tokens) >= 3 and tokens[1] == "as" else name
                safe_globals[alias] = getattr(mod, name)


def validate_code(code: str) -> None:
    """
    Check user code for disallowed patterns and imports.
    Raises ValueError if any are found.
    """
    for pattern, message in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            raise ValueError(f"Security error: {message}")

    _validate_imports(code)

    if "def apply_rules(" not in code and "def apply_rules (" not in code:
        raise ValueError(
            'Your code must define a function named "apply_rules". '
            'Example: def apply_rules(row):'
        )


def execute_rules(data: list[dict], code: str, logs: list[str]) -> list[dict]:
    """
    Execute user-defined rule code against data rows.

    Args:
        data: List of row dicts from the input
        code: User's Python code containing a `def apply_rules(row):` function
        logs: List to append processing messages to

    Returns:
        List of transformed row dicts (rows returning None are filtered out)

    Raises:
        ValueError: If code is invalid or execution fails
    """
    validate_code(code)

    # Execute the code to define the transform function
    # Include __import__ so that pre-loaded modules' internal imports work
    builtins = {**SAFE_BUILTINS, "__import__": __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__}
    safe_globals = {"__builtins__": builtins}

    # Auto-inject all allowed modules + common members so users don't need imports
    _auto_inject_modules(safe_globals)

    # Also pre-load any explicit imports the user wrote (handles aliases, specific names)
    _preload_imports(code, safe_globals)

    # Strip import lines from code so exec doesn't re-execute them
    code_lines = []
    for line in code.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("from "):
            continue
        code_lines.append(line)
    code = "\n".join(code_lines)
    try:
        exec(code, safe_globals)
    except SyntaxError as e:
        raise ValueError(f"Syntax error in your code (line {e.lineno}): {e.msg}") from e
    except Exception as e:
        raise ValueError(f"Error loading your code: {e}") from e

    transform_fn = safe_globals.get("apply_rules")
    if not callable(transform_fn):
        raise ValueError(
            'Your code must define a callable function named "apply_rules". '
            'Example: def apply_rules(row):'
        )

    logs.append(f"Loaded apply_rules function from user code ({len(code)} chars)")

    # Apply transform to each row
    results = []
    errors = []
    for i, row in enumerate(data):
        try:
            row_copy = copy.deepcopy(row)
            result = transform_fn(row_copy)
            if result is not None:
                if not isinstance(result, dict):
                    raise TypeError(
                        f"apply_rules() must return a dict or None, got {type(result).__name__}"
                    )
                results.append(result)
        except Exception as e:
            errors.append(f"Row {i + 1}: {e}")
            if len(errors) >= 10:
                errors.append("... (stopping after 10 errors)")
                break

    if errors and not results:
        raise ValueError(
            "Transform failed on all rows:\n" + "\n".join(errors)
        )

    if errors:
        logs.append(f"Warning: {len(errors)} row(s) had errors and were skipped")
        for err in errors:
            logs.append(f"  {err}")

    skipped = len(data) - len(results) - len(errors)
    if skipped > 0:
        logs.append(f"Filtered out {skipped} row(s) (apply_rules returned None)")

    logs.append(f"Transform complete: {len(data)} input -> {len(results)} output rows")

    return results


# ============================================================================
# Natural-language rule engine (no external dependencies)
# ============================================================================

_NL_HANDLERS: list[tuple[re.Pattern, callable]] = []


def _register(pattern: str):
    """Decorator to register a natural-language rule handler."""
    compiled = re.compile(pattern, re.IGNORECASE)

    def decorator(fn):
        _NL_HANDLERS.append((compiled, fn))
        return fn

    return decorator


def _find_col(columns: list[str], name: str) -> str:
    """Case-insensitive column lookup."""
    name_lower = name.strip().strip("'\"").lower()
    for c in columns:
        if c.lower() == name_lower:
            return c
    raise ValueError(f'Column "{name}" not found. Available: {", ".join(columns)}')


def _col_names(data: list[dict]) -> list[str]:
    """Collect all keys preserving first-seen order."""
    seen = {}
    for row in data:
        for k in row:
            if k not in seen:
                seen[k] = True
    return list(seen.keys())


def _to_num(val):
    """Try to convert a value to float for comparisons."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def execute_natural_rules(data: list[dict], rules_text: str) -> tuple[list[dict], list[str]]:
    """
    Parse natural-language rules (one per line) and apply sequentially.
    Returns (transformed_data, logs).
    """
    logs: list[str] = []
    lines = [l.strip() for l in rules_text.splitlines()
             if l.strip() and not l.strip().startswith("#")]

    if not lines:
        logs.append("No rules provided - returning original data")
        return data, logs

    logs.append(f"Parsing {len(lines)} rule(s)")

    data = copy.deepcopy(data)

    for i, raw in enumerate(lines, 1):
        tag = f"Rule {i}"
        matched = False
        for pat, handler in _NL_HANDLERS:
            m = pat.match(raw)
            if m:
                data = handler(data, m, logs, tag)
                matched = True
                break
        if not matched:
            raise ValueError(f'{tag}: Could not understand rule: "{raw}"')

    logs.append(f"Done: {len(data)} rows in output")
    return data, logs


# ---- Text transforms ----

@_register(r"^uppercase\s+(.+)$")
def _nl_uppercase(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    for row in data:
        if col in row:
            row[col] = str(row[col]).upper()
    logs.append(f'{tag}: Uppercased column "{col}"')
    return data


@_register(r"^lowercase\s+(.+)$")
def _nl_lowercase(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    for row in data:
        if col in row:
            row[col] = str(row[col]).lower()
    logs.append(f'{tag}: Lowercased column "{col}"')
    return data


@_register(r"^titlecase\s+(.+)$")
def _nl_titlecase(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    for row in data:
        if col in row:
            row[col] = str(row[col]).title()
    logs.append(f'{tag}: Title-cased column "{col}"')
    return data


@_register(r"^trim\s+(.+)$")
def _nl_trim(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    for row in data:
        if col in row:
            row[col] = str(row[col]).strip()
    logs.append(f'{tag}: Trimmed whitespace in "{col}"')
    return data


@_register(r"^replace\s+(?:text\s+)?in\s+(\S+)\s+(.+?)\s+with\s+(.+)$")
def _nl_replace(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    old = m.group(2).strip().strip("'\"")
    new = m.group(3).strip().strip("'\"")
    for row in data:
        if col in row:
            row[col] = str(row[col]).replace(old, new)
    logs.append(f'{tag}: Replaced "{old}" with "{new}" in "{col}"')
    return data


@_register(r"^regex\s+replace\s+(.+?)\s+with\s+(.+?)\s+in\s+(\S+)$")
def _nl_regex_replace(data, m, logs, tag):
    pattern = m.group(1).strip().strip("'\"")
    repl = m.group(2).strip().strip("'\"")
    col = _find_col(_col_names(data), m.group(3))
    compiled = re.compile(pattern)
    for row in data:
        if col in row:
            row[col] = compiled.sub(repl, str(row[col]))
    logs.append(f'{tag}: Regex-replaced /{pattern}/ with "{repl}" in "{col}"')
    return data


@_register(r"^concat(?:enate)?\s+(.+?)\s+as\s+(\S+)$")
def _nl_concat(data, m, logs, tag):
    cols_raw = [c.strip().strip("'\"") for c in re.split(r"[,\s]+", m.group(1)) if c.strip()]
    new_col = m.group(2).strip().strip("'\"")
    columns = _col_names(data)
    resolved = [_find_col(columns, c) for c in cols_raw]
    for row in data:
        row[new_col] = " ".join(str(row.get(c, "")) for c in resolved)
    logs.append(f'{tag}: Concatenated {resolved} -> "{new_col}"')
    return data


# ---- Filtering ----

_FILTER_OPS = {
    "equals": lambda v, t: str(v) == t,
    "=": lambda v, t: str(v) == t,
    "==": lambda v, t: str(v) == t,
    "not_equals": lambda v, t: str(v) != t,
    "!=": lambda v, t: str(v) != t,
    "contains": lambda v, t: t.lower() in str(v).lower(),
    "startswith": lambda v, t: str(v).lower().startswith(t.lower()),
    "endswith": lambda v, t: str(v).lower().endswith(t.lower()),
    ">": lambda v, t: (_to_num(v) is not None and _to_num(t) is not None and _to_num(v) > _to_num(t)),
    ">=": lambda v, t: (_to_num(v) is not None and _to_num(t) is not None and _to_num(v) >= _to_num(t)),
    "<": lambda v, t: (_to_num(v) is not None and _to_num(t) is not None and _to_num(v) < _to_num(t)),
    "<=": lambda v, t: (_to_num(v) is not None and _to_num(t) is not None and _to_num(v) <= _to_num(t)),
}


@_register(
    r"^filter\s+(\S+)\s+"
    r"(equals|not_equals|contains|startswith|endswith|[!=<>]=?)\s+"
    r"(.+)$"
)
def _nl_filter_word(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    op = m.group(2).strip().lower()
    val = m.group(3).strip().strip("'\"")
    fn = _FILTER_OPS.get(op)
    if fn is None:
        raise ValueError(f'Unknown operator "{op}"')
    before = len(data)
    data = [row for row in data if fn(row.get(col, ""), val)]
    logs.append(f'{tag}: Filtered "{col}" {op} "{val}" - {before} -> {len(data)} rows')
    return data


@_register(r"^filter\s+(\S+)\s*([><!]=?|==|!=)\s*(.+)$")
def _nl_filter_symbolic(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1))
    op = m.group(2).strip()
    val = m.group(3).strip().strip("'\"")
    fn = _FILTER_OPS.get(op)
    if fn is None:
        raise ValueError(f'Unknown operator "{op}"')
    before = len(data)
    data = [row for row in data if fn(row.get(col, ""), val)]
    logs.append(f'{tag}: Filtered "{col}" {op} {val} - {before} -> {len(data)} rows')
    return data


# ---- Sorting ----

@_register(r"^sort\s+(?:by\s+)?(.+)$")
def _nl_sort(data, m, logs, tag):
    parts = [p.strip() for p in m.group(1).split(",")]
    columns = _col_names(data)
    sort_specs = []
    for part in parts:
        tokens = part.split()
        col = _find_col(columns, tokens[0].strip("'\""))
        desc = len(tokens) > 1 and tokens[1].lower().startswith("desc")
        sort_specs.append((col, desc))

    for col, desc in reversed(sort_specs):
        data.sort(key=lambda row, c=col: _sort_key(row.get(c, "")), reverse=desc)

    desc_str = ", ".join(f'{c} {"desc" if d else "asc"}' for c, d in sort_specs)
    logs.append(f"{tag}: Sorted by {desc_str}")
    return data


def _sort_key(val):
    n = _to_num(val)
    if n is not None:
        return (0, n, "")
    return (1, 0, str(val).lower())


# ---- Column operations ----

def _rename_key_in_place(d: dict, old_key: str, new_key: str) -> None:
    """Rename a key in a dict while preserving insertion order."""
    items = list(d.items())
    d.clear()
    for k, v in items:
        d[new_key if k == old_key else k] = v


@_register(r"^rename\s+(\S+)\s+to\s+(\S+)$")
def _nl_rename(data, m, logs, tag):
    old = _find_col(_col_names(data), m.group(1))
    new = m.group(2).strip().strip("'\"")
    for row in data:
        if old in row:
            _rename_key_in_place(row, old, new)
    logs.append(f'{tag}: Renamed "{old}" -> "{new}"')
    return data


@_register(r"^reorder\s+(.+)$")
def _nl_reorder(data, m, logs, tag):
    """Reorder columns: 'reorder col1, col2, col3' or 'reorder col1 col2 col3'."""
    columns = _col_names(data)
    parts = [p.strip().strip("'\"") for p in re.split(r"[,\s]+", m.group(1)) if p.strip()]
    ordered = [_find_col(columns, p) for p in parts]
    # Columns not listed go at the end
    remaining = [c for c in columns if c not in ordered]
    final_order = ordered + remaining
    for row in data:
        items = {k: row.get(k, "") for k in final_order}
        row.clear()
        row.update(items)
    logs.append(f'{tag}: Reordered columns to {final_order}')
    return data


@_register(r"^remove\s+(.+)$")
def _nl_remove(data, m, logs, tag):
    col = _find_col(_col_names(data), m.group(1).strip().strip("'\""))
    for row in data:
        row.pop(col, None)
    logs.append(f'{tag}: Removed column "{col}"')
    return data


@_register(r"^duplicate\s+(\S+)\s+as\s+(\S+)$")
def _nl_duplicate(data, m, logs, tag):
    src = _find_col(_col_names(data), m.group(1))
    dst = m.group(2).strip().strip("'\"")
    for row in data:
        row[dst] = row.get(src, "")
    logs.append(f'{tag}: Duplicated "{src}" -> "{dst}"')
    return data


@_register(r"^(?:create|add)\s+(\S+)\s*=\s*(.+)$")
def _nl_create(data, m, logs, tag):
    new_col = m.group(1).strip().strip("'\"")
    expr = m.group(2).strip()

    columns = _col_names(data)

    # String concatenation: col1 + col2
    if "+" in expr:
        parts = [p.strip().strip("'\"") for p in expr.split("+")]
        all_cols = True
        for p in parts:
            try:
                _find_col(columns, p)
            except ValueError:
                all_cols = False
                break
        if all_cols:
            resolved = [_find_col(columns, p) for p in parts]
            for row in data:
                row[new_col] = " ".join(str(row.get(c, "")) for c in resolved)
            logs.append(f'{tag}: Created "{new_col}" by concatenating {resolved}')
            return data

    # Arithmetic expression
    for row in data:
        row[new_col] = _eval_row_expr(row, expr, columns)
    logs.append(f'{tag}: Created "{new_col}" = {expr}')
    return data


def _eval_row_expr(row: dict, expr: str, columns: list[str]):
    """Safely evaluate an arithmetic expression for a single row."""
    safe_ns = {"__builtins__": {}}
    expr_safe = expr

    sorted_cols = sorted(columns, key=len, reverse=True)
    for i, col in enumerate(sorted_cols):
        placeholder = f"__c{i}__"
        pat = re.compile(r'\b' + re.escape(col) + r'\b', re.IGNORECASE)
        if pat.search(expr_safe):
            expr_safe = pat.sub(placeholder, expr_safe)
            val = row.get(col, 0)
            n = _to_num(val)
            safe_ns[placeholder] = n if n is not None else 0

    check = re.sub(r'__c\d+__', '', expr_safe)
    check = re.sub(r'[\d\s.\+\-\*/\(\)%]', '', check)
    if check:
        raise ValueError(f"Expression contains disallowed characters: {check}")

    try:
        result = eval(expr_safe, safe_ns)  # noqa: S307
        if isinstance(result, float) and result == int(result):
            return int(result)
        if isinstance(result, float):
            return round(result, 4)
        return result
    except Exception as exc:
        raise ValueError(f'Failed to evaluate "{expr}": {exc}') from exc
