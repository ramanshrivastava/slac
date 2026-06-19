"""Read and write a loop's on-disk memory (`log.md`).

`log.md` is the OKF-reserved file SLAC uses as the loop's state between runs.
It is human-readable markdown: one `## Iteration N` section per turn. Each
section also carries a single machine-readable HTML-comment marker
(`<!-- slac-state {...} -->`) that `load_state` reads — so agent output that
happens to contain `## Iteration 999` or `- consecutive_green: 7` can never
corrupt the recovered counters.
"""

import json
import os
import re

# The state marker is written by us at the end of each iteration; agent text is
# written before it, so the LAST marker in the file is always the latest turn.
_STATE_RE = re.compile(r"<!-- slac-state (.*?) -->", re.DOTALL)


def load_state(path):
    """Return {iterations, consecutive_green, last_signals} from an existing log."""
    empty = {"iterations": 0, "consecutive_green": 0, "last_signals": {}}
    if not path or not os.path.exists(path):
        return empty
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    markers = _STATE_RE.findall(text)
    if not markers:
        return empty
    try:
        st = json.loads(markers[-1])
    except ValueError:
        return empty
    sig = st.get("signals")
    return {
        "iterations": int(st.get("iteration", 0)),
        "consecutive_green": int(st.get("consecutive_green", 0)),
        "last_signals": sig if isinstance(sig, dict) else {},
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
    marker = json.dumps({
        "iteration": record["iteration"],
        "consecutive_green": record.get("consecutive_green", 0),
        "signals": sig,
    }, sort_keys=True)
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
        # Machine-recoverable metadata for load_state(), isolated from prose.
        "<!-- slac-state %s -->" % marker,
        "",
    ]
    with open(path, "a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
