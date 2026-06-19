"""Tests for the runner's dry-run and pre-flight gate (no agents spawned)."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from slac import runner  # noqa: E402

EXAMPLE = os.path.join(ROOT, "examples", "pr_babysitter.slac.md")

BROKEN = """\
---
type: slac.loop
loop: broken
context: "not a list"
agents:
  maker:
    model: opus
---
No goal.
"""


class DryRun(unittest.TestCase):
    def test_dry_run_prints_plan_and_runs_nothing(self):
        lines = []
        code = runner.run(EXAMPLE, dry_run=True, out=lines.append)
        self.assertEqual(code, 0)
        joined = "\n".join(lines)
        self.assertIn("pr_babysitter", joined)
        self.assertIn("claude_cli", joined)
        self.assertIn("dry run", joined)


class ExplicitMaxIterZero(unittest.TestCase):
    def test_max_iter_zero_is_honored(self):
        # `--max-iter 0` must override the frontmatter default (not fall back via `or`).
        lines = []
        runner.run(EXAMPLE, max_iter=0, dry_run=True, out=lines.append)
        self.assertIn("max_iterations=0", "\n".join(lines))


class PreflightGate(unittest.TestCase):
    def test_refuses_invalid_loop(self):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "broken.slac.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(BROKEN)
        lines = []
        code = runner.run(path, dry_run=True, out=lines.append)
        self.assertEqual(code, 2)  # refused, not run
        self.assertIn("Refusing to run", "\n".join(lines))


class ContextFetch(unittest.TestCase):
    def test_fetch_cmd_and_signal(self):
        text, declared = runner.fetch_context(
            [{"cmd": "echo hello"}, {"signal": "ci"}], cwd=".")
        self.assertIn("hello", text)
        self.assertEqual(declared, ["ci"])


if __name__ == "__main__":
    unittest.main()
