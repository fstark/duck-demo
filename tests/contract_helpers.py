"""Contract-checking helpers for duck-demo API tests.

Instead of asserting exact values (brittle), we check *shape*:
- required keys are present
- values have the expected type
- lists are non-empty when they should be

Use ``check_shape(data, spec)`` in tests.  A *spec* is a dict mapping
key names to expected types or nested specs.  Special sentinels:

    ANY          – key must be present, any value (including None)
    AnyOf(...)   – value must be one of the listed types
    ListOf(spec) – value must be a list, each element matching spec
    Optional(t)  – key may be missing; if present must match t
"""

from __future__ import annotations

from typing import Any, Dict, List, Type, Union

# ── Sentinels ──────────────────────────────────────────────────────────────

class _Any:
    """Matches any value (including ``None``)."""
    def __repr__(self):
        return "ANY"

ANY = _Any()


class AnyOf:
    """Value must be an instance of one of the given types."""
    def __init__(self, *types: Type):
        self.types = types

    def __repr__(self):
        return f"AnyOf({', '.join(t.__name__ for t in self.types)})"


class ListOf:
    """Value must be a list; each element is checked against ``inner``."""
    def __init__(self, inner):
        self.inner = inner

    def __repr__(self):
        return f"ListOf({self.inner!r})"


class Optional:
    """Key may be absent.  If present, value must match ``inner``."""
    def __init__(self, inner):
        self.inner = inner

    def __repr__(self):
        return f"Optional({self.inner!r})"


Spec = Union[Type, _Any, AnyOf, ListOf, Optional, Dict[str, Any]]


# ── Core checker ───────────────────────────────────────────────────────────

def check_shape(data: Any, spec: Spec, path: str = "$") -> List[str]:
    """Return a list of mismatch descriptions (empty = pass).

    Parameters
    ----------
    data : any JSON-decoded value
    spec : a Spec describing expected shape
    path : breadcrumb string for error messages
    """
    errors: list[str] = []

    if isinstance(spec, _Any):
        return errors

    if isinstance(spec, AnyOf):
        if not isinstance(data, spec.types):
            errors.append(f"{path}: expected {spec}, got {type(data).__name__}")
        return errors

    if isinstance(spec, ListOf):
        if not isinstance(data, list):
            errors.append(f"{path}: expected list, got {type(data).__name__}")
            return errors
        for i, item in enumerate(data):
            errors.extend(check_shape(item, spec.inner, f"{path}[{i}]"))
        return errors

    if isinstance(spec, Optional):
        # Caller should handle key-missing; if we get here, value is present
        return check_shape(data, spec.inner, path)

    if isinstance(spec, type):
        if not isinstance(data, spec):
            errors.append(f"{path}: expected {spec.__name__}, got {type(data).__name__} ({data!r})")
        return errors

    if isinstance(spec, dict):
        if not isinstance(data, dict):
            errors.append(f"{path}: expected dict, got {type(data).__name__}")
            return errors
        for key, val_spec in spec.items():
            if key not in data:
                if isinstance(val_spec, Optional):
                    continue
                errors.append(f"{path}: missing key '{key}'")
                continue
            errors.extend(check_shape(data[key], val_spec, f"{path}.{key}"))
        return errors

    errors.append(f"{path}: unknown spec type {type(spec)}")
    return errors


def assert_shape(data: Any, spec: Spec, msg: str = ""):
    """Like ``check_shape`` but raises ``AssertionError`` on mismatch."""
    errs = check_shape(data, spec)
    if errs:
        detail = "\n  ".join(errs)
        raise AssertionError(f"Shape mismatch{' — ' + msg if msg else ''}:\n  {detail}")
