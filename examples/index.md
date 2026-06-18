---
type: index
title: SLAC Example Loops
description: A loopbook — the canonical example loops shipped with SLAC v0.0.1.
tags: [examples, loopbook]
---

# SLAC Example Loops

This directory is an [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
bundle. `index.md` (this file) lists the loops for progressive disclosure; each loop
is one `.slac.md` concept.

| Loop | Goal | Stop condition (`until`) |
|---|---|---|
| [PR Babysitter](./pr_babysitter.slac.md) | Get a PR's CI green without changing public behavior | `ci.green and tests.passed == tests.total and consecutive_green >= 2` |
| [Bug Fixer](./bug_fixer.slac.md) | Fix a reported bug and lock it with a regression test | `not repro.fails and tests.passed == tests.total` |
| [Flaky Hunter](./flaky_hunter.slac.md) | Kill flaky tests, proven by consecutive green runs | `flaky.count == 0 and suite.green_streak >= 5` |

All three are fully specified — they lint clean (zero errors, zero warnings):

```bash
python3 ../linter/slac_lint.py *.slac.md
```
