"""Default backend: the Claude Code CLI in headless print mode.

Invokes `claude --print --output-format json --permission-mode <m> "<prompt>"`,
using the user's existing login (subscription) — no API key, no metered billing.
The agent's reply is read from the JSON `result` field; the checker's signals
contract is parsed from a fenced ```json block in that reply.
"""

import json
import re
import shutil
import subprocess

from .base import AgentResult, Backend

# A fenced ```json { ... } ``` block (non-greedy, supports nesting one level deep).
_JSON_BLOCK = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


class ClaudeCLIBackend(Backend):
    name = "claude_cli"

    def __init__(self, binary="claude"):
        self.binary = binary

    def is_available(self):
        return shutil.which(self.binary) is not None

    def describe(self):
        return "claude_cli -> `%s --print --output-format json` (login: %s)" % (
            self.binary, "found" if self.is_available() else "NOT found")

    def run_agent(self, role, prompt, model=None, permission_mode=None, timeout=900):
        if not self.is_available():
            return AgentResult(ok=False, error="`%s` CLI not on PATH" % self.binary)

        cmd = [self.binary, "--print", "--output-format", "json",
               "--permission-mode", permission_mode or "default"]
        if model:
            cmd += ["--model", model]
        cmd.append(prompt)

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return AgentResult(ok=False, error="claude timed out after %ss" % timeout)
        except OSError as e:
            return AgentResult(ok=False, error="failed to launch claude: %s" % e)

        if proc.returncode != 0:
            return AgentResult(ok=False, raw=proc.stdout,
                               error="claude exited %d: %s"
                               % (proc.returncode, (proc.stderr or "").strip()[:300]))

        text, tokens, cost = _parse_output(proc.stdout)
        contract = _parse_contract(text) if role == "checker" else {}
        return AgentResult(text=text, contract=contract, raw=proc.stdout,
                           tokens=tokens, cost=cost)


_USAGE_KEYS = ("input_tokens", "output_tokens",
               "cache_creation_input_tokens", "cache_read_input_tokens")


def _parse_output(stdout):
    """Return (text, tokens, cost) from `--output-format json` output.

    The CLI emits a JSON array of stream events whose final `result` event holds
    the assistant text plus `usage`/`total_cost_usd`.
    """
    stdout = (stdout or "").strip()
    try:
        data = json.loads(stdout)
    except ValueError:
        return stdout, 0, 0.0
    events = data if isinstance(data, list) else [data]
    text, tokens, cost = stdout, 0, 0.0
    for ev in reversed(events):
        if isinstance(ev, dict) and ("result" in ev or ev.get("type") == "result"):
            text = ev.get("result") or ev.get("text") or stdout
            usage = ev.get("usage") or {}
            tokens = sum(int(usage.get(k, 0) or 0) for k in _USAGE_KEYS)
            try:
                cost = float(ev.get("total_cost_usd") or 0.0)
            except (TypeError, ValueError):
                cost = 0.0
            break
    return text, tokens, cost


def _parse_contract(text):
    """Find the last fenced ```json block carrying signals/done/verdict."""
    best = {}
    for m in _JSON_BLOCK.finditer(text or ""):
        try:
            obj = json.loads(m.group(1))
        except ValueError:
            continue
        if isinstance(obj, dict) and (
            "signals" in obj or "done" in obj or "verdict" in obj
        ):
            best = obj
    return best
