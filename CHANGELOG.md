# Changelog

All notable changes to SLAC are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

> **Draft notice.** SLAC is **v0.0.1** — a first draft. Breaking changes to the
> language, schema, and diagnostics are expected before **0.1.0**. Pin the
> `version` field in your loops and read this file before upgrading.

## [Unreleased]

### Planned
- `slac run` — a reference **engine** that executes a validated loop directly
  (fetch context → maker → separate checker → evaluate `until` → repeat), so a
  `.slac.md` no longer needs a host harness to run.
- Editor support — syntax highlighting and inline diagnostics for `.slac.md`
  (language server / extension).

## [0.0.1] - 2026-06-18

First public draft: the language, its compiler front-end, and the tooling to
write and validate loops.

### Added
- **SLAC language specification** ([SPEC.md](./SPEC.md)) — the normative
  reference: file format (`.slac.md` = markdown + YAML frontmatter), the OKF
  profile (`type: slac.loop`), the frontmatter and body field reference, the
  two-form `until` condition (machine-evaluated expression over a signal
  namespace, or checker-judged prose), three-tier `boundaries`, the validation
  model, and the execution lifecycle.
- **JSON Schema type-check layer** (`src/slac/slac.schema.json`) — validates the
  frontmatter: required keys, types, enum values, and `additionalProperties:
  false` (so typos like `untill:` are caught).
- **Zero-dependency linter** (stock Python 3.8+; uses `pyyaml` if present)
  running **three ordered stages** that stop at the first hard failure:
  **OKF conformance → schema type-check → semantic lint**. Diagnostics read like
  a **Python traceback**, not numeric codes — errors named like Python
  exceptions (`SLACSyntaxError`, `MissingFieldError`, `UnknownFieldError`,
  `TypeError`, `ValueError`) that **halt**, and warnings (`NoCheckerWarning`,
  `NoStateWarning`, `UnreachableStopWarning`, `NoBoundaryWarning`,
  `RunawayWarning`) that **notify**. Every finding carries a `fixSafety` label
  (`safe` / `review` / `needs-human`). `--json` emits machine-readable findings
  so an agent can auto-apply the `safe` fixes; `--strict` promotes warnings to
  errors for CI.
- **`slac` CLI** (`src/slac/cli.py`) — `slac lint` (type-check + lint, with
  `--json` and `--strict`), `slac new` (scaffold a starter loop that lints
  clean), and `slac explain` (describe a diagnostic, or list them all).
- **Three worked examples** + **OKF index** (`examples/`) — `pr_babysitter`,
  `bug_fixer`, and `flaky_hunter`, plus an `index.md` directory ("loopbook").
- **Engine mappings** (`mappings/`) — field-by-field lowering onto **Claude Code
  `/loop`** (cron + subagents) and **OpenAI Codex `/goal`** (objective +
  budget + `spawn_agent`), each documenting what the engine **cannot yet
  enforce** — notably, neither enforces a separate checker.
- **Claude Code integration skill**
  (`integrations/claude-code/SKILL.md`) — teaches an agent to consume a
  `.slac.md`: validate with `slac lint`, then drive the loop on `/loop`.
- **Test suite** (`tests/test_linter.py`) — stdlib `unittest`, zero deps.
- **Makefile** and **pre-commit** config — `make check` (lint + test) is what CI
  runs.

[Unreleased]: https://github.com/ramanshrivastava/slac/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/ramanshrivastava/slac/releases/tag/v0.0.1
