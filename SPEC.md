# SLAC Specification — v0.0.1

**Structured Language for Agentic Coding**

> Status: draft (v0.0.1). The language is small on purpose. This document is the
> normative reference; the JSON Schema (`schema/slac.schema.json`) and the linter
> (`linter/slac_lint.py`) implement it.

---

## 1. What SLAC is (and isn't)

SLAC is a **declarative language for describing agentic coding loops**. A *loop* is
a recurring goal: an agent is given a goal, fetches context, does work, and a check
decides whether the goal is met — repeating until it is (or a limit is hit).

SLAC describes **what the loop is**. It does not, by itself, run anything. Running a
loop is the job of an **engine** (an agent harness such as Claude Code or Codex).
This is the same split every programming language has:

```
  LANGUAGE = a spec (what is valid)      ENGINE = the thing that runs it
  Python grammar        + CPython
  ECMAScript            + V8
  ───────────────────────────────────────────────
  SLAC (this document)  + an agent harness (/loop, /goal, …)
```

### The "compiler" of SLAC

SLAC has a compiler, in two halves:

- **Front-end** — `linter/slac_lint.py` + `schema/slac.schema.json`. It parses a
  loop file, type-checks it, and lints it. This is **deterministic** and runs
  **before** execution (a pre-flight gate). An invalid loop is *refused, not run*.
- **Back-end** — the `mappings/` documents. They *lower* a validated loop onto a
  target engine's primitives (Claude Code `/loop` `CronTask`, Codex `/goal`).

There is one twist a normal language doesn't have: the thing that finally executes a
SLAC loop is an **LLM**, which is non-deterministic. So **outcome-correctness cannot
be proven at compile time**. The compiler can only prove the loop is *well-formed*.
Proving the loop *succeeded* is deferred to runtime and delegated to the **`checker`
agent**, which judges the `until` condition. The checker is the type-checker that the
fuzzy executor took away — which is why a separate checker is **structurally
required**, not a nice-to-have.

---

## 2. File format

A SLAC loop is a single UTF-8 text file with the extension **`.slac.md`**. It has
two parts:

1. **YAML frontmatter** — a `---`-delimited block at the very top. Structured,
   machine-checked configuration.
2. **Markdown body** — prose the agent reads, beginning after the closing `---`.

```markdown
---
type: slac.loop
loop: my_loop
until: "<stop condition>"
context: [ ... ]
agents: { maker: { ... } }
---

# Goal
<prose>
```

### 2.1 OKF profile

A `.slac.md` file is a valid **Open Knowledge Format** document. SLAC is an OKF
*profile*: it satisfies OKF's single requirement (a `type` field) by fixing
`type: slac.loop`, and it reuses OKF's reserved optional fields. Consequences:

- Any OKF-aware agent can *read* a SLAC file as a knowledge concept.
- OKF's reserved **`log.md`** is the conventional `state` file (the loop's memory).
- OKF's reserved **`index.md`** lists the loops in a directory (a "loopbook").
- A directory of loops + knowledge is a single OKF bundle: **OKF is the fuel,
  SLAC is the loop that consumes it.**

---

## 3. Frontmatter reference

Legend: **R** = required (else `MissingFieldError`); **O** = optional;
**O‡** = optional but its absence raises a *warning* (a footgun).

| field | type | req | meaning |
|---|---|:---:|---|
| `type` | const `"slac.loop"` | **R** | OKF discriminator. Any other value → `ValueError`. |
| `loop` | string (snake_case) | **R** | Unique loop id, like a Python module name. |
| `until` | string | **R** | Stop / evaluation condition. See §5. Absent → `MissingFieldError` (a loop with no stop is a "slop cannon"). |
| `context` | list | **R** | The fuel. Items are `{cmd: ...}`, `{file: glob}`, `{signal: name}`, `{okf: path}`, or `{mcp: query}`. Absent/empty → `MissingFieldError`. |
| `agents` | mapping | **R** | Must contain `maker`. |
| `agents.maker` | mapping `{model, instructions?}` | **R** | The implementer. |
| `agents.checker` | mapping `{model, mode?, instructions?}` | **O‡** | The separate verifier. Absent → `NoCheckerWarning`. `mode` ∈ `{refute, confirm}` (default `refute`). |
| `state` | path (string) | **O‡** | On-disk memory between runs. Defaults to sibling `log.md`. Absent and no default resolvable → `NoStateWarning`. |
| `boundaries` | mapping `{always?, ask?, never?}` of string-lists | **O‡** | Three-tier safety (§6). No `never` list → `NoBoundaryWarning`. |
| `schedule` | string | **O** | Cadence for automation, e.g. `"15m"`, `"daily"`, or a 5-field cron. |
| `isolation` | enum `none \| worktree` | **O** | Parallel-safety. Default `none`. Other value → `ValueError`. |
| `max_iterations` | integer ≥ 1 | **O‡** | Runaway backstop. Absent *and* no `budget` → `RunawayWarning`. |
| `budget` | mapping `{tokens?, minutes?}` | **O** | Resource ceiling. Maps to Codex `token_budget`. |
| `version` | string | **O** | SLAC version this file targets. Default `"0.0.1"`. |
| `title`, `description`, `tags`, `timestamp` | OKF | **O** | Inherited from OKF verbatim. |

Unknown frontmatter keys are an **error** (`UnknownFieldError`) — this is what
catches typos like `untill:`. (The schema sets `additionalProperties: false`.)

### 3.1 `context` item forms

| form | example | meaning |
|---|---|---|
| `cmd` | `{cmd: "gh pr checks"}` | A shell command; its output is fuel. |
| `file` | `{file: "src/**/*.py"}` | Files matching a glob. |
| `signal` | `{signal: "ci"}` | Declares a runtime signal usable in `until` (§5). |
| `okf` | `{okf: "/knowledge/payments.md"}` | An OKF cross-link into a knowledge bundle. |
| `mcp` | `{mcp: "linear.issues(state=open)"}` | An MCP connector query. |

A bare string item is shorthand for `{cmd: "<string>"}`.

---

## 4. Body reference

| section | req | meaning |
|---|:---:|---|
| `# Goal` | **R** | Prose objective. Absent → `MissingFieldError` (`Goal`). |
| `## Context` | O | Human elaboration of the fuel. |
| `## Evaluation` | O | How the `checker` decides "done"; elaborates `until`. |
| `## Boundaries` | O | Rationale for the three-tier rules. |
| `## Notes` | O | Anything else. |

---

## 5. The `until` condition

`until` answers *"when is this loop done?"* It has two forms; the linter picks
automatically.

### 5.1 Expression form (machine-evaluated)

A **restricted Python boolean expression** over a *signal namespace*. Example:

```yaml
until: ci.green and tests.passed == tests.total and consecutive_green >= 2
```

Allowed syntax (whitelist, checked via Python's `ast`):

- Boolean ops: `and`, `or`, `not`
- Comparisons: `==`, `!=`, `<`, `<=`, `>`, `>=`
- Names and attribute access: `ci`, `ci.green`, `tests.passed`
- Literals: numbers, strings, `True`/`False`/`None`

**Forbidden:** function calls, subscripts, imports, comprehensions, lambdas, and
any dunder (`__...__`). This is `eval()` with the dangerous parts removed.

**Signal namespace.** Names must be *declared* by a `context` item of the form
`{signal: name}`, or be one of the always-available signals:

| signal | type | meaning |
|---|---|---|
| `iteration` | int | Current loop count (1-based). |
| `consecutive_green` | int | How many consecutive iterations met the goal so far. |
| `elapsed_minutes` | int | Minutes since the loop started. |

A name in `until` that is neither always-available nor declared as a signal →
`UnreachableStopWarning` (the loop can never observe it, so it can never stop on it).

At runtime: the `checker` agent supplies/confirms the signal values; the engine
evaluates the boolean. **The agent judges the facts; arithmetic decides "done."**

### 5.2 Prose form (checker-judged)

If `until` does not parse as a whitelisted expression over known signals, it is
treated as **prose** and handed to the `checker` agent to judge holistically:

```yaml
until: "the bug from the report no longer reproduces and a regression test covers it"
```

Prose `until` cannot be machine-verified for reachability — prefer the expression
form when your goal is observable through signals.

---

## 6. Boundaries (three-tier)

From a study of 2,500+ real agent config files, the effective constraint model is
three tiers. SLAC adopts it directly:

```yaml
boundaries:
  always: [run the test suite before pushing]      # ✅ do without asking
  ask:    [changing a database schema]              # ⚠️ pause for human approval
  never:  [edit the public API, commit secrets]     # 🚫 hard stop
```

Omitting a `never` list raises `NoBoundaryWarning`: a loop with no hard stops is a
loop that can do anything.

---

## 7. Validation model

The linter runs **three ordered stages and stops at the first hard failure**
(progressive validation, borrowed from zerolang):

1. **OKF conformance** — the file parses as frontmatter + body and `type` is present.
2. **Type check** — frontmatter validates against `schema/slac.schema.json`:
   required keys, correct types, enum values, and `additionalProperties: false`.
3. **Semantic lint** — footguns the schema can't see (§3 `O‡` rows, `until`
   reachability, missing `# Goal` body).

### 7.1 Diagnostics — Python's model, not numeric codes

Diagnostics are **named like Python exceptions** and split into errors and warnings,
mirroring Python's `Exception` vs `warnings` distinction:

**Errors (HALT — the loop is refused):**

| name | Python analog | when |
|---|---|---|
| `SLACSyntaxError` | `SyntaxError` | frontmatter YAML won't parse / no body |
| `MissingFieldError` | `TypeError` (missing arg) | a required field/section is absent |
| `UnknownFieldError` | `NameError` | a frontmatter key isn't defined in SLAC |
| `TypeError` | `TypeError` | a field has the wrong type |
| `ValueError` | `ValueError` | a field value is out of range / not an allowed enum |

**Warnings (NOTIFY — the loop still runs):**

| name | when |
|---|---|
| `NoCheckerWarning` | `maker` present but no `checker` (it grades itself) |
| `NoStateWarning` | no `state` and no default `log.md` resolvable |
| `UnreachableStopWarning` | `until` names a signal nothing produces |
| `NoBoundaryWarning` | no `boundaries.never` |
| `RunawayWarning` | no `max_iterations` and no `budget` |

Every diagnostic carries a **`fixSafety`** label — `safe` (auto-fixable, e.g. a
key typo), `review` (needs a human glance), or `needs-human` (a real design gap).
`--json` emits `{name, message, line, fixSafety}` so an agent can apply the `safe`
fixes itself. `--strict` promotes all warnings to errors (for CI). The process exits
non-zero if any error remains.

---

## 8. Execution lifecycle (informative)

How a conformant engine *should* run a validated loop:

```
        ┌─────────────────────────────────────────────┐
        │  validate (§7) — REFUSE if any error remains  │
        └───────────────────────┬─────────────────────┘
                                 ▼
        ┌──────────────┐   load state (log.md) into the run
        │  iteration   │◄──────────────────────────────────┐
        └──────┬───────┘                                    │
               ▼                                            │
        fetch `context` (cmd/file/signal/okf/mcp)           │
               ▼                                            │
        run `agents.maker` within `boundaries`              │
               ▼                                            │
        run `agents.checker` → produce signal values        │
               ▼                                            │
        evaluate `until`  ───── met? ── yes ──► STOP (done) │
               │                                            │
               no                                           │
               ▼                                            │
        append progress to `state`;                         │
        iteration += 1                                      │
               ▼                                            │
        iteration > max_iterations  or  budget exhausted? ──┘
               │ yes
               ▼
            STOP (limit reached — not done)
```

The two distinct stop reasons — **done** (`until` met, confirmed by the checker)
vs **limit** (`max_iterations`/`budget`) — must be reported separately.

---

## 9. Versioning

SLAC uses semantic versioning. This is **v0.0.1**: a first draft. Breaking changes
are expected before v0.1.0. A file may pin the version it targets via the `version`
field; an engine should warn on a mismatch it cannot honor.

---

## 10. Relationship to the engines (summary)

| SLAC field | Claude Code `/loop` | Codex `/goal` |
|---|---|---|
| `schedule` | `CronTask.cron` (interval cron) | automation cadence |
| `until` | *(no native eval — engine must add the checker step)* | `objective` + self-`update_goal` (SLAC adds a real checker) |
| `agents.maker` | a subagent | `spawn_agent` |
| `agents.checker` | a second subagent (SLAC-added) | a second `spawn_agent` (SLAC-added) |
| `budget` | — | `token_budget` |
| `isolation: worktree` | (manual) | (manual) |
| `state` | disk `log.md` | disk `log.md` (vs Codex's SQLite memories) |

Full details, with source citations, in `mappings/claude-code.md` and
`mappings/codex.md`.
