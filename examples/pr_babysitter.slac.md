---
type: slac.loop
loop: pr_babysitter
version: 0.0.1
title: PR Babysitter
description: Drive an open PR to green CI without changing public behavior.
tags: [ci, maintenance]
timestamp: 2026-06-18T00:00:00Z

context:
  - cmd: git diff main
  - cmd: gh pr checks
  - signal: ci          # fills ci.green, ci.failing_logs
  - signal: tests       # fills tests.passed, tests.total

agents:
  maker:
    model: opus
    instructions: |
      Read the failing CI logs and the diff against main, then fix the failing
      tests. Touch only what is needed to make CI pass.
  checker:
    model: opus
    mode: refute        # try to DISPROVE "done"; default to not-done if unsure
    instructions: |
      Confirm CI is genuinely green from the real `gh pr checks` output, and that
      no public API changed. Do not trust the maker's claim.

until: ci.green and tests.passed == tests.total and consecutive_green >= 2

state: ./log.md         # OKF log.md doubles as on-disk memory

boundaries:
  always: [run the test suite before pushing]
  ask:    [changing a database schema]
  never:
    - edit the public API
    - skip or delete tests
    - commit secrets

max_iterations: 20
budget:
  tokens: 500_000
---

# Goal

Get this pull request's CI to green **without changing public behavior**. A run is
done only when CI passes twice in a row and the public API is untouched.

## Context

The failing checks and the diff against `main` are the fuel. Pull fresh logs every
iteration — never trust the previous run's output.

## Evaluation

The `checker` confirms `until` independently of the `maker`, reading green CI from
the real `gh pr checks` output, not the maker's word.

## Boundaries

Public API stability is the hard line. When unsure about a schema change, stop and
ask rather than guess.
