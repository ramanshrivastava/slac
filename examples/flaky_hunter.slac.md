---
type: slac.loop
loop: flaky_hunter
version: 0.0.1
title: Flaky Test Hunter
description: Find and kill flaky tests, proving stability with consecutive green runs.
tags: [ci, flaky, quality]
timestamp: 2026-06-18T00:00:00Z

schedule: daily          # runs as a morning automation

context:
  - cmd: gh run list --limit 50 --json conclusion,databaseId
  - file: "tests/**/*.py"
  - signal: flaky         # fills flaky.count (suspected flaky tests remaining)
  - signal: suite         # fills suite.green_streak (consecutive all-green runs)

agents:
  maker:
    model: opus
    instructions: |
      Identify flaky tests from CI retry history, diagnose the source of
      non-determinism (timing, ordering, shared state), and make each test
      deterministic. Do not weaken assertions to hide flakiness.
  checker:
    model: opus
    mode: refute
    instructions: |
      Re-run each touched test many times. Reject the fix unless it is green on
      every run and the assertion strength is preserved.

until: flaky.count == 0 and suite.green_streak >= 5

state: ./log.md

boundaries:
  always: [re-run a touched test at least 20 times before declaring it stable]
  ask:    [removing a test entirely]
  never:
    - weaken or delete assertions to make a test pass
    - add blanket retries to mask flakiness

max_iterations: 30
budget:
  tokens: 600_000
---

# Goal

Drive the suite to zero suspected flaky tests, proven by five consecutive all-green
runs. Stability must come from determinism, not from hidden retries.

## Evaluation

The `checker` re-runs touched tests repeatedly; a fix counts only if every run is
green and the assertions are as strong as before.

## Boundaries

Masking flakiness with retries or weakened assertions is forbidden — it trades a
visible problem for an invisible one.
