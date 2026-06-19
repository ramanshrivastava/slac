"""Tests for backend result handling (no subprocess spawned)."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from slac.backends.base import AgentResult  # noqa: E402


class SignalsGuard(unittest.TestCase):
    def test_dict_signals(self):
        r = AgentResult(contract={"signals": {"ci": {"green": True}}})
        self.assertEqual(r.signals, {"ci": {"green": True}})

    def test_non_dict_signals_become_empty(self):
        # A checker that reports signals as a list/string must not crash runner.py.
        self.assertEqual(AgentResult(contract={"signals": ["nope"]}).signals, {})
        self.assertEqual(AgentResult(contract={"signals": "nope"}).signals, {})

    def test_non_dict_contract(self):
        self.assertEqual(AgentResult(contract=None).signals, {})

    def test_done_and_verdict(self):
        r = AgentResult(contract={"done": True, "verdict": "ok"})
        self.assertTrue(r.done)
        self.assertEqual(r.verdict, "ok")


if __name__ == "__main__":
    unittest.main()
