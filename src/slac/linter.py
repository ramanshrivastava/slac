#!/usr/bin/env python3
"""
slac_lint.py — the SLAC type-checker + linter (SLAC v0.0.1).

Zero-dependency: runs on a stock Python 3.8+. If PyYAML is installed it is used
for frontmatter parsing; otherwise a small bundled parser handles the SLAC subset.

It runs three ordered stages and stops at the first that produces a hard error:

    1. OKF conformance  — frontmatter parses and `type` is present
    2. Type check       — frontmatter validates against src/slac/slac.schema.json
    3. Semantic lint     — footguns the schema can't see (no checker, runaway, ...)

Diagnostics are named like Python exceptions. Errors HALT (loop refused); warnings
NOTIFY (loop still runs). See linter/rules.md.

Usage:
    python3 slac_lint.py FILE...           # human report
    python3 slac_lint.py --json FILE...    # machine-readable findings
    python3 slac_lint.py --strict FILE...  # warnings become errors (CI)
"""

import argparse
import ast
import difflib
import json
import os
import re
import sys

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "slac.schema.json")

ERROR_NAMES = {
    "SLACSyntaxError", "MissingFieldError", "UnknownFieldError",
    "TypeError", "ValueError",
}
WARNING_NAMES = {
    "NoCheckerWarning", "NoStateWarning", "UnreachableStopWarning",
    "NoBoundaryWarning", "RunawayWarning",
}

ALWAYS_SIGNALS = {"iteration", "consecutive_green", "elapsed_minutes"}

DEFAULT_FIXSAFETY = {
    "SLACSyntaxError": "needs-human",
    "MissingFieldError": "needs-human",
    "UnknownFieldError": "safe",
    "TypeError": "review",
    "ValueError": "review",
    "NoCheckerWarning": "review",
    "NoStateWarning": "safe",
    "UnreachableStopWarning": "review",
    "NoBoundaryWarning": "review",
    "RunawayWarning": "review",
}


class Diagnostic:
    def __init__(self, name, message, line=None, fix_safety=None):
        self.name = name
        self.message = message
        self.line = line
        self.fix_safety = fix_safety or DEFAULT_FIXSAFETY.get(name, "review")

    @property
    def severity(self):
        return "error" if self.name in ERROR_NAMES else "warning"

    def as_dict(self):
        return {
            "name": self.name,
            "message": self.message,
            "line": self.line,
            "fixSafety": self.fix_safety,
            "severity": self.severity,
        }


# --------------------------------------------------------------------------- #
# Frontmatter splitting
# --------------------------------------------------------------------------- #
def split_frontmatter(text):
    """Return (frontmatter_text, body_text, fm_start_line). Raise on malformed."""
    lines = text.split("\n")
    i = 0
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    if i >= len(lines) or lines[i].strip() != "---":
        raise SlacSyntax("file must start with a '---' YAML frontmatter block")
    fm_start = i + 1  # first frontmatter content line (0-based)
    j = fm_start
    while j < len(lines) and lines[j].strip() != "---":
        j += 1
    if j >= len(lines):
        raise SlacSyntax("frontmatter block is not closed with '---'")
    fm_text = "\n".join(lines[fm_start:j])
    body_text = "\n".join(lines[j + 1:])
    return fm_text, body_text, fm_start + 1  # 1-based abs line of fm content


class SlacSyntax(Exception):
    pass


# --------------------------------------------------------------------------- #
# YAML parsing — PyYAML if available, else a bundled subset parser
# --------------------------------------------------------------------------- #
def parse_frontmatter(fm_text):
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(fm_text)
        if data is None:
            data = {}
        if not isinstance(data, dict):
            raise SlacSyntax("frontmatter must be a mapping")
        return data
    except ImportError:
        return _bundled_parse(fm_text)


def _indent(s):
    return len(s) - len(s.lstrip(" "))


def _strip_comment(s):
    out, quote, i = [], None, 0
    while i < len(s):
        c = s[i]
        if quote:
            out.append(c)
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            quote = c
            out.append(c)
        elif c == "#" and (i == 0 or s[i - 1] in " \t"):
            break
        else:
            out.append(c)
        i += 1
    return "".join(out).rstrip()


def _is_blank_or_comment(s):
    t = _strip_comment(s).strip()
    return t == ""


def _has_top_level_colon(s):
    quote, depth = None, 0
    for i, c in enumerate(s):
        if quote:
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            quote = c
        elif c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
        elif c == ":" and depth == 0:
            if i + 1 >= len(s) or s[i + 1] in " \t":
                return True
    return False


def _scalar(s):
    s = s.strip()
    if s == "":
        return None
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    if s.startswith("["):
        return _flow_seq(s)
    if s.startswith("{"):
        return _flow_map(s)
    low = s.lower()
    if low in ("true",):
        return True
    if low in ("false",):
        return False
    if low in ("null", "~"):
        return None
    t = s.replace("_", "")
    if re.fullmatch(r"[+-]?\d+", t):
        return int(t)
    if re.fullmatch(r"[+-]?\d*\.\d+", t):
        return float(t)
    return s


def _split_top_commas(s):
    parts, quote, depth, cur = [], None, 0, []
    for c in s:
        if quote:
            cur.append(c)
            if c == quote:
                quote = None
        elif c in ('"', "'"):
            quote = c
            cur.append(c)
        elif c in "[{":
            depth += 1
            cur.append(c)
        elif c in "]}":
            depth -= 1
            cur.append(c)
        elif c == "," and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(c)
    if "".join(cur).strip():
        parts.append("".join(cur))
    return parts


def _flow_seq(s):
    inner = s.strip()[1:-1]
    return [_scalar(p.strip()) for p in _split_top_commas(inner)]


def _flow_map(s):
    inner = s.strip()[1:-1]
    out = {}
    for part in _split_top_commas(inner):
        k, _, v = part.partition(":")
        out[k.strip()] = _scalar(v.strip())
    return out


def _bundled_parse(fm_text):
    lines = fm_text.split("\n")
    value, _ = _parse_block(lines, 0)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise SlacSyntax("frontmatter must be a mapping")
    return value


def _next_meaningful(lines, i):
    while i < len(lines) and _is_blank_or_comment(lines[i]):
        i += 1
    return i


def _parse_block(lines, i):
    i = _next_meaningful(lines, i)
    if i >= len(lines):
        return None, i
    content = _strip_comment(lines[i]).strip()
    if content.startswith("-"):
        return _parse_sequence(lines, i, _indent(_strip_comment(lines[i])))
    if _has_top_level_colon(content):
        return _parse_mapping(lines, i, _indent(_strip_comment(lines[i])))
    return _scalar(content), i + 1


def _parse_mapping(lines, i, indent):
    result = {}
    while True:
        i = _next_meaningful(lines, i)
        if i >= len(lines):
            break
        stripped = _strip_comment(lines[i])
        cur = _indent(stripped)
        if cur != indent or stripped.strip().startswith("-"):
            break
        content = stripped.strip()
        key, _, val = content.partition(":")
        key, val = key.strip(), val.strip()
        if val == "":
            i = _next_meaningful(lines, i + 1)
            if i < len(lines) and _indent(_strip_comment(lines[i])) > indent:
                child, i = _parse_block(lines, i)
                result[key] = child
            else:
                result[key] = None
        elif val in ("|", "|-", "|+", ">", ">-", ">+"):
            block, i = _collect_block_scalar(lines, i + 1, indent)
            result[key] = block
        else:
            result[key] = _scalar(val)
            i += 1
    return result, i


def _collect_block_scalar(lines, i, parent_indent):
    captured = []
    base = None
    while i < len(lines):
        raw = lines[i]
        if raw.strip() == "":
            captured.append("")
            i += 1
            continue
        if _indent(raw) <= parent_indent:
            break
        if base is None:
            base = _indent(raw)
        captured.append(raw[base:])
        i += 1
    while captured and captured[-1] == "":
        captured.pop()
    return "\n".join(captured), i


def _parse_sequence(lines, i, indent):
    items = []
    while True:
        i = _next_meaningful(lines, i)
        if i >= len(lines):
            break
        stripped = _strip_comment(lines[i])
        if _indent(stripped) != indent or not stripped.strip().startswith("-"):
            break
        lstripped = stripped.strip()
        after = lstripped[1:]
        n_spaces = len(after) - len(after.lstrip(" "))
        child_indent = indent + 1 + n_spaces
        rest = after.strip()
        sub = []
        if rest != "":
            sub.append(" " * child_indent + rest)
        i += 1
        while i < len(lines):
            nxt = _strip_comment(lines[i])
            if nxt.strip() == "":
                i += 1
                continue
            if _indent(nxt) >= child_indent and not (
                _indent(nxt) == indent and nxt.strip().startswith("-")
            ):
                sub.append(nxt)
                i += 1
            else:
                break
        if sub:
            val, _ = _parse_block(sub, 0)
            items.append(val)
        else:
            items.append(None)
    return items, i


# --------------------------------------------------------------------------- #
# Locating line numbers for diagnostics (best effort)
# --------------------------------------------------------------------------- #
def find_line(file_lines, key):
    pat = re.compile(r"^\s*" + re.escape(key) + r"\s*:")
    for idx, line in enumerate(file_lines):
        if pat.match(line):
            return idx + 1
    return None


# --------------------------------------------------------------------------- #
# Minimal JSON Schema validation (the subset our schema uses)
# --------------------------------------------------------------------------- #
_TYPE_MAP = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
}


def _type_ok(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "null":
        return value is None
    return isinstance(value, _TYPE_MAP[t])


def _resolve(root, schema):
    if "$ref" in schema:
        ref = schema["$ref"]
        node = root
        for part in ref.lstrip("#/").split("/"):
            node = node[part]
        return node
    return schema


def _validate(value, schema, root, path):
    schema = _resolve(root, schema)
    errs = []

    if "type" in schema and not _type_ok(value, schema["type"]):
        errs.append(("TypeError",
                     "%s must be of type %s, got %s"
                     % (_p(path), schema["type"], _typename(value)), path))
        return errs

    if "const" in schema and value != schema["const"]:
        errs.append(("ValueError",
                     "%s must be %r" % (_p(path), schema["const"]), path))
    if "enum" in schema and value not in schema["enum"]:
        errs.append(("ValueError",
                     "%s must be one of %s" % (_p(path), schema["enum"]), path))
    if "minLength" in schema and isinstance(value, str) and len(value) < schema["minLength"]:
        errs.append(("ValueError", "%s must not be empty" % _p(path), path))
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        errs.append(("ValueError",
                     "%s does not match required pattern %s"
                     % (_p(path), schema["pattern"]), path))
    if "minimum" in schema and isinstance(value, (int, float)) and value < schema["minimum"]:
        errs.append(("ValueError",
                     "%s must be >= %s" % (_p(path), schema["minimum"]), path))

    if isinstance(value, list) and "minItems" in schema and len(value) < schema["minItems"]:
        if len(value) == 0:
            errs.append(("MissingFieldError",
                         "%s must not be empty" % _p(path), path))
        else:
            errs.append(("ValueError",
                         "%s needs at least %d items" % (_p(path), schema["minItems"]), path))

    if isinstance(value, dict):
        props = schema.get("properties", {})
        if "minProperties" in schema and len(value) < schema["minProperties"]:
            errs.append(("ValueError", "%s has too few keys" % _p(path), path))
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errs.append(("ValueError", "%s has too many keys" % _p(path), path))
        for req in schema.get("required", []):
            if req not in value:
                errs.append(("MissingFieldError",
                             "required field %s is missing" % _p(path + [req]),
                             path + [req]))
        if schema.get("additionalProperties", True) is False:
            allowed = set(props.keys())
            for k in value:
                if k not in allowed:
                    suggestion = _suggest(k, allowed)
                    hint = " — did you mean '%s'?" % suggestion if suggestion else ""
                    errs.append(("UnknownFieldError",
                                 "'%s' is not a valid field here%s" % (k, hint),
                                 path + [k]))
        for k, sub in props.items():
            if k in value:
                errs += _validate(value[k], sub, root, path + [k])

    if isinstance(value, list) and "items" in schema:
        item_schema = schema["items"]
        for idx, item in enumerate(value):
            if "oneOf" in item_schema:
                if not any(not _validate(item, br, root, path + [idx]) for br in item_schema["oneOf"]):
                    errs.append(("TypeError",
                                 "%s[%d] must be a string or a single-key mapping "
                                 "(cmd/file/signal/okf/mcp)" % (_p(path), idx),
                                 path))
            else:
                errs += _validate(item, item_schema, root, path + [idx])

    if "oneOf" in schema and "items" not in schema and not isinstance(value, list):
        if not any(not _validate(value, br, root, path) for br in schema["oneOf"]):
            errs.append(("TypeError", "%s does not match any allowed form" % _p(path), path))

    return errs


def _suggest(key, allowed):
    m = difflib.get_close_matches(key, list(allowed), n=1, cutoff=0.7)
    return m[0] if m else None


def _typename(v):
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, str):
        return "string"
    if isinstance(v, int):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    if v is None:
        return "null"
    return type(v).__name__


def _p(path):
    if not path:
        return "frontmatter"
    out = str(path[0])
    for seg in path[1:]:
        if isinstance(seg, int):
            out += "[%d]" % seg
        else:
            out += "." + str(seg)
    return "'%s'" % out


# --------------------------------------------------------------------------- #
# `until` expression analysis
# --------------------------------------------------------------------------- #
_ALLOWED_AST = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not,
    ast.Compare, ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Name, ast.Attribute, ast.Load, ast.Constant,
)


def analyze_until(expr):
    """Return (is_expression, root_names) or (False, set()) if it's prose."""
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError:
        return False, set()
    roots = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_AST):
            return False, set()  # has a call/subscript/etc → treat as prose
        if isinstance(node, ast.Name):
            roots.add(node.id)
    # An attribute root like ci.green surfaces as Name('ci'); a bare Name too.
    return True, roots


# --------------------------------------------------------------------------- #
# The three stages
# --------------------------------------------------------------------------- #
def lint_text(text, schema):
    file_lines = text.split("\n")

    # Stage 1: OKF conformance --------------------------------------------- #
    try:
        fm_text, body, _ = split_frontmatter(text)
        data = parse_frontmatter(fm_text)
    except SlacSyntax as e:
        return [Diagnostic("SLACSyntaxError", str(e), line=1)]

    if not isinstance(data, dict):
        return [Diagnostic("SLACSyntaxError", "frontmatter must be a mapping", line=1)]

    if "type" not in data:
        return [Diagnostic("MissingFieldError",
                           "required field 'type' is missing (OKF requires it; "
                           "use type: slac.loop)", line=find_line(file_lines, "type"))]

    # Stage 2: type check against the schema ------------------------------- #
    raw_errs = _validate(data, schema, schema, [])
    if raw_errs:
        diags = []
        for name, msg, path in raw_errs:
            key = next((str(s) for s in reversed(path) if isinstance(s, str)), None)
            diags.append(Diagnostic(name, msg, line=find_line(file_lines, key) if key else None))
        return diags

    # Stage 3: semantic lint ----------------------------------------------- #
    diags = []

    # 3a. body must contain a `# Goal` heading
    if not re.search(r"(?m)^\#\s+Goal\b", body):
        diags.append(Diagnostic("MissingFieldError",
                                "body is missing a required '# Goal' section",
                                line=None))

    agents = data.get("agents", {})
    if "checker" not in agents:
        diags.append(Diagnostic("NoCheckerWarning",
                                "'maker' has no 'checker' — it will grade its own "
                                "work (the /goal footgun). Add agents.checker.",
                                line=find_line(file_lines, "agents")))

    if "state" not in data:
        diags.append(Diagnostic("NoStateWarning",
                                "no 'state' set — the loop has no memory between "
                                "runs. Defaults to ./log.md; set it explicitly.",
                                line=None))

    boundaries = data.get("boundaries") or {}
    if not boundaries.get("never"):
        diags.append(Diagnostic("NoBoundaryWarning",
                                "no 'boundaries.never' — the loop has no hard stops.",
                                line=find_line(file_lines, "boundaries")))

    has_budget = bool(data.get("budget"))
    if "max_iterations" not in data and not has_budget:
        diags.append(Diagnostic("RunawayWarning",
                                "no 'max_iterations' and no 'budget' — the loop can "
                                "run forever. Add at least one cap.",
                                line=None))

    # 3b. `until` reachability (only for the expression form)
    declared = set()
    for item in data.get("context", []):
        if isinstance(item, dict) and "signal" in item:
            declared.add(item["signal"])
    until = data.get("until", "")
    if isinstance(until, str):
        is_expr, roots = analyze_until(until)
        if is_expr:
            allowed = declared | ALWAYS_SIGNALS
            for name in sorted(roots):
                if name not in allowed:
                    diags.append(Diagnostic(
                        "UnreachableStopWarning",
                        "until references signal '%s', which nothing produces "
                        "(declare it with a context item `- signal: %s`)."
                        % (name, name),
                        line=find_line(file_lines, "until")))

    return diags


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def load_schema():
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run(files, as_json=False, strict=False):
    """Lint ``files`` and print a report. Returns a process exit code.

    Shared entry point used by both the standalone shim and the ``slac`` CLI.
    """
    try:
        schema = load_schema()
    except Exception as e:  # pragma: no cover
        print("could not load schema at %s: %s" % (SCHEMA_PATH, e), file=sys.stderr)
        return 2

    results = {}
    total_errors = 0
    total_warnings = 0
    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
        except OSError as e:
            results[path] = [Diagnostic("SLACSyntaxError", "cannot read file: %s" % e)]
            total_errors += 1
            continue
        diags = lint_text(text, schema)
        results[path] = diags
        for d in diags:
            if d.severity == "error":
                total_errors += 1
            else:
                total_warnings += 1

    exit_code = 1 if (total_errors or (strict and total_warnings)) else 0

    if as_json:
        out = {
            p: [d.as_dict() for d in diags] for p, diags in results.items()
        }
        print(json.dumps(out, indent=2))
        return exit_code

    for path, diags in results.items():
        if not diags:
            print("\033[32mPASS\033[0m %s" % path)
            continue
        n_err = sum(1 for d in diags if d.severity == "error")
        tag = "\033[31mFAIL\033[0m" if n_err else "\033[33mWARN\033[0m"
        print("%s %s" % (tag, path))
        for d in diags:
            loc = ":%d" % d.line if d.line else ""
            colour = "\033[31m" if d.severity == "error" else "\033[33m"
            print("  %s%s\033[0m%s: %s  [fixSafety: %s]"
                  % (colour, d.name, loc, d.message, d.fix_safety))
        print()

    summary = "%d error(s), %d warning(s)" % (total_errors, total_warnings)
    if strict and total_warnings:
        summary += " (--strict: warnings count as errors)"
    print(summary)
    return exit_code


def main(argv=None):
    """Standalone lint entry point (used by the back-compat shim)."""
    parser = argparse.ArgumentParser(description="SLAC linter (type-check + lint).")
    parser.add_argument("files", nargs="+", help="one or more .slac.md files")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as errors")
    args = parser.parse_args(argv)
    return run(args.files, args.json, args.strict)


if __name__ == "__main__":
    sys.exit(main())
