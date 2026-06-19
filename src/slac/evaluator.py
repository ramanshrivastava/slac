"""Evaluate a loop's `until` condition at runtime.

The expression grammar and whitelist are shared with the linter
(`analyze_until`, `_ALLOWED_AST`), so what the linter proves *reachable* at
compile time is exactly what this evaluates at run time. Evaluation is safe:
no builtins, no calls/imports/subscripts — only the whitelisted boolean algebra
over the signal namespace the checker reports.
"""

import ast

from .linter import _ALLOWED_AST, ALWAYS_SIGNALS, analyze_until


class UntilError(Exception):
    """Raised when `until` is prose (not a machine-evaluable expression)."""


class _Attr:
    """Wrap a dict so `ci.green` works in an expression (attribute access)."""

    def __init__(self, d):
        for k, v in d.items():
            setattr(self, k, _wrap(v))

    def __repr__(self):
        return "Attr(%r)" % self.__dict__


def _wrap(v):
    return _Attr(v) if isinstance(v, dict) else v


def is_expression(expr):
    """True if `until` is a whitelisted boolean expression (vs prose)."""
    ok, _ = analyze_until(expr or "")
    return ok


def signal_roots(expr):
    """The top-level signal names referenced by an expression `until`."""
    ok, roots = analyze_until(expr or "")
    return roots if ok else set()


def signal_paths(expr):
    """The full dotted access paths in an expression `until`.

    e.g. `ci.green and tests.passed == tests.total` -> {'ci.green',
    'tests.passed', 'tests.total'}. Used to tell the checker the exact shape to
    report (so `answer.value` isn't answered with a bare scalar).
    """
    if not is_expression(expr):
        return set()
    tree = ast.parse(expr.strip(), mode="eval")
    paths = set()

    class _V(ast.NodeVisitor):
        def visit_Attribute(self, node):  # noqa: N802
            parts, cur = [], node
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
                paths.add(".".join(reversed(parts)))
            # do not recurse — the inner Name is part of this path

        def visit_Name(self, node):  # noqa: N802
            paths.add(node.id)

    _V().visit(tree)
    return paths


def signal_skeleton(paths):
    """Build a nested skeleton dict from dotted paths, for the checker prompt."""
    root = {}
    for p in sorted(paths):
        parts = p.split(".")
        d = root
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d.setdefault(parts[-1], "<value>")
    return root


def evaluate_until(expr, signals):
    """Evaluate an expression `until` against a signal dict.

    Returns (met: bool, reason: str). Raises UntilError if `expr` is prose
    (the caller should then fall back to the checker's verdict).
    """
    expr = (expr or "").strip()
    ok, _ = analyze_until(expr)
    if not ok:
        raise UntilError("until is prose, not an expression")

    tree = ast.parse(expr, mode="eval")
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            raise UntilError("until contains a disallowed construct: %s"
                             % type(node).__name__)

    namespace = {k: _wrap(v) for k, v in (signals or {}).items()}
    # SAFETY: this eval is intentional and constrained. Every AST node was just
    # checked against _ALLOWED_AST (only BoolOp/UnaryOp/Compare/Name/Attribute/
    # Constant — no Call, Subscript, Import, comprehension, or dunder is reachable),
    # and builtins are stripped ({"__builtins__": {}}). So the only thing that can
    # run is whitelisted boolean algebra over the signal namespace. ast.literal_eval
    # can't be used here because we need names/attribute access (e.g. `ci.green`).
    try:
        code = compile(tree, "<until>", "eval")
        result = bool(eval(code, {"__builtins__": {}}, namespace))  # noqa: S307
        return result, ("until met" if result else "until not yet met")
    except (NameError, AttributeError) as e:
        # A signal named in `until` wasn't reported by the checker this turn.
        return False, "waiting on signal (%s)" % e


def always_signals(iteration, consecutive_green, elapsed_minutes):
    """The built-in signals every loop can reference in `until`."""
    return {
        "iteration": iteration,
        "consecutive_green": consecutive_green,
        "elapsed_minutes": elapsed_minutes,
    }


# Re-exported so callers don't reach into the linter for the constant.
ALWAYS = ALWAYS_SIGNALS
