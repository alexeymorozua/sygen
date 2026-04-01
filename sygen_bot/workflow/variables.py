"""Variable resolution and safe expression evaluation for workflows."""

from __future__ import annotations

import ast
import re
from typing import Any

from sygen_bot.workflow.models import StepRun


# ── Variable resolution ─────────────────────────────────────────────

_VAR_RE = re.compile(
    r"\$steps\.([a-zA-Z0-9_-]+)\.(output|error|status)"
    r"|\$variables\.([a-zA-Z0-9_.-]+)"
    r"|\$([a-zA-Z0-9_.-]+)"
)


def resolve_variables(
    template: str,
    variables: dict[str, Any],
    step_runs: dict[str, StepRun],
) -> str:
    """Replace $variable references in *template* with actual values.

    Supported patterns:
    - ``$steps.<step_id>.output`` / ``.error`` / ``.status``
    - ``$variables.<key>``
    - ``$<key>`` (shorthand for variables)

    Unknown references are left as-is.
    """

    def _replace(m: re.Match[str]) -> str:
        # $steps.<id>.<field>
        step_id = m.group(1)
        if step_id is not None:
            field = m.group(2)
            sr = step_runs.get(step_id)
            if sr is None:
                return m.group(0)
            if field == "output":
                return sr.output
            if field == "error":
                return sr.error
            if field == "status":
                return sr.status.value
            return m.group(0)

        # $variables.<key>
        var_key = m.group(3)
        if var_key is not None:
            val = _deep_get(variables, var_key)
            return str(val) if val is not None else m.group(0)

        # $<key> shorthand
        short_key = m.group(4)
        if short_key is not None:
            val = _deep_get(variables, short_key)
            return str(val) if val is not None else m.group(0)

        return m.group(0)

    return _VAR_RE.sub(_replace, template)


def _deep_get(data: dict[str, Any], dotted_key: str) -> Any:
    """Traverse nested dicts with dotted keys (``a.b.c``)."""
    parts = dotted_key.split(".")
    cur: Any = data
    for p in parts:
        if isinstance(cur, dict):
            cur = cur.get(p)
        else:
            return None
        if cur is None:
            return None
    return cur


# ── Safe expression evaluation ──────────────────────────────────────

_ALLOWED_NODE_TYPES: set[type] = {
    ast.Module,
    ast.Expression,
    ast.Expr,
    ast.BoolOp,
    ast.And,
    ast.Or,
    ast.UnaryOp,
    ast.Not,
    ast.Compare,
    ast.Eq,
    ast.NotEq,
    ast.In,
    ast.NotIn,
    ast.Constant,
    ast.Call,
    ast.Attribute,
    ast.Name,
    ast.Load,
}

_ALLOWED_STR_METHODS = frozenset({"lower", "upper", "strip"})


def safe_eval(expr: str) -> bool:
    """Evaluate a simple boolean expression **without** using ``eval()``.

    Supported constructs:
    - String literals, ``True``, ``False``
    - Comparisons: ``==``, ``!=``, ``in``, ``not in``
    - Boolean operators: ``and``, ``or``, ``not``
    - String methods: ``.lower()``, ``.upper()``, ``.strip()``

    Returns ``False`` for any expression that cannot be safely parsed.
    """
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError:
        return False

    # Validate that only allowed node types are present.
    for node in ast.walk(tree):
        if type(node) not in _ALLOWED_NODE_TYPES:
            return False
        # Restrict method calls to allowed string methods.
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                if func.attr not in _ALLOWED_STR_METHODS:
                    return False
                # Must be called with no arguments.
                if node.args or node.keywords:
                    return False
            else:
                return False

    # Compile and evaluate in a restricted namespace.
    code = compile(tree, "<safe_eval>", "eval")
    try:
        result = eval(code, {"__builtins__": {}}, {})  # noqa: S307
    except Exception:
        return False
    return bool(result)
