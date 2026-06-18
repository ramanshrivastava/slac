# Contributing to SLAC

SLAC is a small language on purpose. Changes should keep it small: the linter is
**zero-dependency** (stock Python 3.8+), diagnostics read like Python exceptions,
and every bundled example **must lint clean**.

## Core design principle

The **maker and checker MUST be separate agents.** The checker is the
type-checker the fuzzy LLM executor took away, moved to runtime — it judges the
`until` condition independently instead of letting the maker grade its own
homework. Any change that lets one agent both do and approve the work, or that
makes the checker optional in spirit, defeats the reason SLAC exists. Keep them
distinct.

Corollary: **examples must lint clean.** `make lint` runs over `examples/*.slac.md`
in CI; a new example that emits an error (or, under `--strict`, a warning) does
not merge.

## Dev setup

```bash
make install-dev     # editable install + dev extras (pytest, pyyaml, pre-commit)
make check           # lint the examples + run the test suite (what CI runs)
pre-commit install   # run the checks on every commit (also: make hooks)
```

The linter has no runtime dependencies; `pyyaml` is dev-only (maximal YAML
coverage — a bundled parser handles the SLAC subset otherwise).

## Project layout

```
src/slac/
  cli.py             the `slac` command (lint / new / explain)
  linter.py          zero-dependency validator (OKF → schema → semantic)
  slac.schema.json   JSON Schema for the frontmatter (the type-check)
tests/
  test_linter.py     stdlib unittest suite
examples/            worked loops + OKF index — must lint clean
linter/rules.md      every diagnostic, with rationale
```

## Lint and test

```bash
make lint            # PYTHONPATH=src python -m slac lint examples/*.slac.md
make test            # PYTHONPATH=src python -m unittest discover -s tests -v
make check           # both
```

Run the CLI straight from a clone with `PYTHONPATH=src python -m slac ...`, or via
the zero-install shim `python3 linter/slac_lint.py examples/*.slac.md`.

## Adding a new diagnostic

A diagnostic is an error (HALT, named like a Python exception) or a warning
(NOTIFY, `*Warning`). To add one, touch all of these:

1. **`src/slac/linter.py`** — add the name to `ERROR_NAMES` or `WARNING_NAMES`,
   add its default label to `DEFAULT_FIXSAFETY` (`safe` / `review` /
   `needs-human`), and emit the `Diagnostic` from the right validation stage
   (OKF → schema → semantic). Errors stop validation at their stage; warnings
   accumulate.
2. **`linter/rules.md`** — document it under Errors or Warnings: what triggers
   it, the rationale, the fix, and its `fixSafety`.
3. **`src/slac/cli.py`** — add a one-line entry to the `DIAGNOSTICS` map so
   `slac explain <Name>` works and it appears in the full listing.
4. **`tests/test_linter.py`** — add a test: a minimal loop that triggers the new
   diagnostic, asserting its name, severity, and `fixSafety`.

Keep names self-explanatory — a name like `NoCheckerWarning` *is* the
explanation. Reuse Python's exception vocabulary (`TypeError` here means what it
means everywhere) rather than inventing numeric codes.

## Before you open a PR

- `make check` is green.
- New behavior has a test; new diagnostics are documented in `linter/rules.md`
  and `cli.py`'s `DIAGNOSTICS`.
- Any new or changed example still lints clean.
- Spec-level changes are reflected in `SPEC.md` and noted in `CHANGELOG.md`
  (`Unreleased`). Breaking changes are fine pre-0.1.0 — just call them out.
