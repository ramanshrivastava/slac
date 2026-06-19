"""The `slac run` engine — execute a validated loop, one iteration at a time.

Pipeline per iteration: fetch context -> run the maker -> run a SEPARATE checker
-> evaluate `until` over the checker's reported signals -> append to log.md ->
check caps. Loops are refused (not run) if they don't lint clean.
"""

import datetime
import glob
import json
import os
import subprocess
import time
import uuid

from . import state as state_mod
from .backends import get_backend
from .evaluator import (
    ALWAYS, always_signals, evaluate_until, is_expression, signal_paths,
    signal_roots, signal_skeleton,
)
from .linter import lint_text, load_schema, parse_frontmatter, split_frontmatter

_MAX_CTX = 4000
_BIG = 10 ** 9  # sentinel streak: tests whether the non-streak clauses of `until` hold


# --------------------------------------------------------------------------- #
# Context fetching
# --------------------------------------------------------------------------- #
def _truncate(s, n=_MAX_CTX):
    s = s or ""
    return s if len(s) <= n else s[:n] + "\n... [truncated %d chars]" % (len(s) - n)


def fetch_context(items, cwd):
    """Resolve context items to text. Returns (context_text, declared_signals)."""
    parts, declared = [], []
    for it in items or []:
        if isinstance(it, str):
            it = {"cmd": it}
        if not isinstance(it, dict):
            continue
        if "cmd" in it:
            parts.append("$ %s\n%s" % (it["cmd"], _truncate(_run_cmd(it["cmd"], cwd))))
        elif "file" in it:
            parts.append("# file: %s\n%s" % (it["file"], _truncate(_read_glob(it["file"], cwd))))
        elif "okf" in it:
            parts.append("# okf: %s\n%s" % (it["okf"], _truncate(_read_file(it["okf"], cwd))))
        elif "signal" in it:
            declared.append(it["signal"])
        elif "mcp" in it:
            parts.append("# mcp (not executed by the v0.1 runner): %s" % it["mcp"])
    return "\n\n".join(parts), declared


def _run_cmd(cmd, cwd):
    # TRUST MODEL: a `cmd:` context item is shell written by the LOOP AUTHOR
    # (like a CI `run:` step or a Makefile target), so shell=True is intentional —
    # pipes/&&/globs in context commands are expected. The string is NOT external
    # user input. As with `make` or a CI file, only run `.slac.md` loops you trust;
    # `slac lint` shows a loop's commands before you run it.
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True,  # noqa: S602
                           text=True, timeout=120)
        out = p.stdout or ""
        if (p.stderr or "").strip():
            out += "\n[stderr]\n" + p.stderr
        return out
    except subprocess.TimeoutExpired:
        return "[context cmd timed out]"
    except OSError as e:
        return "[context cmd failed: %s]" % e


def _read_glob(pattern, cwd):
    files = sorted(glob.glob(os.path.join(cwd, pattern), recursive=True))[:20]
    if not files:
        return "[no files match %s]" % pattern
    out = []
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                out.append("--- %s ---\n%s" % (f, fh.read()))
        except OSError as e:
            out.append("--- %s --- [unreadable: %s]" % (f, e))
    return "\n".join(out)


def _read_file(path, cwd):
    try:
        with open(os.path.join(cwd, path), encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError as e:
        return "[unreadable %s: %s]" % (path, e)


# --------------------------------------------------------------------------- #
# Prompt building
# --------------------------------------------------------------------------- #
def _boundaries_text(b):
    if not b:
        return ""
    rows = []
    for tier, label in (("always", "ALWAYS (no approval needed)"),
                        ("ask", "ASK FIRST (pause for human approval)"),
                        ("never", "NEVER (hard stop)")):
        for item in b.get(tier) or []:
            rows.append("  - [%s] %s" % (label, item))
    return ("\n## Boundaries\n" + "\n".join(rows)) if rows else ""


def _maker_prompt(goal, instructions, context_text, boundaries):
    return "\n".join([
        goal.strip(),
        "\n## Your role: MAKER",
        (instructions or "").strip(),
        "\n## Context (fetched this iteration)",
        context_text or "_(none)_",
        _boundaries_text(boundaries),
    ]).strip()


def _checker_prompt(goal, instructions, until, maker_text, boundaries):
    # Tell the checker the exact dotted paths `until` needs (excluding the
    # runner-filled always-signals) and the nested shape to return them in, so
    # `answer.value` isn't answered with a bare scalar.
    paths = sorted(p for p in signal_paths(until) if p not in ALWAYS)
    skeleton = signal_skeleton(paths)
    example = json.dumps({"signals": skeleton, "done": True,
                          "verdict": "one line"}, indent=2)
    return "\n".join([
        goal.strip(),
        "\n## Your role: CHECKER",
        "Independently verify whether the goal is met. Do NOT trust the maker.",
        (instructions or "").strip(),
        "\n## Stop condition (`until`)",
        "`%s`" % until,
        "\n## What the maker just did",
        maker_text or "_(no output)_",
        _boundaries_text(boundaries),
        "\n## Required output",
        "Report these exact signal paths: %s" % (", ".join(paths) or "(none)"),
        "End your reply with ONE fenced json block of EXACTLY this shape "
        "(fill in real values; set done to whether `until` is satisfied):",
        "```json",
        example,
        "```",
    ]).strip()


def _oneline(text, n=140):
    s = " ".join((text or "").split())
    return s if len(s) <= n else s[:n] + "…"


# --------------------------------------------------------------------------- #
# The run loop
# --------------------------------------------------------------------------- #
def run(path, maker_engine="claude_cli", checker_engine=None, max_iter=None,
        permission_mode="default", dry_run=False, out=print):
    """Execute a loop file. Returns a process exit code."""
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        out("cannot read %s: %s" % (path, e))
        return 2

    # Pre-flight: refuse to run an invalid loop (the "don't fall flat" gate).
    schema = load_schema()
    diags = lint_text(text, schema)
    errors = [d for d in diags if d.severity == "error"]
    if errors:
        out("Refusing to run %s — %d error(s). Fix them first (`slac lint %s`):"
            % (path, len(errors), path))
        for d in errors:
            out("  %s: %s" % (d.name, d.message))
        return 2
    for d in diags:
        if d.severity == "warning":
            out("warning: %s: %s" % (d.name, d.message))

    fm_text, body, _ = split_frontmatter(text)
    fm = parse_frontmatter(fm_text)
    cwd = os.path.dirname(os.path.abspath(path)) or "."

    loop = fm.get("loop", "loop")
    until = fm.get("until", "")
    goal = body.strip()
    agents = fm.get("agents") or {}
    maker_cfg = agents.get("maker") or {}
    checker_cfg = agents.get("checker") or {}
    boundaries = fm.get("boundaries") or {}
    context_items = fm.get("context") or []
    state_path = os.path.join(cwd, fm.get("state", "./log.md"))
    max_iter = max_iter or fm.get("max_iterations", 20)
    roots = signal_roots(until)

    maker_engine = maker_cfg.get("engine", maker_engine)
    checker_engine = checker_cfg.get("engine", checker_engine or maker_engine)

    if dry_run:
        _print_plan(out, loop, until, roots, context_items,
                    maker_engine, checker_engine, max_iter, fm.get("budget"),
                    bool(checker_cfg))
        return 0

    # Resolve backends.
    try:
        maker_be = get_backend(maker_engine)
        checker_be = get_backend(checker_engine) if checker_cfg else None
    except KeyError as e:
        out(str(e))
        return 3
    if not maker_be.is_available():
        out("Cannot run: maker engine unavailable — %s" % maker_be.describe())
        return 3
    if checker_be and not checker_be.is_available():
        out("Cannot run: checker engine unavailable — %s" % checker_be.describe())
        return 3

    st = state_mod.load_state(state_path)
    run_id = datetime.datetime.now().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    state_mod.init_log(state_path, loop, run_id)

    start = time.time()
    consecutive_green = st["consecutive_green"]
    iteration = st["iterations"]
    expr_until = is_expression(until)

    while iteration < max_iter:
        iteration += 1
        elapsed = int((time.time() - start) / 60)
        out("\n=== Iteration %d ===" % iteration)

        context_text, _ = fetch_context(context_items, cwd)
        out("running maker (%s)…" % maker_engine)
        mres = maker_be.run_agent("maker",
                                  _maker_prompt(goal, maker_cfg.get("instructions"),
                                                context_text, boundaries),
                                  model=maker_cfg.get("model"),
                                  permission_mode=permission_mode)
        if not mres.ok:
            out("maker failed: %s" % mres.error)
            return 4
        out("  maker: %s" % _oneline(mres.text))

        reported, checker_done, checker_text = {}, None, ""
        if checker_be:
            out("running checker (%s)…" % checker_engine)
            cres = checker_be.run_agent("checker",
                                        _checker_prompt(goal, checker_cfg.get("instructions"),
                                                        until, mres.text, boundaries),
                                        model=checker_cfg.get("model"),
                                        permission_mode=permission_mode)
            if not cres.ok:
                out("checker failed: %s" % cres.error)
                return 4
            reported, checker_done, checker_text = dict(cres.signals), cres.done, cres.text
            out("  checker: %s" % _oneline(cres.verdict or cres.text))

        # Streak logic: does the loop's core condition hold this iteration?
        if expr_until:
            core_signals = dict(reported)
            core_signals.update(always_signals(iteration, _BIG, elapsed))
            core_met, _ = evaluate_until(until, core_signals)
        else:
            core_met = bool(checker_done)
        consecutive_green = consecutive_green + 1 if core_met else 0

        signals = dict(reported)
        signals.update(always_signals(iteration, consecutive_green, elapsed))
        if expr_until:
            met, reason = evaluate_until(until, signals)
        else:
            met, reason = bool(checker_done), "checker verdict"

        stop_reason = "done" if met else ("limit" if iteration >= max_iter else "continue")
        state_mod.append_iteration(state_path, {
            "iteration": iteration, "maker": mres.text, "checker": checker_text,
            "signals": signals, "until": until, "met": met,
            "consecutive_green": consecutive_green, "elapsed_minutes": elapsed,
            "stop_reason": stop_reason,
        })
        out("  → %s (%s)" % ("DONE" if met else "not yet", reason))
        if met:
            out("\n✓ done in %d iteration(s); `until` met. log: %s" % (iteration, state_path))
            return 0

    out("\n✗ stopped at limit (max_iterations=%d) without meeting `until`. log: %s"
        % (max_iter, state_path))
    return 1


def _print_plan(out, loop, until, roots, context_items, maker_engine,
                checker_engine, max_iter, budget, has_checker):
    out("Loop:    %s" % loop)
    out("Maker:   %s" % maker_engine)
    out("Checker: %s" % (checker_engine if has_checker else "(none — maker would grade itself!)"))
    out("Until:   %s" % until)
    out("Signals: %s" % (", ".join(sorted(roots)) if roots else "(prose `until` — checker judges)"))
    out("Caps:    max_iterations=%s%s" % (max_iter, ", budget=%s" % budget if budget else ""))
    out("Context sources:")
    for it in context_items or []:
        if isinstance(it, str):
            it = {"cmd": it}
        kind = next(iter(it)) if isinstance(it, dict) and it else "?"
        out("  - %s: %s" % (kind, it.get(kind)))
    out("\n(dry run — nothing executed)")
