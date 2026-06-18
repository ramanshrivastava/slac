---
type: slac.loop
loop: bug_fixer
version: 0.0.1
title: Bug Fixer
description: Reproduce a reported bug, fix it, and lock it down with a regression test.
tags: [bugs, quality]
timestamp: 2026-06-18T00:00:00Z

context:
  - okf: ./reports/bug-1234.md   # the bug report as an OKF concept
  - cmd: pytest -x -q
  - signal: repro                 # fills repro.fails (does the bug still reproduce?)
  - signal: tests                 # fills tests.passed, tests.total

agents:
  maker:
    model: opus
    instructions: |
      Reproduce the bug from the report, find the root cause, and fix it. Add a
      regression test that fails before your fix and passes after.
  checker:
    model: opus
    mode: refute
    instructions: |
      Verify the regression test actually fails on the pre-fix code and passes now,
      and that the original repro no longer triggers. Reject if the test is trivial.

until: not repro.fails and tests.passed == tests.total

state: ./log.md

boundaries:
  always: [add a regression test for every fix]
  ask:    [changing behavior other code depends on]
  never:
    - suppress or xfail the failing test instead of fixing it
    - commit secrets

max_iterations: 15
budget:
  tokens: 400_000
---

# Goal

Fix the bug described in `reports/bug-1234.md` and prove it stays fixed with a
regression test. Done only when the bug no longer reproduces and the suite is green.

## Evaluation

The `checker` must confirm the regression test is meaningful: it should fail on the
original code and pass on the fixed code. A fix without a failing-then-passing test
does not count as done.

## Boundaries

Never paper over the failure by skipping the test — that defeats the loop's purpose.
