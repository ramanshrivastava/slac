---
type: slac.loop
loop: test1_raman
version: 0.0.1
title: Test1 Raman
description: TODO — one sentence on what this loop achieves.

context:
  - cmd: echo "TODO: real fuel (commands, files, signals)"
  - signal: ci          # fills ci.green; declare every signal used in `until`

agents:
  maker:
    model: opus
    instructions: |
      TODO: what the implementer should do each iteration.
  checker:
    model: opus
    mode: refute        # a SEPARATE agent confirms "done" — never the maker
    instructions: |
      TODO: how the checker independently verifies the goal is met.

until: ci.green and consecutive_green >= 2

state: ./log.md         # on-disk memory between runs (OKF log.md)

boundaries:
  always: []
  ask: []
  never:
    - commit secrets

max_iterations: 20
budget:
  tokens: 500_000
---

# Goal

TODO: one clear sentence describing the outcome this loop drives toward.
