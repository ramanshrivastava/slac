# SLAC — Structured Language for Agentic Coding

[![version](https://img.shields.io/badge/spec-v0.0.1-blue)](./SPEC.md)
[![license](https://img.shields.io/badge/license-Apache--2.0-green)](./LICENSE)
[![OKF profile](https://img.shields.io/badge/OKF-profile-4285F4?logo=google&logoColor=white)](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
[![zero deps](https://img.shields.io/badge/linter-zero--dependency-purple)](./linter/slac_lint.py)

**SLAC is a small, declarative language for *agentic coding loops*.** You write
*what* a loop should achieve, *who* does the work, *how* it's checked, and *when*
it's done — in a single markdown file. A validator checks the loop is well-formed
*before* an agent runs it, so agents don't fall flat on a half-specified task.

A SLAC file is just **markdown + YAML frontmatter** — it is a valid
[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
document (`type: slac.loop`), so any OKF-aware agent can read it, and a SLAC engine
can execute it.

## Supported engines

SLAC is **tool-agnostic**: the same `.slac.md` loop *compiles down* onto the loop
primitives of the agent harnesses people actually use.

[![Claude Code](https://img.shields.io/badge/Claude%20Code-%2Floop-D97757?logo=anthropic&logoColor=white)](./mappings/claude-code.md)
[![OpenAI Codex](https://img.shields.io/badge/OpenAI%20Codex-%2Fgoal-412991?logo=openai&logoColor=white)](./mappings/codex.md)

| Engine | SLAC lowers to | Mapping |
|---|---|---|
| <img src="https://img.shields.io/badge/Claude%20Code-D97757?logo=anthropic&logoColor=white" alt="Claude Code" height="18"> | `/loop` cron (`CronTask`) + subagents | [mappings/claude-code.md](./mappings/claude-code.md) |
| <img src="https://img.shields.io/badge/OpenAI%20Codex-412991?logo=openai&logoColor=white" alt="Codex" height="18"> | `/goal` (objective + budget) + `spawn_agent` | [mappings/codex.md](./mappings/codex.md) |

> Each mapping also documents what the engine **cannot yet enforce** — notably,
> neither Claude Code's `/loop` nor Codex's `/goal` enforces a separate *checker*
> agent. That gap is the reason SLAC exists (see below).

## A loop in 20 lines

```markdown
---
type: slac.loop
loop: pr_babysitter
until: ci.green and tests.passed == tests.total and consecutive_green >= 2
context:
  - cmd: gh pr checks
  - signal: ci
agents:
  maker:   { model: opus }
  checker: { model: opus, mode: refute }   # a SEPARATE agent verifies "done"
boundaries:
  never: [edit the public API, skip tests]
max_iterations: 20
---

# Goal
Get this PR's CI green without changing public behavior.
```

## Why SLAC exists

We read the real source of both shipping loop tools:

- **Claude Code `/loop`** is interval cron — it reschedules a prompt and expires
  after ~7 days. **It never evaluates whether the goal was met.**
- **Codex `/goal`** lets the *same working model* mark its own goal `complete`.
  **The maker grades its own homework** — exactly the footgun Addy Osmani warns
  about ("the model grades its own work too leniently").

SLAC adds the missing structure both lack: an **explicit, independently-judged
stop condition** (`until`) and a **mandatory separate `checker` agent**. In
compiler terms, the checker is the *type-checker the fuzzy LLM executor took away*,
moved to runtime. See [SPEC.md](./SPEC.md) for the full rationale.

## Install

The linter is **zero-dependency** — stock Python 3.8+. (`pyyaml` is used
automatically if present for maximal YAML coverage; otherwise a bundled parser
handles the SLAC subset.)

```bash
# one-line install (wraps pipx)
curl -fsSL https://raw.githubusercontent.com/ramanshrivastava/slac/main/install.sh | bash

# …or pick a package manager
pipx install slac          # recommended: isolated CLI on your PATH
pip install slac           # into the current environment

# …or no install at all — run straight from a clone
python3 linter/slac_lint.py examples/*.slac.md
```

> **Distribution status (v0.0.1):** the package is built for **PyPI** as
> `slac` (publish-ready via `pyproject.toml`); `pipx`/`pip` are the primary
> channels and the `curl … | bash` script just wraps `pipx`. A **Homebrew** tap is
> planned once there's a tagged release. Nothing is published yet — these are the
> targets, and `install.sh` already installs from a local clone today.

## Use the `slac` CLI

```bash
slac lint examples/*.slac.md              # validate (type-check + lint)
slac lint --json my_loop.slac.md          # machine-readable findings (agents auto-fix the `safe` ones)
slac lint --strict examples/*.slac.md     # CI mode: warnings become errors
slac new my_loop                          # scaffold a starter loop that lints clean
slac explain NoCheckerWarning             # what a diagnostic means (or list them all)
```

Diagnostics read like a **Python traceback**, not a barcode — errors are named
like Python exceptions (`MissingFieldError`, `UnknownFieldError`, `TypeError`)
and **halt** the loop; warnings (`NoCheckerWarning`, `RunawayWarning`) **notify**
but let it run. See [linter/rules.md](./linter/rules.md).

## Use it from an agent

A `.slac.md` is a loop *definition*; an agent harness *runs* it. The bundled
[Claude Code skill](./integrations/claude-code/SKILL.md) teaches an agent to
consume one: validate with `slac lint`, then drive the loop (fetch context → run
the maker → run a **separate** checker → evaluate `until` → repeat) by lowering
onto `/loop`. Drop it in `~/.claude/skills/run-slac-loop/` and say *"run this
loop."* See [`mappings/`](./mappings) for the field-by-field lowering onto Claude
Code `/loop` and Codex `/goal`.

## Repository layout

```
slac/
  SPEC.md                    the language definition (fields, semantics, lifecycle)
  pyproject.toml             packaging — installs the `slac` CLI
  src/slac/
    cli.py                   the `slac` command (lint / new / explain)
    linter.py                zero-dependency validator (OKF → schema → semantic)
    slac.schema.json         JSON Schema for the frontmatter (the type-check)
  linter/slac_lint.py        back-compat shim (zero-install entry point)
  linter/rules.md            every diagnostic, with rationale
  tests/test_linter.py       the test suite (stdlib unittest)
  examples/
    index.md                 OKF directory index (the "loopbook")
    pr_babysitter.slac.md
    bug_fixer.slac.md
    flaky_hunter.slac.md
  mappings/
    claude-code.md           how SLAC lowers onto /loop
    codex.md                 how SLAC lowers onto /goal
  integrations/
    claude-code/SKILL.md     skill: teach an agent to run a .slac.md loop
  Makefile  .pre-commit-config.yaml
```

## Relationship to OKF

[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog/tree/main/okf)
(Google Cloud, 2026) standardizes *curated knowledge for agents* as markdown +
frontmatter. **OKF is the fuel; SLAC is the loop that consumes it.** SLAC is an
OKF *profile*: every loop sets the required `type` field to `slac.loop`, reuses
OKF's optional fields (`title`, `description`, `tags`, `timestamp`), and uses OKF's
reserved `log.md` as the loop's on-disk memory between runs.

## License

[Apache-2.0](./LICENSE) — matching OKF, to keep the ecosystem interoperable.
