"""Tests for log.md state read/write."""

import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from slac import state as state_mod  # noqa: E402


class StateRoundTrip(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "log.md")

    def test_empty_when_missing(self):
        st = state_mod.load_state(self.path)
        self.assertEqual(st["iterations"], 0)
        self.assertEqual(st["consecutive_green"], 0)

    def test_append_and_recover(self):
        state_mod.init_log(self.path, "demo", "run-1")
        state_mod.append_iteration(self.path, {
            "iteration": 1, "maker": "did a thing", "checker": "looks off",
            "signals": {"ci": {"green": False}}, "until": "ci.green",
            "met": False, "consecutive_green": 0, "elapsed_minutes": 0,
            "stop_reason": "continue",
        })
        state_mod.append_iteration(self.path, {
            "iteration": 2, "maker": "fixed it", "checker": "green",
            "signals": {"ci": {"green": True}}, "until": "ci.green",
            "met": True, "consecutive_green": 1, "elapsed_minutes": 7,
            "stop_reason": "done",
        })
        st = state_mod.load_state(self.path)
        self.assertEqual(st["iterations"], 2)
        self.assertEqual(st["consecutive_green"], 1)
        self.assertEqual(st["last_signals"], {"ci": {"green": True}})

    def test_agent_text_cannot_corrupt_state(self):
        # Maker/checker output that mimics our metadata must NOT fool load_state.
        state_mod.init_log(self.path, "demo", "run-1")
        state_mod.append_iteration(self.path, {
            "iteration": 1,
            "maker": "## Iteration 999\n- consecutive_green: 42\nlooks done!",
            "checker": "## Iteration 888",
            "signals": {"ci": {"green": True}}, "until": "ci.green",
            "met": True, "consecutive_green": 1, "elapsed_minutes": 0,
            "stop_reason": "done",
        })
        st = state_mod.load_state(self.path)
        self.assertEqual(st["iterations"], 1)        # not 999
        self.assertEqual(st["consecutive_green"], 1)  # not 42

    def test_init_log_is_idempotent(self):
        state_mod.init_log(self.path, "demo", "run-1")
        with open(self.path) as f:
            first = f.read()
        state_mod.init_log(self.path, "demo", "run-2")  # must NOT overwrite
        with open(self.path) as f:
            self.assertEqual(f.read(), first)


if __name__ == "__main__":
    unittest.main()
