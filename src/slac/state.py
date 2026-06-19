"""Read and write a loop's on-disk memory (`log.md`).

`log.md` is the OKF-reserved file SLAC uses as the loop's state between runs.
It is human-readable markdown: one `## Iteration N` section per turn, each
carrying the signals and a machine-recoverable `consecutive_green` line so a
later run can resume.
"""

import json
import os
import re

_ITER_RE = re.compile(r"(?m)^##\s+Iteration\s+(\d+)\b")
_CG_RE = re.compile(r"(?m)^- consecutive_green:\s*(\d+)\s*$")
_SIGNALS_RE = re.compile(r"(?ms)^<!-- signals (\{.*?\}) -->\s*$")


def load_state(path):
    """Return {iterations, consecutive_green, last_signals} from an existing log."""
    empty = {"iterations": 0, "consecutive_green": 0, "last_signals": {}}
    if not path or not os.path.exists(path):
        return empty
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    iters = [int(m.group(1)) for m in _ITER_RE.finditer(text)]
    iterations = max(iters) if iters else 0
    cg_matches = _CG_RE.findall(text)
    consecutive_green = int(cg_matches[-1]) if cg_matches else 0
    sig_matches = _SIGNALS_RE.findall(text)
    last_signals = {}
    if sig_matches:
        try:
            last_signals = json.loads(sig_matches[-1])
        except ValueError:
            last_signals = {}
    return {
        "iterations": iterations,
        "consecutive_green": consecutive_green,
        "last_signals": last_signals,
    }


def init_log(path, loop, run_id):
    """Create the log header if the file doesn't already exist."""
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(
            "---\n"
            "type: okf.log\n"
            "loop: %s\n"
            "run_id: %s\n"
            "---\n\n"
            "# Execution Log\n\n" % (loop, run_id)
        )


def append_iteration(path, record):
    """Append one iteration section.

    record: {iteration, maker, checker, signals, until, met, stop_reason,
             consecutive_green, elapsed_minutes}
    """
    sig = record.get("signals") or {}
    lines = [
        "## Iteration %d" % record["iteration"],
        "",
        "- elapsed_minutes: %s" % record.get("elapsed_minutes", 0),
        "- consecutive_green: %s" % record.get("consecutive_green", 0),
        "- until: `%s`" % record.get("until", ""),
        "- met: %s" % bool(record.get("met")),
        "- stop_reason: %s" % (record.get("stop_reason") or "continue"),
        "",
        "**Maker**",
        "",
        (record.get("maker") or "").strip() or "_(no output)_",
        "",
        "**Checker**",
        "",
        (record.get("checker") or "").strip() or "_(no output)_",
        "",
        "**Signals**",
        "",
        "```json",
        json.dumps(sig, indent=2, sort_keys=True),
        "```",
        # Machine-recoverable copy for load_state() (single line).
        "<!-- signals %s -->" % json.dumps(sig, sort_keys=True),
        "",
    ]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
