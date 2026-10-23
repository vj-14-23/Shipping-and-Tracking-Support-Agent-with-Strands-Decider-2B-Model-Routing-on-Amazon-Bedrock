"""Read agent/decision.py without importing it: the pattern tag and the QUESTIONS source.

Used by ./kit check, ./kit readme and ./kit article. Parses the file (ast), so annotated
assignments (`QUESTIONS: dict[...] = {...}`) and any formatting work.
"""

from __future__ import annotations

import ast
from typing import Any


def assignments(src: str, name: str) -> list[ast.stmt]:
    """Module-level `name = ...` and `name: T = ...` statements."""
    out = []
    for n in ast.parse(src).body:
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in n.targets):
            out.append(n)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name) and n.target.id == name and n.value is not None:
            out.append(n)
    return out


def constant(src: str, name: str) -> Any:
    """The literal value of a module-level constant (e.g. PATTERN_TAG), or None."""
    found = assignments(src, name)
    try:
        return ast.literal_eval(found[0].value) if found else None  # type: ignore[attr-defined]
    except ValueError:
        return None


def source_of(src: str, name: str) -> str:
    """The source text of the module-level assignment to `name` (e.g. the QUESTIONS dict)."""
    found = assignments(src, name)
    return (ast.get_source_segment(src, found[0]) or "") if found else ""
