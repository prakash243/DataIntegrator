"""
Sandboxed execution of user-defined Python rule functions.

Users write a `def apply_rules(row):` function in the UI.
This module executes it row-by-row against the data with basic safety checks.
"""

import re
import logging
import copy

logger = logging.getLogger(__name__)

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
    (r'\bimport\b', "import statements are not allowed"),
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
    (r'\bos\b', "os module is not allowed"),
    (r'\bsys\b', "sys module is not allowed"),
    (r'\bsubprocess\b', "subprocess is not allowed"),
]


def validate_code(code: str) -> None:
    """
    Check user code for disallowed patterns.
    Raises ValueError if any are found.
    """
    for pattern, message in BLOCKED_PATTERNS:
        if re.search(pattern, code):
            raise ValueError(f"Security error: {message}")

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
    safe_globals = {"__builtins__": SAFE_BUILTINS}
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
