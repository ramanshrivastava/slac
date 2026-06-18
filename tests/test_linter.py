"""Tests for the SLAC linter. Runs under plain `unittest` (zero deps) or pytest.

    python3 -m unittest discover -s tests        # from the repo root
    pytest                                        # if pytest is installed
"""

import os
import sys
import unittest

# Make the package importable without installing it.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from slac.linter import lint_text, load_schema, analyze_until  # noqa: E402

SCHEMA = load_schema()
EXAMPLES = os.path.join(ROOT, "examples")


def names(diags):
    return [d.name for d in diags]


class ExamplesLintClean(unittest.TestCase):
    def test_all_examples_pass(self):
        for fn in sorted(os.listdir(EXAMPLES)):
            if not fn.endswith(".slac.md"):
                continue
            with open(os.path.join(EXAMPLES, fn), encoding="utf-8") as f:
                diags = lint_text(f.read(), SCHEMA)
            self.assertEqual(diags, [], "%s should lint clean, got %s" % (fn, names(diags)))


BROKEN = """\
---
type: slac.loop
loop: BadName
untill: ci.green
context: "should be a list"
agents:
  maker:
    model: opus
isolation: docker
---
No goal heading here.
"""

RISKY = """\
---
type: slac.loop
loop: risky
until: mystery.signal and ci.green
context:
  - cmd: gh pr checks
agents:
  maker:
    model: opus
---
# Goal
Do a thing with no checker, state, boundaries, or cap.
"""

GOOD = """\
---
type: slac.loop
loop: good_loop
until: ci.green and consecutive_green >= 2
context:
  - signal: ci
agents:
  maker: { model: opus }
  checker: { model: opus, mode: refute }
state: ./log.md
boundaries:
  never: [commit secrets]
max_iterations: 10
---
# Goal
A fully specified loop.
"""


class BrokenFileHalts(unittest.TestCase):
    def setUp(self):
        self.diags = lint_text(BROKEN, SCHEMA)
        self.names = names(self.diags)

    def test_all_errors(self):
        self.assertTrue(all(d.severity == "error" for d in self.diags))

    def test_missing_until(self):
        self.assertIn("MissingFieldError", self.names)

    def test_typo_is_unknown_field_with_suggestion(self):
        unknown = [d for d in self.diags if d.name == "UnknownFieldError"]
        self.assertTrue(unknown)
        self.assertIn("until", unknown[0].message)  # "did you mean 'until'?"

    def test_bad_loop_name_and_enum(self):
        self.assertIn("ValueError", self.names)

    def test_context_wrong_type(self):
        self.assertIn("TypeError", self.names)

    def test_typo_fixsafety_is_safe(self):
        unknown = [d for d in self.diags if d.name == "UnknownFieldError"][0]
        self.assertEqual(unknown.fix_safety, "safe")


class RiskyFileWarns(unittest.TestCase):
    def setUp(self):
        self.diags = lint_text(RISKY, SCHEMA)
        self.names = names(self.diags)

    def test_no_errors(self):
        self.assertTrue(all(d.severity == "warning" for d in self.diags))

    def test_expected_warnings_present(self):
        for expected in ["NoCheckerWarning", "NoStateWarning",
                         "NoBoundaryWarning", "RunawayWarning",
                         "UnreachableStopWarning"]:
            self.assertIn(expected, self.names)

    def test_unreachable_names_the_signals(self):
        unreach = [d for d in self.diags if d.name == "UnreachableStopWarning"]
        joined = " ".join(d.message for d in unreach)
        self.assertIn("mystery", joined)
        self.assertIn("ci", joined)


class GoodFileClean(unittest.TestCase):
    def test_clean(self):
        self.assertEqual(lint_text(GOOD, SCHEMA), [])


class UntilGrammar(unittest.TestCase):
    def test_expression_collects_roots(self):
        is_expr, roots = analyze_until("ci.green and tests.passed == tests.total")
        self.assertTrue(is_expr)
        self.assertEqual(roots, {"ci", "tests"})

    def test_prose_is_not_expression(self):
        is_expr, _ = analyze_until("CI is green twice in a row")
        self.assertFalse(is_expr)

    def test_function_calls_rejected_as_prose(self):
        # A call is forbidden in the whitelist, so it is treated as prose.
        is_expr, _ = analyze_until("len(failures) == 0")
        self.assertFalse(is_expr)


if __name__ == "__main__":
    unittest.main()
