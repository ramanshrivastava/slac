"""Tests for the runtime `until` evaluator."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from slac.evaluator import (  # noqa: E402
    UntilError, evaluate_until, is_expression, signal_paths, signal_roots,
    signal_skeleton,
)


class SignalPaths(unittest.TestCase):
    def test_dotted_paths(self):
        self.assertEqual(
            signal_paths("ci.green and tests.passed == tests.total"),
            {"ci.green", "tests.passed", "tests.total"},
        )

    def test_bare_name(self):
        self.assertEqual(signal_paths("consecutive_green >= 2"), {"consecutive_green"})

    def test_skeleton_nests(self):
        self.assertEqual(
            signal_skeleton({"ci.green", "tests.passed"}),
            {"ci": {"green": "<value>"}, "tests": {"passed": "<value>"}},
        )


class ExpressionDetection(unittest.TestCase):
    def test_expression(self):
        self.assertTrue(is_expression("ci.green and tests.passed == tests.total"))

    def test_prose(self):
        self.assertFalse(is_expression("CI is green twice in a row"))

    def test_roots(self):
        self.assertEqual(signal_roots("ci.green and tests.passed >= 1"),
                         {"ci", "tests"})


class EvaluateUntil(unittest.TestCase):
    def test_attribute_access_true(self):
        met, _ = evaluate_until(
            "ci.green and tests.passed == tests.total",
            {"ci": {"green": True}, "tests": {"passed": 5, "total": 5}},
        )
        self.assertTrue(met)

    def test_attribute_access_false(self):
        met, _ = evaluate_until(
            "ci.green and tests.passed == tests.total",
            {"ci": {"green": True}, "tests": {"passed": 4, "total": 5}},
        )
        self.assertFalse(met)

    def test_consecutive_green_clause(self):
        sig = {"ci": {"green": True}, "tests": {"passed": 5, "total": 5},
               "consecutive_green": 2}
        met, _ = evaluate_until(
            "ci.green and tests.passed == tests.total and consecutive_green >= 2", sig)
        self.assertTrue(met)
        sig["consecutive_green"] = 1
        met, _ = evaluate_until(
            "ci.green and tests.passed == tests.total and consecutive_green >= 2", sig)
        self.assertFalse(met)

    def test_missing_signal_is_not_met(self):
        met, reason = evaluate_until("ci.green", {})
        self.assertFalse(met)
        self.assertIn("signal", reason)

    def test_type_mismatch_does_not_crash(self):
        # "5" >= 1 raises TypeError in py3; must be recoverable, not fatal.
        met, reason = evaluate_until("tests.passed >= 1", {"tests": {"passed": "5"}})
        self.assertFalse(met)
        self.assertIn("waiting", reason)

    def test_prose_raises(self):
        with self.assertRaises(UntilError):
            evaluate_until("the bug no longer reproduces", {})

    def test_no_builtins_available(self):
        # `len` is not callable (calls are rejected at parse → treated as prose).
        with self.assertRaises(UntilError):
            evaluate_until("len(x) == 0", {"x": []})


if __name__ == "__main__":
    unittest.main()
